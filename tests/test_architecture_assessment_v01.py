"""B7 Pareto decision and source-derived advisory adversarial controls."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator

from codeqa.evaluation.architecture.assessment import (
    ArchitectureAssessmentError, assemble_architecture_advisory,
    assess_explicit_question, compare_bounded_layouts,
)
from codeqa.evaluation.architecture.scenarios import generate_virtual_layout_scenarios
from codeqa.evaluation.architecture.migration import assess_architecture_migration
from test_architecture_scenarios_v01 import reports, CONCENTRATED, SOURCES, POLICY, PROFILE, SHA
from codeqa.core.dependency import DependencyGraph, StaticDependency
from codeqa.evaluation.architecture.inventory import analyze_architecture_inventory
from codeqa.evaluation.architecture.metrics import analyze_architecture_metrics
from codeqa.evaluation.architecture.opportunities import discover_architecture_opportunities


ROOT = Path(__file__).resolve().parents[1]
IDENTITY = dict(snapshot_sha="a" * 40, inventory_id="b" * 64,
                metrics_id="c" * 64, role_policy_sha256="d" * 64,
                dependency_profile_id="test-profile")
DENOMINATORS = {"tracked_files": 12, "resolved_pairs": 6}
BASE = {
    "cross_boundary_pairs": 6, "static_cycles": 2,
    "reverse_change_surface": 8, "interface_burden": 0,
    "migration_sites": 0,
}


def compare(changes=None, **kwargs):
    proposed = {**BASE, **(changes or {})}
    return compare_bounded_layouts(
        BASE, proposed, baseline_identity=IDENTITY,
        candidate_identity=IDENTITY, baseline_denominators=DENOMINATORS,
        candidate_denominators=DENOMINATORS, **kwargs,
    )


def assembled(edges=CONCENTRATED, *, sources=None):
    inv, metrics, opportunities, policy = reports(sources=sources, edges=edges)
    scenarios = generate_virtual_layout_scenarios(inv, metrics, opportunities, policy)
    migration = assess_architecture_migration(inv, scenarios, sources or SOURCES)
    return assemble_architecture_advisory(inv, metrics, opportunities, scenarios, migration)


class ArchitectureDecisionTests(unittest.TestCase):
    def test_pareto_dominating_candidate_requires_verified_relationship_change(self):
        result = compare({"cross_boundary_pairs": 4, "static_cycles": 1},
                         relationship_changes_verified=True)
        self.assertEqual(result["decision"], "PREFER")
        self.assertEqual(result["metric_delta"]["cross_boundary_pairs"], -2)
        self.assertEqual(result["evidence_class"], "PROXY_INFERENCE")

    def test_dominated_and_tie_with_move_cost_keep(self):
        self.assertEqual(compare({"cross_boundary_pairs": 8},
                                 relationship_changes_verified=True)["decision"], "KEEP")
        self.assertEqual(compare({"migration_sites": 1},
                                 relationship_changes_verified=True)["decision"], "KEEP")
        self.assertEqual(compare()["decision"], "KEEP")

    def test_conflicting_and_immaterial_changes_require_review(self):
        self.assertEqual(compare({"cross_boundary_pairs": 4, "migration_sites": 3},
                                 relationship_changes_verified=True)["decision"],
                         "REVIEW_REQUIRED")
        self.assertEqual(compare({"cross_boundary_pairs": 5},
                                 relationship_changes_verified=True,
                                 material_delta=2)["decision"], "REVIEW_REQUIRED")

    def test_known_hard_violation_blocks_even_if_metrics_improve(self):
        result = compare({"cross_boundary_pairs": 0},
                         relationship_changes_verified=True,
                         hard_violations=("FORBIDDEN_ROLE_DEPENDENCY",))
        self.assertEqual(result["decision"], "KEEP")
        self.assertIn("KNOWN_HARD_CONSTRAINT_VIOLATION", result["reasons"])

    def test_critical_unknown_blocks_strong_preference(self):
        result = compare({"cross_boundary_pairs": 0},
                         relationship_changes_verified=True,
                         critical_unknowns=("EXTERNAL_CONSUMERS_NOT_EVALUATED",))
        self.assertEqual(result["decision"], "INSUFFICIENT_EVIDENCE")
        self.assertEqual(compare({"cross_boundary_pairs": 0},
                                 relationship_changes_verified=True,
                                 migration_risk="HIGH")["decision"], "REVIEW_REQUIRED")

    def test_path_only_relabel_does_not_claim_coupling_improvement(self):
        result = compare({"cross_boundary_pairs": 2, "migration_sites": 3},
                         relationship_changes_verified=False)
        self.assertEqual(result["decision"], "KEEP")
        self.assertIn("PATH_ONLY_RELABELLING_WITH_MIGRATION_BURDEN",
                      result["reasons"])
        self.assertEqual(compare({"cross_boundary_pairs": 2})["decision"],
                         "REVIEW_REQUIRED")

    def test_untyped_relationship_evidence_cannot_promote_preference(self):
        # Without independent verification, a path-only proxy gain needs
        # review. A truthy string/int must not silently become proof.
        self.assertEqual(
            compare({"cross_boundary_pairs": 4})["decision"], "REVIEW_REQUIRED"
        )
        for untrusted in ("verified", 1, None, [], {"checked": True}):
            with self.subTest(untrusted=repr(untrusted)):
                with self.assertRaises(ArchitectureAssessmentError):
                    compare(
                        {"cross_boundary_pairs": 4},
                        relationship_changes_verified=untrusted,
                    )
        self.assertEqual(
            compare({"cross_boundary_pairs": 4},
                    relationship_changes_verified=True)["decision"], "PREFER"
        )

    def test_untyped_ownership_dispute_is_not_silently_accepted(self):
        # In particular, 0/None previously suppressed the review gate.
        for untrusted in ("false", 0, None, [], {}):
            with self.subTest(untrusted=repr(untrusted)):
                with self.assertRaises(ArchitectureAssessmentError):
                    compare(
                        {"cross_boundary_pairs": 4},
                        relationship_changes_verified=True,
                        ownership_disputed=untrusted,
                    )
        self.assertEqual(
            compare({"cross_boundary_pairs": 4},
                    relationship_changes_verified=True,
                    ownership_disputed=True)["decision"], "REVIEW_REQUIRED"
        )

    def test_numeric_lookalike_denominators_cannot_promote_preference(self):
        # Bool and float compare equal to int in Python, but are not measured
        # source counts. The two compared evidence sets must be exactly typed.
        counts = {"tracked_files": 1, "resolved_pairs": 0}
        invalid = (
            {"tracked_files": True, "resolved_pairs": False},
            {"tracked_files": 1.0, "resolved_pairs": 0.0},
        )
        for proposed in invalid:
            for baseline, candidate in ((counts, proposed), (proposed, counts)):
                with self.subTest(baseline=baseline, candidate=candidate):
                    result = compare_bounded_layouts(
                        BASE, {**BASE, "cross_boundary_pairs": 0},
                        baseline_identity=IDENTITY, candidate_identity=IDENTITY,
                        baseline_denominators=baseline,
                        candidate_denominators=candidate,
                        relationship_changes_verified=True,
                    )
                    self.assertEqual(result["decision"], "INSUFFICIENT_EVIDENCE")
                    self.assertFalse(result["comparable"])
                    self.assertEqual(result["metric_delta"], {})
        valid = compare_bounded_layouts(
            BASE, {**BASE, "cross_boundary_pairs": 0},
            baseline_identity=IDENTITY, candidate_identity=IDENTITY,
            baseline_denominators=counts, candidate_denominators=dict(counts),
            relationship_changes_verified=True,
        )
        self.assertEqual(valid["decision"], "PREFER")

    def test_constraint_and_unknown_evidence_require_typed_nonempty_tuples(self):
        for field in ("hard_violations", "critical_unknowns"):
            for invalid in ("TARGET_COLLISION", ["TARGET_COLLISION"],
                            ("",), ("  ",), (True,), None):
                with self.subTest(field=field, invalid=repr(invalid)):
                    with self.assertRaises(ArchitectureAssessmentError):
                        compare({"cross_boundary_pairs": 0},
                                relationship_changes_verified=True,
                                **{field: invalid})
        self.assertEqual(
            compare({"cross_boundary_pairs": 0},
                    relationship_changes_verified=True,
                    hard_violations=("TARGET_COLLISION",))["decision"], "KEEP"
        )
        self.assertEqual(
            compare({"cross_boundary_pairs": 0},
                    relationship_changes_verified=True,
                    critical_unknowns=("EXTERNAL_CONSUMERS_NOT_EVALUATED",)
                    )["decision"], "INSUFFICIENT_EVIDENCE"
        )

    def test_missing_or_inconsistent_source_denominators_fail_closed(self):
        other = {**IDENTITY, "snapshot_sha": "f" * 40}
        result = compare_bounded_layouts(
            BASE, BASE, baseline_identity=IDENTITY,
            candidate_identity=other, baseline_denominators=DENOMINATORS,
            candidate_denominators=DENOMINATORS,
        )
        self.assertEqual(result["decision"], "INSUFFICIENT_EVIDENCE")
        result = compare_bounded_layouts(
            BASE, BASE, baseline_identity=IDENTITY,
            candidate_identity=IDENTITY, baseline_denominators=DENOMINATORS,
            candidate_denominators={"tracked_files": 13, "resolved_pairs": 6},
        )
        self.assertEqual(result["decision"], "INSUFFICIENT_EVIDENCE")

    def test_disputed_semantic_ownership_is_not_machine_certified(self):
        self.assertEqual(compare({"cross_boundary_pairs": 1},
                                 relationship_changes_verified=True,
                                 ownership_disputed=True)["decision"], "REVIEW_REQUIRED")

    def test_healthy_no_question_no_forced_split(self):
        result = assembled(edges=())
        self.assertEqual(result["mode"], "DISCOVERY")
        self.assertEqual(result["architecture_signals"], [])
        self.assertEqual(result["question_opportunities"], [])
        self.assertEqual(result["scenario_assessments"], [])
        self.assertEqual(result["decision"], "NOT_EVALUATED")
        self.assertNotIn("PASS", result["decision"])

    def test_discovery_witnesses_and_unverified_move(self):
        result = assembled()
        self.assertGreater(len(result["question_opportunities"]), 0)
        self.assertEqual(len(result["scenario_assessments"]), 1)
        item = result["scenario_assessments"][0]
        self.assertTrue(item["originating_signal_ids"])
        self.assertTrue(item["source_witnesses"])
        self.assertEqual(item["decision_evidence"]["decision"], "INSUFFICIENT_EVIDENCE")
        self.assertIn("EXTERNAL_CONSUMERS_UNOBSERVED",
                      item["decision_evidence"]["critical_unknowns"])
        self.assertFalse(item["decision_evidence"]["relationship_changes_verified"])

    def test_source_tamper_or_orphan_question_rejected(self):
        inv, metrics, opportunities, policy = reports(edges=CONCENTRATED)
        scenarios = generate_virtual_layout_scenarios(inv, metrics, opportunities, policy)
        migration = assess_architecture_migration(inv, scenarios, SOURCES)
        tampered = deepcopy(opportunities)
        tampered["question_opportunities"][0]["originating_signal_ids"] = ["f" * 64]
        with self.assertRaises(ArchitectureAssessmentError):
            assemble_architecture_advisory(inv, metrics, tampered, scenarios, migration)
        changed = deepcopy(migration)
        changed["snapshot_sha"] = "0" * 40
        with self.assertRaises(ArchitectureAssessmentError):
            assemble_architecture_advisory(inv, metrics, opportunities, scenarios, changed)

    def test_explicit_request_does_not_contaminate_discovery(self):
        result = assess_explicit_question(
            "Should this boundary change?", BASE, BASE,
            baseline_identity=IDENTITY, candidate_identity=IDENTITY,
            baseline_denominators=DENOMINATORS,
            candidate_denominators=DENOMINATORS,
        )
        self.assertEqual(result["mode"], "EXPLICIT_QUESTION")
        self.assertEqual(result["discovery_coverage_claim"], "NOT_EVALUATED")
        self.assertNotIn("question_opportunities", result)

    def test_renamed_isomorphic_package_keeps_same_decision_class(self):
        renamed = {
            p.replace("orchard", "woodland"): v.replace("orchard", "woodland")
            for p, v in SOURCES.items()
        }
        policy = deepcopy(POLICY)
        policy["scope"] = "src/woodland"
        edges = tuple(StaticDependency(
            e.source_path.replace("orchard", "woodland"),
            e.target_path.replace("orchard", "woodland"),
            e.line, e.expression.replace("orchard", "woodland"), e.execution,
        ) for e in CONCENTRATED)
        inventory = analyze_architecture_inventory(SHA, renamed, renamed, policy)
        graph = DependencyGraph(SHA, tuple(sorted(renamed)), (), edges, ())
        metrics = analyze_architecture_metrics(inventory, graph, policy, PROFILE)
        opportunities = discover_architecture_opportunities(inventory, metrics)
        scenarios = generate_virtual_layout_scenarios(
            inventory, metrics, opportunities, policy
        )
        migration = assess_architecture_migration(inventory, scenarios, renamed)
        other = assemble_architecture_advisory(
            inventory, metrics, opportunities, scenarios, migration
        )
        original = assembled()
        self.assertEqual(len(other["question_opportunities"]),
                         len(original["question_opportunities"]))
        self.assertEqual([x["decision_evidence"]["decision"]
                          for x in other["scenario_assessments"]],
                         [x["decision_evidence"]["decision"]
                          for x in original["scenario_assessments"]])

    def test_deceptive_filename_does_not_force_semantic_ownership(self):
        sources = {**SOURCES,
                   "src/orchard/earth/model.py": "class NamingAdapter: pass\n"}
        report = assembled(sources=sources)
        original = assembled()
        self.assertEqual(len(report["question_opportunities"]),
                         len(original["question_opportunities"]))
        self.assertTrue(all(
            item["decision_evidence"]["decision"] != "PREFER"
            for item in report["scenario_assessments"]
        ))

    def test_b6_language_family_pressure_becomes_unseeded_question(self):
        from test_architecture_adapter_boundaries_v01 import (
            reports as family_reports, declaration, edge,
            POLICY as FAMILY_POLICY, SOURCES as FAMILY_SOURCES,
        )
        from codeqa.evaluation.architecture.adapter_boundaries import assess_adapter_boundaries
        inv, metrics = family_reports((edge("a", "b"), edge("a", "c")))
        opportunities = discover_architecture_opportunities(inv, metrics)
        self.assertEqual(opportunities["question_opportunities"], [])
        scenarios = generate_virtual_layout_scenarios(
            inv, metrics, opportunities, FAMILY_POLICY
        )
        migration = assess_architecture_migration(inv, scenarios, FAMILY_SOURCES)
        b6 = assess_adapter_boundaries(inv, metrics, declaration())
        result = assemble_architecture_advisory(
            inv, metrics, opportunities, scenarios, migration,
            adapter_boundaries=b6,
        )
        self.assertEqual(len(result["question_opportunities"]), 1)
        self.assertEqual(len(result["architecture_signals"]), 1)
        self.assertEqual(result["scenario_assessments"], [])
        self.assertEqual(result["question_opportunities"][0]["originating_signal_ids"],
                         [b6["architecture_signals"][0]["signal_id"]])
        self.assertIn("KEEP", result["question_opportunities"][0]["alternatives"])
        self.assertIn("EXTERNAL_CONSUMERS_NOT_EVALUATED", result["unknowns"])
        self.assertEqual(result["analyzer_hashes"]["adapter_boundary_id"],
                         b6["boundary_id"])
        renamed = declaration()
        renamed["families"][0]["family"] = "quartz"
        renamed["families"][1]["family"] = "moss"
        changed = assess_adapter_boundaries(inv, metrics, renamed)
        other = assemble_architecture_advisory(
            inv, metrics, opportunities, scenarios, migration,
            adapter_boundaries=changed,
        )
        self.assertEqual(result["question_opportunities"],
                         other["question_opportunities"])

    def test_healthy_adapter_family_does_not_invent_question(self):
        from test_architecture_adapter_boundaries_v01 import (
            reports as family_reports, declaration,
            POLICY as FAMILY_POLICY, SOURCES as FAMILY_SOURCES,
        )
        from codeqa.evaluation.architecture.adapter_boundaries import assess_adapter_boundaries
        inv, metrics = family_reports()
        opportunities = discover_architecture_opportunities(inv, metrics)
        scenarios = generate_virtual_layout_scenarios(
            inv, metrics, opportunities, FAMILY_POLICY
        )
        migration = assess_architecture_migration(inv, scenarios, FAMILY_SOURCES)
        b6 = assess_adapter_boundaries(inv, metrics, declaration())
        result = assemble_architecture_advisory(
            inv, metrics, opportunities, scenarios, migration,
            adapter_boundaries=b6,
        )
        self.assertEqual(result["question_opportunities"], [])
        self.assertEqual(result["architecture_signals"], [])

    def test_determinism_and_json_schema(self):
        result = assembled()
        self.assertEqual(result, assembled())
        self.assertEqual(result["assessment_id"], sha256(json.dumps(
            {k: v for k, v in result.items() if k != "assessment_id"},
            sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest())
        schema = json.loads((ROOT / "contracts/qa/architecture-assessment-v0.1.schema.json").read_text())
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(result)


if __name__ == "__main__":
    unittest.main()
