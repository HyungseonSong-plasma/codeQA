"""#166: no-move must be justified without a global KEEP/PASS inference."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import unittest

from codeqa.evaluation.architecture.assessment import assemble_architecture_advisory
from codeqa.evaluation.architecture.bounded_disposition import (
    BoundedDispositionError, assess_bounded_disposition,
    render_bounded_disposition_markdown,
)
from codeqa.evaluation.architecture.edge_responsibility import census_edge_responsibility
from codeqa.evaluation.architecture.internal_consumers import census_internal_consumers
from codeqa.evaluation.architecture.migration import assess_architecture_migration
from codeqa.evaluation.architecture.policy_triage import triage_cross_role_concentration
from codeqa.evaluation.architecture.scenarios import generate_virtual_layout_scenarios
from test_architecture_policy_triage_v01 import reports
from test_architecture_opportunities_v01 import SOURCES


def _digest(report):
    return sha256(json.dumps(
        report, sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()


def fixture(*, edges=None, collision=False, duplicate=False):
    if edges is None:
        inv, metrics, opportunities, policy = reports()
    else:
        inv, metrics, opportunities, policy = reports(edges=edges)
    mapping = None
    if (collision or duplicate) and opportunities["question_opportunities"]:
        qid = opportunities["question_opportunities"][0]["opportunity_id"]
        if duplicate:
            # A duplicate destination may be a *new*, unoccupied path.
            mapping = {qid: {
                "src/orchard/sky/view.py": "src/orchard/rain/combined.py",
                "src/orchard/sky/helper.py": "src/orchard/rain/combined.py",
            }}
        else:
            mapping = {qid: {"src/orchard/sky/view.py": "src/orchard/earth/model.py"}}
    scenarios = generate_virtual_layout_scenarios(
        inv, metrics, opportunities, policy, candidate_mappings=mapping,
    )
    migration = assess_architecture_migration(inv, scenarios, SOURCES)
    assessment = assemble_architecture_advisory(
        inv, metrics, opportunities, scenarios, migration,
    )
    triage = triage_cross_role_concentration(inv, metrics, opportunities, policy)
    consumers = census_internal_consumers(inv, metrics, triage)
    responsibility = census_edge_responsibility(
        inv, metrics, triage, consumers, policy,
    )
    return inv, triage, responsibility, assessment


class BoundedDispositionTests(unittest.TestCase):
    def test_collision_is_not_global_keep(self):
        report = assess_bounded_disposition(*fixture(collision=True))
        self.assertEqual(report["decision"], "NOT_EVALUATED")
        self.assertEqual(report["current_action"], "NO_AUTOMATIC_MOVE")
        self.assertEqual(len(report["signal_dispositions"]), 1)
        signal = report["signal_dispositions"][0]
        self.assertEqual(signal["disposition"], "INSUFFICIENT_EVIDENCE")
        self.assertEqual(signal["compared_candidates"], [])
        self.assertTrue(signal["collision_witnesses"])
        self.assertEqual(signal["rejected_candidates"][0]["reason"], "TARGET_COLLISION")
        self.assertEqual(signal["semantic_ownership"], "NOT_EVALUATED")
        summary = render_bounded_disposition_markdown(report)
        self.assertIn("No viable measured alternative", summary)
        self.assertIn("NOT_EVALUATED", summary)
        self.assertIn("TARGET_COLLISION", summary)

    def test_duplicate_destination_with_unoccupied_target_is_valid_collision(self):
        report = assess_bounded_disposition(*fixture(duplicate=True))
        signal = report["signal_dispositions"][0]
        self.assertEqual(signal["disposition"], "INSUFFICIENT_EVIDENCE")
        self.assertEqual(signal["compared_candidates"], [])
        self.assertEqual(len(signal["collision_witnesses"]), 2)
        self.assertEqual(
            {w["source_path"] for w in signal["collision_witnesses"]},
            {"src/orchard/sky/view.py", "src/orchard/sky/helper.py"},
        )
        self.assertTrue(all(
            w["proposed_target_path"] == "src/orchard/rain/combined.py"
            and w["collision_kind"] == "DUPLICATE_DESTINATION"
            for w in signal["collision_witnesses"]
        ))
        self.assertIn("DUPLICATE_DESTINATION", render_bounded_disposition_markdown(report))

    def test_reject_resealed_collision_kind_and_target_hash(self):
        inv, triage, responsibility, assessment = fixture(collision=True)
        forged = deepcopy(assessment)
        witness = forged["rejected_scenarios"][0]["collision_witnesses"][0]
        witness["occupied_target_sha256"] = "0" * 64
        forged["assessment_id"] = _digest({
            k: v for k, v in forged.items() if k != "assessment_id"
        })
        with self.assertRaises(BoundedDispositionError):
            assess_bounded_disposition(inv, triage, responsibility, forged)

        forged = deepcopy(assessment)
        witness = forged["rejected_scenarios"][0]["collision_witnesses"][0]
        witness["collision_kind"] = "DUPLICATE_DESTINATION"
        witness.pop("occupied_target_sha256")
        witness["conflicting_sources"] = ["src/orchard/sky/helper.py"]
        forged["assessment_id"] = _digest({
            k: v for k, v in forged.items() if k != "assessment_id"
        })
        with self.assertRaises(BoundedDispositionError):
            assess_bounded_disposition(inv, triage, responsibility, forged)

    def test_reject_incomplete_duplicate_destination_group(self):
        inv, triage, responsibility, assessment = fixture(duplicate=True)
        forged = deepcopy(assessment)
        forged["rejected_scenarios"][0]["collision_witnesses"].pop()
        forged["assessment_id"] = _digest({
            k: v for k, v in forged.items() if k != "assessment_id"
        })
        with self.assertRaises(BoundedDispositionError):
            assess_bounded_disposition(inv, triage, responsibility, forged)

    def test_noncolliding_candidate_preserves_b7_unknowns(self):
        report = assess_bounded_disposition(*fixture())
        signal = report["signal_dispositions"][0]
        self.assertTrue(signal["compared_candidates"])
        self.assertEqual(signal["disposition"], "INSUFFICIENT_EVIDENCE")
        self.assertTrue(signal["compared_candidates"][0]["critical_unknowns"])
        self.assertEqual(signal["current_action"], "NO_MOVE")

    def test_healthy_zero_signal_does_not_invent_a_problem(self):
        report = assess_bounded_disposition(*fixture(edges=()))
        self.assertEqual(report["signal_dispositions"], [])
        self.assertEqual(report["decision"], "NOT_EVALUATED")
        self.assertIn("no forced question", render_bounded_disposition_markdown(report))
        self.assertEqual(report, assess_bounded_disposition(*fixture(edges=())))

    def test_reject_stale_or_forged_evidence_even_when_resealed(self):
        inv, triage, responsibility, assessment = fixture(collision=True)
        changed = deepcopy(responsibility)
        changed["source_identity"]["snapshot_sha"] = "f" * 40
        changed["responsibility_id"] = _digest({
            k: v for k, v in changed.items() if k != "responsibility_id"
        })
        with self.assertRaises(BoundedDispositionError):
            assess_bounded_disposition(inv, triage, changed, assessment)
        forged = deepcopy(assessment)
        forged["rejected_scenarios"][0]["collision_witnesses"][0]["source_sha256"] = "0" * 64
        forged["assessment_id"] = _digest({
            k: v for k, v in forged.items() if k != "assessment_id"
        })
        with self.assertRaises(BoundedDispositionError):
            assess_bounded_disposition(inv, triage, responsibility, forged)

    def test_renderer_rejects_mutated_disposition(self):
        report = assess_bounded_disposition(*fixture())
        report["signal_dispositions"][0]["disposition"] = "PREFER"
        with self.assertRaises(BoundedDispositionError):
            render_bounded_disposition_markdown(report)


if __name__ == "__main__":
    unittest.main()
