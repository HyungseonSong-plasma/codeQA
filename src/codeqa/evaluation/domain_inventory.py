"""Pure read-only domain hint inventory of pinned Python dependency evidence.

File naming rules are explicitly *hints*. Static imports and exported symbols
are candidate witnesses, never proof of semantic cohesion, runtime coupling or
a complete change-impact bound. Unmatched/ambiguous names remain visible.
"""
from __future__ import annotations

import ast
from collections import Counter, defaultdict
from collections.abc import Mapping
from hashlib import sha256
import json
import re
from typing import Any

from codeqa.core.dependency import DependencyGraph
from codeqa.evaluation.impact import analyze_change_impact
from codeqa.evaluation.semantic_layout import evaluate_semantic_layout


class DomainInventoryError(ValueError):
    """Input snapshot or declared domain mapping cannot be trusted."""


def _fingerprint(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _validate_rules(policy: Mapping[str, Any]) -> tuple[tuple[str, re.Pattern[str]], ...]:
    if not isinstance(policy, Mapping) or set(policy) != {"version", "scope", "meaning", "rules"}:
        raise DomainInventoryError("invalid domain mapping policy")
    if (policy["version"] != "0.1" or policy["scope"] != "src/codeqa/"
            or policy["meaning"] != "DECLARED_FILENAME_DOMAIN_HINTS_NOT_SEMANTIC_COHESION"):
        raise DomainInventoryError("unrecognized domain mapping scope or interpretation")
    rules = policy["rules"]
    if not isinstance(rules, list) or not rules:
        raise DomainInventoryError("missing mapping rules")
    seen: set[str] = set()
    parsed = []
    for rule in rules:
        if not isinstance(rule, dict) or set(rule) != {"domain", "pattern"}:
            raise DomainInventoryError("invalid domain rule")
        domain, pattern = rule["domain"], rule["pattern"]
        if (not isinstance(domain, str) or not re.fullmatch(r"[a-z_]+", domain)
                or domain in seen or not isinstance(pattern, str) or not pattern
                or len(pattern) > 200):
            raise DomainInventoryError("duplicate/invalid domain rule")
        seen.add(domain)
        try:
            parsed.append((domain, re.compile(pattern)))
        except re.error as exc:
            raise DomainInventoryError("invalid domain regex") from exc
    return tuple(parsed)


def _safe_source_path(path: str) -> bool:
    return (
        isinstance(path, str) and path.startswith("src/codeqa/") and path.endswith(".py")
        and "\\" not in path and ":" not in path
        and not any(ord(char) < 32 or ord(char) == 127 for char in path)
        and all(p not in ("", ".", "..") and not p.endswith((".", " "))
                for p in path.split("/"))
    )


def _exports(path: str, text: str) -> list[dict[str, Any]]:
    """Only syntactic imports in __init__, NOT stable public API certification."""
    if not path.endswith("/__init__.py"):
        return []
    try:
        tree = ast.parse(text, filename=path)
    except SyntaxError:
        return []
    found = []
    for statement in tree.body:
        if isinstance(statement, ast.ImportFrom):
            for alias in statement.names:
                found.append({
                    "path": path, "line": statement.lineno,
                    "from": "." * statement.level + (statement.module or ""),
                    "name": alias.name, "asname": alias.asname,
                    "meaning": "INIT_IMPORT_CANDIDATE_NOT_PUBLIC_API_GUARANTEE",
                })
        elif isinstance(statement, ast.Import):
            for alias in statement.names:
                found.append({
                    "path": path, "line": statement.lineno,
                    "from": alias.name, "name": alias.name,
                    "asname": alias.asname,
                    "meaning": "INIT_IMPORT_CANDIDATE_NOT_PUBLIC_API_GUARANTEE",
                })
    return found


def analyze_domain_inventory(
    sources: Mapping[str, str],
    dependencies: DependencyGraph,
    domain_policy: Mapping[str, Any],
    role_policy: Mapping[str, Any],
) -> dict[str, Any]:
    """Deterministic source-backed inventory; all unknowns stay explicit."""
    rules = _validate_rules(domain_policy)
    if not isinstance(dependencies, DependencyGraph):
        raise DomainInventoryError("real DependencyGraph required")
    if not isinstance(sources, Mapping) or not sources or any(
        not _safe_source_path(path) or not isinstance(source, str)
        for path, source in sources.items()
    ):
        raise DomainInventoryError("only product Python sources are allowed")
    if (set(dependencies.analyzed_paths) | set(dependencies.unprocessed_paths) != set(sources)
            or set(dependencies.analyzed_paths) & set(dependencies.unprocessed_paths)):
        raise DomainInventoryError("dependency graph and source coverage mismatch")
    classified: dict[str, str] = {}
    inventory = []
    counts: dict[str, dict[str, int]] = defaultdict(lambda: {"files": 0, "lines": 0, "nonblank_lines": 0})
    for path, source in sorted(sources.items()):
        matches = [name for name, regex in rules if regex.search(path)]
        domain = matches[0] if len(matches) == 1 else (
            "UNCLASSIFIED" if not matches else "AMBIGUOUS"
        )
        classified[path] = domain
        lines = source.splitlines()
        counts[domain]["files"] += 1
        counts[domain]["lines"] += len(lines)
        counts[domain]["nonblank_lines"] += sum(bool(line.strip()) for line in lines)
        inventory.append({
            "path": path, "domain": domain, "matched_rules": matches,
            "sha256": sha256(source.encode()).hexdigest(),
            "lines": len(lines),
            "parsed": path in dependencies.analyzed_paths,
        })
    edges = []
    intra = cross = 0
    for edge in dependencies.edges:
        if edge.source_path not in classified or edge.target_path not in classified:
            raise DomainInventoryError("dependency edge escapes the supplied source set")
        left, right = classified[edge.source_path], classified[edge.target_path]
        if left == right and left not in ("UNCLASSIFIED", "AMBIGUOUS"):
            intra += 1
        elif left not in ("UNCLASSIFIED", "AMBIGUOUS") and right not in ("UNCLASSIFIED", "AMBIGUOUS"):
            cross += 1
        edges.append({
            "source": edge.source_path, "target": edge.target_path,
            "line": edge.line, "expression": edge.expression,
            "execution": edge.execution,
            "source_domain": left, "target_domain": right,
            "classification": (
                "INTRA_DOMAIN" if left == right and left not in ("UNCLASSIFIED", "AMBIGUOUS")
                else "CROSS_DOMAIN" if left not in ("UNCLASSIFIED", "AMBIGUOUS") and right not in ("UNCLASSIFIED", "AMBIGUOUS")
                else "DOMAIN_UNKNOWN"
            ),
        })
    # Per-domain counts are observed static sites, not runtime dependencies.
    # Ambiguous and unclassified domains retain their own evidence buckets.
    domain_metrics = {
        domain: {
            **count,
            "intra_import_sites": 0,
            "cross_outgoing_import_sites": 0,
            "cross_incoming_import_sites": 0,
            "domain_unknown_outgoing_import_sites": 0,
            "unknown_import_sites": 0,
            "potential_reverse_dependents_total": 0,
            "potential_reverse_dependents_max": 0,
        }
        for domain, count in counts.items()
    }
    for edge in edges:
        left, right = edge["source_domain"], edge["target_domain"]
        if edge["classification"] == "INTRA_DOMAIN":
            domain_metrics[left]["intra_import_sites"] += 1
        elif edge["classification"] == "CROSS_DOMAIN":
            domain_metrics[left]["cross_outgoing_import_sites"] += 1
            domain_metrics[right]["cross_incoming_import_sites"] += 1
        else:
            domain_metrics[left]["domain_unknown_outgoing_import_sites"] += 1
    for item in dependencies.unknown:
        if item.source_path not in classified:
            raise DomainInventoryError("unknown import witness escapes the supplied source set")
        domain_metrics[classified[item.source_path]]["unknown_import_sites"] += 1
    unknown = [vars(item) if hasattr(item, "__dict__") else {
        "source_path": item.source_path, "line": item.line,
        "expression": item.expression, "reason": item.reason,
    } for item in dependencies.unknown]
    role = evaluate_semantic_layout(
        sources, ((edge.source_path, edge.target_path) for edge in dependencies.edges),
        role_policy,
    )
    rankings = []
    for path in sorted(dependencies.analyzed_paths):
        impact = analyze_change_impact(dependencies, [path])
        if impact.affected:
            bucket = domain_metrics[classified[path]]
            bucket["potential_reverse_dependents_total"] += len(impact.affected)
            bucket["potential_reverse_dependents_max"] = max(
                bucket["potential_reverse_dependents_max"], len(impact.affected)
            )
            rankings.append({
                "path": path, "potential_dependents": len(impact.affected),
                "direct": len(impact.direct_dependents),
                "witnesses": [
                    {"path": entry.path, "distance": entry.distance, "chain": list(entry.witness)}
                    for entry in impact.affected[:10]
                ],
            })
    rankings.sort(key=lambda r: (-r["potential_dependents"], r["path"]))
    exports = [entry for path, source in sorted(sources.items()) for entry in _exports(path, source)]
    return {
        "schema_version": "0.1",
        "snapshot_id": dependencies.snapshot_id,
        "source_scope": "CODEQA_PRODUCT_PYTHON",
        "domain_policy_sha256": _fingerprint(domain_policy),
        "role_policy_sha256": _fingerprint(role_policy),
        "status": "VIOLATION" if role.status == "VIOLATION" else "NOT_EVALUATED",
        "interpretation": "STATIC_SOURCE_WITNESSES_NOT_RUNTIME_COHESION_OR_COMPATIBILITY_PROOF",
        "inventory": inventory,
        "domain_counts": dict(sorted(counts.items())),
        "domain_metrics": dict(sorted(domain_metrics.items())),
        "observed_import_sites": len(edges),
        "classified_intra_import_sites": intra,
        "classified_cross_import_sites": cross,
        "import_witnesses": edges,
        "unknown_imports": unknown,
        "unknown_reasons": dict(sorted(Counter(item.reason for item in dependencies.unknown).items())),
        "unprocessed_paths": list(dependencies.unprocessed_paths),
        "init_import_candidates": exports,
        "potential_reverse_impact_top10": rankings[:10],
        "role_findings": [
            {"status": f.status, "code": f.code, "source": f.source,
             "target": f.target, "reason": f.reason} for f in role.findings
        ],
        "limitations": [
            "filename rules do not prove domain ownership or semantic cohesion",
            "static import edges are not executed dependency or complete runtime coupling",
            "unclassified and ambiguous source names are not silently assigned",
            "init imports are not independently reviewed stable public APIs",
            "reverse import paths are potential impacts only, not a safe exclusion bound",
            "before/after quality comparisons require one pinned analyzer and identical policy",
            "per-domain import and reverse-impact metrics are static observed sites only",
        ],
    }


def compare_domain_inventories(before: Mapping[str, Any], after: Mapping[str, Any],
                               *, analyzer_sha: str) -> dict[str, Any]:
    """Read-only, identical-policy static metrics; no quality or runtime verdict."""
    if not re.fullmatch(r"[0-9a-f]{40}", analyzer_sha):
        raise DomainInventoryError("exact analyzer SHA required")
    if not isinstance(before, Mapping) or not isinstance(after, Mapping):
        raise DomainInventoryError("two inventory mappings required")
    for field in ("schema_version", "source_scope", "domain_policy_sha256",
                  "role_policy_sha256", "interpretation"):
        if field not in before or before[field] != after.get(field):
            raise DomainInventoryError("incomparable inventory field: " + field)
    if before["schema_version"] != "0.1":
        raise DomainInventoryError("unsupported inventory schema")
    for report in (before, after):
        if (not isinstance(report.get("snapshot_id"), str)
                or not re.fullmatch(r"[0-9a-f]{40}", report["snapshot_id"])
                or report.get("status") not in {"NOT_EVALUATED", "VIOLATION"}):
            raise DomainInventoryError("invalid pinned snapshot or status")
    if before["snapshot_id"] == after["snapshot_id"]:
        raise DomainInventoryError("identical revisions cannot be an evolution comparison")

    def source_hashes(report: Mapping[str, Any]) -> dict[str, str]:
        items = report.get("inventory")
        if not isinstance(items, list):
            raise DomainInventoryError("missing source inventory")
        result = {}
        for item in items:
            if (not isinstance(item, dict) or not _safe_source_path(item.get("path"))
                    or not isinstance(item.get("sha256"), str)
                    or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"])
                    or item["path"] in result):
                raise DomainInventoryError("invalid or duplicate source hash")
            domain = item.get("domain")
            if (not isinstance(domain, str)
                    or (domain not in {"UNCLASSIFIED", "AMBIGUOUS"}
                        and not re.fullmatch(r"[a-z_]+", domain))):
                raise DomainInventoryError("missing or invalid source domain classification")
            result[item["path"]] = item["sha256"]
        return result

    original, current = source_hashes(before), source_hashes(after)

    def verify_import_counts(report: Mapping[str, Any], source_paths: set[str]) -> None:
        domains = {item["path"]: item["domain"] for item in report["inventory"]}
        witnesses = report.get("import_witnesses")
        if not isinstance(witnesses, list):
            raise DomainInventoryError("missing source-backed import witnesses")
        counts = {"observed_import_sites": len(witnesses),
                  "classified_intra_import_sites": 0,
                  "classified_cross_import_sites": 0}
        for entry in witnesses:
            if (not isinstance(entry, dict)
                    or entry.get("source") not in source_paths
                    or entry.get("target") not in source_paths
                    or type(entry.get("line")) is not int or entry["line"] < 1
                    or entry.get("classification") not in {
                        "INTRA_DOMAIN", "CROSS_DOMAIN", "DOMAIN_UNKNOWN"
                    }):
                raise DomainInventoryError("invalid source-backed import witness")
            source_domain = domains[entry["source"]]
            target_domain = domains[entry["target"]]
            expected_classification = (
                "DOMAIN_UNKNOWN"
                if source_domain in {"UNCLASSIFIED", "AMBIGUOUS"}
                or target_domain in {"UNCLASSIFIED", "AMBIGUOUS"}
                else "INTRA_DOMAIN" if source_domain == target_domain
                else "CROSS_DOMAIN"
            )
            if (entry.get("source_domain") != source_domain
                    or entry.get("target_domain") != target_domain
                    or entry["classification"] != expected_classification):
                raise DomainInventoryError("import witness contradicts source domain classification")
            if entry["classification"] == "INTRA_DOMAIN":
                counts["classified_intra_import_sites"] += 1
            elif entry["classification"] == "CROSS_DOMAIN":
                counts["classified_cross_import_sites"] += 1
        for key, count in counts.items():
            if type(report.get(key)) is not int or report[key] != count:
                raise DomainInventoryError("metric contradicts import witnesses: " + key)

    verify_import_counts(before, set(original))
    verify_import_counts(after, set(current))
    numbers = {}
    for field in ("observed_import_sites", "classified_intra_import_sites",
                  "classified_cross_import_sites"):
        left, right = before.get(field), after.get(field)
        if type(left) is not int or type(right) is not int or min(left, right) < 0:
            raise DomainInventoryError("unverified metric: " + field)
        numbers[field] = {"before": left, "after": right, "delta": right - left}
    numbers["source_files"] = {
        "before": len(original), "after": len(current),
        "delta": len(current) - len(original),
    }

    def public_import_candidates(report: Mapping[str, Any]) -> set[tuple[str, str, str, str]] | None:
        items = report.get("init_import_candidates")
        if items is None:
            return None
        if not isinstance(items, list):
            raise DomainInventoryError("invalid __init__ import candidate list")
        found = set()
        selected_paths = {item["path"] for item in report["inventory"]}
        for item in items:
            if not isinstance(item, dict):
                raise DomainInventoryError("invalid __init__ import candidate")
            path, origin, name, alias = (
                item.get("path"), item.get("from"), item.get("name"), item.get("asname")
            )
            if (not _safe_source_path(path) or not path.endswith("/__init__.py")
                    or path not in selected_paths
                    or not isinstance(origin, str) or not origin
                    or not isinstance(name, str) or not name
                    or alias is not None and (not isinstance(alias, str) or not alias)):
                raise DomainInventoryError("invalid __init__ import witness")
            found.add((path, origin, name, alias or ""))
        return found

    earlier = public_import_candidates(before)
    later = public_import_candidates(after)
    if earlier is None or later is None:
        init_import_review = {
            "status": "NOT_EVALUATED", "removed_candidates": [],
            "added_candidates": [], "reason": "IMPORT_CANDIDATE_COVERAGE_MISSING",
        }
    else:
        removed = sorted(earlier - later)
        added = sorted(later - earlier)
        init_import_review = {
            "status": "REVIEW_REQUIRED" if removed else "NOT_EVALUATED",
            "removed_candidates": [list(entry) for entry in removed],
            "added_candidates": [list(entry) for entry in added],
            "reason": "SYNTACTIC_IMPORT_CHANGES_NOT_PROVEN_PUBLIC_API_BREAKAGE",
        }
    return {
        "schema_version": "0.1",
        "status": "NOT_EVALUATED",
        "meaning": "STATIC_COUNT_DELTA_NOT_DESIGN_QUALITY_OR_COMPATIBILITY",
        "analyzer_sha": analyzer_sha,
        "source_before_sha": before["snapshot_id"],
        "source_after_sha": after["snapshot_id"],
        "domain_policy_sha256": after["domain_policy_sha256"],
        "role_policy_sha256": after["role_policy_sha256"],
        "source_status": {"before": before["status"], "after": after["status"]},
        "init_import_change_review": init_import_review,
        "metrics": numbers,
        "added_paths": sorted(set(current) - set(original)),
        "removed_paths": sorted(set(original) - set(current)),
        "modified_paths": sorted(p for p in set(current) & set(original)
                                 if current[p] != original[p]),
        "limitations": [
            "same-process pinned analyzer is caller obligation",
            "static import counts do not establish runtime coupling or cohesion",
            "public compatibility and human review burden NOT_EVALUATED",
        ],
    }
