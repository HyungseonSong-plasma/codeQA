"""#184: source-bound policy direction is not a semantic ownership verdict."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import unittest

from codeqa.adapters.python_dependencies import extract_python_dependencies
from codeqa.evaluation.architecture.inventory import analyze_architecture_inventory
from codeqa.evaluation.architecture.metrics import analyze_architecture_metrics
from codeqa.evaluation.architecture.opportunities import discover_architecture_opportunities
from codeqa.evaluation.architecture.assessment import assemble_architecture_advisory
from codeqa.evaluation.architecture.migration import assess_architecture_migration
from codeqa.evaluation.architecture.scenarios import generate_virtual_layout_scenarios
from codeqa.evaluation.architecture.policy_triage import (
    ArchitecturePolicyTriageError,
    render_policy_triage_markdown,
    render_policy_candidate_decisions,
    triage_cross_role_concentration,
)
from codeqa.infrastructure.git import GitReader
from test_architecture_opportunities_v01 import (
    POLICY, PROFILE, SOURCES, edge, make_report,
)


ROOT = Path(__file__).resolve().parents[1]
CONCENTRATED = (
    edge("sky/view", "earth/model"),
    edge("sky/helper", "earth/model"),
    edge("sky/view", "rain/flow"),
    edge("sky/view", "sky/helper"),
)


def reports(*, edges=CONCENTRATED, policy=None):
    policy = POLICY if policy is None else policy
    inventory, metrics = make_report(edges=edges, policy=policy)
    opportunities = discover_architecture_opportunities(inventory, metrics)
    return inventory, metrics, opportunities, policy


class ArchitecturePolicyTriageTests(unittest.TestCase):
    def test_healthy_zero_signal_is_empty_and_not_pass(self):
        triage = triage_cross_role_concentration(*reports(edges=()))
        self.assertEqual(triage["signal_triage"], [])
        self.assertEqual(triage["decision"], "NOT_EVALUATED")
        self.assertIn("No concentration signal", render_policy_triage_markdown(triage))

    def test_allowed_cross_role_edges_are_not_semantic_approval(self):
        triage = triage_cross_role_concentration(*reports())
        self.assertEqual(len(triage["signal_triage"]), 1)
        signal = triage["signal_triage"][0]
        self.assertEqual(signal["observed_cross_pairs"], 3)
        self.assertEqual(signal["observed_outgoing_pairs"], 4)
        self.assertEqual(signal["declared_policy_counts"], {"DECLARED_ALLOWED": 3})
        self.assertTrue(all(
            item["semantic_ownership"] == "NOT_EVALUATED"
            and item["external_consumers"] == "NOT_EVALUATED"
            and item["source_witnesses"]
            for item in signal["pairs"]
        ))
        rendered = render_policy_triage_markdown(triage)
        self.assertIn("src/orchard/sky/view.py:1", rendered)
        self.assertIn("DECLARED_ALLOWED", rendered)
        self.assertIn("sha256=", rendered)
        self.assertIn("not semantic ownership", rendered)

    def test_forbidden_and_transitional_directions_are_distinguished(self):
        policy = deepcopy(POLICY)
        policy["roles"]["sky"]["forbidden_imports"] = ["earth"]
        triage = triage_cross_role_concentration(*reports(policy=policy))
        self.assertEqual(triage["signal_triage"][0]["declared_policy_counts"], {
            "DECLARED_ALLOWED": 1, "DECLARED_FORBIDDEN": 2,
        })
        policy["exceptions"] = [{
            "source": "src/orchard/sky/view.py",
            "target": "src/orchard/earth/model.py",
            "status": "TRANSITIONAL_REVIEW",
            "rationale": "temporary reviewed dependency",
        }]
        triage = triage_cross_role_concentration(*reports(policy=policy))
        self.assertEqual(triage["signal_triage"][0]["declared_policy_counts"], {
            "DECLARED_ALLOWED": 1,
            "DECLARED_FORBIDDEN": 1,
            "DECLARED_TRANSITIONAL_REVIEW": 1,
        })

    def test_stale_policy_and_resealed_signal_tampering_fail_closed(self):
        inventory, metrics, opportunities, policy = reports()
        changed_policy = deepcopy(policy)
        changed_policy["roles"]["sky"]["responsibility"] = "new interpretation"
        with self.assertRaises(ArchitecturePolicyTriageError):
            triage_cross_role_concentration(
                inventory, metrics, opportunities, changed_policy
            )
        tampered = deepcopy(opportunities)
        concentration = next(s for s in tampered["architecture_signals"]
                             if s["family"] == "CROSS_BOUNDARY_CONCENTRATION")
        concentration["measurement"]["numerator"] = 2
        tampered["opportunities_id"] = sha256(json.dumps({
            k: v for k, v in tampered.items() if k != "opportunities_id"
        }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        with self.assertRaises(ArchitecturePolicyTriageError):
            triage_cross_role_concentration(inventory, metrics, tampered, policy)
        forged = deepcopy(opportunities)
        concentration = next(s for s in forged["architecture_signals"]
                             if s["family"] == "CROSS_BOUNDARY_CONCENTRATION")
        concentration["source_witnesses"][0]["source_sha256"] = "0" * 64
        forged["opportunities_id"] = sha256(json.dumps({
            k: v for k, v in forged.items() if k != "opportunities_id"
        }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        with self.assertRaises(ArchitecturePolicyTriageError):
            triage_cross_role_concentration(inventory, metrics, forged, policy)

    def test_real_codeqa_pipeline_policy_allowed_is_not_keep_verdict(self):
        reader = GitReader(ROOT)
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
        paths = sorted(p for p in reader.tracked_paths()
                       if p.startswith("src/codeqa/") and p.endswith(".py"))
        sources = {p: reader.read_file(head, p).decode("utf-8") for p in paths}
        policy = json.loads(
            (ROOT / "profiles/semantic-directory-roles-v0.1.json").read_text()
        )
        inventory = analyze_architecture_inventory(head, paths, sources, policy)
        graph = extract_python_dependencies(
            sources, snapshot_id=head, analyzed_paths=tuple(paths),
        )
        metrics = analyze_architecture_metrics(inventory, graph, policy, PROFILE)
        opportunities = discover_architecture_opportunities(inventory, metrics)
        triage = triage_cross_role_concentration(
            inventory, metrics, opportunities, policy
        )
        pipeline = [item for item in triage["signal_triage"]
                    if item["source_role"] == "pipeline"]
        self.assertTrue(pipeline, "the live pipeline concentration must be examined")
        self.assertTrue(all(
            item["declared_policy_counts"] == {
                "DECLARED_ALLOWED": item["observed_cross_pairs"]
            } for item in pipeline
        ))
        self.assertEqual(triage["source_identity"]["snapshot_sha"], head)
        self.assertEqual(triage["decision"], "NOT_EVALUATED")


    def _assessment_for(self, inv, metrics, opportunities, policy, mappings=None):
        scenarios = generate_virtual_layout_scenarios(
            inv, metrics, opportunities, policy, candidate_mappings=mappings
        )
        migration = assess_architecture_migration(inv, scenarios, SOURCES)
        return assemble_architecture_advisory(
            inv, metrics, opportunities, scenarios, migration
        )

    def test_collision_keep_is_scoped_to_rejected_mapping_not_architecture(self):
        inv, metrics, opportunities, policy = reports()
        qid = opportunities["question_opportunities"][0]["opportunity_id"]
        assessment = self._assessment_for(
            inv, metrics, opportunities, policy,
            {qid: {"src/orchard/sky/view.py": "src/orchard/earth/model.py"}},
        )
        triage = triage_cross_role_concentration(
            inv, metrics, opportunities, policy
        )
        report = render_policy_candidate_decisions(triage, assessment)
        self.assertIn("KEEP rejected mapping only: TARGET_COLLISION", report)
        self.assertIn(
            "src/orchard/sky/view.py -> src/orchard/earth/model.py", report
        )
        self.assertIn("no-move is the safe current action", report)
        self.assertIn("not a global KEEP/PASS verdict", report)
        self.assertIn("External consumers and", report)
        self.assertIn("semantic ownership: NOT_EVALUATED", report)

    def test_viable_scenario_preserves_b7_unknown_and_denominators(self):
        inv, metrics, opportunities, policy = reports()
        assessment = self._assessment_for(
            inv, metrics, opportunities, policy
        )
        triage = triage_cross_role_concentration(
            inv, metrics, opportunities, policy
        )
        self.assertTrue(assessment["scenario_assessments"])
        report = render_policy_candidate_decisions(triage, assessment)
        decision = assessment["scenario_assessments"][0]["decision_evidence"]
        self.assertIn("Compared scenario", report)
        self.assertIn(decision["decision"], report)
        self.assertIn("matched denominators=True", report)
        self.assertIn("EXTERNAL_CONSUMERS_NOT_EVALUATED", report)
        self.assertNotIn("KEEP rejected mapping only", report)

    def test_zero_signal_and_mismatched_provenance_fail_closed(self):
        inv, metrics, opportunities, policy = reports(edges=())
        triage = triage_cross_role_concentration(
            inv, metrics, opportunities, policy
        )
        assessment = self._assessment_for(
            inv, metrics, opportunities, policy
        )
        report = render_policy_candidate_decisions(triage, assessment)
        self.assertIn("zero questions is valid, not PASS", report)
        self.assertNotIn("KEEP rejected mapping only", report)
        changed = deepcopy(assessment)
        changed["source_identity"]["snapshot_sha"] = "f" * 40
        changed["assessment_id"] = sha256(json.dumps({
            k: v for k, v in changed.items() if k != "assessment_id"
        }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        with self.assertRaises(ArchitecturePolicyTriageError):
            render_policy_candidate_decisions(triage, changed)
        tampered = deepcopy(triage)
        tampered["signal_triage"].append({"signal_id": "fake"})
        with self.assertRaises(ArchitecturePolicyTriageError):
            render_policy_candidate_decisions(tampered, assessment)



if __name__ == "__main__":
    unittest.main()
