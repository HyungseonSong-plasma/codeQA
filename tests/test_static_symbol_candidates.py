"""Ground truth: cross-module candidates must never become runtime certainty."""
from __future__ import annotations

from pathlib import Path
import unittest

from codeqa.infrastructure.resources import ResourceRegistry
from codeqa.pipeline.python import analyze_python


ROOT = Path(__file__).resolve().parents[1]


class StaticSymbolEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        registry = ResourceRegistry(ROOT)
        cls.schema = registry.load_json("ccg_schema")
        cls.profile = registry.load_json("mechanical_profile")

    def analyze(self, sources: dict[str, str]):
        return analyze_python(
            sources,
            snapshot_id="frozen-test-sha",
            ccg_schema=self.schema,
            mechanical_profile=self.profile,
        )

    def test_from_import_explicit_alias_has_exact_target_and_witness(self) -> None:
        result = self.analyze({
            "src/pkg/core.py": "def helper(): pass\n",
            "src/pkg/use.py": "from pkg.core import helper as h\n"
                              "def caller():\n    h()\n",
        })
        report = result.symbol_calls
        self.assertEqual(len(report.candidates), 1)
        match = report.candidates[0]
        self.assertEqual(match.import_kind, "direct_symbol_import")
        self.assertEqual(match.import_binding, "h")
        self.assertEqual(match.imported_module, "pkg.core")
        self.assertEqual(match.target_path, "src/pkg/core.py")
        self.assertEqual(match.target_node_id, "def::src/pkg/core.py::helper@1:0")
        self.assertEqual(match.source_node_id, "def::src/pkg/use.py::caller@2:0")
        self.assertEqual(match.call_line, 3)
        self.assertIn(match.evidence_id, {fact.evidence_id for fact in result.evidence.facts})
        self.assertEqual(match.assurance, "STATIC_DECLARATION_CANDIDATE_NOT_RUNTIME_TARGET")
        self.assertTrue(all(
            edge.resolution == "unresolved"
            for edge in result.graph.edges if edge.kind == "imports"
        ))

    def test_dotted_module_alias_resolves_declaration_candidate(self) -> None:
        result = self.analyze({
            "src/pkg/core.py": "def helper(): pass\n",
            "src/pkg/use.py": "import pkg.core as mod\n"
                              "def caller():\n    mod.helper()\n",
        })
        candidate = result.symbol_calls.candidates[0]
        self.assertEqual(candidate.import_kind, "module_alias")
        self.assertEqual(candidate.call_expression, "mod.helper")
        self.assertEqual(candidate.target_node_id, "def::src/pkg/core.py::helper@1:0")

    def test_unaliased_dotted_import_is_not_an_exact_module_binding(self) -> None:
        report = self.analyze({
            "src/pkg/core.py": "def helper(): pass\n",
            "src/pkg/use.py": "import pkg.core\n"
                              "def caller():\n    pkg.core.helper()\n",
        }).symbol_calls
        self.assertEqual(report.candidates, ())

    def test_relative_module_import_maps_unique_function(self) -> None:
        result = self.analyze({
            "src/pkg/core.py": "def helper(): pass\n",
            "src/pkg/use.py": "from .core import helper\n"
                              "def caller():\n    helper()\n",
        })
        self.assertEqual(len(result.symbol_calls.candidates), 1)

    def test_package_member_is_not_guessed_as_a_submodule(self) -> None:
        result = self.analyze({
            "src/pkg/__init__.py": "",
            "src/pkg/core.py": "def helper(): pass\n",
            "src/pkg/use.py": "from pkg import core\n"
                              "def caller():\n    core.helper()\n",
        })
        self.assertEqual(result.symbol_calls.candidates, ())

    def test_module_name_ambiguity_is_not_linked(self) -> None:
        result = self.analyze({
            "pkg/core.py": "def helper(): pass\n",
            "src/pkg/core.py": "def helper(): pass\n",
            "src/pkg/use.py": "from pkg.core import helper\n"
                              "def caller():\n    helper()\n",
        })
        self.assertEqual(result.symbol_calls.candidates, ())
        self.assertIn(
            ("ambiguous_or_outside_snapshot_module", 1),
            result.symbol_calls.excluded_by_reason,
        )

    def test_source_side_import_rebinding_excludes_candidate(self) -> None:
        result = self.analyze({
            "src/pkg/core.py": "def helper(): pass\n",
            "src/pkg/use.py": "from pkg.core import helper\n"
                              "helper = object()\n"
                              "def caller():\n    helper()\n",
        })
        self.assertEqual(result.symbol_calls.candidates, ())

    def test_function_parameter_and_local_shadow_are_excluded(self) -> None:
        result = self.analyze({
            "src/pkg/core.py": "def helper(): pass\n",
            "src/pkg/use.py": "from pkg.core import helper\n"
                              "def parameter(helper):\n    helper()\n"
                              "def local():\n    helper = lambda: 1\n    helper()\n",
        })
        self.assertEqual(result.symbol_calls.candidates, ())
        self.assertEqual(
            dict(result.symbol_calls.excluded_by_reason).get("locally_shadowed_binding"),
            2,
        )

    def test_decorated_or_reassigned_target_cannot_be_promoted(self) -> None:
        decorated = self.analyze({
            "src/pkg/core.py": "def deco(fn): return fn\n"
                               "@deco\n"
                               "def helper(): pass\n",
            "src/pkg/use.py": "from pkg.core import helper\n"
                              "def caller():\n    helper()\n",
        })
        reassigned = self.analyze({
            "src/pkg/core.py": "def helper(): pass\nhelper = 1\n",
            "src/pkg/use.py": "from pkg.core import helper\n"
                              "def caller():\n    helper()\n",
        })
        self.assertFalse(decorated.symbol_calls.candidates)
        self.assertFalse(reassigned.symbol_calls.candidates)

    def test_nested_import_is_not_a_module_level_binding(self) -> None:
        result = self.analyze({
            "src/pkg/core.py": "def helper(): pass\n",
            "src/pkg/use.py": "def caller():\n"
                              "    from pkg.core import helper\n"
                              "    helper()\n",
        })
        self.assertEqual(result.symbol_calls.candidates, ())

    def test_wildcard_import_suppresses_source_bindings(self) -> None:
        result = self.analyze({
            "src/pkg/core.py": "def helper(): pass\n",
            "src/pkg/use.py": "from pkg.core import helper\n"
                              "from elsewhere import *\n"
                              "def caller():\n    helper()\n",
        })
        self.assertEqual(result.symbol_calls.candidates, ())

    def test_nested_function_does_not_borrow_outer_import_binding(self) -> None:
        result = self.analyze({
            "src/pkg/core.py": "def helper(): pass\n",
            "src/pkg/use.py": "from pkg.core import helper\n"
                              "def outer():\n"
                              "    def inner():\n        helper()\n",
        })
        self.assertEqual(result.symbol_calls.candidates, ())

    def test_syntactic_cross_file_candidates_annotate_existing_context_only(self) -> None:
        source = "from pkg.core import helper\n"
        source += "def caller():\n"
        source += "    helper()\n" * 14
        result = self.analyze({
            "src/pkg/core.py": "def helper(): pass\n",
            "src/pkg/use.py": source,
        })
        self.assertEqual(len(result.symbol_calls.candidates), 14)
        review = result.contextual_review.reviews[0]
        self.assertEqual(review.cross_file_declaration_candidates, 14)
        self.assertEqual(review.call_sites, 14)
        self.assertEqual(review.unresolved_call_sites, 14)
        self.assertEqual(result.quality.status, "REVIEW_REQUIRED")
        self.assertEqual(result.symbol_calls.assurance, "STATIC_DECLARATIONS_ONLY")
        self.assertEqual(
            result.summary_document()["symbol_calls"]["cross_file_declaration_candidates"],
            14,
        )

    def test_cross_file_target_is_rechecked_per_snapshot_not_cached_globally(self) -> None:
        from codeqa.adapters import PythonAnalysisCache
        cache = PythonAnalysisCache()
        src = {
            "src/pkg/core.py": "def helper(): pass\n",
            "src/pkg/use.py": "from pkg.core import helper\n"
                              "def caller():\n    helper()\n",
        }
        first = analyze_python(src, snapshot_id="one",
            ccg_schema=self.schema, mechanical_profile=self.profile, cache=cache)
        removed = analyze_python({"src/pkg/use.py": src["src/pkg/use.py"]},
            snapshot_id="two", ccg_schema=self.schema,
            mechanical_profile=self.profile, cache=cache)
        self.assertEqual(len(first.symbol_calls.candidates), 1)
        self.assertFalse(removed.symbol_calls.candidates)
        self.assertEqual(removed.efficiency.parsed_files, 0)


if __name__ == "__main__":
    unittest.main()
