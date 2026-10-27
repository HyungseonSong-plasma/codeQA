"""Pattern captures must not yield false static import provenance (#144 B3)."""
from __future__ import annotations

import unittest

from codeqa.core.naming_internal_import_graph_v04 import (
    classify_static_import_chains, scan_module_imports,
)


ROOT_PATH = "src/codeqa/core/complexity.py"
CLIENT_PATH = "src/codeqa/core/match_client.py"
IMPORT = "from codeqa.core.complexity import ControlFlowObservation\n"


def graph_for(code: str) -> tuple[dict, dict]:
    root = scan_module_imports(
        b"class ControlFlowObservation: pass\n", path=ROOT_PATH,
    )
    client = scan_module_imports(code.encode("utf-8"), path=CLIENT_PATH)
    graph = classify_static_import_chains({
        root["module"]: root, client["module"]: client,
    })
    return client, graph


class MatchCaptureShadowTests(unittest.TestCase):
    def test_match_as_capture_overrides_import_candidate(self):
        client, graph = graph_for(
            IMPORT + "match subject:\n"
            "    case ControlFlowObservation:\n"
            "        pass\n"
        )
        self.assertEqual(graph["syntax_candidate_edges"], 0)
        self.assertEqual(graph["unresolved_target_edges"], 1)
        self.assertIn(
            "AMBIGUOUS_TARGET_MODULE_BINDING",
            {reason["reason"] for reason in client["unresolved"]},
        )

    def test_match_star_capture_overrides_import_candidate(self):
        client, graph = graph_for(
            IMPORT + "match subject:\n"
            "    case [*ControlFlowObservation]:\n"
            "        pass\n"
        )
        self.assertEqual(graph["syntax_candidate_edges"], 0)
        self.assertIn(
            "AMBIGUOUS_TARGET_MODULE_BINDING",
            {reason["reason"] for reason in client["unresolved"]},
        )

    def test_match_mapping_rest_capture_overrides_import_candidate(self):
        client, graph = graph_for(
            IMPORT + "match subject:\n"
            "    case {'key': value, **ControlFlowObservation}:\n"
            "        pass\n"
        )
        self.assertEqual(graph["syntax_candidate_edges"], 0)
        self.assertIn(
            "AMBIGUOUS_TARGET_MODULE_BINDING",
            {reason["reason"] for reason in client["unresolved"]},
        )

    def test_class_pattern_is_not_a_capture_binding(self):
        _, graph = graph_for(
            IMPORT + "match subject:\n"
            "    case ControlFlowObservation():\n"
            "        pass\n"
        )
        self.assertEqual(graph["syntax_candidate_edges"], 1)
        self.assertEqual(graph["runtime_symbol_identity"], "NOT_EVALUATED")
        self.assertFalse(graph["rename_authorized"])

    def test_function_local_capture_does_not_change_module_binding(self):
        _, graph = graph_for(
            IMPORT + "def examine(subject):\n"
            "    match subject:\n"
            "        case ControlFlowObservation:\n"
            "            return None\n"
        )
        self.assertEqual(graph["syntax_candidate_edges"], 1)
        self.assertEqual(graph["graph_completeness"], "NOT_EVALUATED")


if __name__ == "__main__":
    unittest.main()
