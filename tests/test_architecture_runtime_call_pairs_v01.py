"""Bounded opt-in runtime call witnesses: observed Python frames, not import PASS."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import sys
import tempfile
import unittest

from codeqa.evaluation.architecture.runtime_call_pairs import (
    RuntimeCallPairError, capture_unittest_call_pairs,
)


SRC = "src/demo/producer.py"
DST = "src/demo/consumer.py"
OTHER = "src/demo/other.py"
COMMIT = "a" * 40


class CallPairTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.texts = {
            SRC: "def produce():\n    return consume()\n",
            DST: "def consume():\n    return 7\n",
            OTHER: "def unrelated():\n    return 0\n",
        }
        for path, text in self.texts.items():
            full = self.root / path
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(text)
        consumer = {}
        exec(compile(self.texts[DST], str(self.root / DST), "exec"), consumer)
        producer = {"consume": consumer["consume"]}
        exec(compile(self.texts[SRC], str(self.root / SRC), "exec"), producer)
        self.produce = producer["produce"]

    def hashes(self, *paths):
        return {p: sha256(self.texts[p].encode()).hexdigest() for p in paths}

    def suite(self, call=True, skip=False):
        produce = self.produce

        class Example(unittest.TestCase):
            def test_observe(self):
                if call:
                    self.assertEqual(produce(), 7)
                else:
                    self.assertTrue(True)

        if skip:
            Example.test_observe = unittest.skip("intentional")(Example.test_observe)
        return unittest.TestSuite([Example("test_observe")])

    def observe(self, *, suite=None, pairs=None, hashes=None):
        return capture_unittest_call_pairs(
            suite or self.suite(), snapshot_sha=COMMIT, repository_root=self.root,
            source_sha256=hashes or self.hashes(SRC, DST),
            pairs=pairs or [(SRC, DST)],
        )

    def test_direct_call_is_observed_but_import_not_proved(self):
        report = self.observe()
        edge = report["observed_pairs"][0]
        self.assertEqual(edge["observed_direct_python_calls"], 1)
        self.assertEqual(edge["call_witnesses"][0]["caller_line"], 2)
        self.assertEqual(edge["call_witnesses"][0]["callee_first_line"], 1)
        self.assertEqual(report["executed_tests"][0]["outcome"], "PASSED")
        self.assertEqual(report["static_import_edge_traversal"], "NOT_EVALUATED")
        self.assertEqual(report["decision"], "NOT_EVALUATED")
        self.assertRegex(report["observation_id"], r"^[0-9a-f]{64}$")

    def test_no_call_and_skipped_test_do_not_prove_edge_absence(self):
        for suite in (self.suite(call=False), self.suite(skip=True)):
            with self.subTest(suite=suite):
                report = self.observe(suite=suite)
                self.assertEqual(report["observed_pairs"][0]["observed_direct_python_calls"], 0)
                self.assertEqual(report["static_import_edge_traversal"], "NOT_EVALUATED")

    def test_reverse_and_unrelated_pairs_are_not_invented(self):
        pairs = [(DST, SRC), (SRC, OTHER)]
        report = self.observe(pairs=pairs, hashes=self.hashes(SRC, DST, OTHER))
        self.assertEqual([e["observed_direct_python_calls"] for e in report["observed_pairs"]], [0, 0])

    def test_mismatched_hash_rejected_before_running_test(self):
        invoked = []
        class SideEffect(unittest.TestCase):
            def test_side_effect(self):
                invoked.append(True)
        with self.assertRaises(RuntimeCallPairError):
            self.observe(suite=unittest.TestSuite([SideEffect("test_side_effect")]),
                         hashes={SRC: "0" * 64, DST: self.hashes(DST)[DST]})
        self.assertEqual(invoked, [])

    def test_unsafe_or_duplicate_pairs_rejected(self):
        for pairs in ([(SRC, DST), (SRC, DST)], [("../outside.py", DST)], [(SRC, SRC)]):
            with self.subTest(pairs=pairs), self.assertRaises(RuntimeCallPairError):
                self.observe(pairs=pairs)

    def test_subtest_failures_and_errors_are_classified_in_runtime_receipt(self):
        class FailingSubtests(unittest.TestCase):
            def test_cases(self):
                with self.subTest(case="failure"):
                    self.assertEqual(1, 2)
                with self.subTest(case="later-pass"):
                    self.assertTrue(True)

        class ErrorThenFailure(unittest.TestCase):
            def test_cases(self):
                with self.subTest(case="error"):
                    raise RuntimeError("controlled subtest error")
                with self.subTest(case="later-failure"):
                    self.fail("controlled subtest failure")

        class PassingSubtests(unittest.TestCase):
            def test_cases(self):
                with self.subTest(case="pass"):
                    self.assertTrue(True)

        suite = unittest.TestSuite([
            FailingSubtests("test_cases"), ErrorThenFailure("test_cases"),
            PassingSubtests("test_cases"),
        ])
        report = self.observe(suite=suite)
        outcomes = {
            item["test_id"].split(".")[-2]: item["outcome"]
            for item in report["executed_tests"]
        }
        self.assertEqual(outcomes, {
            "FailingSubtests": "FAILED",
            "ErrorThenFailure": "ERROR",
            "PassingSubtests": "PASSED",
        })
        self.assertEqual(report["tests_run"], 3)
        self.assertFalse(report["suite_was_successful"])
        self.assertEqual(report["observed_pairs"][0]["observed_direct_python_calls"], 0)
        self.assertEqual(report["static_import_edge_traversal"], "NOT_EVALUATED")
        self.assertEqual(report["semantic_ownership"], "NOT_EVALUATED")
        self.assertIsNone(sys.getprofile())

    def test_profile_restored_after_test_failure(self):
        class Failing(unittest.TestCase):
            def test_fail(self):
                self.fail("controlled")
        self.assertIsNone(sys.getprofile())
        report = self.observe(suite=unittest.TestSuite([Failing("test_fail")]))
        self.assertIsNone(sys.getprofile())
        self.assertEqual(report["executed_tests"][0]["outcome"], "FAILED")

    def test_setup_class_error_is_not_reported_as_success(self):
        class SetupError(unittest.TestCase):
            @classmethod
            def setUpClass(cls):
                raise RuntimeError("setup failed")
            def test_never_started(self):
                self.fail("not reached")
        report = self.observe(suite=unittest.TestSuite([SetupError("test_never_started")]))
        self.assertFalse(report["suite_was_successful"])
        self.assertEqual(report["tests_run"], 0)
        self.assertEqual(report["decision"], "NOT_EVALUATED")

    def test_existing_profiler_is_not_overwritten(self):
        def existing(frame, event, arg):
            return None
        sys.setprofile(existing)
        try:
            with self.assertRaises(RuntimeCallPairError):
                self.observe()
            self.assertIs(sys.getprofile(), existing)
        finally:
            sys.setprofile(None)

    def test_changed_source_after_test_is_rejected(self):
        root = self.root
        class Mutator(unittest.TestCase):
            def test_mutate(self):
                (root / DST).write_text("def consume():\n    return 8\n")
        with self.assertRaises(RuntimeCallPairError):
            self.observe(suite=unittest.TestSuite([Mutator("test_mutate")]))


if __name__ == "__main__":
    unittest.main()
