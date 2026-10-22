"""Conservative local Python call binding; adversarial shadowing regression."""
from __future__ import annotations

from pathlib import Path
import unittest

from codeqa.adapters import adapt_python_sources
from codeqa.infrastructure.resources import ResourceRegistry


ROOT = Path(__file__).resolve().parents[1]


class PythonLocalResolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = ResourceRegistry(ROOT).load_json("ccg_schema")

    def calls(self, source: str, extra: dict[str, str] | None = None):
        files = {"src/a.py": source, **(extra or {})}
        graph = adapt_python_sources(files, snapshot_id="immutable-input", schema=self.schema)
        return graph, [edge for edge in graph.edges if edge.kind == "calls"]

    def test_direct_module_function_call_is_resolved_with_evidence(self) -> None:
        source = "def helper():\n    pass\n\ndef caller():\n    helper()\n"
        graph, calls = self.calls(source)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].resolution, "resolved")
        self.assertIsNone(calls[0].target_hint)
        self.assertEqual(calls[0].provenance.method, "lexical_module_binding")
        self.assertIn(calls[0].target, {n.id for n in graph.nodes})
        self.assertEqual(
            calls[0].target,
            next(n.id for n in graph.nodes if n.name == "helper"),
        )

    def test_forward_reference_uses_module_definition_index(self) -> None:
        _, calls = self.calls("def caller():\n    helper()\n\ndef helper():\n    pass\n")
        self.assertEqual(calls[0].resolution, "resolved")

    def test_direct_recursive_name_is_lexically_resolvable(self) -> None:
        _, calls = self.calls("def recurse():\n    recurse()\n")
        self.assertEqual(calls[0].resolution, "resolved")

    def test_duplicate_module_definitions_are_ambiguous(self) -> None:
        _, calls = self.calls(
            "def helper(): pass\n"
            "def helper(): pass\n"
            "def caller(): helper()\n"
        )
        self.assertEqual(calls[0].resolution, "unresolved")

    def test_module_rebinding_excludes_static_binding(self) -> None:
        _, calls = self.calls(
            "def helper(): pass\nhelper = lambda: 42\n"
            "def caller(): helper()\n"
        )
        self.assertEqual(calls[0].resolution, "unresolved")

    def test_module_import_shadow_excludes_static_binding(self) -> None:
        _, calls = self.calls(
            "def helper(): pass\nfrom package import helper\n"
            "def caller(): helper()\n"
        )
        self.assertEqual(calls[0].resolution, "unresolved")

    def test_parameter_shadow_is_not_resolved(self) -> None:
        _, calls = self.calls(
            "def helper(): pass\n"
            "def caller(helper): helper()\n"
        )
        self.assertEqual(calls[0].resolution, "unresolved")

    def test_local_assignment_shadow_is_not_resolved(self) -> None:
        _, calls = self.calls(
            "def helper(): pass\n"
            "def caller():\n    helper()\n    helper = object()\n"
        )
        self.assertEqual(calls[0].resolution, "unresolved")
        self.assertEqual(calls[0].target_hint, "helper")

    def test_dynamic_global_rebinding_is_not_resolved(self) -> None:
        _, calls = self.calls(
            "def helper(): pass\n"
            "def mutate():\n    global helper\n    helper = object()\n"
            "def caller(): helper()\n"
        )
        self.assertEqual(calls[1].resolution, "unresolved")

    def test_decorated_and_conditional_definitions_are_not_resolved(self) -> None:
        for prefix in (
            "@decorator\ndef helper(): pass\n",
            "if condition:\n    def helper(): pass\n",
        ):
            with self.subTest(prefix=prefix):
                _, calls = self.calls(prefix + "def caller(): helper()\n")
                self.assertEqual(calls[0].resolution, "unresolved")

    def test_dynamic_receivers_and_methods_are_unresolved(self) -> None:
        _, calls = self.calls(
            "def helper(): pass\n"
            "class Worker:\n"
            "    def run(self):\n"
            "        helper()\n"
            "        self.helper()\n"
        )
        self.assertTrue(all(e.resolution == "unresolved" for e in calls))

    def test_nested_function_binding_is_not_guessed(self) -> None:
        _, calls = self.calls(
            "def helper(): pass\n"
            "def outer():\n"
            "    def inner(): helper()\n"
        )
        self.assertEqual(calls[0].resolution, "unresolved")

    def test_comprehension_shadow_stays_unresolved(self) -> None:
        _, calls = self.calls(
            "def helper(): pass\n"
            "def caller(values):\n"
            "    return [helper() for helper in values]\n"
        )
        self.assertEqual(calls[0].resolution, "unresolved")

    def test_cross_file_import_is_not_guessed(self) -> None:
        _, calls = self.calls(
            "from src.b import helper\n"
            "def caller(): helper()\n",
            {"src/b.py": "def helper(): pass\n"},
        )
        self.assertEqual(calls[0].resolution, "unresolved")

    def test_wildcard_import_prevents_speculative_resolution(self) -> None:
        _, calls = self.calls(
            "from unknown_package import *\n"
            "def helper(): pass\n"
            "def caller(): helper()\n"
        )
        self.assertEqual(calls[0].resolution, "unresolved")

    def test_async_top_level_definition_can_be_lexically_linked(self) -> None:
        _, calls = self.calls(
            "async def helper(): pass\n"
            "async def caller(): await helper()\n"
        )
        self.assertEqual(calls[0].resolution, "resolved")

    def test_module_level_call_is_not_resolved_by_future_declaration(self) -> None:
        _, calls = self.calls("helper()\ndef helper(): pass\n")
        self.assertEqual(calls[0].resolution, "unresolved")


if __name__ == "__main__":
    unittest.main()
