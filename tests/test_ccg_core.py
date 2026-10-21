"""CCG Core v0.1 model, semantic integrity, and deterministic serialization."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from codeqa.core import (
    Graph, GraphValidationError, canonical_json, parse_graph, validate_semantics,
)
from codeqa.infrastructure.resources import ResourceRegistry


ROOT = Path(__file__).resolve().parents[1]


def sample() -> dict:
    return {
        "schema_version": "0.1",
        "snapshot": {"id": "snapshot:abc123"},
        "nodes": [
            {
                "id": "a:run", "kind": "function", "name": "run",
                "location": {"path": "a.py", "start_line": 3, "end_line": 4},
                "provenance": {"producer": "python-ast", "method": "syntax"},
            },
            {
                "id": "a:other", "kind": "function", "name": "other",
                "location": {"path": "a.py", "start_line": 6, "end_line": 6,
                             "start_column": 1, "end_column": 7},
                "provenance": {"producer": "python-ast", "method": "syntax"},
            },
        ],
        "edges": [
            {
                "source": "a:run", "kind": "calls", "resolution": "resolved",
                "target": "a:other",
                "provenance": {"producer": "python-ast", "method": "symbol_resolution"},
            },
            {
                "source": "a:other", "kind": "calls", "resolution": "unresolved",
                "target_hint": "external_function",
                "location": {"path": "a.py", "start_line": 6, "end_line": 6},
                "provenance": {"producer": "python-ast", "method": "syntax"},
            },
        ],
        "coverage": {
            "status": "partial",
            "analyzed_paths": ["a.py"],
            "unprocessed": [{"path": "broken.py", "reason": "parse_error"}],
        },
        "diagnostics": [{
            "severity": "error", "code": "PARSE_ERROR",
            "message": "syntax error", "path": "broken.py",
        }],
    }


class CcgCoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = ResourceRegistry(ROOT).load_json("ccg_schema")

    def parse(self, document: dict) -> Graph:
        return parse_graph(document, self.schema)

    def assert_issue(self, document: dict, expected_code: str) -> None:
        with self.assertRaises(GraphValidationError) as context:
            self.parse(document)
        self.assertIn(expected_code, {issue.code for issue in context.exception.issues})

    def test_model_roundtrips_without_mutation(self) -> None:
        document = sample()
        graph = self.parse(document)
        self.assertIsInstance(graph, Graph)
        self.assertEqual(graph.to_document(), document)
        self.assertEqual(validate_semantics(graph), ())
        self.assertEqual(graph.to_document(), document)
        self.assertEqual(canonical_json(graph), canonical_json(self.parse(graph.to_document())))

    def test_unresolved_reference_preserves_observed_hint(self) -> None:
        edge = self.parse(sample()).edges[1]
        self.assertEqual(edge.resolution, "unresolved")
        self.assertEqual(edge.target_hint, "external_function")
        self.assertIsNone(edge.target)

    def test_schema_rejects_new_version_ast_and_invented_target(self) -> None:
        document = sample()
        document["schema_version"] = "0.2"
        self.assert_issue(document, "schema_violation")
        document = sample()
        document["nodes"][0]["ast"] = {"FunctionDef": "run"}
        self.assert_issue(document, "schema_violation")
        document = sample()
        document["edges"][1]["target"] = "a:other"
        self.assert_issue(document, "schema_violation")

    def test_invalid_schema_is_not_accepted(self) -> None:
        with self.assertRaises(GraphValidationError) as context:
            parse_graph(sample(), {"type": "unrecognized"})
        self.assertEqual(context.exception.issues[0].code, "invalid_schema")

    def test_node_ids_must_be_unique(self) -> None:
        document = sample()
        document["nodes"][1]["id"] = "a:run"
        self.assert_issue(document, "duplicate_node_id")

    def test_edge_sources_and_resolved_targets_must_exist(self) -> None:
        for field, expected in (("source", "missing_source"), ("target", "missing_target")):
            with self.subTest(field=field):
                document = sample()
                document["edges"][0][field] = "not-a-node"
                self.assert_issue(document, expected)

    def test_rejects_inverted_source_span(self) -> None:
        document = sample()
        document["nodes"][0]["location"]["end_line"] = 2
        self.assert_issue(document, "invalid_span")
        document = sample()
        document["nodes"][1]["location"]["end_column"] = 0
        self.assert_issue(document, "invalid_span")

    def test_paths_must_be_snapshot_relative(self) -> None:
        for path in ("../escape.py", "/absolute.py", "a//b.py", "C:/win.py", "a\\b.py"):
            with self.subTest(path=path):
                document = sample()
                document["coverage"]["analyzed_paths"][0] = path
                self.assert_issue(document, "invalid_path")

    def test_fact_source_must_be_in_analyzed_coverage(self) -> None:
        document = sample()
        document["nodes"][0]["location"]["path"] = "broken.py"
        self.assert_issue(document, "uncovered_fact")

    def test_complete_cannot_contain_unprocessed_paths(self) -> None:
        document = sample()
        document["coverage"]["status"] = "complete"
        self.assert_issue(document, "coverage_status")

    def test_partial_requires_both_analyzed_and_unprocessed(self) -> None:
        document = sample()
        document["coverage"]["unprocessed"] = []
        self.assert_issue(document, "coverage_status")

    def test_none_cannot_contain_analyzed_paths_or_facts(self) -> None:
        document = sample()
        document["coverage"]["status"] = "none"
        document["coverage"]["analyzed_paths"] = []
        self.assert_issue(document, "coverage_status")

    def test_complete_empty_snapshot_is_possible(self) -> None:
        document = sample()
        document["nodes"] = []
        document["edges"] = []
        document["diagnostics"] = []
        document["coverage"] = {"status": "complete", "analyzed_paths": [], "unprocessed": []}
        self.parse(document)

    def test_repeated_unprocessed_and_overlapping_paths_fail(self) -> None:
        document = sample()
        document["coverage"]["unprocessed"].append({"path": "broken.py", "reason": "retry_failed"})
        self.assert_issue(document, "duplicate_unprocessed")
        document = sample()
        document["coverage"]["unprocessed"].append({"path": "a.py", "reason": "failed"})
        self.assert_issue(document, "coverage_overlap")

    def test_diagnostics_cannot_use_unsafe_path(self) -> None:
        document = sample()
        document["diagnostics"][0]["path"] = "../../etc"
        self.assert_issue(document, "invalid_path")

    def test_canonical_json_is_independent_of_array_order(self) -> None:
        document = sample()
        canonical = canonical_json(self.parse(document))
        shuffled = deepcopy(document)
        shuffled["nodes"].reverse()
        shuffled["edges"].reverse()
        shuffled["diagnostics"].append({
            "severity": "info", "code": "INFO", "message": "hint",
        })
        forward = canonical_json(self.parse(shuffled))
        shuffled["diagnostics"].reverse()
        self.assertEqual(forward, canonical_json(self.parse(shuffled)))
        self.assertNotEqual(canonical, forward)
        self.assertEqual(canonical, canonical_json(self.parse(json.loads(canonical))))

    def test_model_is_immutable(self) -> None:
        graph = self.parse(sample())
        with self.assertRaises((AttributeError, TypeError)):
            graph.nodes[0].id = "changed"


if __name__ == "__main__":
    unittest.main()
