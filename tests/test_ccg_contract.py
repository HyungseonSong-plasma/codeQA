"""Conformance checks for the versioned, language-neutral CCG schema."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator

from codeqa.infrastructure.resources import ResourceRegistry


ROOT = Path(__file__).resolve().parents[1]


class CcgContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = ResourceRegistry(ROOT).load_json("ccg_schema")
        Draft202012Validator.check_schema(cls.schema)
        cls.validator = Draft202012Validator(cls.schema)

    def valid_graph(self) -> dict:
        return {
            "schema_version": "0.1",
            "snapshot": {"id": "snapshot-abc123"},
            "nodes": [
                {
                    "id": "src/example.py:function:run",
                    "kind": "function",
                    "name": "run",
                    "location": {
                        "path": "src/example.py",
                        "start_line": 1,
                        "end_line": 2,
                    },
                    "provenance": {"producer": "python-ast", "method": "syntax"},
                }
            ],
            "edges": [
                {
                    "source": "src/example.py:function:run",
                    "kind": "calls",
                    "resolution": "unresolved",
                    "target_hint": "maybe_external",
                    "provenance": {"producer": "python-ast", "method": "syntax"},
                }
            ],
            "coverage": {
                "status": "partial",
                "analyzed_paths": ["src/example.py"],
                "unprocessed": [{"path": "src/broken.py", "reason": "parse_error"}],
            },
            "diagnostics": [
                {
                    "severity": "error",
                    "code": "PARSE_ERROR",
                    "message": "cannot parse source",
                    "path": "src/broken.py",
                }
            ],
        }

    def test_schema_has_stable_version_and_identity(self) -> None:
        self.assertEqual(self.schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(self.schema["$id"], "urn:codeqa:ccg:graph:v0.1")
        self.assertEqual(self.schema["properties"]["schema_version"]["const"], "0.1")

    def test_unresolved_reference_and_partial_coverage_are_valid(self) -> None:
        self.validator.validate(self.valid_graph())

    def test_resolved_edge_must_have_target(self) -> None:
        graph = self.valid_graph()
        graph["edges"][0].pop("target_hint")
        graph["edges"][0].update({"resolution": "resolved", "target": "src/example.py:function:run"})
        self.validator.validate(graph)

    def test_resolved_edge_without_target_is_rejected(self) -> None:
        graph = self.valid_graph()
        graph["edges"][0]["resolution"] = "resolved"
        with self.assertRaises(Exception) as cm:
            self.validator.validate(graph)
        self.assertEqual(cm.exception.__class__.__name__, "ValidationError")

    def test_unresolved_edge_cannot_invent_target(self) -> None:
        graph = self.valid_graph()
        graph["edges"][0]["target"] = "fabricated-id"
        self.assertFalse(self.validator.is_valid(graph))

    def test_missing_coverage_is_rejected(self) -> None:
        graph = self.valid_graph()
        graph.pop("coverage")
        self.assertFalse(self.validator.is_valid(graph))

    def test_missing_provenance_is_rejected(self) -> None:
        for collection in ("nodes", "edges"):
            with self.subTest(collection=collection):
                graph = self.valid_graph()
                graph[collection][0].pop("provenance")
                self.assertFalse(self.validator.is_valid(graph))

    def test_invalid_schema_version_or_coverage_state_is_rejected(self) -> None:
        for edit in ("version", "coverage"):
            graph = self.valid_graph()
            if edit == "version":
                graph["schema_version"] = "0.2"
            else:
                graph["coverage"]["status"] = "PASS"
            self.assertFalse(self.validator.is_valid(graph))

    def test_unknown_quality_verdict_field_is_rejected(self) -> None:
        graph = self.valid_graph()
        graph["quality_verdict"] = "PASS"
        self.assertFalse(self.validator.is_valid(graph))


if __name__ == "__main__":
    unittest.main()
