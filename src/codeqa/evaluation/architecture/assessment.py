"""B7 bounded, deterministic architecture decisions over immutable B1--B5 evidence.

Discovery never accepts a seeded question list. A path-only move cannot turn
unchanged import edges into a verified cohesion/coupling improvement.
"""
from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
import json
from typing import Any

from codeqa.evaluation.architecture.opportunities import discover_architecture_opportunities


class ArchitectureAssessmentError(ValueError):
    """Untrusted or contradictory architecture assessment inputs."""


OBJECTIVES = (
    "cross_boundary_pairs", "static_cycles", "reverse_change_surface",
    "interface_burden", "migration_sites",
)
IDENTITY = (
    "snapshot_sha", "inventory_id", "metrics_id",
    "role_policy_sha256", "dependency_profile_id",
)


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _authentic(report: Mapping[str, Any], key: str) -> bool:
    return report[key] == _digest({k: v for k, v in report.items() if k != key})


def compare_bounded_layouts(
    current: Mapping[str, int],
    candidate: Mapping[str, int],
    *,
    baseline_identity: Mapping[str, str],
    candidate_identity: Mapping[str, str],
    baseline_denominators: Mapping[str, int],
    candidate_denominators: Mapping[str, int],
    hard_violations: tuple[str, ...] = (),
    critical_unknowns: tuple[str, ...] = (),
    relationship_changes_verified: bool = False,
    ownership_disputed: bool = False,
    migration_risk: str = "NONE",
    material_delta: int = 1,
) -> dict[str, Any]:
    """Pareto compare five lower-is-better proxies; never return global PASS.

    Only independently verified changes in actual relationships can support a
    positive coupling/cohesion claim. A virtual file move is path-only.
    """
    if (not isinstance(current, Mapping) or not isinstance(candidate, Mapping)
            or not isinstance(baseline_identity, Mapping)
            or not isinstance(candidate_identity, Mapping)
            or not isinstance(baseline_denominators, Mapping)
            or not isinstance(candidate_denominators, Mapping)
            or migration_risk not in ("NONE", "MITIGATED", "LOW", "MEDIUM", "HIGH", "BLOCKED")
            # A truthy string or integer is not independent relationship proof.
            # Do not let malformed caller flags bypass the path-only review gate.
            or type(relationship_changes_verified) is not bool
            or type(ownership_disputed) is not bool
            or type(material_delta) is not int or material_delta < 1):
        raise ArchitectureAssessmentError("invalid comparison input")
    if any(type(v) is not str for v in (*hard_violations, *critical_unknowns)):
        raise ArchitectureAssessmentError("invalid constraint/unknown entry")
    reasons: list[str] = []
    comparable = (
        all(isinstance(baseline_identity.get(k), str) and baseline_identity.get(k)
            == candidate_identity.get(k) for k in IDENTITY)
        and baseline_denominators == candidate_denominators
        and bool(baseline_denominators)
        and all(type(v) is int and v >= 0 for v in baseline_denominators.values())
        and all(type(current.get(k)) is int and current[k] >= 0
                and type(candidate.get(k)) is int and candidate[k] >= 0
                for k in OBJECTIVES)
    )
    if not comparable:
        decision = "INSUFFICIENT_EVIDENCE"
        reasons.append("NONCOMPARABLE_SOURCE_PROFILE_DENOMINATORS_OR_METRICS")
        delta = {}
    else:
        delta = {k: candidate[k] - current[k] for k in OBJECTIVES}
        if hard_violations or migration_risk == "BLOCKED":
            decision = "KEEP"
            reasons.append("KNOWN_HARD_CONSTRAINT_VIOLATION")
        elif critical_unknowns:
            decision = "INSUFFICIENT_EVIDENCE"
            reasons.append("CRITICAL_COMPATIBILITY_OR_COVERAGE_UNKNOWN")
        elif ownership_disputed:
            decision = "REVIEW_REQUIRED"
            reasons.append("SEMANTIC_OWNERSHIP_DISPUTED")
        elif not relationship_changes_verified and any(
            delta[k] < 0 for k in ("cross_boundary_pairs", "static_cycles", "reverse_change_surface")
        ):
            # Do not count a path relabel as a physical graph improvement.
            if any(delta[k] > 0 for k in OBJECTIVES) or migration_risk not in ("NONE", "MITIGATED"):
                decision = "KEEP"
                reasons.append("PATH_ONLY_RELABELLING_WITH_MIGRATION_BURDEN")
            else:
                decision = "REVIEW_REQUIRED"
                reasons.append("PATH_ONLY_PROXY_IMPROVEMENT_UNVERIFIED")
        elif migration_risk in ("MEDIUM", "HIGH"):
            decision = "REVIEW_REQUIRED"
            reasons.append("MATERIAL_MIGRATION_RISK")
        elif all(v >= 0 for v in delta.values()):
            decision = "KEEP"
            reasons.append("BASELINE_WEAKLY_DOMINATES_OR_TIES")
        elif all(v <= 0 for v in delta.values()) and any(
            v <= -material_delta for v in delta.values()
        ):
            decision = "PREFER"
            reasons.append("CANDIDATE_PARETO_DOMINATES_PROVISIONALLY")
        else:
            decision = "REVIEW_REQUIRED"
            reasons.append("CONFLICTING_OR_IMMATERIAL_PROXY_CHANGES")
    return {
        "decision": decision,
        "reasons": reasons,
        "comparable": comparable,
        "metric_delta": delta,
        "hard_violations": sorted(set(hard_violations)),
        "critical_unknowns": sorted(set(critical_unknowns)),
        "relationship_changes_verified": relationship_changes_verified,
        "migration_risk": migration_risk,
        "evidence_class": "PROXY_INFERENCE",
        "human_review_question": (
            "Which responsibility and compatibility evidence resolves this trade-off?"
            if decision == "REVIEW_REQUIRED" else None
        ),
        "limitations": [
            "provisional proxy comparison is not semantic or runtime certification",
            "PREFER never authorizes an automatic source move",
        ],
    }


def assemble_architecture_advisory(
    inventory: Mapping[str, Any],
    metrics: Mapping[str, Any],
    opportunities: Mapping[str, Any],
    scenarios: Mapping[str, Any],
    migration: Mapping[str, Any],
    *,
    adapter_boundaries: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble evidence-first discovery, then compare only B3-triggered B4 candidates.

    The caller must independently authenticate the exact-head B1--B5 inputs.
    This function additionally verifies digests, identities and B3 derivation.
    It does not read source, invent missing candidates or certify external APIs.
    """
    try:
        if not all(isinstance(x, Mapping) for x in (
            inventory, metrics, opportunities, scenarios, migration
        )):
            raise ArchitectureAssessmentError("reports must be mappings")
        source = inventory["source_identity"]
        sha = source["repository_commit_sha"]
        if (not _authentic(inventory, "inventory_id")
                or not _authentic(metrics, "metrics_id")
                or not _authentic(opportunities, "opportunities_id")
                or not _authentic(scenarios, "scenarios_id")
                or not _authentic(migration, "migration_id")
                or any(r["schema_version"] != "0.1" for r in (
                    inventory, metrics, opportunities, scenarios, migration
                ))
                or any(r["snapshot_sha"] != sha for r in (
                    metrics, opportunities, scenarios, migration
                ))
                or any(r["inventory_id"] != inventory["inventory_id"] for r in (
                    metrics, opportunities, scenarios, migration
                ))
                or opportunities["metrics_id"] != metrics["metrics_id"]
                or scenarios["metrics_id"] != metrics["metrics_id"]
                or scenarios["opportunities_id"] != opportunities["opportunities_id"]
                or migration["scenarios_id"] != scenarios["scenarios_id"]
                or scenarios["role_policy_sha256"] != source["role_policy_sha256"]
                or scenarios["dependency_profile_id"] != metrics["dependency_profile_id"]
                or discover_architecture_opportunities(
                    inventory, metrics, **opportunities["thresholds"]
                ) != opportunities):
            raise ArchitectureAssessmentError("B1--B5 provenance/derivation mismatch")
        questions = {q["opportunity_id"]: q for q in opportunities["question_opportunities"]}
        signals = {s["signal_id"]: s for s in opportunities["architecture_signals"]}
        if (len(questions) != len(opportunities["question_opportunities"])
                or len(signals) != len(opportunities["architecture_signals"])
                or any(not q["originating_signal_ids"] or
                       not set(q["originating_signal_ids"]) <= signals.keys()
                       for q in questions.values())):
            raise ArchitectureAssessmentError("orphan/duplicate question or signal")
        by_migration = {c["scenario_id"]: c for c in migration["candidates"]}
        by_scenario = {c["scenario_id"]: c for c in scenarios["candidates"]}
        if set(by_migration) != set(by_scenario) or len(by_migration) != len(migration["candidates"]):
            raise ArchitectureAssessmentError("B4/B5 candidate set mismatch")
        if any(c["opportunity_id"] not in questions for c in by_scenario.values()):
            raise ArchitectureAssessmentError("candidate without discovered question")
        if migration["rejected_scenarios"] != scenarios["rejected"]:
            raise ArchitectureAssessmentError("rejected candidate mismatch")
        if metrics["denominators"]["resolved_distinct_pairs"] != len(metrics["resolved_pairs"]):
            raise ArchitectureAssessmentError("static edge denominator mismatch")
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise ArchitectureAssessmentError("untrustworthy B1--B5 architecture evidence") from exc

    # B6 can contribute independently measured language-family pressure. Its
    # generic evidence is not a preselected architecture question or a move.
    adapter_signals: list[dict[str, Any]] = []
    adapter_questions: list[dict[str, Any]] = []
    if adapter_boundaries is not None:
        try:
            if (not isinstance(adapter_boundaries, Mapping)
                    or not _authentic(adapter_boundaries, "boundary_id")
                    or adapter_boundaries["schema_version"] != "0.1"
                    or adapter_boundaries["snapshot_sha"] != sha
                    or adapter_boundaries["inventory_id"] != inventory["inventory_id"]
                    or adapter_boundaries["metrics_id"] != metrics["metrics_id"]
                    or adapter_boundaries["decision"] != "NOT_EVALUATED"):
                raise ArchitectureAssessmentError("B6 provenance mismatch")
            source_files = {f["path"]: f for f in inventory["files"]}
            observed_adapter_ids: set[str] = set()
            for signal in adapter_boundaries["architecture_signals"]:
                sid = signal["signal_id"]
                witnesses = signal["source_witnesses"]
                if (sid in signals or sid in observed_adapter_ids or not witnesses
                        or any(w["source_path"] not in source_files
                               or w["source_sha256"] !=
                               source_files[w["source_path"]]["source_sha256"]
                               or type(w["line"]) is not int or w["line"] < 1
                               for w in witnesses)):
                    raise ArchitectureAssessmentError("unbound B6 adapter signal")
                observed_adapter_ids.add(sid)
                normalized = {
                    "signal_id": sid, "family": signal["family"],
                    "scope_roles": [adapter_boundaries["adapter_scope"]],
                    "measurement": signal["measurement"],
                    "derivation_rule": signal["derivation_rule"],
                    "source_witnesses": witnesses,
                    "evidence_class": "PROXY_INFERENCE",
                    "hypothesis": "Observed cross-family static imports may warrant a boundary review.",
                    "benign_counterhypothesis": signal["benign_counterhypothesis"],
                    "unknowns": adapter_boundaries["unknowns"],
                }
                qid = _digest({"signal_ids": [sid]})
                if qid in questions:
                    raise ArchitectureAssessmentError("duplicate B3/B6 opportunity")
                adapter_signals.append(normalized)
                adapter_questions.append({
                    "opportunity_id": qid,
                    "originating_signal_ids": [sid],
                    "affected_roles": [adapter_boundaries["adapter_scope"]],
                    "why_question_arises": normalized["hypothesis"],
                    "candidate_question": (
                        "Would a different declared language-family boundary reduce "
                        "observed cross-family import pressure without breaking consumers?"
                    ),
                    "alternatives": [c["layout"] for c in adapter_boundaries["candidates"]],
                    "source_witnesses": witnesses,
                    "benign_counterhypothesis": signal["benign_counterhypothesis"],
                    "unknowns": adapter_boundaries["unknowns"],
                    "decision": "NOT_EVALUATED",
                })
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise ArchitectureAssessmentError("untrustworthy B6 boundary evidence") from exc

    reverse_surface = sum(
        g["reverse_import_impact"]["potential_dependents"]
        for g in metrics["groups"] if g["reverse_import_impact"] is not None
    )
    baseline = {
        "cross_boundary_pairs": metrics["denominators"]["cross_declared_pairs"],
        "static_cycles": len(metrics["cycles"]),
        "reverse_change_surface": reverse_surface,
        "interface_burden": 0,
        "migration_sites": 0,
    }
    identity = {
        "snapshot_sha": sha,
        "inventory_id": inventory["inventory_id"],
        "metrics_id": metrics["metrics_id"],
        "role_policy_sha256": source["role_policy_sha256"],
        "dependency_profile_id": metrics["dependency_profile_id"],
    }
    denominators = {
        "tracked_files": len(inventory["files"]),
        "analyzed_modules": len(metrics["modules"]),
        "resolved_pairs": len(metrics["resolved_pairs"]),
    }
    assessments = []
    for sid, scenario in sorted(by_scenario.items()):
        impact = by_migration[sid]
        change = scenario["measured_proxy_delta"]
        candidate = {
            **baseline,
            "cross_boundary_pairs": baseline["cross_boundary_pairs"] + change["cross_declared_pairs"],
            "static_cycles": baseline["static_cycles"] + change["static_cycles"],
            "interface_burden": impact["moved_file_count"],
            "migration_sites": impact["observed_site_count"],
        }
        unknowns = sorted(set([
            *impact["unknowns"],
            *scenario["unknowns"],
            *opportunities["unknowns"],
        ]))
        constraints = tuple(
            ["DOTTED_MODULE_NAMESPACE_COLLISION"] if impact["namespace_collisions"] else []
        )
        decision = compare_bounded_layouts(
            baseline, candidate, baseline_identity=identity, candidate_identity=identity,
            baseline_denominators=denominators, candidate_denominators=denominators,
            hard_violations=constraints, critical_unknowns=tuple(unknowns),
            relationship_changes_verified=False, migration_risk=impact["cost_band"],
        )
        assessments.append({
            "scenario_id": sid, "opportunity_id": scenario["opportunity_id"],
            "originating_signal_ids": scenario["originating_signal_ids"],
            "baseline": baseline, "candidate": candidate, "denominators": denominators,
            "migration_id": migration["migration_id"], "decision_evidence": decision,
            "source_witnesses": questions[scenario["opportunity_id"]]["source_witnesses"],
            "counterhypothesis": questions[scenario["opportunity_id"]]["benign_counterhypothesis"],
        })
    result = {
        "schema_version": "0.1",
        "mode": "DISCOVERY",
        "source_identity": identity,
        "analyzer_hashes": {
            "inventory_id": inventory["inventory_id"], "metrics_id": metrics["metrics_id"],
            "opportunities_id": opportunities["opportunities_id"],
            "scenarios_id": scenarios["scenarios_id"], "migration_id": migration["migration_id"],
            "adapter_boundary_id": (adapter_boundaries["boundary_id"]
                                    if adapter_boundaries is not None else None),
        },
        "coverage": metrics["coverage"],
        "architecture_signals": opportunities["architecture_signals"] + adapter_signals,
        "question_opportunities": opportunities["question_opportunities"] + adapter_questions,
        "scenario_assessments": assessments,
        "rejected_scenarios": scenarios["rejected"],
        "unknowns": sorted(set([*opportunities["unknowns"], *(
            "NO_VIABLE_VIRTUAL_CANDIDATE" for _ in scenarios["rejected"]
        ), *(adapter_boundaries["unknowns"] if adapter_boundaries is not None else [])])),
        "provenance": {
            "snapshot_sha": sha, "derivation": "B3/B6 independent signals; B4 virtual paths; B5 static impact",
            "evidence_classes": [
                "OBSERVED", "DECLARED_POLICY", "PROXY_INFERENCE", "HUMAN_REVIEW"
            ],
        },
        "reviewer_decisions": [],
        "decision": "NOT_EVALUATED",
        "limitations": [
            "no preseeded architecture questions; zero opportunities is valid",
            "virtual moves cannot prove semantic cohesion or physical graph improvements",
            "external consumers, dynamic imports and runtime compatibility unverified",
            "real migrations require separate approval, exact-head tests and post-change comparison",
        ],
    }
    result["assessment_id"] = _digest(result)
    return result


def assess_explicit_question(
    question: str,
    current: Mapping[str, int],
    candidate: Mapping[str, int],
    **comparison_evidence: Any,
) -> dict[str, Any]:
    """Separate explicit-request path; never contributes to discovery recall."""
    if not isinstance(question, str) or not question.strip():
        raise ArchitectureAssessmentError("nonempty explicit question required")
    return {
        "schema_version": "0.1", "mode": "EXPLICIT_QUESTION",
        "user_question": question.strip(),
        "comparison": compare_bounded_layouts(
            current, candidate, **comparison_evidence
        ),
        "discovery_coverage_claim": "NOT_EVALUATED",
    }
