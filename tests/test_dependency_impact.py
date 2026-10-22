"""Ground-truth static module dependencies and conservative reverse impact."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from codeqa.adapters import extract_python_dependencies
from codeqa.core import DependencyGraph, canonical_json
from codeqa.evaluation.impact import analyze_change_impact
from codeqa.infrastructure.resources import ResourceRegistry
from codeqa.pipeline.python import analyze_python


ROOT = Path(__file__).resolve().parents[1]


class DependencyImpactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        registry = ResourceRegistry(ROOT)
        cls.schema = registry.load_json("ccg_schema")
        cls.profile = registry.load_json("mechanical_profile")
        cls.fixture = json.loads(
            (ROOT / "fixtures/analysis/dependency-impact-v0.1.json").read_text("utf-8")
        )

    def analyze(self, sources: dict[str, str] | None = None):
        return analyze_python(
            self.fixture["sources"] if sources is None else sources,
            snapshot_id="immutable-test-snapshot",
            ccg_schema=self.schema,
            mechanical_profile=self.profile,
        )

    def test_exact_ground_truth_module_correspondence(self) -> None:
        analysis = self.analyze()
        dep = analysis.dependencies
        self.assertIsInstance(dep, DependencyGraph)
        expected = self.fixture["expected"]
        observed = sorted({(edge.source_path, edge.target_path) for edge in dep.edges})
        self.assertEqual(observed, [tuple(pair) for pair in expected["pairs"]])
        self.assertEqual(dep.snapshot_id, analysis.graph.snapshot.id)
        # Import syntax in CCG v0.1 remains unresolved as before: independent view.
        self.assertTrue(all(e.resolution == "unresolved" for e in analysis.graph.edges
                            if e.kind == "imports"))

    def test_reverse_impact_has_direct_transitive_witnesses_and_cycle_termination(self) -> None:
        report = analyze_change_impact(
            self.analyze().dependencies, [self.fixture["expected"]["changed"]]
        )
        expected = self.fixture["expected"]
        self.assertEqual(set(report.direct_dependents), set(expected["direct"]))
        self.assertEqual(set(report.transitive_dependents), set(expected["transitive"]))
        self.assertEqual(
            next(entry for entry in report.affected if entry.path == "src/demo/cli.py").witness,
            ("src/demo/core.py", "src/demo/service.py", "src/demo/api.py", "src/demo/cli.py"),
        )
        self.assertNotIn("src/demo/core.py", {item.path for item in report.affected})
        self.assertEqual(len({item.path for item in report.affected}), len(report.affected))
        self.assertEqual(report.confidence, "STATIC_LOWER_BOUND")

    def test_duplicate_imports_are_distinct_evidence_but_not_double_counted_impact(self) -> None:
        sources = dict(self.fixture["sources"])
        sources["src/demo/service.py"] += "import demo.core\n"
        result = self.analyze(sources)
        edges = [e for e in result.dependencies.edges if e.source_path == "src/demo/service.py"]
        self.assertEqual(len(edges), 2)
        impact = analyze_change_impact(result.dependencies, ["src/demo/core.py"])
        self.assertEqual(impact.direct_dependents.count("src/demo/service.py"), 1)

    def test_symbol_import_does_not_invent_submodule_link(self) -> None:
        edges = [edge for edge in self.analyze().dependencies.edges
                 if edge.source_path == "src/demo/attribute.py"]
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0].target_path, "src/demo/__init__.py")

    def test_conditional_import_is_potential_not_guaranteed_execution(self) -> None:
        edges = [edge for edge in self.analyze().dependencies.edges
                 if edge.source_path == "src/demo/conditional.py"]
        self.assertEqual(edges[0].execution, "conditional_or_deferred")
        top = [e for e in self.analyze().dependencies.edges
               if e.source_path == "src/demo/service.py"]
        self.assertEqual(top[0].execution, "top_level")

    def test_dynamic_and_outside_snapshot_imports_are_unknown(self) -> None:
        graph = self.analyze().dependencies
        by_path = {(x.source_path, x.reason) for x in graph.unknown}
        self.assertIn(("src/demo/runtime.py", "dynamic_import"), by_path)
        self.assertIn(("src/demo/external.py", "outside_snapshot"), by_path)
        self.assertFalse(any(e.source_path == "src/demo/runtime.py"
                             and e.target_path == "src/demo/core.py" for e in graph.edges))
        impact = analyze_change_impact(graph, ["src/demo/core.py"])
        self.assertIn("src/demo/runtime.py", impact.unknown_dependency_sources)
        self.assertNotIn("src/demo/runtime.py",
                         set(impact.direct_dependents) | set(impact.transitive_dependents))

    def test_multiple_changes_are_seeded_simultaneously_without_false_dependents(self) -> None:
        report = analyze_change_impact(
            self.analyze().dependencies,
            ["src/demo/core.py", "src/demo/service.py", "src/demo/core.py"],
        )
        self.assertNotIn("src/demo/service.py", [x.path for x in report.affected])
        self.assertIn("src/demo/test_support.py", report.direct_dependents)
        self.assertIn("src/demo/api.py", report.direct_dependents)

    def test_ambiguous_module_mapping_has_no_fabricated_edge(self) -> None:
        sources = {
            "src/demo/core.py": "x = 1\n",
            "demo/core.py": "x = 2\n",
            "src/demo/user.py": "import demo.core\n",
        }
        result = self.analyze(sources)
        self.assertFalse(result.dependencies.edges)
        self.assertEqual(
            [(x.expression, x.reason) for x in result.dependencies.unknown],
            [("import demo.core", "ambiguous")],
        )

    def test_invalid_relative_import_is_not_silently_resolved(self) -> None:
        result = self.analyze({"src/demo/a.py": "from ....outside import thing\n"})
        self.assertEqual(result.dependencies.edges, ())
        self.assertEqual(result.dependencies.unknown[0].reason, "invalid_relative")

    def test_unindexable_file_can_still_link_absolute_module_import(self) -> None:
        sources = {
            "src/demo/core.py": "x = 1\n",
            ".github/scripts/qa.py": "import demo.core\n",
        }
        result = self.analyze(sources)
        self.assertEqual(
            [(edge.source_path, edge.target_path) for edge in result.dependencies.edges],
            [(".github/scripts/qa.py", "src/demo/core.py")],
        )

    def test_partial_parse_and_unknown_changed_file_are_not_falsely_cleared(self) -> None:
        sources = {
            "src/demo/core.py": "pass\n",
            "src/demo/broken.py": "def broken(:\n",
            "README.md": "not python",
        }
        result = self.analyze(sources)
        report = analyze_change_impact(
            result.dependencies, ["src/demo/broken.py", "README.md"]
        )
        self.assertEqual(result.graph.coverage.status, "partial")
        self.assertEqual(report.unprocessed_paths, ("README.md", "src/demo/broken.py"))
        self.assertEqual(report.untracked_changed_paths, ("README.md", "src/demo/broken.py"))
        self.assertEqual(report.confidence, "STATIC_LOWER_BOUND")

    def test_invalid_or_empty_change_request_fails_closed(self) -> None:
        deps = self.analyze().dependencies
        for values in ([], ["../oops.py"], ["/abs.py"], ["a//b.py"], ["a\\b.py"]):
            with self.subTest(values=values), self.assertRaises(ValueError):
                analyze_change_impact(deps, values)

    def test_snapshot_and_source_order_determinism(self) -> None:
        source = self.fixture["sources"]
        reversed_source = dict(reversed(list(source.items())))
        original = self.analyze(source)
        reordered = self.analyze(reversed_source)
        self.assertEqual(original.dependencies.to_document(), reordered.dependencies.to_document())
        self.assertEqual(
            analyze_change_impact(original.dependencies, ["src/demo/core.py"]).to_document(),
            analyze_change_impact(reordered.dependencies, ["src/demo/core.py"]).to_document(),
        )

    def test_existing_ccg_and_quality_do_not_change_as_side_effect(self) -> None:
        inputs = deepcopy(self.fixture["sources"])
        result = self.analyze(inputs)
        self.assertEqual(inputs, self.fixture["sources"])
        self.assertEqual(result.quality.status, "PASS")
        self.assertEqual(canonical_json(result.graph), canonical_json(self.analyze(inputs).graph))
        exported = result.to_document()
        self.assertIn("dependencies", exported)
        self.assertIn("quality", exported)
        json.dumps(exported)
        self.assertIsNone(
            result.quality.call_metrics[0].external_dependencies
            if result.quality.call_metrics else None
        )


if __name__ == "__main__":
    unittest.main()
