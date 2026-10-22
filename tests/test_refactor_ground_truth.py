"""Frozen ground truth plus semantic equivalence checks across refactoring."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import unittest

from codeqa.core import Graph, validate_semantics
from codeqa.core.graph import SourceLocation
from codeqa.adapters import adapt_python_sources
from codeqa.evaluation.mechanical import MechanicalProfile, evaluate_mechanical
from codeqa.infrastructure.resources import ResourceRegistry


ROOT = Path(__file__).resolve().parents[1]


class GroundTruthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        registry = ResourceRegistry(ROOT)
        cls.schema = registry.load_json("ccg_schema")
        cls.profile = MechanicalProfile.from_mapping(registry.load_json("mechanical_profile"))
        cls.expected = json.loads(
            (ROOT / "fixtures/python/quality-ground-truth.expected.json").read_text()
        )
        cls.source = (ROOT / "fixtures/python/quality-ground-truth.py").read_text()

    def test_known_source_yields_exact_call_targets_and_evidence(self) -> None:
        graph = adapt_python_sources(
            {"case.py": self.source}, snapshot_id="ground-truth-1", schema=self.schema,
        )
        self.assertEqual(dict(Counter(n.kind for n in graph.nodes)), self.expected["node_kinds"])
        self.assertEqual(dict(Counter(e.kind for e in graph.edges)), self.expected["edge_kinds"])
        calls = [e for e in graph.edges if e.kind == "calls"]
        self.assertEqual([{
            "resolution": edge.resolution,
            **({"target": edge.target} if edge.target else {"target_hint": edge.target_hint}),
            "line": edge.location.start_line,
        } for edge in calls], self.expected["call_resolutions"])
        self.assertTrue(all(e.source == self.expected["source"] for e in calls))

        report = evaluate_mechanical(graph, self.profile)
        metrics = next(m for m in report.call_metrics if m.node_id == self.expected["source"])
        self.assertEqual({
            "call_sites": metrics.call_sites,
            "distinct_resolved_targets": metrics.distinct_resolved_targets,
            "unresolved_call_sites": metrics.unresolved_call_sites,
            "distinct_unresolved_hints": metrics.distinct_unresolved_hints,
            "external_dependencies": metrics.external_dependencies,
        }, self.expected["call_metrics"])
        self.assertEqual({
            "status": report.status, "analysis_status": report.analysis_status,
            "analysis_limitations": list(report.analysis_limitations),
        }, self.expected["verdict"])

    def test_many_calls_one_callee_is_not_many_distinct_dependencies(self) -> None:
        graph = adapt_python_sources(
            {"x.py": "def helper(): pass\ndef caller():\n    helper()\n    helper()\n"},
            snapshot_id="t", schema=self.schema,
        )
        report = evaluate_mechanical(graph, self.profile)
        caller = next(m for m in report.call_metrics if m.node_id.endswith("caller@2:0"))
        self.assertEqual((caller.call_sites, caller.distinct_resolved_targets), (2, 1))
        self.assertIsNone(caller.external_dependencies)

    def test_multiple_semantic_errors_preserve_stable_order_and_paths(self) -> None:
        graph = Graph.from_document({
            "schema_version": "0.1", "snapshot": {"id": "case"},
            "nodes": [
                {"id": "n", "kind": "function", "name": "a",
                 "location": {"path": "a.py", "start_line": 3, "end_line": 2},
                 "provenance": {"producer": "p", "method": "syntax"}},
                {"id": "n", "kind": "function", "name": "b",
                 "provenance": {"producer": "p", "method": "syntax"}},
            ],
            "edges": [{"source": "missing", "kind": "calls", "resolution": "resolved",
                       "target": "missing", "provenance": {"producer": "p", "method": "syntax"}}],
            "coverage": {"status": "partial", "analyzed_paths": ["a.py"],
                         "unprocessed": [{"path": "bad.py", "reason": "syntax_error"},
                                         {"path": "bad.py", "reason": "retry"}]},
            "diagnostics": [{"severity": "error", "code": "BAD", "message": "bad", "path": "../escape"}],
        })
        self.assertEqual(
            [(issue.code, issue.path) for issue in validate_semantics(graph)],
            [
                ("duplicate_unprocessed", "coverage/unprocessed/1/path"),
                ("invalid_span", "nodes/0/location"),
                ("duplicate_node_id", "nodes/1/id"),
                ("missing_source", "edges/0/source"),
                ("missing_target", "edges/0/target"),
                ("invalid_path", "diagnostics/0/path"),
            ],
        )

    def test_file_error_does_not_discard_valid_file(self) -> None:
        graph = adapt_python_sources(
            {"case.py": self.source, "failed.py": "def nope("},
            snapshot_id="partial", schema=self.schema,
        )
        self.assertEqual(graph.coverage.status, "partial")
        self.assertEqual([x.path for x in graph.coverage.unprocessed], ["failed.py"])
        self.assertEqual(len(graph.nodes), 3)

    def test_external_dependency_count_stays_unknown_despite_imports(self) -> None:
        graph = adapt_python_sources(
            {"x.py": "from pkg import util\ndef f():\n    util()\n"},
            snapshot_id="unknown", schema=self.schema,
        )
        report = evaluate_mechanical(graph, self.profile)
        self.assertEqual(report.call_metrics[0].call_sites, 1)
        self.assertEqual(report.call_metrics[0].unresolved_call_sites, 1)
        self.assertIsNone(report.call_metrics[0].external_dependencies)


if __name__ == "__main__":
    unittest.main()
