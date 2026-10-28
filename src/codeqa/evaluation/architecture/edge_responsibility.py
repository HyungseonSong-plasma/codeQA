"""Per-edge responsibility *review evidence* for source-derived concentration.

This joins declared role responsibilities with measured import witnesses and
known internal consumers. It does not infer intentional composition, prove
behavioral test coverage, or certify compatibility of a package move.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from hashlib import sha256
import json
from typing import Any


class EdgeResponsibilityEvidenceError(ValueError):
    """Mismatched source, role policy, or forged edge/consumer evidence."""


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def census_edge_responsibility(
    inventory: Mapping[str, Any],
    metrics: Mapping[str, Any],
    triage: Mapping[str, Any],
    consumers: Mapping[str, Any],
    role_policy: Mapping[str, Any],
) -> dict[str, Any]:
    """Emit a review record for *every* observed concentration cross-role pair.

    A declared-allowed import is a candidate for intentional composition, not
    evidence that its semantic ownership or runtime effects have been verified.
    """
    try:
        source = inventory["source_identity"]["repository_commit_sha"]
        identity = triage["source_identity"]
        c_identity = consumers["source_identity"]
        roles = role_policy["roles"]
        if (
            inventory["schema_version"] != "0.1"
            or metrics["schema_version"] != "0.1"
            or triage["schema_version"] != "0.1"
            or consumers["schema_version"] != "0.1"
            or inventory["inventory_id"] != _digest({
                k: v for k, v in inventory.items() if k != "inventory_id"
            })
            or metrics["metrics_id"] != _digest({
                k: v for k, v in metrics.items() if k != "metrics_id"
            })
            or triage["triage_id"] != _digest({
                k: v for k, v in triage.items() if k != "triage_id"
            })
            or consumers["census_id"] != _digest({
                k: v for k, v in consumers.items() if k != "census_id"
            })
            or metrics["snapshot_sha"] != source
            or metrics["inventory_id"] != inventory["inventory_id"]
            or identity["snapshot_sha"] != source
            or identity["inventory_id"] != inventory["inventory_id"]
            or identity["metrics_id"] != metrics["metrics_id"]
            or c_identity["snapshot_sha"] != source
            or c_identity["inventory_id"] != inventory["inventory_id"]
            or c_identity["metrics_id"] != metrics["metrics_id"]
            or c_identity["triage_id"] != triage["triage_id"]
            or identity["role_policy_sha256"] != _digest(role_policy)
            or metrics["role_policy_sha256"] != _digest(role_policy)
            or inventory["source_identity"]["role_policy_sha256"] != _digest(role_policy)
            or consumers["decision"] != "NOT_EVALUATED"
            or triage["decision"] != "NOT_EVALUATED"
            or not isinstance(roles, dict)
        ):
            raise EdgeResponsibilityEvidenceError("source/profile/report mismatch")
        tracked = {f["path"]: f for f in inventory["files"]}
        measured = {(p["source_path"], p["target_path"]): p
                    for p in metrics["resolved_pairs"]}
        module_consumers = {m["module_path"]: m for m in consumers["modules"]}
        if (len(tracked) != len(inventory["files"])
                or len(measured) != len(metrics["resolved_pairs"])
                or len(module_consumers) != len(consumers["modules"])
                or consumers["concentration_source_modules"] != len(module_consumers)
                or consumers["known_static_importer_pairs"] != sum(
                    m["known_static_importer_pairs"] for m in module_consumers.values()
                )
                or consumers["known_test_path_importer_pairs"] != sum(
                    m["known_test_path_importer_pairs"] for m in module_consumers.values()
                )):
            raise EdgeResponsibilityEvidenceError("duplicate or inconsistent inputs")
        records = []
        seen_signals: set[str] = set()
        for signal in triage["signal_triage"]:
            sid = signal["signal_id"]
            if sid in seen_signals or signal["observed_cross_pairs"] != len(signal["pairs"]):
                raise EdgeResponsibilityEvidenceError("duplicate signal or bad denominator")
            seen_signals.add(sid)
            if sum(signal["declared_policy_counts"].values()) != len(signal["pairs"]):
                raise EdgeResponsibilityEvidenceError("declared policy denominator mismatch")
            observed_counts: Counter[str] = Counter()
            for edge in signal["pairs"]:
                src, dst = edge["source_path"], edge["target_path"]
                pair = measured.get((src, dst))
                if (pair is None or src not in tracked or dst not in tracked
                        or src not in module_consumers
                        or pair["source_role"] != edge["source_role"]
                        or pair["target_role"] != edge["target_role"]
                        or pair["witnesses"] != edge["source_witnesses"]
                        or edge["source_role"] != signal["source_role"]
                        or edge["source_role"] == edge["target_role"]
                        or edge["semantic_ownership"] != "NOT_EVALUATED"
                        or edge["external_consumers"] != "NOT_EVALUATED"):
                    raise EdgeResponsibilityEvidenceError("unbound cross-role pair")
                for witness in pair["witnesses"]:
                    if (witness["source_path"] != src
                            or witness["target_path"] != dst
                            or witness["source_sha256"] != tracked[src]["source_sha256"]
                            or type(witness["line"]) is not int
                            or witness["line"] < 1):
                        raise EdgeResponsibilityEvidenceError("unbound import witness")
                src_role, dst_role = edge["source_role"], edge["target_role"]
                if src_role not in roles or dst_role not in roles:
                    raise EdgeResponsibilityEvidenceError("undeclared role")
                forbidden = dst_role in roles[src_role]["forbidden_imports"]
                expected = ("DECLARED_FORBIDDEN" if forbidden else "DECLARED_ALLOWED")
                if forbidden and edge["declared_policy_direction"] == "DECLARED_TRANSITIONAL_REVIEW":
                    exceptions = role_policy["exceptions"]
                    if not any(
                        x["source"] == src and x["target"] == dst
                        and x["status"] == "TRANSITIONAL_REVIEW"
                        for x in exceptions
                    ):
                        raise EdgeResponsibilityEvidenceError("unregistered exception")
                elif edge["declared_policy_direction"] != expected:
                    raise EdgeResponsibilityEvidenceError("role direction mismatch")
                observed_counts[edge["declared_policy_direction"]] += 1
                module = module_consumers[src]
                if (module["known_static_importer_pairs"] != len(module["importers"])
                        or module["known_test_path_importer_pairs"] != sum(
                            i["importer_category"] == "TEST_PATH_HEURISTIC"
                            for i in module["importers"]
                        )):
                    raise EdgeResponsibilityEvidenceError("untrusted consumer denominator")
                test_importers = []
                for importer in module["importers"]:
                    if importer["importer_category"] != "TEST_PATH_HEURISTIC":
                        continue
                    for witness in importer["source_witnesses"]:
                        path = witness["source_path"]
                        if (path != importer["importer_path"] or path not in tracked
                                or witness["target_path"] != src
                                or witness["source_sha256"] != tracked[path]["source_sha256"]
                                or type(witness["line"]) is not int
                                or witness["line"] < 1):
                            raise EdgeResponsibilityEvidenceError("unbound test-path witness")
                        test_importers.append(witness)
                records.append({
                    "signal_id": sid,
                    "source_path": src,
                    "target_path": dst,
                    "source_role": src_role,
                    "target_role": dst_role,
                    "source_declared_responsibility": roles[src_role]["responsibility"],
                    "target_declared_responsibility": roles[dst_role]["responsibility"],
                    "declared_policy_direction": edge["declared_policy_direction"],
                    "composition_hypothesis": (
                        "DECLARED_DIRECTION_COMPATIBLE"
                        if not forbidden else "BOUNDARY_REVIEW_REQUIRED"
                    ),
                    "import_witnesses": pair["witnesses"],
                    "known_source_importers": module["known_static_importer_pairs"],
                    "known_test_path_importers": test_importers,
                    "test_behavior_coverage": "NOT_EVALUATED",
                    "semantic_ownership": "NOT_EVALUATED",
                    "external_consumers": "NOT_EVALUATED",
                })
            if dict(observed_counts) != signal["declared_policy_counts"]:
                raise EdgeResponsibilityEvidenceError("triage policy counts mismatch")
        if (len(records) != sum(s["observed_cross_pairs"]
                               for s in triage["signal_triage"])
                or len({(r["signal_id"], r["source_path"], r["target_path"])
                        for r in records}) != len(records)
                or set(module_consumers) != {r["source_path"] for r in records}):
            raise EdgeResponsibilityEvidenceError("missing/duplicated edge or consumer")
        records.sort(key=lambda r: (r["signal_id"], r["source_path"], r["target_path"]))
        result = {
            "schema_version": "0.1",
            "source_identity": {
                "snapshot_sha": source,
                "inventory_id": inventory["inventory_id"],
                "metrics_id": metrics["metrics_id"],
                "triage_id": triage["triage_id"],
                "consumer_census_id": consumers["census_id"],
                "role_policy_sha256": _digest(role_policy),
            },
            "observed_cross_role_pairs": len(records),
            "declared_policy_counts": dict(sorted(Counter(
                r["declared_policy_direction"] for r in records
            ).items())),
            "edges": records,
            "semantic_ownership": "NOT_EVALUATED",
            "test_behavior_coverage": "NOT_EVALUATED",
            "external_consumers": "NOT_EVALUATED",
            "runtime_compatibility": "NOT_EVALUATED",
            "decision": "NOT_EVALUATED",
            "limitations": [
                "role responsibility text is DECLARED_POLICY, not a source-derived semantic verdict",
                "test-path imports are OBSERVED static import witnesses, not assertion coverage",
                "every concentration pair is included; absence of a pair is not absence of dynamic dependency",
                "external consumers, runtime imports and semantic ownership require independent verification",
                "no package move or global KEEP/PASS follows from declared direction alone",
            ],
        }
        result["responsibility_id"] = _digest(result)
        return result
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        raise EdgeResponsibilityEvidenceError("untrustworthy edge responsibility evidence") from exc


def render_edge_responsibility_markdown(report: Mapping[str, Any]) -> str:
    """Render complete cross-role review ledger, with no semantic PASS."""
    try:
        if (report["responsibility_id"] != _digest({
                k: v for k, v in report.items() if k != "responsibility_id"
            })
                or report["decision"] != "NOT_EVALUATED"
                or report["observed_cross_role_pairs"] != len(report["edges"])
                or sum(report["declared_policy_counts"].values()) != len(report["edges"])):
            raise EdgeResponsibilityEvidenceError("modified responsibility ledger")
        lines = [
            "## Source-specific cross-role responsibility review ledger",
            "",
            "Source HEAD: " + report["source_identity"]["snapshot_sha"],
            "Observed cross-role pairs: " + str(report["observed_cross_role_pairs"]),
            "Declared policy counts: " + json.dumps(
                report["declared_policy_counts"], sort_keys=True,
            ),
            "Direction-compatible is a hypothesis, not semantic approval.",
            "Test-path imports are not behavioral test coverage.",
        ]
        for edge in report["edges"]:
            lines.extend([
                "",
                "- `" + edge["source_path"] + "` (" + edge["source_role"]
                + ") -> `" + edge["target_path"] + "` (" + edge["target_role"]
                + "): " + edge["declared_policy_direction"]
                + " / " + edge["composition_hypothesis"],
                "  - Declared source: " + edge["source_declared_responsibility"],
                "  - Declared target: " + edge["target_declared_responsibility"],
            ])
            for witness in edge["import_witnesses"]:
                lines.append(
                    "  - OBSERVED import: `" + witness["source_path"] + ":"
                    + str(witness["line"]) + "` sha256=" + witness["source_sha256"]
                )
            lines.append(
                "  - Known static importers of source: "
                + str(edge["known_source_importers"])
                + "; test-path import sites: " + str(len(edge["known_test_path_importers"]))
            )
            for witness in edge["known_test_path_importers"]:
                lines.append(
                    "  - OBSERVED test-path import: `" + witness["source_path"]
                    + ":" + str(witness["line"]) + "` sha256="
                    + witness["source_sha256"]
                )
            lines.append(
                "  - Semantic ownership, behavioral coverage, external callers: NOT_EVALUATED."
            )
        lines.extend([
            "",
            "No migration or global KEEP/PASS is authorized by this review ledger.",
            "",
        ])
        return "\n".join(lines)
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        raise EdgeResponsibilityEvidenceError("untrustworthy responsibility report") from exc
