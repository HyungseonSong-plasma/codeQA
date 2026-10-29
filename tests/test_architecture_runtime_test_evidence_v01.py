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
