"""#184: source-backed, in-repository Pipeline import smoke (not external API proof).

A successful import only verifies known consumers in this test environment.
It does not establish semantic ownership, distribution compatibility, or
whether a future package move is safe for external callers.
"""
from __future__ import annotations

import ast
import importlib
import inspect
from pathlib import Path
import subprocess
import unittest

from codeqa.infrastructure.git import GitReader


ROOT = Path(__file__).resolve().parents[1]
PREFIX = "codeqa.pipeline"


def _observed_pipeline_imports(source: str):
    """Extract only literal, absolute Pipeline imports from tracked Python."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 0:
            if node.module == PREFIX or (node.module or "").startswith(PREFIX + "."):
                yield node.module, tuple(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == PREFIX or alias.name.startswith(PREFIX + "."):
                    yield alias.name, ()


def _unresolved_imports(source: str):
    """Return broken literal import sites; do not execute the consumer module."""
    unresolved = []
    for module_name, names in _observed_pipeline_imports(source):
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            unresolved.append((module_name, "<module>"))
            continue
        for name in names:
            if name == "*":
                # Star exports have no statically enumerated name set here;
                # this smoke test cannot certify them.
                continue
            if hasattr(module, name):
                continue
            # ``from package import child`` may import a submodule that is not
            # yet exposed as an attribute on the parent package.
            try:
                importlib.import_module(module_name + "." + name)
            except ImportError:
                unresolved.append((module_name, name))
    return unresolved


class PipelineKnownConsumerSmokeTests(unittest.TestCase):
    def test_current_tracked_internal_consumers_resolve(self):
        reader = GitReader(ROOT)
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
        ).strip()
        observed = 0
        failures = []
        for path in sorted(reader.tracked_paths()):
            if not path.endswith(".py") or not (
                path.startswith("src/codeqa/") or path.startswith("tests/")
            ):
                continue
            source = reader.read_file(head, path).decode("utf-8")
            if PREFIX not in source:
                continue
            imports = list(_observed_pipeline_imports(source))
            observed += len(imports)
            failures.extend((path, module, symbol)
                            for module, symbol in _unresolved_imports(source))
        self.assertGreater(observed, 0, "no source-grounded Pipeline consumer evidence")
        self.assertEqual(failures, [], "known internal import surfaces must resolve")

    def test_declared_package_reexports_retain_identity(self):
        import codeqa.pipeline as public
        from codeqa.pipeline.python import PythonAnalysis, analyze_python

        self.assertIs(public.PythonAnalysis, PythonAnalysis)
        self.assertIs(public.analyze_python, analyze_python)
        self.assertEqual(set(public.__all__), {"PythonAnalysis", "analyze_python"})

    def test_known_callable_entrypoint_arguments_remain_bindable(self):
        from codeqa.pipeline.python import analyze_python
        from codeqa.pipeline.analysis_request import analyze_python_request

        inspect.signature(analyze_python).bind(
            {}, snapshot_id="git:known-consumer", ccg_schema={},
            mechanical_profile={},
        )
        inspect.signature(analyze_python_request).bind(object())

    def test_negative_controls_detect_missing_module_and_symbol(self):
        self.assertEqual(
            _unresolved_imports(
                "from codeqa.pipeline.python import __definitely_missing_export__\n"
                "import codeqa.pipeline.__definitely_missing_module__\n"
            ),
            [("codeqa.pipeline.python", "__definitely_missing_export__"),
             ("codeqa.pipeline.__definitely_missing_module__", "<module>")],
        )
        self.assertEqual(_unresolved_imports("import os\n"), [])


if __name__ == "__main__":
    unittest.main()
