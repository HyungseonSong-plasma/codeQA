"""B6 generic adapter-boundary evidence from a pinned B1/B2 source snapshot.

Language family is a declared capability/ownership fact, never inferred from
filename spelling. This evaluator cannot authorize package moves or certify
non-Python parsers, runtime imports, ABI or external consumers.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from hashlib import sha256
import json
from typing import Any


class AdapterBoundaryError(ValueError):
    """Untrustworthy snapshot, declaration or static import evidence."""


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def assess_adapter_boundaries(
    inventory: Mapping[str, Any],
    metrics: Mapping[str, Any],
    declaration: Mapping[str, Any],
    *,
    min_cross_family_pairs: int = 2,
    min_cross_family_share: float = 0.2,
) -> dict[str, Any]:
    """Return bounded language-family pressure, KEEP and conditional alternatives.

    A family declaration describes observed implementation ownership, not
    support for its target language. Only B2 static Python import witnesses
    can contribute to coupling counts. No source is executed or rewritten.
    """
    if (not all(isinstance(x, Mapping) for x in (inventory, metrics, declaration))
            or type(min_cross_family_pairs) is not int or min_cross_family_pairs < 1
            or isinstance(min_cross_family_share, bool)
            or not isinstance(min_cross_family_share, (int, float))
            or not 0 < min_cross_family_share <= 1):
        raise AdapterBoundaryError("invalid inputs or signal thresholds")
    try:
        identity = inventory["source_identity"]
        snapshot = identity["repository_commit_sha"]
        if (inventory["schema_version"] != "0.1"
                or metrics["schema_version"] != "0.1"
                or declaration["schema_version"] != "0.1"
                or snapshot != metrics["snapshot_sha"]
                or inventory["inventory_id"] != metrics["inventory_id"]
                or inventory["inventory_id"] != _digest({
                    k: v for k, v in inventory.items() if k != "inventory_id"
                })
                or metrics["metrics_id"] != _digest({
                    k: v for k, v in metrics.items() if k != "metrics_id"
                })
                or identity["role_policy_sha256"] != metrics["role_policy_sha256"]):
            raise AdapterBoundaryError("B1/B2 source identity mismatch")
        scope = declaration["adapter_scope"]
        if not isinstance(scope, str) or not scope.startswith(inventory["source_scope"] + "/"):
            raise AdapterBoundaryError("adapter scope outside pinned inventory")
        all_files = {f["path"]: f for f in inventory["files"]}
        modules = {m["path"]: m for m in metrics["modules"]}
        if len(all_files) != len(inventory["files"]) or len(modules) != len(metrics["modules"]):
            raise AdapterBoundaryError("duplicate source/module paths")
        adapter_paths = {p for p in all_files if p.startswith(scope + "/") and p.endswith(".py")}
        families = declaration["families"]
        shared = declaration["shared_paths"]
        if (not isinstance(families, list) or not isinstance(shared, list)
                or declaration["external_consumers"] not in ("VERIFIED", "NOT_EVALUATED")
                or declaration["distribution_compatibility"] not in ("VERIFIED", "NOT_EVALUATED")):
            raise AdapterBoundaryError("invalid declared boundary evidence")
        owners: dict[str, str] = {}
        for item in families:
            name, paths = item["family"], item["module_paths"]
            if (not isinstance(name, str) or not name or name == "SHARED"
                    or not isinstance(paths, list) or not paths
                    or item["capability_status"] not in ("SUPPORTED", "PARTIAL", "NOT_EVALUATED")
                    or item["parser_provenance"] not in ("VERIFIED", "NOT_EVALUATED")):
                raise AdapterBoundaryError("invalid family declaration")
            for path in paths:
                if path in owners:
                    raise AdapterBoundaryError("duplicate family ownership")
                owners[path] = name
        if len({f["family"] for f in families}) != len(families):
            raise AdapterBoundaryError("duplicate family names")
        for path in shared:
            if path in owners:
                raise AdapterBoundaryError("shared/family ownership overlap")
            owners[path] = "SHARED"
        if not set(owners) <= adapter_paths:
            raise AdapterBoundaryError("declared path outside tracked adapter Python sources")
        if any(all_files[p]["read_state"] != "READ" or p not in modules for p in owners):
            raise AdapterBoundaryError("declared source is unread or not analyzed by B2")
        pairs = metrics["resolved_pairs"]
        if metrics["denominators"]["resolved_distinct_pairs"] != len(pairs):
            raise AdapterBoundaryError("B2 pair denominator mismatch")
        counts: Counter[str] = Counter()
        witnesses: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for pair in pairs:
            src, dst = pair["source_path"], pair["target_path"]
            if (src, dst) in seen or src not in modules or dst not in modules:
                raise AdapterBoundaryError("invalid or duplicate B2 static pair")
            seen.add((src, dst))
            if not pair["witnesses"]:
                raise AdapterBoundaryError("missing static import witness")
            for witness in pair["witnesses"]:
                if (witness["source_path"] != src or witness["target_path"] != dst
                        or witness["source_sha256"] != all_files[src]["source_sha256"]
                        or type(witness["line"]) is not int or witness["line"] < 1):
                    raise AdapterBoundaryError("unbound static import witness")
            if src not in adapter_paths and dst not in adapter_paths:
                continue
            a, b = owners.get(src, "UNCLASSIFIED"), owners.get(dst, "UNCLASSIFIED")
            if src not in adapter_paths or dst not in adapter_paths:
                category = "EXTERNAL_BOUNDARY"
            elif "UNCLASSIFIED" in (a, b):
                category = "UNCLASSIFIED"
            elif "SHARED" in (a, b):
                category = "SHARED_UTILITY"
            elif a == b:
                category = "WITHIN_FAMILY"
            else:
                category = "CROSS_FAMILY"
            counts[category] += 1
            if category == "CROSS_FAMILY":
                witnesses.extend(pair["witnesses"])
        measured_internal = sum(counts[k] for k in (
            "WITHIN_FAMILY", "CROSS_FAMILY", "SHARED_UTILITY", "UNCLASSIFIED"
        ))
        cross = counts["CROSS_FAMILY"]
        signal = (cross >= min_cross_family_pairs and measured_internal > 0
                  and cross / measured_internal >= min_cross_family_share)
        signals: list[dict[str, Any]] = []
        if signal:
            signals.append({
                "signal_id": _digest({"snapshot": snapshot, "pairs": [
                    (w["source_path"], w["target_path"], w["line"]) for w in witnesses
                ]}),
                "family": "OBSERVED_CROSS_FAMILY_IMPORT_PRESSURE",
                "measurement": {"numerator": cross, "denominator": measured_internal,
                                "ratio": cross / measured_internal},
                "source_witnesses": witnesses,
                "derivation_rule": "B6 cross-family pairs / all observed adapter-internal pairs",
                "benign_counterhypothesis": "A shared integration or orchestration layer may intentionally bridge families.",
                "evidence_class": "PROXY_INFERENCE",
            })
        unclassified = sorted(adapter_paths - set(owners))
        unverified = sorted(f["family"] for f in families
                            if f["parser_provenance"] != "VERIFIED"
                            or f["capability_status"] == "NOT_EVALUATED")
        unknowns = sorted(set([
            "DYNAMIC_PLUGIN_LOADING_NOT_EVALUATED",
            "SHARED_UTILITY_SEMANTICS_NOT_EVALUATED",
            "RUST_MACRO_TRAIT_SEMANTICS_NOT_EVALUATED",
            "CPP_MACRO_HEADER_ABI_NOT_EVALUATED",
            *metrics["coverage"]["unknown_by_reason"].keys(),
            *(["UNCLASSIFIED_ADAPTER_SOURCES"] if unclassified else []),
            *(["EXTERNAL_CONSUMERS_NOT_EVALUATED"]
              if declaration["external_consumers"] != "VERIFIED" else []),
            *(["DISTRIBUTION_COMPATIBILITY_NOT_EVALUATED"]
              if declaration["distribution_compatibility"] != "VERIFIED" else []),
            *(["PARSER_PROVENANCE_NOT_EVALUATED"]
              if unverified else []),
        ]))
        candidates = [{"layout": "KEEP", "status": "BASELINE", "decision": "NOT_EVALUATED"}]
        implemented_families = {
            f["family"] for f in families
            if f["capability_status"] in ("SUPPORTED", "PARTIAL")
        }
        if signal and len(implemented_families) >= 2:
            candidates.append({
                "layout": "GROUP_BY_DECLARED_LANGUAGE_FAMILY",
                "status": "REVIEW_CANDIDATE",
                "decision": "NOT_EVALUATED",
                "unknowns": unknowns,
            })
            if (declaration["distribution_compatibility"] == "VERIFIED"
                    and declaration["external_consumers"] == "VERIFIED"):
                candidates.append({
                    "layout": "SIBLING_DISTRIBUTION",
                    "status": "REVIEW_CANDIDATE",
                    "decision": "NOT_EVALUATED",
                    "unknowns": unknowns,
                })
        result = {
            "schema_version": "0.1",
            "snapshot_sha": snapshot,
            "inventory_id": inventory["inventory_id"],
            "metrics_id": metrics["metrics_id"],
            "declaration_sha256": _digest(declaration),
            "adapter_scope": scope,
            "coverage": {
                "adapter_python_files": len(adapter_paths),
                "declared_family_files": sum(len(f["module_paths"]) for f in families),
                "shared_files": len(shared),
                "unclassified_paths": unclassified,
                "unverified_family_parsers": unverified,
                "external_consumers": declaration["external_consumers"],
                "distribution_compatibility": declaration["distribution_compatibility"],
            },
            "family_capabilities": [
                {"family": f["family"], "module_count": len(f["module_paths"]),
                 "capability_status": f["capability_status"],
                 "parser_provenance": f["parser_provenance"]}
                for f in sorted(families, key=lambda f: f["family"])
            ],
            "static_pairs": dict(sorted(counts.items())),
            "measured_adapter_internal_pairs": measured_internal,
            "architecture_signals": signals,
            "candidates": candidates,
            "unknowns": unknowns,
            "evidence_status": "INCOMPLETE" if unknowns else "EVIDENCE_ONLY",
            "decision": "NOT_EVALUATED",
            "limitations": [
                "Source-family membership is declared, not inferred from filenames.",
                "Python static imports are incomplete for dynamic loading and runtime dispatch.",
                "No semantic cohesion, non-Python parser correctness, ABI or package move is certified.",
                "KEEP is mandatory; a source-backed signal is not a split recommendation.",
            ],
        }
        result["boundary_id"] = _digest(result)
        return result
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        raise AdapterBoundaryError("untrustworthy B6 adapter evidence") from exc
