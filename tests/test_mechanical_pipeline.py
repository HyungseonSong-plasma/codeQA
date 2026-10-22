"""Mechanical evaluation and complete in-memory Python pipeline integration."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from codeqa.adapters import adapt_python_sources
from codeqa.core import canonical_json
from codeqa.evaluation.mechanical import (
    MechanicalProfile, evaluate_mechanical,
)
from codeqa.infrastructure.resources import ResourceRegistry
from codeqa.pipeline.python import analyze_python


ROOT = Path(__file__).resolve().parents[1]


class MechanicalPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        registry = ResourceRegistry(ROOT)
        cls.schema = registry.load_json("ccg_schema")
        cls.profile = registry.load_json("mechanical_profile")

    def analyze(self, sources: dict[str, str], profile: dict | None = None):
        return analyze_python(
            sources,
            snapshot_id="pinned-source-snapshot",
            ccg_schema=self.schema,
            mechanical_profile=profile or self.profile,
        )

    def test_confident_pass_is_limited_to_mechanical_signals(self) -> None:
        result = self.analyze({"simple.py": "def simple():\n    return 1\n"})
        self.assertEqual(result.quality.status, "PASS")
        self.assertEqual(result.quality.function_count, 1)
        self.assertEqual(result.quality.unresolved_edges, 0)
        self.assertFalse(result.quality.findings)

    def test_unknown_calls_are_analysis_limitations_not_quality_findings(self) -> None:
        source = (ROOT / "fixtures/python/example.py").read_text(encoding="utf-8")
        result = self.analyze({"example.py": source})
        self.assertEqual(result.quality.status, "PASS")
        self.assertEqual(result.quality.analysis_status, "LIMITED")
        self.assertIn("unresolved_relationships", result.quality.analysis_limitations)
        self.assertEqual(result.quality.coverage_status, "complete")
        self.assertEqual(result.quality.unresolved_edges, 6)
        self.assertFalse(result.quality.findings)

    def test_big_function_is_review_not_proven_failure(self) -> None:
        profile = {**self.profile, "max_function_lines": 2}
        result = self.analyze({"large.py": "def big():\n    value = 1\n    return value\n"}, profile)
        self.assertEqual(result.quality.status, "REVIEW_REQUIRED")
        finding = next(f for f in result.quality.findings if f.rule_id == "function_span_review")
        self.assertEqual(finding.principle, "P1")
        self.assertEqual(finding.observed, 3)
        self.assertEqual(finding.threshold, 2)
        self.assertEqual(finding.location.path, "large.py")

    def test_call_site_count_is_explicit_review_signal(self) -> None:
        profile = {**self.profile, "max_call_sites": 1}
        result = self.analyze({"calls.py": "def run():\n    first()\n    second()\n"}, profile)
        self.assertEqual(result.quality.status, "REVIEW_REQUIRED")
        finding = next(f for f in result.quality.findings if f.rule_id == "outgoing_call_sites_review")
        self.assertEqual(finding.principle, "P3")
        self.assertEqual(finding.observed, 2)

    def test_partial_parse_reports_separate_scope_limitations(self) -> None:
        result = self.analyze({
            "good.py": "def ok():\n    pass\n",
            "bad.py": "def broken(:",
        })
        self.assertEqual(result.graph.coverage.status, "partial")
        self.assertEqual(result.quality.status, "PASS")
        self.assertEqual(result.quality.analysis_status, "LIMITED")
        self.assertIn("incomplete_source_coverage", result.quality.analysis_limitations)

    def test_no_analyzed_sources_are_not_evaluated(self) -> None:
        self.assertEqual(self.analyze({}).quality.status, "NOT_EVALUATED")
        self.assertEqual(
            self.analyze({"bad.py": "def broken("}).quality.status,
            "NOT_EVALUATED",
        )

    def test_no_functions_is_explicitly_not_evaluated(self) -> None:
        result = self.analyze({"empty.py": "answer = 42\n"})
        self.assertEqual(result.quality.status, "NOT_EVALUATED")
        self.assertIn("no_function_or_method", result.quality.not_evaluated)

    def test_missing_function_span_evidence_cannot_pass(self) -> None:
        graph = adapt_python_sources(
            {"ok.py": "def f():\n    pass\n"},
            snapshot_id="pinned", schema=self.schema,
        )
        doc = graph.to_document()
        next(node for node in doc["nodes"] if node["kind"] == "function").pop("location")
        from codeqa.core import parse_graph
        without_span = parse_graph(doc, self.schema)
        report = evaluate_mechanical(without_span, MechanicalProfile.from_mapping(self.profile))
        self.assertEqual(report.status, "NOT_EVALUATED")
        self.assertEqual(report.analysis_status, "LIMITED")
        self.assertIn("function_span_without_location", report.not_evaluated)

    def test_known_local_calls_do_not_create_analysis_uncertainty(self) -> None:
        result = self.analyze({
            "local.py": "def helper():\n    return 1\n\ndef run():\n    return helper()\n"
        })
        self.assertEqual(result.quality.status, "PASS")
        self.assertEqual(result.quality.analysis_status, "COMPLETE")
        self.assertEqual(result.quality.unresolved_edges, 0)
        self.assertEqual(result.quality.analysis_limitations, ())

    def test_threshold_finding_is_independent_of_unresolved_edges(self) -> None:
        result = self.analyze(
            {"mixed.py": "def many():\n    a()\n    b()\n"},
            {**self.profile, "max_call_sites": 1},
        )
        self.assertEqual(result.quality.status, "REVIEW_REQUIRED")
        self.assertEqual(result.quality.analysis_status, "LIMITED")
        self.assertTrue(result.quality.findings)

    def test_empty_snapshot_marks_evidence_as_none(self) -> None:
        quality = self.analyze({}).quality
        self.assertEqual(quality.status, "NOT_EVALUATED")
        self.assertEqual(quality.analysis_status, "NONE")

    def test_profile_rejects_unknown_or_invalid_fields(self) -> None:
        for value in (
            {**self.profile, "max_function_lines": True},
            {**self.profile, "max_call_sites": 0},
            {**self.profile, "unknown": 5},
            {"profile_id": "different", "max_function_lines": 10, "max_call_sites": 10},
        ):
            with self.subTest(profile=value), self.assertRaises(ValueError):
                MechanicalProfile.from_mapping(value)

    def test_graph_and_report_are_serializable_and_input_is_unchanged(self) -> None:
        sources = {"ok.py": "def f():\n    pass\n"}
        unchanged = deepcopy(sources)
        result = self.analyze(sources)
        payload = result.to_document()
        self.assertEqual(sources, unchanged)
        self.assertEqual(payload["graph"]["schema_version"], "0.1")
        self.assertEqual(payload["quality"]["profile_id"], self.profile["profile_id"])
        json.dumps(payload)
        self.assertEqual(
            canonical_json(result.graph),
            canonical_json(self.analyze(dict(reversed(list(sources.items())))).graph),
        )


if __name__ == "__main__":
    unittest.main()
