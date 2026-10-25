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
        and "\\" not in path and "\x00" not in path
        and all(p not in ("", ".", "..") for p in path.split("/"))
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
        ],
    }
