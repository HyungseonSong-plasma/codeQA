"""B3 source-triggered architecture opportunities; no seeded questions or verdicts.

This pure evaluator consumes the exact B1/B2 reports, not source code or an LLM.
Signals are review hypotheses with explicit benign explanations, not defects.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from hashlib import sha256
import json
from typing import Any


class ArchitectureOpportunityError(ValueError):
    """Incompatible or internally contradictory architecture evidence."""


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def discover_architecture_opportunities(
    inventory: Mapping[str, Any],
    metrics: Mapping[str, Any],
    *,
    min_cross_role_pairs: int = 3,
    min_distinct_target_roles: int = 2,
    min_cross_share: float = 0.6,
) -> dict[str, Any]:
    """Mine bounded graph signals; a zero-opportunity result is valid.

    Thresholds trigger *questions*, never architecture-quality verdicts.
    External callers, dynamic imports and semantic ownership stay unverified.
    """
    if (not isinstance(inventory, Mapping) or not isinstance(metrics, Mapping)
            or type(min_cross_role_pairs) is not int or min_cross_role_pairs < 2
            or type(min_distinct_target_roles) is not int
            or min_distinct_target_roles < 2
            or not isinstance(min_cross_share, (int, float))
            or isinstance(min_cross_share, bool)
            or not 0 < min_cross_share <= 1):
        raise ArchitectureOpportunityError("invalid report or trigger configuration")
    try:
        identity = inventory["source_identity"]
        paths = {item["path"]: item for item in inventory["files"]}
        pairs = metrics["resolved_pairs"]
        modules = {item["path"]: item for item in metrics["modules"]}
        coverage = metrics["coverage"]
        if (inventory["schema_version"] != "0.1"
                or metrics["schema_version"] != "0.1"
                or inventory["inventory_id"] != _digest({
                    k: v for k, v in inventory.items() if k != "inventory_id"
                })
                or metrics["metrics_id"] != _digest({
                    k: v for k, v in metrics.items() if k != "metrics_id"
                })
                or identity["repository_commit_sha"] != metrics["snapshot_sha"]
                or inventory["inventory_id"] != metrics["inventory_id"]
                or identity["role_policy_sha256"] != metrics["role_policy_sha256"]
                or len(paths) != len(inventory["files"])
                or len(modules) != len(metrics["modules"])
                or metrics["denominators"]["resolved_distinct_pairs"] != len(pairs)
                or coverage["python_analyzed"] != len(modules)):
            raise ArchitectureOpportunityError("B1/B2 identity or denominator mismatch")
        pair_index = {}
        for pair in pairs:
            src, dst = pair["source_path"], pair["target_path"]
            if ((src, dst) in pair_index or src not in modules or dst not in modules
                    or pair["source_role"] != modules[src]["role"]
                    or pair["target_role"] != modules[dst]["role"]
                    or not pair["witnesses"]):
                raise ArchitectureOpportunityError("untrustworthy measured import pair")
            for w in pair["witnesses"]:
                if (w["source_path"] != src or w["target_path"] != dst
                        or src not in paths
                        or w["source_sha256"] != paths[src]["source_sha256"]
                        or type(w["line"]) is not int or w["line"] < 1):
                    raise ArchitectureOpportunityError("unbound source witness")
            pair_index[(src, dst)] = pair
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        raise ArchitectureOpportunityError("untrustworthy B1/B2 evidence") from exc

    unknowns = sorted(set([
        *coverage["unknown_by_reason"],
        "EXTERNAL_CONSUMERS_NOT_EVALUATED",
        "DYNAMIC_IMPORT_COMPLETENESS_NOT_EVALUATED",
        "SEMANTIC_RESPONSIBILITY_NOT_EVALUATED",
    ]))
    signals: list[dict[str, Any]] = []

    def emit(family: str, scope: list[str], numerator: int, denominator: int,
             witnesses: list[dict[str, Any]], rule: str,
             hypothesis: str, counterhypothesis: str) -> None:
        if not witnesses or denominator <= 0 or numerator <= 0:
            raise ArchitectureOpportunityError("signal must have measured source evidence")
        unique = {(w["source_path"], w["target_path"], w["line"]): w
                  for w in witnesses}
        observed = [unique[key] for key in sorted(unique)]
        sid = _digest({
            "snapshot": metrics["snapshot_sha"], "metrics": metrics["metrics_id"],
            "family": family, "scope": sorted(scope),
            "witness_sites": list(sorted(unique)), "rule": rule,
        })
        signals.append({
            "signal_id": sid,
            "family": family,
            "scope_roles": sorted(scope),
            "measurement": {
                "numerator": numerator, "denominator": denominator,
                "ratio": numerator / denominator,
            },
            "derivation_rule": rule,
            "source_witnesses": observed,
            "evidence_class": "PROXY_INFERENCE",
            "hypothesis": hypothesis,
            "benign_counterhypothesis": counterhypothesis,
            "unknowns": unknowns,
        })

    for cycle in metrics["cycles"]:
        witnesses = cycle["edge_witnesses"]
        if not witnesses or any(
            (w["source_path"], w["target_path"]) not in pair_index
            for w in witnesses
        ):
            raise ArchitectureOpportunityError("cycle has no bound import witnesses")
        roles = sorted({modules[path]["role"] for path in cycle["nodes"]})
        emit("STATIC_IMPORT_CYCLE", roles, 1, max(1, len(modules)), witnesses,
             "B3-CYCLE-v0.1: observed B2 closed SCC walk",
             "The static cycle may complicate independent ownership or initialization.",
             "The imports may be intentional or deferred; runtime effects are unverified.")

    for finding in metrics["declared_role_findings"]:
        if finding["status"] != "VIOLATION" or finding["code"] != "FORBIDDEN_ROLE_DEPENDENCY":
            continue
        key = (finding["source"], finding["target"])
        if key not in pair_index:
            raise ArchitectureOpportunityError("declared violation lacks an import witness")
        pair = pair_index[key]
        emit("DECLARED_BOUNDARY_CONFLICT",
             [pair["source_role"], pair["target_role"]], 1, len(pairs),
             pair["witnesses"],
             "B3-POLICY-v0.1: observed import contradicts declared role boundary",
             "The observed import crosses a declared forbidden ownership boundary.",
             "The policy may need an explicit reviewed exception or revision.")

    by_source_role: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for pair in pairs:
        if (pair["source_role"] not in {"UNCLASSIFIED", "OUT_OF_SCOPE"}
                and pair["target_role"] not in {"UNCLASSIFIED", "OUT_OF_SCOPE"}):
            by_source_role[pair["source_role"]].append(pair)
    for role, outgoing in sorted(by_source_role.items()):
        cross = [p for p in outgoing if p["source_role"] != p["target_role"]]
        destinations = {p["target_role"] for p in cross}
        if (len(cross) < min_cross_role_pairs
                or len(destinations) < min_distinct_target_roles
                or len(cross) / len(outgoing) < min_cross_share):
            continue
        emit("CROSS_BOUNDARY_CONCENTRATION", [role, *destinations],
             len(cross), len(outgoing),
             [w for p in cross for w in p["witnesses"]],
             "B3-CONCENTRATION-v0.1: cross-role pairs / all observed outgoing pairs",
             "Observed static imports span multiple declared responsibility boundaries.",
             "A stable composition layer or shared utility may legitimately import many roles.")

    signals.sort(key=lambda item: (item["family"], item["signal_id"]))
    opportunities = []
    for signal in signals:
        family = signal["family"]
        directions = (["KEEP", "INVESTIGATE_DEPENDENCY_DIRECTION"]
                      if family in {"STATIC_IMPORT_CYCLE", "DECLARED_BOUNDARY_CONFLICT"}
                      else ["KEEP", "INVESTIGATE_BOUNDARY_OR_COMPOSITION"])
        opportunities.append({
            "opportunity_id": _digest({"signal_ids": [signal["signal_id"]]}),
            "originating_signal_ids": [signal["signal_id"]],
            "affected_roles": signal["scope_roles"],
            "why_question_arises": signal["hypothesis"],
            "candidate_question": (
                "Would a different responsibility boundary or dependency direction "
                "reduce this observed structural pressure without breaking consumers?"
            ),
            "alternatives": directions,
            "source_witnesses": signal["source_witnesses"],
            "benign_counterhypothesis": signal["benign_counterhypothesis"],
            "unknowns": signal["unknowns"],
            "decision": "NOT_EVALUATED",
        })
    result = {
        "schema_version": "0.1",
        "snapshot_sha": metrics["snapshot_sha"],
        "inventory_id": inventory["inventory_id"],
        "metrics_id": metrics["metrics_id"],
        "derivation_id": "codeqa.architecture.opportunity-miner.v0.1",
        "thresholds": {
            "min_cross_role_pairs": min_cross_role_pairs,
            "min_distinct_target_roles": min_distinct_target_roles,
            "min_cross_share": min_cross_share,
        },
        "observation": "SIGNALS_OBSERVED" if signals else "NO_SIGNALS_OBSERVED",
        "evidence_status": (
            "INCOMPLETE" if metrics["status"] in {"INCOMPLETE", "NOT_EVALUATED"}
            or coverage["unknown_by_reason"] else "STATIC_ONLY"
        ),
        "coverage": coverage,
        "architecture_signals": signals,
        "question_opportunities": opportunities,
        "unknowns": unknowns,
        "limitations": [
            "no question seeded by names, paths or preselected target modules",
            "static import evidence cannot prove runtime behavior or semantic cohesion",
            "no migration, architecture verdict or public API compatibility proof",
            "thresholds trigger review hypotheses, not defect or PASS classifications",
        ],
    }
    result["opportunities_id"] = _digest(result)
    return result
