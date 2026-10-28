"""B2 source-bounded module metrics, reusing static dependency and role evaluators.

Import correspondence and source hashes are caller-attested; this module never
claims semantic cohesion, complete runtime dependencies or a clean public API.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import replace
from hashlib import sha256
import json
from typing import Any

from codeqa.core.dependency import DependencyGraph
from codeqa.evaluation.dependency_metrics import (
    DependencyMetricsError, DependencyMetricsProfile, evaluate_dependency_metrics,
)
from codeqa.evaluation.impact import analyze_change_impact
from codeqa.evaluation.semantic_layout import evaluate_semantic_layout


class ArchitectureMetricsError(ValueError):
    """Contradictory inventory, policy or dependency graph identity."""


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def analyze_architecture_metrics(
    inventory: Mapping[str, Any],
    dependencies: DependencyGraph,
    role_policy: Mapping[str, Any],
    profile: DependencyMetricsProfile,
) -> dict[str, Any]:
    """Compare declared module-role boundaries using existing static graph facts.

    The inventory contains the caller-attested tracked-file denominator.
    DependencyGraph is independently produced by an adapter; its import-site
    witnesses are NOT re-parsed or independently authenticated here.
    """
    if not isinstance(inventory, Mapping) or not isinstance(role_policy, Mapping):
        raise ArchitectureMetricsError("inventory and role policy must be mappings")
    if not isinstance(dependencies, DependencyGraph) or not isinstance(
        profile, DependencyMetricsProfile
    ):
        raise ArchitectureMetricsError("DependencyGraph and versioned profile required")
    try:
        identity = inventory["source_identity"]
        snapshot = identity["repository_commit_sha"]
        root = role_policy["scope"]
        roles = role_policy["roles"]
        items = inventory["files"]
        coverage = inventory["coverage"]
        if (
            inventory["schema_version"] != "0.1"
            or inventory["source_scope"] != root
            or identity["role_policy_sha256"] != _digest(role_policy)
            or dependencies.snapshot_id != snapshot
            or not isinstance(snapshot, str) or len(snapshot) != 40
            or not isinstance(items, list) or not isinstance(roles, dict)
            or not isinstance(coverage, dict)
        ):
            raise ArchitectureMetricsError("incompatible snapshot or role-policy identity")
        by_path = {item["path"]: item for item in items}
        if len(by_path) != len(items) or coverage["tracked_total"] != len(items):
            raise ArchitectureMetricsError("inventory tracked-file denominator mismatch")
        if sum(item["read_state"] == "READ" for item in items) != coverage["read"]:
            raise ArchitectureMetricsError("inventory read-file denominator mismatch")
        if any(
            item["ownership_class"] == "POLICY_DECLARED"
            and item["declared_role"] not in roles
            for item in items
        ):
            raise ArchitectureMetricsError("undeclared role marked as policy owned")
        analyzed = set(dependencies.analyzed_paths)
        unprocessed = set(dependencies.unprocessed_paths)
        if (
            analyzed & unprocessed
            or not (analyzed | unprocessed) <= set(by_path)
            or any(by_path[p]["read_state"] != "READ" or
                   by_path[p]["language"] != "python" for p in analyzed)
        ):
            raise ArchitectureMetricsError("dependency graph has invalid source coverage")
        # An unprocessed path may be a readable syntax error or an unavailable
        # source; it is not silently counted as a resolved module.
        if any(by_path[p]["language"] != "python" for p in unprocessed):
            raise ArchitectureMetricsError("non-Python source in Python dependency graph")
        # Canonicalize the graph before using the existing validated SCC/degree
        # implementation, so duplicate input order cannot change measurements.
        graph = replace(
            dependencies,
            analyzed_paths=tuple(sorted(analyzed)),
            unprocessed_paths=tuple(sorted(unprocessed)),
            edges=tuple(sorted(set(dependencies.edges), key=lambda e: (
                e.source_path, e.target_path, e.line, e.expression, e.execution
            ))),
            unknown=tuple(sorted(set(dependencies.unknown), key=lambda u: (
                u.source_path, u.line, u.expression, u.reason
            ))),
        )
        static = evaluate_dependency_metrics(graph, profile)
        layout = evaluate_semantic_layout(
            tuple(sorted(by_path)),
            ((pair.source_path, pair.target_path) for pair in static.pairs),
            role_policy,
        )
    except (KeyError, TypeError, AttributeError, DependencyMetricsError,
            ValueError) as exc:
        raise ArchitectureMetricsError("untrustworthy architecture metrics inputs") from exc

    def role(path: str) -> str:
        item = by_path[path]
        if (item["ownership_class"] == "POLICY_DECLARED"
                and item["declared_role"] in roles):
            return item["declared_role"]
        return "UNCLASSIFIED" if path.startswith(root + "/") else "OUT_OF_SCOPE"

    module_counts = Counter(role(path) for path in static.analyzed_paths)
    role_pairs: Counter[tuple[str, str]] = Counter()
    cross_witnesses: list[dict[str, Any]] = []
    pair_witnesses: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for edge in graph.edges:
        witness = {
            "source_path": edge.source_path,
            "target_path": edge.target_path,
            "source_sha256": by_path[edge.source_path]["source_sha256"],
            "line": edge.line,
            "expression": edge.expression,
            "execution": edge.execution,
            "evidence_class": "GRAPH_PROVIDED_STATIC_IMPORT",
        }
        pair_witnesses[(edge.source_path, edge.target_path)].append(witness)

    within_pairs = cross_pairs = unclassified_pairs = 0
    for pair in static.pairs:
        sr, dr = role(pair.source_path), role(pair.target_path)
        if sr not in roles or dr not in roles:
            unclassified_pairs += 1
        elif sr == dr:
            within_pairs += 1
            role_pairs[(sr, dr)] += 1
        else:
            cross_pairs += 1
            role_pairs[(sr, dr)] += 1
            cross_witnesses.extend(pair_witnesses[(pair.source_path, pair.target_path)])

    groups = []
    for name in sorted(roles):
        size = module_counts[name]
        internal_possible = size * (size - 1)
        inward = sum(role_pairs[(other, name)] for other in roles if other != name)
        outward = sum(role_pairs[(name, other)] for other in roles if other != name)
        outward_possible = size * sum(
            module_counts[other] for other in roles if other != name
        )
        impact = (
            analyze_change_impact(graph, (p for p in static.analyzed_paths
                                         if role(p) == name))
            if size else None
        )
        groups.append({
            "role": name,
            "analyzed_modules": size,
            "within_pairs": role_pairs[(name, name)],
            "possible_within_directed_pairs": internal_possible,
            "within_density_proxy": _ratio(role_pairs[(name, name)], internal_possible),
            "cross_out_pairs": outward,
            "cross_in_pairs": inward,
            "possible_cross_out_directed_pairs": outward_possible,
            "cross_out_density_proxy": _ratio(outward, outward_possible),
            "reverse_import_impact": {
                "potential_dependents": len(impact.affected),
                "witnesses": [
                    {"path": item.path, "distance": item.distance,
                     "chain": list(item.witness)}
                    for item in impact.affected
                ],
                "interpretation": "STATIC_POTENTIAL_ONLY",
            } if impact else None,
        })

    cycles = []
    for cycle in static.cycles:
        witnesses = []
        for src, dst in zip(cycle.witness, cycle.witness[1:]):
            witnesses.append(pair_witnesses[(src, dst)][0])
        cycles.append({
            "nodes": list(cycle.nodes),
            "closed_walk": list(cycle.witness),
            "edge_witnesses": witnesses,
            "evidence_class": "STATIC_MODULE_PATH",
        })

    read_python = {
        item["path"] for item in items
        if item["read_state"] == "READ" and item["language"] == "python"
    }
    missing_from_graph = sorted(read_python - analyzed - unprocessed)
    unknown = Counter(dict(static.unknown_by_reason))
    if missing_from_graph:
        unknown["MISSING_PYTHON_GRAPH_COVERAGE"] = len(missing_from_graph)
    if unprocessed:
        unknown["UNPROCESSED_PYTHON"] = len(unprocessed)
    if coverage["tracked_total"] != coverage["read"]:
        unknown["UNREAD_TRACKED_SOURCE"] = coverage["tracked_total"] - coverage["read"]
    nonpython = sum(
        item["language"] != "python" for item in items
    )
    if nonpython:
        unknown["NON_PYTHON_PARSER_NOT_EVALUATED"] = nonpython

    declared_violations = [
        item for item in layout.findings if item.status == "VIOLATION"
    ]
    result: dict[str, Any] = {
        "schema_version": "0.1",
        "snapshot_sha": snapshot,
        "inventory_id": inventory["inventory_id"],
        "role_policy_sha256": identity["role_policy_sha256"],
        "dependency_profile_id": profile.profile_id,
        "status": ("VIOLATION" if declared_violations else
                   "NOT_EVALUATED" if not analyzed else
                   "INCOMPLETE" if unknown else "EVIDENCE_ONLY"),
        "evidence_class": "PROXY_INFERENCE",
        "coverage": {
            "tracked_total": coverage["tracked_total"],
            "read": coverage["read"],
            "python_analyzed": len(analyzed),
            "python_unprocessed": len(unprocessed),
            "python_missing_from_graph": missing_from_graph,
            "unknown_by_reason": dict(sorted(unknown.items())),
            "external_consumers": "NOT_EVALUATED",
            "dynamic_import_completeness": "NOT_EVALUATED",
        },
        "denominators": {
            "declared_analyzed_modules": sum(module_counts[name] for name in roles),
            "resolved_distinct_pairs": len(static.pairs),
            "within_declared_pairs": within_pairs,
            "cross_declared_pairs": cross_pairs,
            "unclassified_or_out_of_scope_pairs": unclassified_pairs,
            "within_share_of_declared_pairs": _ratio(
                within_pairs, within_pairs + cross_pairs
            ),
            "cross_share_of_declared_pairs": _ratio(
                cross_pairs, within_pairs + cross_pairs
            ),
        },
        "groups": groups,
        "modules": [
            {"path": item.path, "role": role(item.path),
             "fan_in": item.fan_in, "fan_out": item.fan_out,
             "unknown_import_sites": item.unknown_statements}
            for item in static.files
        ],
        "resolved_pairs": [
            {"source_path": item.source_path, "target_path": item.target_path,
             "source_role": role(item.source_path),
             "target_role": role(item.target_path),
             "statement_count": item.statement_count,
             "conditional_or_deferred_count": item.conditional_or_deferred_count,
             "witnesses": pair_witnesses[(item.source_path, item.target_path)]}
            for item in static.pairs
        ],
        "cross_boundary_witnesses": cross_witnesses,
        "cycles": cycles,
        "declared_role_findings": [
            {"status": f.status, "code": f.code, "source": f.source,
             "target": f.target, "reason": f.reason}
            for f in layout.findings
        ],
        "limitations": [
            "static imports are graph-provided and not independently re-parsed here",
            "density uses distinct directed module pairs, not statement counts",
            "role grouping is declared path ownership, not semantic cohesion/SRP proof",
            "unresolved and dynamic imports may hide edges; absence of cycles is not proof",
            "reverse-import reachability is static potential, not runtime impact",
            "unknown external consumers and non-Python resolution cannot certify safety",
            "zero denominators yield null proxies, not perfect scores",
        ],
    }
    result["metrics_id"] = _digest(result)
    return result
