"""Guard B8's process-local call observer against aliased profiler replacement.

This is a lexical preflight, not a proof that dynamically resolved calls cannot
replace the profiler. Keep dynamic reflection explicitly outside its guarantee.
"""
from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PROFILE_APIS = {"setprofile", "settrace"}
PROFILE_MODULES = {"sys", "threading"}


def profiler_install_calls(source: str) -> list[tuple[int, str]]:
    """Find statically resolvable profiler setters, including import aliases."""
    tree = ast.parse(source)
    module_aliases: dict[str, str] = {}
    setter_aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in PROFILE_MODULES:
                    module_aliases[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module in PROFILE_MODULES:
            for alias in node.names:
                if alias.name in PROFILE_APIS:
                    setter_aliases[alias.asname or alias.name] = (
                        node.module + "." + alias.name
                    )
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id in setter_aliases:
            found.append((node.lineno, setter_aliases[func.id]))
        elif (isinstance(func, ast.Attribute)
              and func.attr in PROFILE_APIS
              and isinstance(func.value, ast.Name)
              and func.value.id in module_aliases):
            found.append((node.lineno, module_aliases[func.value.id] + "." + func.attr))
    return sorted(found)


class B8ProfilerAliasGuardTests(unittest.TestCase):
    def test_aliases_and_direct_imports_are_detected(self):
        sample = (
            "import sys as system\n"
            "import threading as threads\n"
            "from sys import setprofile as profile\n"
            "from threading import settrace as trace\n"
            "system.settrace(None)\n"
            "threads.setprofile(None)\n"
            "profile(None)\n"
            "trace(None)\n"
        )
        self.assertEqual(profiler_install_calls(sample), [
            (5, "sys.settrace"), (6, "threading.setprofile"),
            (7, "sys.setprofile"), (8, "threading.settrace"),
        ])

    def test_unrelated_setters_are_not_false_positives(self):
        sample = (
            "import unrelated as u\n"
            "from unrelated import setprofile as profile\n"
            "u.settrace(None)\n"
            "profile(None)\n"
            "def setprofile(value): pass\n"
            "setprofile(None)\n"
        )
        self.assertEqual(profiler_install_calls(sample), [])

    def test_b8_sample_has_no_statically_resolved_nested_observer(self):
        script = ROOT / ".github/scripts/architecture_self_diagnostic_e2e.py"
        tree = ast.parse(script.read_text(encoding="utf-8"))
        definitions = [
            node.value for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "test_patterns"
                    for target in node.targets)
        ]
        self.assertEqual(len(definitions), 1)
        patterns = ast.literal_eval(definitions[0])
        self.assertEqual(len(patterns), len(set(patterns)))
        violations = []
        for name in patterns:
            path = ROOT / "tests" / name
            self.assertTrue(path.is_file(), name)
            for line, api in profiler_install_calls(path.read_text(encoding="utf-8")):
                violations.append((name, line, api))
        self.assertEqual(violations, [], "B8 runtime sample replaces its profiler")


if __name__ == "__main__":
    unittest.main()
