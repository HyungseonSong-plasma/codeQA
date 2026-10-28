"""Source-bound declared-policy triage for B3 cross-role concentration signals.

This does not infer semantic ownership or authorize package relocation.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from hashlib import sha256
import json
from typing import Any


class ArchitecturePolicyTriageError(ValueError):
    """Input evidence is inconsistent, stale, or insufficiently bound."""


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _witness_key(witness: Mapping[str, Any]) -> tuple[str, str, int]:
    return (witness["source_path"], witness["target_path"], witness["line"])


def triage_cross_role_concentration(
    inventory: Mapping[str, Any],
    metrics: Mapping[str, Any],
    opportunities: Mapping[str, Any],
    role_policy: Mapping[str, Any],
) -> dict[str, Any]:
    """Classify measured cross-role pairs against *declared* policy only.

    Every observed pair remains available even when its direction is allowed.
    An allowed direction is not evidence of correct ownership, runtime
    behavior, test coverage, or external API compatibility.
    """
    try:
        identity = inventory["source_identity"]
        roles = role_policy["roles"]
        if (inventory["schema_version"] != "0.1"
                or metrics["schema_version"] != "0.1"
                or opportunities["schema_version"] != "0.1"
                or identity["repository_commit_sha"] != metrics["snapshot_sha"]
                or identity["repository_commit_sha"] != opportunities["snapshot_sha"]
                or inventory["inventory_id"] != metrics["inventory_id"]
                or inventory["inventory_id"] != opportunities["inventory_id"]
                or metrics["metrics_id"] != opportunities["metrics_id"]
                or identity["role_policy_sha256"] != _digest(role_policy)
                or metrics["role_policy_sha256"] != _digest(role_policy)
                or inventory["inventory_id"] != _digest({
                    k: v for k, v in inventory.items() if k != "inventory_id"
                })
                or metrics["metrics_id"] != _digest({
                    k: v for k, v in metrics.items() if k != "metrics_id"
                })
                or opportunities["opportunities_id"] != _digest({
                    k: v for k, v in opportunities.items() if k != "opportunities_id"
                })
                or not isinstance(roles, dict)):
            raise ArchitecturePolicyTriageError("source/profile/report identity mismatch")
        pairs = metrics["resolved_pairs"]
        pair_index = {(p["source_path"], p["target_path"]): p for p in pairs}
        if len(pair_index) != len(pairs):
            raise ArchitecturePolicyTriageError("duplicate measured pair")
        exceptions = {
            (item["source"], item["target"])
            for item in role_policy["exceptions"]
            if item["status"] == "TRANSITIONAL_REVIEW"
        }
        if len(exceptions) != len(role_policy["exceptions"]):
            raise ArchitecturePolicyTriageError("untrusted exception policy")
        signal_triage = []
        for signal in opportunities["architecture_signals"]:
            if signal["family"] != "CROSS_BOUNDARY_CONCENTRATION":
                continue
            observed = signal["source_witnesses"]
            source_roles = {
                pair_index[(w["source_path"], w["target_path"])]["source_role"]
                for w in observed
            }
            if len(source_roles) != 1:
                raise ArchitecturePolicyTriageError("concentration has multiple source roles")
            source_role = next(iter(source_roles))
            outgoing = [
                p for p in pairs if p["source_role"] == source_role
                and p["source_role"] in roles and p["target_role"] in roles
            ]
            cross = [
                p for p in outgoing if p["source_role"] != p["target_role"]
            ]
            expected_witnesses = {
                _witness_key(w) for p in cross for w in p["witnesses"]
            }
            metric_witnesses = {
                _witness_key(w): w for p in cross for w in p["witnesses"]
            }
            if any(metric_witnesses.get(_witness_key(w)) != w
                   for w in observed):
                raise ArchitecturePolicyTriageError("forged or stale source witness")
            if (not cross
                    or signal["measurement"]["numerator"] != len(cross)
                    or signal["measurement"]["denominator"] != len(outgoing)
                    or abs(signal["measurement"]["ratio"]
                           - len(cross) / len(outgoing)) > 1e-12
                    or set(_witness_key(w) for w in observed) != expected_witnesses
                    or signal["scope_roles"] != sorted({
                        source_role, *(p["target_role"] for p in cross)
                    })):
                raise ArchitecturePolicyTriageError("concentration witness/denominator mismatch")
            entries = []
            for pair in sorted(cross, key=lambda p: (
                    p["source_path"], p["target_path"])):
                src, dst = pair["source_path"], pair["target_path"]
                target_role = pair["target_role"]
                if target_role in roles[source_role]["forbidden_imports"]:
                    policy_status = (
                        "DECLARED_TRANSITIONAL_REVIEW"
                        if (src, dst) in exceptions else "DECLARED_FORBIDDEN"
                    )
                else:
                    policy_status = "DECLARED_ALLOWED"
                entries.append({
                    "source_path": src,
                    "target_path": dst,
                    "source_role": source_role,
                    "target_role": target_role,
                    "declared_policy_direction": policy_status,
                    "source_witnesses": pair["witnesses"],
                    "semantic_ownership": "NOT_EVALUATED",
                    "external_consumers": "NOT_EVALUATED",
                })
            counts = Counter(e["declared_policy_direction"] for e in entries)
            signal_triage.append({
                "signal_id": signal["signal_id"],
                "source_role": source_role,
                "observed_cross_pairs": len(entries),
                "observed_outgoing_pairs": len(outgoing),
                "declared_policy_counts": dict(sorted(counts.items())),
                "pairs": entries,
            })
        result = {
            "schema_version": "0.1",
            "source_identity": {
                "snapshot_sha": identity["repository_commit_sha"],
                "inventory_id": inventory["inventory_id"],
                "metrics_id": metrics["metrics_id"],
                "opportunities_id": opportunities["opportunities_id"],
                "role_policy_sha256": identity["role_policy_sha256"],
            },
            "signal_triage": signal_triage,
            "semantic_ownership": "NOT_EVALUATED",
            "external_consumers": "NOT_EVALUATED",
            "decision": "NOT_EVALUATED",
            "limitations": [
                "DECLARED_ALLOWED is not proof of intentional composition",
                "static import pairs do not cover dynamic or external consumers",
                "no automatic relocation, KEEP verdict, or compatibility approval",
            ],
        }
        result["triage_id"] = _digest(result)
        return result
    except (KeyError, TypeError, AttributeError, ValueError, ZeroDivisionError) as exc:
        raise ArchitecturePolicyTriageError("untrustworthy architecture triage evidence") from exc


def render_policy_triage_markdown(triage: Mapping[str, Any]) -> str:
    """Render measured pairs without promoting declared allowance to PASS."""
    lines = [
        "## Cross-boundary declared-policy triage",
        "",
        "Declared permission is not semantic ownership or migration approval.",
        "Semantic ownership and external consumers: NOT_EVALUATED.",
    ]
    for item in triage["signal_triage"]:
        lines.extend([
            "",
            "- Source role `" + item["source_role"] + "`: "
            + str(item["observed_cross_pairs"]) + "/"
            + str(item["observed_outgoing_pairs"]) + " outgoing pairs cross roles.",
        ])
        for pair in item["pairs"]:
            for witness in pair["source_witnesses"]:
                lines.append(
                    "  - `" + witness["source_path"] + ":"
                    + str(witness["line"]) + "` -> `"
                    + witness["target_path"] + "` ("
                    + pair["declared_policy_direction"] + "; sha256="
                    + witness["source_sha256"] + ")"
                )
    if not triage["signal_triage"]:
        lines.extend(["", "No concentration signal; no policy triage entries."])
    return "\n".join(lines) + "\n"


def render_policy_candidate_decisions(
    triage: Mapping[str, Any], assessment: Mapping[str, Any],
) -> str:
    """Bind B7 candidate decisions to B3 concentration and B4 rejection evidence.

    KEEP here applies only to a rejected *mapping*, never to semantic ownership
    or the whole repository. No viable candidate is not proof of a good layout.
    """
    try:
        if (triage["triage_id"] != _digest({
                k: v for k, v in triage.items() if k != "triage_id"
            })
                or assessment["assessment_id"] != _digest({
                    k: v for k, v in assessment.items() if k != "assessment_id"
                })
                or assessment["mode"] != "DISCOVERY"
                or assessment["decision"] != "NOT_EVALUATED"
                or triage["decision"] != "NOT_EVALUATED"
                or triage["semantic_ownership"] != "NOT_EVALUATED"
                or triage["external_consumers"] != "NOT_EVALUATED"):
            raise ArchitecturePolicyTriageError("untrusted decision report")
        source = triage["source_identity"]
        expected = assessment["source_identity"]
        if (source["snapshot_sha"] != expected["snapshot_sha"]
                or source["inventory_id"] != expected["inventory_id"]
                or source["metrics_id"] != expected["metrics_id"]
                or source["role_policy_sha256"] != expected["role_policy_sha256"]
                or source["opportunities_id"] !=
                   assessment["analyzer_hashes"]["opportunities_id"]):
            raise ArchitecturePolicyTriageError("candidate source/profile drift")
        concentrations = {
            s["signal_id"] for s in assessment["architecture_signals"]
            if s["family"] == "CROSS_BOUNDARY_CONCENTRATION"
        }
        triaged = {s["signal_id"] for s in triage["signal_triage"]}
        if concentrations != triaged or len(triaged) != len(triage["signal_triage"]):
            raise ArchitecturePolicyTriageError("missing or duplicate concentration")
        questions = assessment["question_opportunities"]
        scenarios = assessment["scenario_assessments"]
        rejected = assessment["rejected_scenarios"]
        lines = [
            "## Source-bound concentration candidate decisions",
            "",
            "KEEP is only a disposition of a specific rejected mapping, not",
            "certification of the existing architecture. External consumers and",
            "semantic ownership: NOT_EVALUATED.",
        ]
        for signal in triage["signal_triage"]:
            sid = signal["signal_id"]
            if (signal["observed_cross_pairs"] != len(signal["pairs"])
                    or sum(signal["declared_policy_counts"].values()) !=
                       len(signal["pairs"])):
                raise ArchitecturePolicyTriageError("triage denominator mismatch")
            linked = [q for q in questions if sid in q["originating_signal_ids"]]
            if len(linked) != 1:
                raise ArchitecturePolicyTriageError("missing or ambiguous B7 question")
            qid = linked[0]["opportunity_id"]
            accepted = [s for s in scenarios if s["opportunity_id"] == qid]
            denied = [r for r in rejected if r["opportunity_id"] == qid]
            lines.extend([
                "",
                "- Signal " + sid + " (role `" + signal["source_role"] + "`): "
                + str(signal["observed_cross_pairs"]) + "/"
                + str(signal["observed_outgoing_pairs"]) + " cross-role pairs.",
            ])
            for candidate in accepted:
                decision = candidate["decision_evidence"]
                if decision["decision"] not in {
                    "KEEP", "PREFER", "REVIEW_REQUIRED", "INSUFFICIENT_EVIDENCE"
                }:
                    raise ArchitecturePolicyTriageError("unknown B7 verdict")
                lines.append(
                    "  - Compared scenario " + candidate["scenario_id"] + ": "
                    + decision["decision"] + "; matched denominators="
                    + str(decision["comparable"])
                    + "; migration risk=" + decision["migration_risk"]
                    + "; unknowns=" + ", ".join(decision["critical_unknowns"])
                )
            for denied_candidate in denied:
                reason = denied_candidate["reason"]
                if reason == "TARGET_COLLISION":
                    witnesses = denied_candidate.get("collision_witnesses", [])
                    if not witnesses:
                        raise ArchitecturePolicyTriageError("collision without source proof")
                    lines.append("  - KEEP rejected mapping only: TARGET_COLLISION.")
                    for witness in witnesses:
                        lines.append(
                            "    - " + witness["source_path"] + " -> "
                            + witness["proposed_target_path"]
                            + " (source_sha256=" + witness["source_sha256"] + ")"
                        )
                else:
                    lines.append(
                        "  - Rejected candidate (" + reason
                        + "); no compatibility or quality inference."
                    )
            if not accepted:
                lines.append(
                    "  - No viable measured alternative; no-move is the safe "
                    "current action, not a global KEEP/PASS verdict."
                )
            if signal["declared_policy_counts"].get("DECLARED_FORBIDDEN", 0):
                lines.append(
                    "  - REVIEW_REQUIRED: declared forbidden edges need "
                    "separate ownership/policy investigation."
                )
        if not triage["signal_triage"]:
            lines.append("- No concentration signal: zero questions is valid, not PASS.")
        lines.extend([
            "",
            "Actual relocation requires independent API/policy authorization,",
            "exact-head CI and same-scope post-change validation.",
            "",
        ])
        return "\n".join(lines)
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        raise ArchitecturePolicyTriageError(
            "untrustworthy concentration candidate evidence"
        ) from exc
