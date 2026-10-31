"""#184: every source-derived concentration edge gets bounded ownership evidence."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import unittest

from codeqa.evaluation.architecture.edge_responsibility import (
    EdgeResponsibilityEvidenceError,
    census_edge_responsibility,
    render_edge_responsibility_markdown,
)
from codeqa.evaluation.architecture.internal_consumers import census_internal_consumers
from codeqa.evaluation.architecture.policy_triage import triage_cross_role_concentration
from test_architecture_opportunities_v01 import POLICY
from test_architecture_policy_triage_v01 import reports
from test_architecture_internal_consumers_v01 import with_test_importer


def evidence(*, edges=None, policy=None):
    if edges is None:
        inv, metrics, opportunities, role_policy = reports(policy=policy)
    else:
        inv, metrics, opportunities, role_policy = reports(edges=edges, policy=policy)
    triage = triage_cross_role_concentration(inv, metrics, opportunities, role_policy)
    consumers = census_internal_consumers(inv, metrics, triage)
    return inv, metrics, triage, consumers, role_policy


def digest(value):
    return sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()


class EdgeResponsibilityTests(unittest.TestCase):
    def test_every_measured_edge_has_role_and_source_witness_without_semantic_pass(self):
        report = census_edge_responsibility(*evidence())
        self.assertEqual(report["observed_cross_role_pairs"], 3)
        self.assertEqual(report["declared_policy_counts"], {"DECLARED_ALLOWED": 3})
        self.assertEqual(len(report["edges"]), 3)
        self.assertTrue(all(
            r["source_declared_responsibility"] == POLICY["roles"][r["source_role"]]["responsibility"]
            and r["target_declared_responsibility"] == POLICY["roles"][r["target_role"]]["responsibility"]
            and r["composition_hypothesis"] == "DECLARED_DIRECTION_COMPATIBLE"
            and r["semantic_ownership"] == "NOT_EVALUATED"
            and r["test_behavior_coverage"] == "NOT_EVALUATED"
            and r["import_witnesses"]
            for r in report["edges"]
        ))
        self.assertEqual(report["decision"], "NOT_EVALUATED")
        human = render_edge_responsibility_markdown(report)
        self.assertIn("src/orchard/sky/view.py:1", human)
        self.assertIn("Direction-compatible is a hypothesis", human)
        self.assertIn("not behavioral test coverage", human)
        self.assertIn("no", human.lower())

    def test_test_importer_witness_is_not_behavioral_coverage(self):
        inv, metrics, triage = with_test_importer()
        consumers = census_internal_consumers(inv, metrics, triage)
        report = census_edge_responsibility(inv, metrics, triage, consumers, POLICY)
        self.assertEqual(report["observed_cross_role_pairs"], 3)
        self.assertTrue(any(
            witness["source_path"] == "tests/test_view.py"
            for edge in report["edges"]
            for witness in edge["known_test_path_importers"]
        ))
        self.assertTrue(all(
            edge["test_behavior_coverage"] == "NOT_EVALUATED"
            for edge in report["edges"]
        ))
        self.assertIn("tests/test_view.py:1", render_edge_responsibility_markdown(report))

    def test_no_signal_is_empty_not_global_pass(self):
        report = census_edge_responsibility(*evidence(edges=()))
        self.assertEqual(report["edges"], [])
        self.assertEqual(report["observed_cross_role_pairs"], 0)
        self.assertEqual(report["decision"], "NOT_EVALUATED")
        self.assertNotIn("PASS", [report["decision"]])
        self.assertEqual(report, census_edge_responsibility(*evidence(edges=())))

    def test_forbidden_direction_needs_review_not_composition_approval(self):
        policy = deepcopy(POLICY)
        policy["roles"]["sky"]["forbidden_imports"] = ["earth"]
        report = census_edge_responsibility(*evidence(policy=policy))
        self.assertEqual(report["declared_policy_counts"], {
            "DECLARED_ALLOWED": 1, "DECLARED_FORBIDDEN": 2,
        })
        forbidden = [r for r in report["edges"]
                     if r["declared_policy_direction"] == "DECLARED_FORBIDDEN"]
        self.assertTrue(all(
            r["composition_hypothesis"] == "BOUNDARY_REVIEW_REQUIRED"
            for r in forbidden
        ))
        self.assertEqual(report["decision"], "NOT_EVALUATED")

    def test_reject_stale_consumer_and_forged_witness_even_if_resealed(self):
        inv, metrics, triage, consumers, policy = evidence()
        stale = deepcopy(consumers)
        stale["source_identity"]["snapshot_sha"] = "f" * 40
        stale["census_id"] = digest({
            k: v for k, v in stale.items() if k != "census_id"
        })
        with self.assertRaises(EdgeResponsibilityEvidenceError):
            census_edge_responsibility(inv, metrics, triage, stale, policy)
        forged = deepcopy(triage)
        forged["signal_triage"][0]["pairs"][0]["source_witnesses"][0]["source_sha256"] = "0" * 64
        forged["triage_id"] = digest({
            k: v for k, v in forged.items() if k != "triage_id"
        })
        with self.assertRaises(EdgeResponsibilityEvidenceError):
            census_edge_responsibility(inv, metrics, forged, consumers, policy)

    def test_resealed_consumer_claims_must_match_measured_import_pairs(self):
        # Recomputing the census digest cannot turn a changed importer into
        # a source-backed B2 pair. All four variants used to be accepted.
        inv, metrics, triage = with_test_importer()
        consumers = census_internal_consumers(inv, metrics, triage)
        self.assertEqual(
            census_edge_responsibility(inv, metrics, triage, consumers, POLICY)[
                "observed_cross_role_pairs"
            ], 3,
        )
        tracked = {f["path"]: f for f in inv["files"]}
        for mutation in ("category", "line", "unmeasured", "duplicate"):
            with self.subTest(mutation=mutation):
                forged = deepcopy(consumers)
                module = next(m for m in forged["modules"]
                              if m["module_path"] == "src/orchard/sky/view.py")
                importer = next(i for i in module["importers"]
                                if i["importer_path"] == "tests/test_view.py")
                if mutation == "category":
                    importer["importer_category"] = "PACKAGE_SOURCE"
                    module["known_test_path_importer_pairs"] -= 1
                    forged["known_test_path_importer_pairs"] -= 1
                elif mutation == "line":
                    importer["source_witnesses"][0]["line"] += 1
                elif mutation == "unmeasured":
                    fake_path = "src/orchard/sky/view.py"
                    importer["importer_path"] = fake_path
                    importer["importer_category"] = "PACKAGE_SOURCE"
                    importer["source_witnesses"][0]["source_path"] = fake_path
                    importer["source_witnesses"][0]["source_sha256"] = (
                        tracked[fake_path]["source_sha256"]
                    )
                    module["known_test_path_importer_pairs"] -= 1
                    forged["known_test_path_importer_pairs"] -= 1
                else:
                    module["importers"].append(deepcopy(importer))
                    module["known_static_importer_pairs"] += 1
                    module["known_test_path_importer_pairs"] += 1
                    forged["known_static_importer_pairs"] += 1
                    forged["known_test_path_importer_pairs"] += 1
                forged["census_id"] = digest({
                    k: v for k, v in forged.items() if k != "census_id"
                })
                with self.assertRaises(EdgeResponsibilityEvidenceError):
                    census_edge_responsibility(
                        inv, metrics, triage, forged, POLICY,
                    )

    def test_renderer_rejects_modified_counts(self):
        report = census_edge_responsibility(*evidence())
        changed = deepcopy(report)
        changed["observed_cross_role_pairs"] = 2
        with self.assertRaises(EdgeResponsibilityEvidenceError):
            render_edge_responsibility_markdown(changed)


if __name__ == "__main__":
    unittest.main()
