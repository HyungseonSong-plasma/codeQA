"""Exact-snapshot internal static importer census for source-derived architecture signals.

The census is a bounded dependency witness, not a public API or test-coverage
certification. Only paths already observed in B3 concentration signals are
selected; there are no seeded package names or architecture questions.
"""
from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
import json
from typing import Any


class InternalConsumerEvidenceError(ValueError):
    """B1/B2/B3/policy evidence does not describe one trustworthy source."""


def _digest(value: Any) -> str:
    return sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()


def census_internal_consumers(
    inventory: Mapping[str, Any],
    metrics: Mapping[str, Any],
    triage: Mapping[str, Any],
) -> dict[str, Any]:
    """Find known static importers of modules implicated in concentration.

    A `tests/` importer is an import witness, not proof that a test asserts
    the module's behavior. An absent importer is never proof of an unused API.
    """
    try:
        identity = inventory["source_identity"]
        source_sha = identity["repository_commit_sha"]
        if (
            inventory["schema_version"] != "0.1"
            or metrics["schema_version"] != "0.1"
            or triage["schema_version"] != "0.1"
            or metrics["snapshot_sha"] != source_sha
            or triage["source_identity"]["snapshot_sha"] != source_sha
            or metrics["inventory_id"] != inventory["inventory_id"]
            or triage["source_identity"]["inventory_id"] != inventory["inventory_id"]
            or triage["source_identity"]["metrics_id"] != metrics["metrics_id"]
            or inventory["inventory_id"] != _digest({
                k: v for k, v in inventory.items() if k != "inventory_id"
            })
            or metrics["metrics_id"] != _digest({
                k: v for k, v in metrics.items() if k != "metrics_id"
            })
            or triage["triage_id"] != _digest({
                k: v for k, v in triage.items() if k != "triage_id"
            })
            or metrics["denominators"]["resolved_distinct_pairs"]
               != len(metrics["resolved_pairs"])
            or triage["decision"] != "NOT_EVALUATED"
        ):
            raise InternalConsumerEvidenceError("snapshot/report identity mismatch")
        files = {f["path"]: f for f in inventory["files"]}
        pairs = {
            (p["source_path"], p["target_path"]): p
            for p in metrics["resolved_pairs"]
        }
        if (len(files) != len(inventory["files"])
                or len(pairs) != len(metrics["resolved_pairs"])):
            raise InternalConsumerEvidenceError("duplicate file or dependency pair")

        targets: set[str] = set()
        for signal in triage["signal_triage"]:
            if signal["observed_cross_pairs"] != len(signal["pairs"]):
                raise InternalConsumerEvidenceError("concentration denominator mismatch")
            for edge in signal["pairs"]:
                key = (edge["source_path"], edge["target_path"])
                if key not in pairs or pairs[key]["witnesses"] != edge["source_witnesses"]:
                    raise InternalConsumerEvidenceError("triage pair not in measured graph")
                targets.add(edge["source_path"])
        if not targets <= set(files):
            raise InternalConsumerEvidenceError("target module outside inventory")

        by_target: dict[str, list[dict[str, Any]]] = {p: [] for p in sorted(targets)}
        for (source, target), pair in sorted(pairs.items()):
            if target not in by_target:
                continue
            if source not in files or not pair["witnesses"]:
                raise InternalConsumerEvidenceError("untracked or unwitnessed importer")
            for witness in pair["witnesses"]:
                if (
                    witness["source_path"] != source
                    or witness["target_path"] != target
                    or witness["source_sha256"] != files[source]["source_sha256"]
                    or type(witness["line"]) is not int
                    or witness["line"] < 1
                ):
                    raise InternalConsumerEvidenceError("import witness identity mismatch")
            scope = inventory["source_scope"] + "/"
            category = (
                "TEST_PATH_HEURISTIC" if source.startswith("tests/")
                else "PACKAGE_SOURCE" if source.startswith(scope)
                else "OTHER_TRACKED_SOURCE"
            )
            by_target[target].append({
                "importer_path": source,
                "importer_category": category,
                "source_witnesses": pair["witnesses"],
            })

        modules = [{
            "module_path": target,
            "known_static_importer_pairs": len(importers),
            "known_test_path_importer_pairs": sum(
                p["importer_category"] == "TEST_PATH_HEURISTIC"
                for p in importers
            ),
            "importers": importers,
        } for target, importers in by_target.items()]
        result: dict[str, Any] = {
            "schema_version": "0.1",
            "source_identity": {
                "snapshot_sha": source_sha,
                "inventory_id": inventory["inventory_id"],
                "metrics_id": metrics["metrics_id"],
                "triage_id": triage["triage_id"],
            },
            "concentration_source_modules": len(modules),
            "known_static_importer_pairs": sum(
                m["known_static_importer_pairs"] for m in modules
            ),
            "known_test_path_importer_pairs": sum(
                m["known_test_path_importer_pairs"] for m in modules
            ),
            "modules": modules,
            "unknown_imports_by_reason": metrics["coverage"]["unknown_by_reason"],
            "external_consumers": "NOT_EVALUATED",
            "semantic_ownership": "NOT_EVALUATED",
            "runtime_compatibility": "NOT_EVALUATED",
            "decision": "NOT_EVALUATED",
            "limitations": [
                "only B2-resolved static imports into signal source modules are counted",
                "tests/ is a path heuristic, not proof of exercised assertions",
                "dynamic imports, package re-exports and external callers may be missing",
                "no static importer does not establish that a public API is unused",
                "observed consumers do not certify semantic ownership or migration safety",
            ],
        }
        result["census_id"] = _digest(result)
        return result
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        raise InternalConsumerEvidenceError(
            "untrustworthy internal consumer evidence"
        ) from exc


def render_internal_consumers_markdown(census: Mapping[str, Any]) -> str:
    """Render per-module import sites while preserving unknown boundaries."""
    if census["census_id"] != _digest({
        k: v for k, v in census.items() if k != "census_id"
    }):
        raise InternalConsumerEvidenceError("modified consumer census")
    lines = [
        "## Known in-repository static consumers of concentration source modules",
        "",
        "Source HEAD: " + census["source_identity"]["snapshot_sha"],
        "Modules: " + str(census["concentration_source_modules"]),
        "Observed static importer pairs: " + str(census["known_static_importer_pairs"]),
        "Observed tests/-path importer pairs (not test coverage): "
        + str(census["known_test_path_importer_pairs"]),
        "External consumers, semantic ownership, runtime compatibility: NOT_EVALUATED.",
    ]
    for module in census["modules"]:
        lines.extend([
            "",
            "- `" + module["module_path"] + "`: "
            + str(module["known_static_importer_pairs"]) + " observed importers.",
        ])
        for importer in module["importers"]:
            for witness in importer["source_witnesses"]:
                lines.append(
                    "  - `" + witness["source_path"] + ":"
                    + str(witness["line"]) + "` ("
                    + importer["importer_category"] + "; sha256="
                    + witness["source_sha256"] + ")"
                )
    lines.extend([
        "",
        "No observed importer is not proof of an unused API. "
        "Dynamic and external consumers remain NOT_EVALUATED.",
        "",
    ])
    return "\n".join(lines)
