"""Conservative source-bound no-move disposition for architecture signals.

A rejected mapping is not an endorsement of the existing package structure.
This report records what can and cannot be decided from B1--B8 evidence.
"""
from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
import json
from typing import Any


class BoundedDispositionError(ValueError):
    """Inputs do not describe the same authenticated architecture evidence."""


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _authentic(report: Mapping[str, Any], key: str) -> bool:
    return report[key] == _digest({k: v for k, v in report.items() if k != key})


def assess_bounded_disposition(
    inventory: Mapping[str, Any],
    triage: Mapping[str, Any],
    responsibility: Mapping[str, Any],
    assessment: Mapping[str, Any],
) -> dict[str, Any]:
    """Distinguish mapping-level KEEP from an unproved global architecture KEEP."""
    try:
        source = inventory["source_identity"]
        t_source = triage["source_identity"]
        r_source = responsibility["source_identity"]
        a_source = assessment["source_identity"]
        if (
            not _authentic(inventory, "inventory_id")
            or not _authentic(triage, "triage_id")
            or not _authentic(responsibility, "responsibility_id")
            or not _authentic(assessment, "assessment_id")
            or any(r["schema_version"] != "0.1" for r in (
                inventory, triage, responsibility, assessment
            ))
            or assessment["mode"] != "DISCOVERY"
            or any(r["decision"] != "NOT_EVALUATED" for r in (
                triage, responsibility, assessment
            ))
            or responsibility["semantic_ownership"] != "NOT_EVALUATED"
            or responsibility["test_behavior_coverage"] != "NOT_EVALUATED"
            or responsibility["external_consumers"] != "NOT_EVALUATED"
            or t_source["snapshot_sha"] != source["repository_commit_sha"]
            or r_source["snapshot_sha"] != source["repository_commit_sha"]
            or a_source["snapshot_sha"] != source["repository_commit_sha"]
            or any(s["inventory_id"] != inventory["inventory_id"]
                   for s in (t_source, r_source, a_source))
            or r_source["triage_id"] != triage["triage_id"]
            or r_source["metrics_id"] != t_source["metrics_id"]
            or a_source["metrics_id"] != t_source["metrics_id"]
            or a_source["role_policy_sha256"] != t_source["role_policy_sha256"]
            or a_source["role_policy_sha256"] != r_source["role_policy_sha256"]
            or assessment["analyzer_hashes"]["opportunities_id"] != t_source["opportunities_id"]
        ):
            raise BoundedDispositionError("source or analysis provenance mismatch")
        tracked = {f["path"]: f for f in inventory["files"]}
        if len(tracked) != len(inventory["files"]):
            raise BoundedDispositionError("duplicate source paths")
        triaged = {s["signal_id"]: s for s in triage["signal_triage"]}
        signals = {s["signal_id"]: s for s in assessment["architecture_signals"]
                   if s["family"] == "CROSS_BOUNDARY_CONCENTRATION"}
        if (len(triaged) != len(triage["signal_triage"])
                or len(signals) != len([s for s in assessment["architecture_signals"]
                                      if s["family"] == "CROSS_BOUNDARY_CONCENTRATION"])
                or set(triaged) != set(signals)):
            raise BoundedDispositionError("unmatched concentration signals")
        edges = responsibility["edges"]
        if (responsibility["observed_cross_role_pairs"] != len(edges)
                or len(edges) != sum(s["observed_cross_pairs"]
                                     for s in triaged.values())):
            raise BoundedDispositionError("responsibility denominator mismatch")
        edge_keys = {(e["signal_id"], e["source_path"], e["target_path"])
                     for e in edges}
        expected_keys = {(sid, p["source_path"], p["target_path"])
                         for sid, s in triaged.items() for p in s["pairs"]}
        if len(edge_keys) != len(edges) or edge_keys != expected_keys:
            raise BoundedDispositionError("missing or duplicate responsibility pair")
        records = []
        for sid, signal in sorted(triaged.items()):
            linked = [q for q in assessment["question_opportunities"]
                      if sid in q["originating_signal_ids"]]
            if len(linked) != 1:
                raise BoundedDispositionError("ambiguous or absent discovered question")
            qid = linked[0]["opportunity_id"]
            compared = [s for s in assessment["scenario_assessments"]
                        if s["opportunity_id"] == qid]
            rejected = [s for s in assessment["rejected_scenarios"]
                        if s["opportunity_id"] == qid]
            if len({s["scenario_id"] for s in compared}) != len(compared):
                raise BoundedDispositionError("duplicate compared candidate")
            if len({json.dumps(s, sort_keys=True) for s in rejected}) != len(rejected):
                raise BoundedDispositionError("duplicate rejected candidate")
            if not compared and not rejected:
                # A signal without any scenario is not a proven KEEP decision.
                verdict = "INSUFFICIENT_EVIDENCE"
            elif not compared:
                verdict = "INSUFFICIENT_EVIDENCE"
            else:
                decisions = [s["decision_evidence"]["decision"] for s in compared]
                if any(d not in ("PREFER", "KEEP", "REVIEW_REQUIRED",
                                 "INSUFFICIENT_EVIDENCE") for d in decisions):
                    raise BoundedDispositionError("unknown B7 decision")
                if any(d in ("PREFER", "REVIEW_REQUIRED") for d in decisions):
                    verdict = "REVIEW_REQUIRED"
                elif any(d == "INSUFFICIENT_EVIDENCE" for d in decisions):
                    verdict = "INSUFFICIENT_EVIDENCE"
                else:
                    verdict = "KEEP"  # only compared alternatives, not architecture
            rejected_witnesses = []
            for candidate in rejected:
                if candidate["originating_signal_ids"] != linked[0]["originating_signal_ids"]:
                    raise BoundedDispositionError("rejection belongs to another signal")
                if candidate["reason"] != "TARGET_COLLISION":
                    continue
                witnesses = candidate.get("collision_witnesses", [])
                if not isinstance(witnesses, list) or not witnesses:
                    raise BoundedDispositionError("collision without witness")
                seen_witnesses: set[tuple[str, str, str]] = set()
                duplicate_groups: dict[str, list[dict[str, Any]]] = {}
                for w in witnesses:
                    path = w["source_path"]
                    target = w["proposed_target_path"]
                    kind = w["collision_kind"]
                    key = (path, target, kind)
                    if (path not in tracked
                            or w["source_sha256"] != tracked[path]["source_sha256"]
                            or not isinstance(target, str) or path == target
                            or key in seen_witnesses):
                        raise BoundedDispositionError("unbound collision witness")
                    seen_witnesses.add(key)
                    if kind == "OCCUPIED_TARGET":
                        if (target not in tracked
                                or w.get("occupied_target_sha256")
                                != tracked[target]["source_sha256"]
                                or "conflicting_sources" in w):
                            raise BoundedDispositionError("unverified occupied target")
                    elif kind == "DUPLICATE_DESTINATION":
                        if ("occupied_target_sha256" in w
                                or not isinstance(w.get("conflicting_sources"), list)):
                            raise BoundedDispositionError("unverified duplicate target")
                        duplicate_groups.setdefault(target, []).append(w)
                    else:
                        raise BoundedDispositionError("unknown collision kind")
                    rejected_witnesses.append({
                        "source_path": path,
                        "proposed_target_path": target,
                        "source_sha256": w["source_sha256"],
                        "collision_kind": kind,
                    })
                for target, group in duplicate_groups.items():
                    sources = {w["source_path"] for w in group}
                    if len(sources) < 2 or len(sources) != len(group):
                        raise BoundedDispositionError("incomplete duplicate destination group")
                    for w in group:
                        if w["conflicting_sources"] != sorted(
                            sources - {w["source_path"]}
                        ):
                            raise BoundedDispositionError("unbound conflicting sources")
            records.append({
                "signal_id": sid,
                "source_role": signal["source_role"],
                "observed_cross_pairs": signal["observed_cross_pairs"],
                "observed_outgoing_pairs": signal["observed_outgoing_pairs"],
                "compared_candidates": [
                    {"scenario_id": c["scenario_id"],
                     "decision": c["decision_evidence"]["decision"],
                     "comparable": c["decision_evidence"]["comparable"],
                     "critical_unknowns": c["decision_evidence"]["critical_unknowns"]}
                    for c in compared
                ],
                "rejected_candidates": [
                    {"opportunity_id": c["opportunity_id"], "reason": c["reason"]}
                    for c in rejected
                ],
                "collision_witnesses": rejected_witnesses,
                "disposition": verdict,
                "current_action": "NO_MOVE",
                "semantic_ownership": "NOT_EVALUATED",
                "external_consumers": "NOT_EVALUATED",
                "behavioral_test_coverage": "NOT_EVALUATED",
                "scope": "CONCENTRATION_SIGNAL_ONLY",
            })
        result = {
            "schema_version": "0.1",
            "source_identity": {
                "snapshot_sha": source["repository_commit_sha"],
                "inventory_id": inventory["inventory_id"],
                "triage_id": triage["triage_id"],
                "responsibility_id": responsibility["responsibility_id"],
                "assessment_id": assessment["assessment_id"],
            },
            "signal_dispositions": records,
            "decision": "NOT_EVALUATED",
            "current_action": "NO_AUTOMATIC_MOVE",
            "limitations": [
                "KEEP of a rejected mapping is not a KEEP verdict for the existing architecture",
                "no viable measured candidate means INSUFFICIENT_EVIDENCE, not PASS",
                "declared allowed edges do not establish intentional semantic composition",
                "behavioral tests, external/dynamic callers and runtime/API compatibility remain NOT_EVALUATED",
                "source growth between snapshots is not a matched-scope quality delta",
            ],
        }
        result["disposition_id"] = _digest(result)
        return result
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        raise BoundedDispositionError("untrustworthy bounded disposition evidence") from exc


def render_bounded_disposition_markdown(report: Mapping[str, Any]) -> str:
    """Human-readable no-move decision boundary, without claiming acceptance."""
    try:
        if (not _authentic(report, "disposition_id")
                or report["decision"] != "NOT_EVALUATED"
                or report["current_action"] != "NO_AUTOMATIC_MOVE"):
            raise BoundedDispositionError("modified disposition")
        lines = [
            "## Bounded architecture disposition",
            "",
            "Source HEAD: " + report["source_identity"]["snapshot_sha"],
            "No automatic move; global semantic ownership: NOT_EVALUATED.",
        ]
        for item in report["signal_dispositions"]:
            lines.append(
                "- " + item["signal_id"] + " (" + item["source_role"] + "): "
                + str(item["observed_cross_pairs"]) + "/"
                + str(item["observed_outgoing_pairs"]) + " cross-role pairs; "
                + item["disposition"] + " for this signal; action NO_MOVE."
            )
            for candidate in item["compared_candidates"]:
                lines.append(
                    "  - Compared " + candidate["scenario_id"] + ": "
                    + candidate["decision"] + "; comparable="
                    + str(candidate["comparable"]) + "; unknowns="
                    + ", ".join(candidate["critical_unknowns"])
                )
            for rejected in item["rejected_candidates"]:
                lines.append(
                    "  - Rejected opportunity " + rejected["opportunity_id"] + ": " + rejected["reason"]
                )
            for witness in item["collision_witnesses"]:
                lines.append(
                    "    - " + witness["source_path"] + " -> "
                    + witness["proposed_target_path"] + " sha256="
                    + witness["source_sha256"]
                )
        if not report["signal_dispositions"]:
            lines.append("- No concentration signals; no forced question or KEEP/PASS.")
        lines.extend([
            "",
            "No viable measured alternative does not certify the existing layout.",
            "Semantic responsibility, test behavior, dynamic/external consumers, "
            "installed package and public API compatibility: NOT_EVALUATED.",
            "",
        ])
        return "\n".join(lines)
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        raise BoundedDispositionError("untrustworthy bounded disposition report") from exc
