"""Bounded static witnesses for #184's pipeline composition counterhypothesis.

These observations are not semantic ownership or public-consumer certification.
"""
from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "src" / "codeqa" / "pipeline" / "python.py"
ROLE_PREFIX = "codeqa."


def role_import_witnesses(source: str) -> dict[str, set[str]]:
    """Return explicit imported names by declared role; do not infer execution."""
    tree = ast.parse(source)
    roles: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            module = node.module
            if not module.startswith(ROLE_PREFIX):
                continue
            parts = module.split(".")
            if len(parts) < 3:
                continue
            role = parts[1]
            roles.setdefault(role, set()).update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if len(parts) >= 3 and parts[0] == "codeqa":
                    roles.setdefault(parts[1], set()).add(alias.name)
    return roles


def direct_call_names(source: str) -> set[str]:
    """Only syntactically direct calls, excluding dynamic dispatch and aliases."""
    return {
        node.func.id
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


class PipelineCompositionWitnessTests(unittest.TestCase):
    def test_real_pipeline_has_multi_role_imports_and_stage_calls(self) -> None:
        source = PIPELINE.read_text(encoding="utf-8")
        witnesses = role_import_witnesses(source)
        self.assertTrue({"adapters", "core", "evaluation"} <= witnesses.keys())
        self.assertIn("parse_python_snapshot", witnesses["adapters"])
        self.assertIn("evaluate_mechanical", witnesses["evaluation"])
        calls = direct_call_names(source)
        self.assertIn("parse_python_snapshot", calls)
        self.assertIn("evaluate_mechanical", calls)
        self.assertIn("adapt_parsed_python", calls)
        # Import and call witnesses support the orchestration hypothesis, but
        # do not decide whether any of the 43 edges belong in this package.

    def test_negative_fixture_does_not_invent_cross_role_edges(self) -> None:
        fixture = "from codeqa.pipeline.local import execute\nexecute()\n"
        self.assertEqual(role_import_witnesses(fixture), {"pipeline": {"execute"}})
        self.assertNotIn("adapters", role_import_witnesses(fixture))
        self.assertNotIn("evaluation", role_import_witnesses(fixture))

    def test_nested_imports_are_static_not_runtime_certification(self) -> None:
        fixture = (
            "def unreachable():\n"
            "    from codeqa.adapters.python import adapt_parsed_python\n"
            "    return adapt_parsed_python\n"
        )
        self.assertIn("adapt_parsed_python", role_import_witnesses(fixture)["adapters"])
        self.assertNotIn("adapt_parsed_python", direct_call_names(fixture))


if __name__ == "__main__":
    unittest.main()
