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
