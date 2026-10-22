"""End-to-end Python AST extraction into a validated CCG v0.1 document."""
from __future__ import annotations

from pathlib import Path
import unittest

from codeqa.adapters import adapt_python_sources
from codeqa.core import GraphValidationError, canonical_json
from codeqa.infrastructure.resources import ResourceRegistry


ROOT = Path(__file__).resolve().parents[1]


class PythonAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = ResourceRegistry(ROOT).load_json("ccg_schema")
        cls.source = (ROOT / "fixtures/python/example.py").read_text(encoding="utf-8")

    def adapt(self, sources: dict[str, str]):
        return adapt_python_sources(sources, snapshot_id="pinned-snapshot", schema=self.schema)

    def test_file_class_function_method_and_containment(self) -> None:
        graph = self.adapt({"project/example.py": self.source})
        self.assertEqual(graph.coverage.status, "complete")
        self.assertEqual({n.kind for n in graph.nodes}, {"file", "class", "method", "function"})
        self.assertEqual(len(graph.nodes), 4)
        definitions = [e for e in graph.edges if e.kind == "defines"]
        self.assertEqual(len(definitions), 3)
        node_ids = {n.id for n in graph.nodes}
        self.assertTrue(all(e.source in node_ids and e.target in node_ids for e in definitions))
        method = next(n for n in graph.nodes if n.kind == "method")
        parent = next(n for n in graph.nodes if n.kind == "class")
        self.assertTrue(any(e.source == parent.id and e.target == method.id for e in definitions))

    def test_unknown_import_calls_and_inheritance_stay_unresolved(self) -> None:
        graph = self.adapt({"project/example.py": self.source})
        unresolved = [e for e in graph.edges if e.resolution == "unresolved"]
        self.assertEqual(len(unresolved), 6)
        self.assertEqual(
            {e.target_hint for e in unresolved},
            {"os", "pkg.helper", "Base", "assist", "self.trace", "run_external"},
        )
        self.assertTrue(all(e.target is None for e in unresolved))

    def test_bad_file_does_not_prevent_good_file(self) -> None:
        graph = self.adapt({
            "good.py": self.source,
            "bad.py": "def broken(:\n    pass\n",
            "unsupported.cpp": "int main() {}",
        })
        self.assertEqual(graph.coverage.status, "partial")
        self.assertEqual(graph.coverage.analyzed_paths, ("good.py",))
        self.assertEqual(
            {(e.path, e.reason) for e in graph.coverage.unprocessed},
            {("bad.py", "syntax_error"), ("unsupported.cpp", "unsupported_extension")},
        )
        self.assertEqual(graph.diagnostics[0].code, "PYTHON_SYNTAX_ERROR")

    def test_all_bad_and_empty_inputs_are_not_complete(self) -> None:
        self.assertEqual(self.adapt({"broken.py": "def ("}).coverage.status, "none")
        self.assertEqual(self.adapt({}).coverage.status, "none")

    def test_duplicate_function_names_get_distinct_stable_ids(self) -> None:
        source = "def f():\n    pass\n\ndef f():\n    pass\n"
        graph = self.adapt({"a.py": source})
        ids = [node.id for node in graph.nodes if node.kind == "function"]
        self.assertEqual(len(set(ids)), 2)
        self.assertEqual(canonical_json(graph), canonical_json(self.adapt({"a.py": source})))

    def test_nested_definitions_preserve_evidence(self) -> None:
        graph = self.adapt({"n.py": "def outer():\n    def inner():\n        return ping()\n"})
        self.assertEqual(len([n for n in graph.nodes if n.kind == "function"]), 2)
        unresolved = [e for e in graph.edges if e.kind == "calls"]
        self.assertEqual(len(unresolved), 1)
        self.assertEqual(unresolved[0].target_hint, "ping")
        self.assertEqual(unresolved[0].location.path, "n.py")

    def test_graph_is_independent_of_input_mapping_order(self) -> None:
        first = self.adapt({"b.py": "x()", "a.py": "y()"})
        second = self.adapt({"a.py": "y()", "b.py": "x()"})
        self.assertEqual(canonical_json(first), canonical_json(second))

    def test_path_traversal_is_rejected_by_core(self) -> None:
        with self.assertRaises(GraphValidationError):
            self.adapt({"../escape.py": "x()"})

    def test_no_source_execution(self) -> None:
        # A syntax-only adapter must not execute code as it scans.
        graph = self.adapt({"x.py": "raise RuntimeError('should not execute')"})
        self.assertEqual(graph.coverage.status, "complete")


if __name__ == "__main__":
    unittest.main()
