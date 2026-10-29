"""Import-line entry is bounded runtime evidence, not target-resolution proof."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

from codeqa.evaluation.architecture.runtime_call_pairs import (
    RuntimeCallPairError, capture_unittest_call_pairs,
)
from codeqa.evaluation.architecture.runtime_edge_correlation import (
    RuntimeEdgeCorrelationError, correlate_b8_runtime_pairs,
)
from test_architecture_runtime_edge_correlation_v01 import inputs, seal


SRC = "src/demo/producer.py"
DST = "src/demo/consumer.py"
HEAD = "a" * 40


class ImportLineRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sources = {
            SRC: "def produce():\n    import math\n    return 7\n",
            DST: "def consume():\n    return 7\n",
        }
        for path, source in self.sources.items():
            full = self.root / path
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(source, encoding="utf-8")
        ns = {}
        exec(compile(self.sources[SRC], str(self.root / SRC), "exec"), ns)
        self.produce = ns["produce"]

    def capture(self, *, call=True, lines=None, suite=None):
        produce = self.produce

        class Sample(unittest.TestCase):
            def test_run(self):
                if call:
                    self.assertEqual(produce(), 7)

        if suite is None:
            suite = unittest.TestSuite([Sample("test_run")])
        return capture_unittest_call_pairs(
            suite,
            snapshot_sha=HEAD,
            repository_root=self.root,
            source_sha256={
                path: sha256(source.encode()).hexdigest()
                for path, source in self.sources.items()
            },
            pairs=[(SRC, DST)],
            import_witness_lines={(SRC, DST): [2] if lines is None else lines},
        )

    def test_import_line_visited_without_direct_target_call(self):
        result = self.capture()
        edge = result["observed_pairs"][0]
        self.assertEqual(edge["observed_direct_python_calls"], 0)
        self.assertEqual(edge["selected_import_lines"], [2])
        self.assertEqual(edge["import_line_scope"], [
            {"line": 2, "scope": "NESTED_OR_CONDITIONAL"}
        ])
        self.assertEqual(edge["import_line_visits"], 1)
        self.assertEqual(edge["import_line_witnesses"][0]["line"], 2)
        self.assertEqual(result["import_line_observation"], "LOCAL_PYTHON_LINE_EVENT_UNATTESTED")
        self.assertEqual(result["static_import_edge_traversal"], "NOT_EVALUATED")
        self.assertIsNone(sys.gettrace())
        self.assertIsNone(sys.getprofile())

    def test_module_top_level_import_precedes_test_time_trace(self):
        source = "import math\\ndef produce():\\n    return 7\\n"
        self.sources[SRC] = source
        (self.root / SRC).write_text(source, encoding="utf-8")
        namespace = {}
        exec(compile(source, str(self.root / SRC), "exec"), namespace)
        self.produce = namespace["produce"]
        report = self.capture(lines=[1])
        edge = report["observed_pairs"][0]
        self.assertEqual(edge["import_line_scope"], [
            {"line": 1, "scope": "MODULE_TOP_LEVEL"}
        ])
        self.assertEqual(edge["import_line_visits"], 0)
        self.assertEqual(report["decision"], "NOT_EVALUATED")

    def test_unexecuted_import_line_is_not_inferred(self):
        result = self.capture(call=False)
        edge = result["observed_pairs"][0]
        self.assertEqual(edge["import_line_visits"], 0)
        self.assertEqual(edge["import_line_witnesses"], [])
        self.assertEqual(result["decision"], "NOT_EVALUATED")

    def test_wrong_line_or_duplicate_witness_rejected_before_suite(self):
        for lines in ([1], [2, 2], [0], [999]):
            with self.subTest(lines=lines), self.assertRaises(RuntimeCallPairError):
                self.capture(lines=lines)

    def test_existing_trace_is_preserved_and_rejected(self):
        def existing(frame, event, arg):
            return existing
        sys.settrace(existing)
        try:
            with self.assertRaises(RuntimeCallPairError):
                self.capture()
            self.assertIs(sys.gettrace(), existing)
        finally:
            sys.settrace(None)

    def test_trace_restored_after_failing_suite(self):
        class Failing(unittest.TestCase):
            def test_fail(self):
                self.fail("expected failure")
        report = self.capture(suite=unittest.TestSuite([Failing("test_fail")]))
        self.assertFalse(report["suite_was_successful"])
        self.assertIsNone(sys.gettrace())
        self.assertIsNone(sys.getprofile())


class ImportLineCorrelationTests(unittest.TestCase):
    def correlated(self):
        selection, responsibility, observation = inputs()
        observation["import_line_observation"] = "LOCAL_PYTHON_LINE_EVENT_UNATTESTED"
        for index, edge in enumerate(observation["observed_pairs"]):
            edge["selected_import_lines"] = [7]
            edge["import_line_scope"] = [{"line": 7, "scope": "MODULE_TOP_LEVEL"}]
            edge["import_line_visits"] = 2 if index == 1 else 0
            edge["import_line_witnesses"] = (
                [{"test_id": "test_one", "line": 7}] if index == 1 else []
            )
            edge["import_lines_truncated"] = index == 1
        seal(observation, "observation_id")
        return selection, responsibility, observation

    def test_call_absent_import_line_present_is_separate_evidence(self):
        selection, responsibility, observation = self.correlated()
        report = correlate_b8_runtime_pairs(selection, responsibility, observation)
        self.assertEqual(report["direct_call_observed_pairs"], 1)
        self.assertEqual(report["import_line_visited_pairs"], 1)
        self.assertEqual(report["not_visited_import_line_pairs"], 1)
        self.assertEqual(report["import_line_visits"], 2)
        self.assertEqual(report["module_top_level_import_pairs"], 2)
        self.assertEqual(report["nested_or_conditional_import_pairs"], 0)
        self.assertEqual(
            [edge["import_line_observation"] for edge in report["edges"]],
            ["OBSERVED_IMPORT_LINE_ENTRY", "NOT_OBSERVED_IN_SAMPLE"],
        )
        self.assertEqual(report["static_import_edge_traversal"], "NOT_EVALUATED")

    def test_reject_forged_line_even_after_resealing(self):
        selection, responsibility, observation = self.correlated()
        changed = deepcopy(observation)
        changed["observed_pairs"][1]["import_line_witnesses"][0]["line"] = 99
        seal(changed, "observation_id")
        with self.assertRaises(RuntimeEdgeCorrelationError):
            correlate_b8_runtime_pairs(selection, responsibility, changed)

    def test_reject_forged_scope_denominator(self):
        selection, responsibility, observation = self.correlated()
        changed = deepcopy(observation)
        changed["observed_pairs"][1]["import_line_scope"][0]["line"] = 99
        seal(changed, "observation_id")
        with self.assertRaises(RuntimeEdgeCorrelationError):
            correlate_b8_runtime_pairs(selection, responsibility, changed)

    def test_reject_forged_line_denominator(self):
        selection, responsibility, observation = self.correlated()
        changed = deepcopy(observation)
        changed["observed_pairs"][1]["selected_import_lines"] = [8]
        seal(changed, "observation_id")
        with self.assertRaises(RuntimeEdgeCorrelationError):
            correlate_b8_runtime_pairs(selection, responsibility, changed)


if __name__ == "__main__":
    unittest.main()
