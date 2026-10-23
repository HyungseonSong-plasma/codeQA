"""#24: reproducible, pinned Samuel AST-to-CCG fixture and negative controls.

These fixtures are byte-identical pinned *source*, not executed Python modules.
Only syntax-grounded graph evidence is asserted; no runtime/quality verdict.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha1
import json
from pathlib import Path
import re
import unittest

from codeqa.adapters import adapt_python_sources
from codeqa.adapters.capability import validate_adapter_capability
from codeqa.core import GraphValidationError, canonical_json
from codeqa.infrastructure.resources import ResourceRegistry


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "fixtures/samuel/provenance.json"


def git_blob_sha(content: bytes) -> str:
    return sha1(f"blob {len(content)}\0".encode("ascii") + content).hexdigest()


class SamuelPinnedConformance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        registry = ResourceRegistry(ROOT)
        cls.schema = registry.load_json("ccg_schema")
        cls.capabilities = validate_adapter_capability(
            registry.load_json("python_adapter_capability"),
            registry.load_json("adapter_capability_schema"),
        )
        cls.sources = {}
        for spec in cls.manifest["files"]:
            raw = (ROOT / spec["fixture"]).read_bytes()
            if git_blob_sha(raw) != spec["git_blob_sha"]:
                raise AssertionError("Samuel source fixture lost exact Git blob identity")
            cls.sources[spec["path"]] = raw.decode("utf-8")

    def graph(self, sources=None):
        return adapt_python_sources(
            self.sources if sources is None else sources,
            snapshot_id=self.manifest["snapshot_id"], schema=self.schema,
        )

    def test_pinned_repository_and_source_identity(self):
        self.assertEqual(self.manifest["source_repository"],
                         "HyungseonSong-plasma/chatgpt-operation")
        sha = self.manifest["commit_sha"]
        self.assertEqual(sha, "9b335e3fbb9c5e8e323e382daeec56fa25336822")
        self.assertEqual(self.manifest["snapshot_id"],
                         f"git:HyungseonSong-plasma/chatgpt-operation@{sha}")
        self.assertEqual(len(self.sources), 3)
        self.assertEqual(self.capabilities["input"]["acquisition"], "caller_supplied")

    def test_definitions_have_exact_ground_truth_lines_and_defines_edges(self):
        graph = self.graph()
        self.assertEqual(graph.coverage.status, "complete")
        self.assertEqual(graph.coverage.analyzed_paths, tuple(sorted(self.sources)))
        ids = {node.id for node in graph.nodes}
        for spec in self.manifest["files"]:
            self.assertIn("file::" + spec["path"], ids)
            source_lines = self.sources[spec["path"]].splitlines()
            for expected in spec["definitions"]:
                with self.subTest(file=spec["path"], symbol=expected["name"]):
                    line = source_lines[expected["line"]-1]
                    self.assertTrue(
                        re.match(rf"^(class|(?:async )?def) {re.escape(expected['name'])}\b", line),
                        line,
                    )
                    matched = [node for node in graph.nodes
                               if node.kind == expected["kind"]
                               and node.name == expected["name"]
                               and node.location is not None
                               and node.location.path == spec["path"]
                               and node.location.start_line == expected["line"]]
                    self.assertEqual(len(matched), 1)
                    self.assertTrue(any(e.kind == "defines" and e.target == matched[0].id
                                        and e.resolution == "resolved" for e in graph.edges))

    def test_samuel_imports_are_syntax_grounded_and_unresolved(self):
        graph = self.graph()
        runtime = next(spec for spec in self.manifest["files"]
                       if spec["path"].endswith("/runtime.py"))
        for item in runtime["unresolved_imports"]:
            with self.subTest(item=item):
                imports = [e for e in graph.edges
                           if e.kind == "imports" and e.target_hint == item["hint"]
                           and e.resolution == "unresolved" and e.target is None
                           and e.location and e.location.path == runtime["path"]
                           and e.location.start_line == item["line"]]
                self.assertEqual(len(imports), 1)
        # A matched module path is NOT a resolved runtime import edge.
        self.assertTrue(all(e.resolution == "unresolved" and e.target is None
                            for e in graph.edges if e.kind == "imports"))

    def test_identical_source_has_deterministic_graph_and_safe_call_targets(self):
        left = self.graph()
        right = self.graph(dict(reversed(tuple(self.sources.items()))))
        self.assertEqual(canonical_json(left), canonical_json(right))
        self.assertTrue(all(e.kind != "calls" or e.resolution == "unresolved"
                            or e.target.startswith("def::" + e.location.path + "::")
                            for e in left.edges))

    def test_adversarial_import_async_decorator_and_dynamic_calls(self):
        source = (
            "from .pkg import thing as renamed\n"
            "import another as alias\n"
            "if flag:\n    from . import *\n"
            "@deco(lambda: not_extracted())\n"
            "async def task():\n    return getattr(obj, 'fn')()\n"
        )
        graph = self.graph({"sub/odd name.py": source})
        self.assertEqual(graph.coverage.status, "complete")
        hints = {edge.target_hint for edge in graph.edges if edge.kind == "imports"}
        self.assertEqual(hints, {".pkg.thing", "another", "..*"})
        self.assertTrue(all(e.resolution == "unresolved" for e in graph.edges
                            if e.kind == "imports"))
        self.assertTrue(any(n.name == "task" and n.kind == "function"
                            for n in graph.nodes))
        self.assertFalse(any(e.kind == "calls" and e.target_hint == "not_extracted"
                             for e in graph.edges))
        self.assertTrue(any(e.kind == "calls" and e.target_hint == "getattr"
                            for e in graph.edges))

    def test_partial_none_coverage_and_unsafe_paths_fail_closed(self):
        broken = {"okay.py": "def good(): pass\n", "broken.py": "def (",
                  "foreign.rs": "fn main() {}"}
        graph = self.graph(broken)
        self.assertEqual(graph.coverage.status, "partial")
        self.assertEqual(set(graph.coverage.analyzed_paths), {"okay.py"})
        self.assertEqual({(u.path, u.reason) for u in graph.coverage.unprocessed},
                         {("broken.py", "syntax_error"), ("foreign.rs", "unsupported_extension")})
        self.assertEqual(self.graph({"bad.py": "def ("}).coverage.status, "none")
        for path in ("../escape.py", "/absolute.py", "x\\y.py"):
            with self.subTest(path=path):
                with self.assertRaises(GraphValidationError):
                    self.graph({path: "x()"})


if __name__ == "__main__":
    unittest.main()
