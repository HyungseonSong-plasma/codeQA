"""Opt-in runtime receipts are executed evidence, not import-edge coverage."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import unittest

from codeqa.evaluation.architecture.runtime_test_evidence import (
    RuntimeTestEvidenceError,
    capture_unittest_execution,
    correlate_runtime_test_candidates,
)


SOURCE = b"def test_example():\n    assert True\n"
SHA = sha256(SOURCE).hexdigest()
COMMIT = "a" * 40


class PassCase(unittest.TestCase):
    def test_example(self):
        self.assertTrue(True)


def digest(obj):
    return sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def fixture():
    suite = unittest.TestSuite([PassCase("test_example")])
    receipt = capture_unittest_execution(
        suite, snapshot_sha=COMMIT, test_path="tests/test_architecture_runtime_test_evidence_v01.py",
        test_source=SOURCE, expected_source_sha256=SHA,
    )
    candidates = {
        "source_identity": {"snapshot_sha": COMMIT},
        "decision": "NOT_EVALUATED",
        "edges": [{
            "source_path": "src/thing/a.py", "target_path": "src/thing/b.py",
            "candidate_test_paths": [{
                "test_path": "tests/test_architecture_runtime_test_evidence_v01.py", "test_source_sha256": SHA,
                "candidate_tests": [{"test_function": "test_example"}],
            }],
        }],
    }
    candidates["candidate_id"] = digest(candidates)
    return candidates, receipt


class RuntimeReceiptTests(unittest.TestCase):
    def test_real_unittest_pass_and_explicit_noncoverage(self):
        candidates, receipt = fixture()
        self.assertEqual(receipt["tests_run"], 1)
        self.assertEqual(receipt["executed_tests"][0]["outcome"], "PASSED")
        self.assertEqual(receipt["edge_traversal"], "NOT_EVALUATED")
        correlated = correlate_runtime_test_candidates(candidates, receipt)
        self.assertEqual(correlated["matched_candidates"][0]["match_state"], "UNIQUE")
        self.assertEqual(correlated["matched_candidates"][0]["unittest_outcome"], "PASSED")
        self.assertEqual(correlated["matched_candidates"][0]["edge_traversal"], "NOT_EVALUATED")

    def test_failure_and_skip_are_not_passed(self):
        class FailCase(unittest.TestCase):
            def test_fail(self):
                self.fail("controlled failure")

        class SkipCase(unittest.TestCase):
            @unittest.skip("controlled skip")
            def test_skip(self):
                self.fail("not executed")

        suite = unittest.TestSuite([FailCase("test_fail"), SkipCase("test_skip")])
        receipt = capture_unittest_execution(
            suite, snapshot_sha=COMMIT, test_path="tests/test_architecture_runtime_test_evidence_v01.py",
            test_source=SOURCE, expected_source_sha256=SHA,
        )
        self.assertFalse(receipt["all_passed"])
        self.assertEqual([x["outcome"] for x in receipt["executed_tests"]], ["FAILED", "SKIPPED"])

    def test_failing_subtest_is_reported_as_failed_not_started(self):
        class SubtestFailure(unittest.TestCase):
            def test_cases(self):
                with self.subTest(case="failing"):
                    self.assertEqual(1, 2)
                with self.subTest(case="passing"):
                    self.assertEqual(2, 2)

        receipt = capture_unittest_execution(
            unittest.TestSuite([SubtestFailure("test_cases")]),
            snapshot_sha=COMMIT,
            test_path="tests/test_architecture_runtime_test_evidence_v01.py",
            test_source=SOURCE, expected_source_sha256=SHA,
        )
        self.assertEqual(receipt["tests_run"], 1)
        self.assertEqual(receipt["executed_tests"][0]["outcome"], "FAILED")
        self.assertFalse(receipt["all_passed"])
        self.assertEqual(receipt["edge_traversal"], "NOT_EVALUATED")
        self.assertEqual(receipt["semantic_ownership"], "NOT_EVALUATED")

    def test_subtest_error_precedes_later_failure_and_pass_control(self):
        class ErrorThenFailure(unittest.TestCase):
            def test_cases(self):
                with self.subTest(case="error"):
                    raise RuntimeError("controlled subtest error")
                with self.subTest(case="failure"):
                    self.fail("controlled subtest failure")

        class PassingSubtests(unittest.TestCase):
            def test_cases(self):
                with self.subTest(case="passing"):
                    self.assertTrue(True)

        receipt = capture_unittest_execution(
            unittest.TestSuite([
                ErrorThenFailure("test_cases"),
                PassingSubtests("test_cases"),
            ]),
            snapshot_sha=COMMIT,
            test_path="tests/test_architecture_runtime_test_evidence_v01.py",
            test_source=SOURCE, expected_source_sha256=SHA,
        )
        outcomes = {
            item["test_id"].split(".")[-2]: item["outcome"]
            for item in receipt["executed_tests"]
        }
        self.assertEqual(outcomes, {
            "ErrorThenFailure": "ERROR", "PassingSubtests": "PASSED",
        })
        self.assertEqual(receipt["tests_run"], 2)
        self.assertFalse(receipt["all_passed"])
        self.assertEqual(receipt["edge_traversal"], "NOT_EVALUATED")

    def test_multiple_unittest_callbacks_keep_error_and_failure_precedence(self):
        # unittest can call multiple result hooks for a single test method:
        # a failing tearDown must not downgrade an earlier ERROR, and a
        # skipped tearDown must not hide a prior ERROR or FAILED outcome.
        class ErrorThenFailure(unittest.TestCase):
            def test_case(self):
                raise RuntimeError("controlled body error")

            def tearDown(self):
                self.fail("controlled tearDown failure")

        class ErrorThenSkip(unittest.TestCase):
            def test_case(self):
                raise RuntimeError("controlled body error")

            def tearDown(self):
                self.skipTest("controlled tearDown skip")

        class FailureThenSkip(unittest.TestCase):
            def test_case(self):
                self.fail("controlled body failure")

            def tearDown(self):
                self.skipTest("controlled tearDown skip")

        suite = unittest.TestSuite([
            ErrorThenFailure("test_case"), ErrorThenSkip("test_case"),
            FailureThenSkip("test_case"),
        ])
        receipt = capture_unittest_execution(
            suite, snapshot_sha=COMMIT,
            test_path="tests/test_architecture_runtime_test_evidence_v01.py",
            test_source=SOURCE, expected_source_sha256=SHA,
        )
        outcomes = {
            item["test_id"].split(".")[-2]: item["outcome"]
            for item in receipt["executed_tests"]
        }
        self.assertEqual(outcomes, {
            "ErrorThenFailure": "ERROR", "ErrorThenSkip": "ERROR",
            "FailureThenSkip": "FAILED",
        })
        self.assertEqual(receipt["tests_run"], 3)
        self.assertFalse(receipt["all_passed"])
        self.assertEqual(receipt["edge_traversal"], "NOT_EVALUATED")
        self.assertEqual(receipt["semantic_ownership"], "NOT_EVALUATED")

    def test_wrong_source_hash_rejected_before_execution(self):
        with self.assertRaises(RuntimeTestEvidenceError):
            capture_unittest_execution(
                unittest.TestSuite([PassCase("test_example")]),
                snapshot_sha=COMMIT, test_path="tests/test_architecture_runtime_test_evidence_v01.py",
                test_source=SOURCE + b"\n", expected_source_sha256=SHA,
            )

    def test_tampered_receipt_and_stale_snapshot_fail_closed(self):
        candidates, receipt = fixture()
        forged = deepcopy(receipt)
        forged["executed_tests"][0]["outcome"] = "PASSED_BUT_UNVERIFIED"
        with self.assertRaises(RuntimeTestEvidenceError):
            correlate_runtime_test_candidates(candidates, forged)
        stale = deepcopy(receipt)
        stale["source_identity"]["snapshot_sha_claim"] = "b" * 40
        stale["receipt_id"] = digest({k: v for k, v in stale.items() if k != "receipt_id"})
        with self.assertRaises(RuntimeTestEvidenceError):
            correlate_runtime_test_candidates(candidates, stale)

    def test_suite_fixture_error_after_pass_does_not_claim_all_passed(self):
        # A setUpClass failure is recorded by unittest without a started test
        # ID. One passing test must not conceal that suite-level failure.
        class BrokenFixture(unittest.TestCase):
            @classmethod
            def setUpClass(cls):
                raise RuntimeError("controlled setUpClass error")

            def test_never_runs(self):
                self.fail("not reached")

        candidates, _ = fixture()
        receipt = capture_unittest_execution(
            unittest.TestSuite([
                PassCase("test_example"), BrokenFixture("test_never_runs"),
            ]),
            snapshot_sha=COMMIT,
            test_path="tests/test_architecture_runtime_test_evidence_v01.py",
            test_source=SOURCE, expected_source_sha256=SHA,
        )
        self.assertEqual(receipt["tests_run"], 1)
        self.assertEqual([r["outcome"] for r in receipt["executed_tests"]], ["PASSED"])
        self.assertFalse(receipt["suite_was_successful"])
        self.assertFalse(receipt["all_passed"])
        correlated = correlate_runtime_test_candidates(candidates, receipt)
        self.assertEqual(correlated["matched_candidates"][0]["match_state"], "UNIQUE")
        self.assertEqual(correlated["decision"], "NOT_EVALUATED")

    def test_rehashed_suite_success_contradiction_is_rejected(self):
        candidates, receipt = fixture()
        for bad in (False, 1, "true"):
            with self.subTest(bad=bad):
                forged = deepcopy(receipt)
                forged["suite_was_successful"] = bad
                forged["receipt_id"] = digest({
                    k: v for k, v in forged.items() if k != "receipt_id"
                })
                with self.assertRaises(RuntimeTestEvidenceError):
                    correlate_runtime_test_candidates(candidates, forged)

    def test_rehashed_invalid_outcomes_are_rejected(self):
        # A caller can recompute the receipt digest: the parser must still
        # reject status values that unittest never emits.
        candidates, receipt = fixture()
        for bad in ("PASSED_BUT_UNVERIFIED", None, 7, ["PASSED"]):
            with self.subTest(bad=repr(bad)):
                forged = deepcopy(receipt)
                forged["executed_tests"][0]["outcome"] = bad
                forged["all_passed"] = False
                forged["receipt_id"] = digest({
                    k: v for k, v in forged.items() if k != "receipt_id"
                })
                with self.assertRaises(RuntimeTestEvidenceError):
                    correlate_runtime_test_candidates(candidates, forged)

    def test_rehashed_inconsistent_summary_and_identity_are_rejected(self):
        candidates, receipt = fixture()
        for variant in ("false_summary", "numeric_summary",
                        "boolean_test_count", "empty_test_id"):
            with self.subTest(variant=variant):
                forged = deepcopy(receipt)
                if variant == "false_summary":
                    forged["all_passed"] = False
                elif variant == "numeric_summary":
                    forged["all_passed"] = 1
                elif variant == "boolean_test_count":
                    forged["tests_run"] = True
                else:
                    forged["executed_tests"][0]["test_id"] = ""
                forged["receipt_id"] = digest({
                    k: v for k, v in forged.items() if k != "receipt_id"
                })
                with self.assertRaises(RuntimeTestEvidenceError):
                    correlate_runtime_test_candidates(candidates, forged)

    def test_duplicate_method_names_are_ambiguous(self):
        candidates, receipt = fixture()
        other = deepcopy(receipt["executed_tests"][0])
        other["test_id"] = "test_architecture_runtime_test_evidence_v01.OtherCase.test_example"
        receipt["executed_tests"].append(other)
        receipt["tests_run"] = 2
        receipt["receipt_id"] = digest({k: v for k, v in receipt.items() if k != "receipt_id"})
        correlated = correlate_runtime_test_candidates(candidates, receipt)
        self.assertEqual(correlated["matched_candidates"][0]["match_state"], "AMBIGUOUS")


    def test_other_module_same_named_method_not_misreported_as_executed(self):
        candidates, receipt = fixture()
        receipt["executed_tests"][0]["test_id"] = "unrelated.module.OtherCase.test_example"
        receipt["receipt_id"] = digest({
            k: v for k, v in receipt.items() if k != "receipt_id"
        })
        matched = correlate_runtime_test_candidates(candidates, receipt)
        self.assertEqual(matched["matched_candidates"][0]["match_state"], "NOT_EXECUTED")
        self.assertIsNone(matched["matched_candidates"][0]["unittest_outcome"])
        self.assertEqual(matched["decision"], "NOT_EVALUATED")

    def test_arbitrary_module_prefix_cannot_spoof_expected_module(self):
        candidates, receipt = fixture()
        receipt["executed_tests"][0]["test_id"] = (
            "foreign.test_architecture_runtime_test_evidence_v01.PassCase.test_example"
        )
        receipt["receipt_id"] = digest({
            k: v for k, v in receipt.items() if k != "receipt_id"
        })
        matched = correlate_runtime_test_candidates(candidates, receipt)
        self.assertEqual(matched["matched_candidates"][0]["match_state"], "NOT_EXECUTED")

    def test_tests_package_qualified_module_is_accepted_as_lexical_match(self):
        candidates, receipt = fixture()
        receipt["executed_tests"][0]["test_id"] = (
            "tests.test_architecture_runtime_test_evidence_v01.PassCase.test_example"
        )
        receipt["receipt_id"] = digest({
            k: v for k, v in receipt.items() if k != "receipt_id"
        })
        matched = correlate_runtime_test_candidates(candidates, receipt)
        self.assertEqual(matched["matched_candidates"][0]["match_state"], "UNIQUE")
        self.assertEqual(matched["matched_candidates"][0]["edge_traversal"], "NOT_EVALUATED")


if __name__ == "__main__":
    unittest.main()
