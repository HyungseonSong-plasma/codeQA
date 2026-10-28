"""#166/#184: bounded source-bound static candidate test call/assert evidence."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import unittest

from codeqa.core.dependency import StaticDependency
from codeqa.evaluation.architecture.internal_consumers import census_internal_consumers
from codeqa.evaluation.architecture.edge_responsibility import census_edge_responsibility
from codeqa.evaluation.architecture.opportunities import discover_architecture_opportunities
from codeqa.evaluation.architecture.policy_triage import triage_cross_role_concentration
from codeqa.evaluation.architecture.test_behavior_candidates import (
    TestBehaviorCandidateError,
    census_test_behavior_candidates,
    render_test_behavior_candidates_markdown,
)
from test_architecture_opportunities_v01 import SOURCES, POLICY, make_report
from test_architecture_policy_triage_v01 import CONCENTRATED


TEST_PATH = "tests/test_view.py"
TEST_TEXT = (
    "from orchard.sky.view import view\n"
    "\n"
    "def test_view_uses_behavior():\n"
    "    result = view()\n"
    "    assert result is not None\n"
)


def reports(text=TEST_TEXT, *, test_import=True):
    sources = dict(SOURCES)
    if test_import:
        sources[TEST_PATH] = text
    edges = list(CONCENTRATED)
    if test_import:
        edges.append(StaticDependency(
            TEST_PATH, "src/orchard/sky/view.py", 1,
            "from orchard.sky.view import view", "top_level",
        ))
    inventory, metrics = make_report(sources=sources, edges=tuple(edges))
    opportunities = discover_architecture_opportunities(inventory, metrics)
    triage = triage_cross_role_concentration(inventory, metrics, opportunities, POLICY)
    consumers = census_internal_consumers(inventory, metrics, triage)
    responsibility = census_edge_responsibility(
        inventory, metrics, triage, consumers, POLICY,
    )
    return inventory, responsibility, {TEST_PATH: text} if test_import else {}


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class TestBehaviorCandidateTests(unittest.TestCase):
    def test_import_call_and_assert_are_candidate_not_verified_coverage(self):
        report = census_test_behavior_candidates(*reports())
        self.assertEqual(report["observed_cross_role_pairs"], 3)
        self.assertEqual(report["decision"], "NOT_EVALUATED")
        self.assertEqual(report["candidate_test_functions_across_edges"], 2)
        observed = [e for e in report["edges"] if e["source_path"].endswith("view.py")]
        self.assertEqual(len(observed), 2)
        for edge in observed:
            candidate = edge["candidate_test_paths"][0]["candidate_tests"][0]
            self.assertEqual(candidate["candidate_call_lines"], [4])
            self.assertEqual(candidate["assertion_lines"], [5])
            self.assertEqual(candidate["assertion_operand_pairs"], [])
            self.assertEqual(candidate["evidence_class"], "STATIC_CANDIDATE_NOT_BEHAVIORAL_COVERAGE")
            self.assertEqual(edge["behavioral_edge_coverage"], "NOT_EVALUATED")
        self.assertIn("candidate only", render_test_behavior_candidates_markdown(report))

    def test_direct_assertion_operand_is_source_bound_but_not_coverage(self):
        text = (
            "from orchard.sky.view import view\n"
            "def test_direct():\n"
            "    assert view() is not None\n"
        )
        report = census_test_behavior_candidates(*reports(text))
        self.assertEqual(report["candidate_test_functions_across_edges"], 2)
        self.assertEqual(report["assertion_operand_candidate_pairs_across_edges"], 2)
        observed = [e for e in report["edges"] if e["source_path"].endswith("view.py")]
        for edge in observed:
            candidate = edge["candidate_test_paths"][0]["candidate_tests"][0]
            self.assertEqual(candidate["assertion_operand_pairs"], [
                {"call_line": 3, "assertion_line": 3},
            ])
            self.assertEqual(edge["behavioral_edge_coverage"], "NOT_EVALUATED")
        self.assertIn("assertion-operand", render_test_behavior_candidates_markdown(report))

    def test_unrelated_assertion_is_not_operand_evidence(self):
        text = (
            "from orchard.sky.view import view\n"
            "def test_unrelated():\n"
            "    view()\n"
            "    assert True\n"
        )
        report = census_test_behavior_candidates(*reports(text))
        self.assertEqual(report["candidate_test_functions_across_edges"], 2)
        self.assertEqual(report["assertion_operand_candidate_pairs_across_edges"], 0)
        for edge in report["edges"]:
            for site in edge["candidate_test_paths"]:
                for candidate in site["candidate_tests"]:
                    self.assertEqual(candidate["assertion_operand_pairs"], [])

    def test_unittest_assertion_operand_and_nested_helper_isolation(self):
        text = (
            "from orchard.sky.view import view\n"
            "def test_method(self):\n"
            "    self.assertEqual(view(), 1)\n"
            "    def helper():\n"
            "        view()\n"
            "        assert False\n"
        )
        report = census_test_behavior_candidates(*reports(text))
        self.assertEqual(report["assertion_operand_candidate_pairs_across_edges"], 2)
        for edge in report["edges"]:
            for site in edge["candidate_test_paths"]:
                for candidate in site["candidate_tests"]:
                    self.assertEqual(candidate["candidate_call_lines"], [3])
                    self.assertEqual(candidate["assertion_lines"], [3])
                    self.assertEqual(candidate["assertion_operand_pairs"], [
                        {"call_line": 3, "assertion_line": 3},
                    ])

    def test_locally_rebound_import_is_not_counted_as_imported_behavior(self):
        for binding in (
            "    view = lambda: 1\\n",
            "    def view():\\n        return 1\\n",
            "    view = 1\\n",
        ):
            with self.subTest(binding=binding):
                text = (
                    "from orchard.sky.view import view\\n"
                    "def test_rebound():\\n"
                    + binding
                    + "    assert view() == 1\\n"
                ).replace("\\\\n", "\\n")
                report = census_test_behavior_candidates(*reports(text))
                self.assertEqual(report["candidate_test_functions_across_edges"], 0)
                self.assertEqual(report["assertion_operand_candidate_pairs_across_edges"], 0)
                self.assertEqual(report["decision"], "NOT_EVALUATED")

    def test_import_shadowed_by_parameter_or_later_assignment(self):
        for text in (
            "from orchard.sky.view import view\\n"
            "def test_parameter(view):\\n    assert view() is not None\\n",
            "from orchard.sky.view import view\\n"
            "def test_later():\\n    assert view() is not None\\n    view = 2\\n",
        ):
            with self.subTest(text=text):
                report = census_test_behavior_candidates(*reports(text))
                self.assertEqual(report["candidate_test_functions_across_edges"], 0)

    def test_deferred_assertion_lambda_and_generator_are_not_operand_witnesses(self):
        for expression in ("(lambda: view())", "(view() for _ in range(1))"):
            with self.subTest(expression=expression):
                text = (
                    "from orchard.sky.view import view\\n"
                    "def test_deferred():\\n"
                    "    view()\\n"
                    "    assert " + expression + "\\n"
                )
                report = census_test_behavior_candidates(*reports(text))
                self.assertEqual(report["candidate_test_functions_across_edges"], 2)
                self.assertEqual(report["assertion_operand_candidate_pairs_across_edges"], 0)
                self.assertTrue(all(
                    not candidate["assertion_operand_pairs"]
                    for edge in report["edges"]
                    for site in edge["candidate_test_paths"]
                    for candidate in site["candidate_tests"]
                ))

    def test_nested_helper_does_not_create_test_behavior_candidate(self):
        text = (
            "from orchard.sky.view import view\n"
            "def test_nested():\n"
            "    def helper():\n"
            "        view()\n"
            "    assert True\n"
        )
        report = census_test_behavior_candidates(*reports(text))
        self.assertEqual(report["candidate_test_functions_across_edges"], 0)
        self.assertEqual(report["assertion_operand_candidate_pairs_across_edges"], 0)

    def test_import_without_call_or_assert_is_not_a_candidate(self):
        for text in (
            "from orchard.sky.view import view\n",
            "from orchard.sky.view import view\ndef test_view():\n    view()\n",
            "from orchard.sky.view import view\ndef test_view():\n    assert True\n",
        ):
            with self.subTest(text=text):
                report = census_test_behavior_candidates(*reports(text))
                self.assertEqual(report["candidate_test_functions_across_edges"], 0)
                self.assertEqual(report["decision"], "NOT_EVALUATED")

    def test_no_test_import_has_no_seeded_behavior(self):
        inventory, responsibility, _ = reports(test_import=False)
        report = census_test_behavior_candidates(inventory, responsibility, {})
        self.assertEqual(report["candidate_test_functions_across_edges"], 0)
        self.assertTrue(all(not edge["candidate_test_paths"] for edge in report["edges"]))

    def test_mismatched_source_and_forged_witness_fail_closed(self):
        inventory, responsibility, sources = reports()
        with self.assertRaises(TestBehaviorCandidateError):
            census_test_behavior_candidates(inventory, responsibility, {TEST_PATH: sources[TEST_PATH] + "\n"})
        stale = deepcopy(responsibility)
        stale["source_identity"]["snapshot_sha"] = "f" * 40
        stale["responsibility_id"] = digest({k: v for k, v in stale.items() if k != "responsibility_id"})
        with self.assertRaises(TestBehaviorCandidateError):
            census_test_behavior_candidates(inventory, stale, sources)
        forged = deepcopy(responsibility)
        forged["edges"][0]["known_test_path_importers"] = [{
            "source_path": TEST_PATH, "target_path": "src/orchard/sky/view.py",
            "line": 99, "source_sha256": sha256(sources[TEST_PATH].encode()).hexdigest(),
        }]
        forged["responsibility_id"] = digest({k: v for k, v in forged.items() if k != "responsibility_id"})
        with self.assertRaises(TestBehaviorCandidateError):
            census_test_behavior_candidates(inventory, forged, sources)

    def test_renderer_detects_modified_counts(self):
        report = census_test_behavior_candidates(*reports())
        report["candidate_test_functions_across_edges"] += 1
        with self.assertRaises(TestBehaviorCandidateError):
            render_test_behavior_candidates_markdown(report)


if __name__ == "__main__":
    unittest.main()
