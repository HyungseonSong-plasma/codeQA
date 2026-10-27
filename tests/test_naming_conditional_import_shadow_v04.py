"""Module-level compound bindings must not certify import provenance (#144 B3)."""
from __future__ import annotations

import unittest

from codeqa.core.naming_internal_import_graph_v04 import (
    classify_static_import_chains, scan_module_imports,
)

ROOT = "src/codeqa/core/complexity.py"
CLIENT = "src/codeqa/core/shadowed_client.py"
DIRECT = "from codeqa.core.complexity import ControlFlowObservation\n"


def inspect(code: str) -> tuple[dict, dict]:
    root = scan_module_imports(
        b"class ControlFlowObservation: pass\n", path=ROOT,
    )
    client = scan_module_imports(code.encode("utf-8"), path=CLIENT)
    result = classify_static_import_chains({
        root["module"]: root,
        client["module"]: client,
    })
    return client, result


class ConditionalImportShadowTests(unittest.TestCase):
    def assert_ambiguous(self, code: str) -> None:
        scan, graph = inspect(DIRECT + code)
        self.assertEqual(graph["syntax_candidate_edges"], 0)
        self.assertGreaterEqual(graph["unresolved_target_edges"], 1)
        self.assertIn(
            "AMBIGUOUS_TARGET_MODULE_BINDING",
            {x["reason"] for x in scan["unresolved"]},
        )
        self.assertEqual(graph["runtime_symbol_identity"], "NOT_EVALUATED")
        self.assertFalse(graph["rename_authorized"])

    def test_conditional_direct_import_is_ambiguous(self):
        self.assert_ambiguous(
            "if condition:\n"
            "    from codeqa.core.complexity import ControlFlowObservation\n"
        )

    def test_conditional_aliased_import_is_ambiguous(self):
        self.assert_ambiguous(
            "if condition:\n"
            "    from other_module import Other as ControlFlowObservation\n"
        )

    def test_conditional_module_import_alias_is_ambiguous(self):
        self.assert_ambiguous(
            "if condition:\n"
            "    import other_module as ControlFlowObservation\n"
        )

    def test_conditional_class_definition_is_ambiguous(self):
        self.assert_ambiguous(
            "if condition:\n"
            "    class ControlFlowObservation: pass\n"
        )

    def test_conditional_function_definition_is_ambiguous(self):
        self.assert_ambiguous(
            "if condition:\n"
            "    def ControlFlowObservation(): pass\n"
        )

    def test_nested_compound_declaration_is_ambiguous(self):
        self.assert_ambiguous(
            "for value in values:\n"
            "    try:\n"
            "        from other_module import Other as ControlFlowObservation\n"
            "    except ImportError:\n"
            "        pass\n"
        )

    def test_function_local_conditional_import_is_not_module_shadowing(self):
        scan, graph = inspect(
            DIRECT
            + "def check(condition):\n"
            + "    if condition:\n"
            + "        from other_module import Other as ControlFlowObservation\n"
        )
        # Existing B3 conservatively withholds static provenance for any
        # nested target import, including a function-local one.
        self.assertEqual(graph["syntax_candidate_edges"], 0)
        self.assertEqual(graph["runtime_symbol_identity"], "NOT_EVALUATED")
        self.assertFalse(graph["rename_authorized"])
        reasons = {x["reason"] for x in scan["unresolved"]}
        self.assertIn("NESTED_TARGET_IMPORT_NOT_GLOBAL", reasons)
        self.assertNotIn("AMBIGUOUS_TARGET_MODULE_BINDING", reasons)

    def test_unshadowed_direct_import_remains_candidate(self):
        _, graph = inspect(DIRECT)
        self.assertEqual(graph["syntax_candidate_edges"], 1)
        self.assertEqual(graph["graph_completeness"], "NOT_EVALUATED")


if __name__ == "__main__":
    unittest.main()
