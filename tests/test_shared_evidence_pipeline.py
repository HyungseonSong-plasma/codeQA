"""One parse, shared evidence, safe cache reuse and unified QA views."""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from codeqa.adapters import PythonAnalysisCache, adapt_python_sources, extract_python_dependencies
from codeqa.core import canonical_json
from codeqa.infrastructure.resources import ResourceRegistry
from codeqa.pipeline.python import analyze_python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SharedEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        registry = ResourceRegistry(ROOT)
        cls.schema = registry.load_json("ccg_schema")
        cls.profile = registry.load_json("mechanical_profile")

    def analyze(self, sources, **kwargs):
        return analyze_python(
            sources, snapshot_id="snapshot-test",
            ccg_schema=self.schema, mechanical_profile=self.profile, **kwargs,
        )

    def test_one_ast_parse_per_valid_python_source(self):
        from codeqa.adapters.python_snapshot import ast
        src = {
            "src/pkg/a.py": "def helper():\n    pass\n",
            "src/pkg/b.py": "from pkg.a import helper\n",
            "notes.md": "not python",
        }
        original_parse = ast.parse
        with patch("codeqa.adapters.python_snapshot.ast.parse", wraps=original_parse) as called:
            result = self.analyze(src)
        self.assertEqual(called.call_count, 2)
        self.assertEqual(result.efficiency.parsed_files, 2)
        self.assertEqual(result.efficiency.extracted_files, 2)
        self.assertEqual(result.graph.coverage.status, "partial")
        self.assertEqual(len(result.dependencies.edges), 1)

    def test_graph_and_dependencies_equal_standalone_apis(self):
        src = {
            "src/pkg/a.py": "def helper():\n    return 1\n",
            "src/pkg/b.py": "from pkg.a import helper\n\ndef run():\n    helper()\n",
        }
        new = self.analyze(src)
        graph = adapt_python_sources(src, snapshot_id="snapshot-test", schema=self.schema)
        deps = extract_python_dependencies(
            src, snapshot_id="snapshot-test", analyzed_paths=graph.coverage.analyzed_paths,
        )
        self.assertEqual(canonical_json(new.graph), canonical_json(graph))
        self.assertEqual(new.dependencies.to_document(), deps.to_document())

    def test_same_evidence_id_for_symbol_and_module_views(self):
        result = self.analyze({
            "src/pkg/a.py": "answer = 42\n",
            "src/pkg/b.py": "from pkg.a import answer\n",
        })
        module = next(x for x in result.evidence.relations
                      if x.layer == "module" and x.target == "src/pkg/a.py")
        symbol = next(x for x in result.evidence.relations if x.layer == "symbol")
        self.assertIsNotNone(module.evidence_id)
        self.assertEqual(symbol.evidence_id, module.evidence_id)
        self.assertEqual(symbol.resolution, "ccg_unresolved")
        self.assertEqual(module.resolution, "static_module_path")

    def test_local_call_evidence_is_grounded(self):
        result = self.analyze({"a.py": "def helper(): pass\ndef use(): helper()\n"})
        entry = next(x for x in result.evidence.relations
                     if x.layer == "function" and x.resolution == "ccg_resolved")
        self.assertIsNotNone(entry.evidence_id)
        self.assertIn(entry.evidence_id, {fact.evidence_id for fact in result.evidence.facts})
        self.assertTrue(entry.target.endswith("helper@1:0"))

    def test_same_line_two_imports_do_not_guess_witness(self):
        out = self.analyze({
            "src/pkg/a.py": "pass\n",
            "src/pkg/b.py": "pass\n",
            "src/pkg/use.py": "import pkg.a; import pkg.b\n",
        })
        self.assertEqual(len(out.dependencies.edges), 2)
        self.assertTrue(all(
            r.evidence_id is None for r in out.evidence.relations
            if r.layer == "module" and r.target
        ))

    def test_cache_reuses_ast_and_file_local_ccg(self):
        cache = PythonAnalysisCache()
        src = {"src/pkg/a.py": "pass\n", "src/pkg/b.py": "import pkg.a\n"}
        old = self.analyze(src, cache=cache)
        reused = self.analyze(dict(reversed(list(src.items()))), cache=cache)
        self.assertEqual((old.efficiency.parsed_files, old.efficiency.extracted_files), (2, 2))
        self.assertEqual((reused.efficiency.parsed_files, reused.efficiency.reused_parses), (0, 2))
        self.assertEqual((reused.efficiency.extracted_files, reused.efficiency.reused_extractions), (0, 2))
        self.assertEqual(canonical_json(old.graph), canonical_json(reused.graph))
        self.assertEqual(old.dependencies, reused.dependencies)

    def test_new_source_changes_resolution_even_for_cached_caller(self):
        cache = PythonAnalysisCache()
        src = {"src/pkg/user.py": "import pkg.helper\n"}
        first = self.analyze(src, cache=cache)
        self.assertFalse(first.dependencies.edges)
        after = {**src, "src/pkg/helper.py": "value = 1\n"}
        second = self.analyze(after, cache=cache)
        self.assertEqual((second.efficiency.parsed_files, second.efficiency.reused_parses), (1, 1))
        self.assertEqual((second.efficiency.extracted_files, second.efficiency.reused_extractions), (1, 1))
        self.assertEqual(second.dependencies.edges[0].target_path, "src/pkg/helper.py")
        self.assertEqual(second.dependencies, self.analyze(after).dependencies)

    def test_deleting_source_invalidates_static_link(self):
        cache = PythonAnalysisCache()
        initial = {
            "src/pkg/core.py": "x = 1\n",
            "src/pkg/consumer.py": "import pkg.core\n",
        }
        self.analyze(initial, cache=cache)
        after = self.analyze({"src/pkg/consumer.py": initial["src/pkg/consumer.py"]},
                             cache=cache)
        self.assertEqual(after.efficiency.reused_parses, 1)
        self.assertEqual(after.efficiency.reused_extractions, 1)
        self.assertFalse(after.dependencies.edges)
        self.assertIn("outside_snapshot", {x.reason for x in after.dependencies.unknown})

    def test_changed_digest_reparses_and_old_version_is_reusable(self):
        cache = PythonAnalysisCache()
        src = {"src/pkg/a.py": "def f(): pass\n"}
        self.analyze(src, cache=cache)
        modified = self.analyze({"src/pkg/a.py": "def f():\n    return 1\n"}, cache=cache)
        self.assertEqual(modified.efficiency.parsed_files, 1)
        self.assertEqual(modified.efficiency.reused_extractions, 0)
        again = self.analyze(src, cache=cache)
        self.assertEqual(again.efficiency.parsed_files, 0)
        self.assertEqual(len(again.graph.nodes), 2)

    def test_syntax_error_cached_but_is_never_analyzed(self):
        cache = PythonAnalysisCache()
        src = {"broken.py": "def wrong("}
        a = self.analyze(src, cache=cache)
        b = self.analyze(src, cache=cache)
        self.assertEqual(b.graph.coverage.status, "none")
        self.assertEqual(b.efficiency.reused_parses, 1)
        self.assertEqual(b.efficiency.reused_extractions, 0)
        self.assertEqual(a.graph.to_document(), b.graph.to_document())

    def test_impact_is_lazy(self):
        src = {"src/pkg/a.py": "pass\n", "src/pkg/b.py": "import pkg.a\n"}
        with patch("codeqa.pipeline.python.analyze_change_impact") as mocked:
            result = self.analyze(src)
            mocked.assert_not_called()
        self.assertIsNone(result.impact)
        with_impact = self.analyze(src, changed_paths=["src/pkg/a.py"])
        self.assertEqual(with_impact.impact.direct_dependents, ("src/pkg/b.py",))
        self.assertEqual(with_impact.summary_document()["impact"]["direct_candidates"], 1)

    def test_multiple_changes_share_one_impact_query(self):
        result = self.analyze({
            "src/pkg/a.py": "pass\n",
            "src/pkg/b.py": "import pkg.a\n",
            "src/pkg/c.py": "import pkg.b\n",
        }, changed_paths=["src/pkg/a.py", "src/pkg/b.py"])
        self.assertEqual(result.impact.direct_dependents, ("src/pkg/c.py",))

    def test_summary_and_complete_report_are_consistent(self):
        result = self.analyze({"src/pkg/a.py": "pass\n",
                               "src/pkg/b.py": "import pkg.a\n"})
        data = result.to_document()
        self.assertEqual(data["summary"], result.summary_document())
        self.assertEqual(data["summary"]["impact"]["status"], "NOT_REQUESTED")
        self.assertEqual(data["summary"]["dependencies"]["resolution_scope"],
                         "STATIC_MODULE_PATH_ONLY")
        self.assertEqual(data["summary"]["dependencies"]["matched_static_imports"], 1)
        for section in ("graph", "quality", "dependencies", "evidence", "efficiency"):
            self.assertIn(section, data)
        json.dumps(data)

    def test_cache_not_implicitly_global(self):
        src = {"a.py": "pass\n"}
        self.assertEqual(self.analyze(src).efficiency.parsed_files, 1)
        self.assertEqual(self.analyze(src).efficiency.parsed_files, 1)


if __name__ == "__main__":
    unittest.main()
