"""#36: static dependency graph degree and SCC conformance."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import unittest

from codeqa.adapters.python_dependencies import extract_python_dependencies
from codeqa.core.dependency import DependencyGraph, StaticDependency, UnknownDependency
from codeqa.evaluation.dependency_metrics import (
    DependencyMetricsError, DependencyMetricsProfile, evaluate_dependency_metrics,
)
from codeqa.infrastructure.resources import ResourceRegistry


ROOT = Path(__file__).resolve().parents[1]


class StaticDependencyMetricTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = DependencyMetricsProfile.from_mapping(
            ResourceRegistry(ROOT).load_json("dependency_metrics_profile")
        )

    def evaluate(self, sources):
        names = tuple(sorted(sources))
        graph = extract_python_dependencies(sources, snapshot_id="sha:pinned",
                                            analyzed_paths=names)
        return evaluate_dependency_metrics(graph, self.profile)

    def test_distinct_neighbors_not_duplicate_import_statement_counts(self):
        report = self.evaluate({
            "src/a.py": "import b\nimport b\nif flag:\n    import b\n",
            "src/b.py": "pass\n",
        })
        a = next(f for f in report.files if f.path == "src/a.py")
        b = next(f for f in report.files if f.path == "src/b.py")
        self.assertEqual((a.fan_out, a.fan_in), (1, 0))
        self.assertEqual((b.fan_out, b.fan_in), (0, 1))
        self.assertEqual(report.pairs[0].statement_count, 3)
        self.assertEqual(report.pairs[0].conditional_or_deferred_count, 1)
        self.assertEqual(report.pairs[0].witness_lines, (1, 2, 4))
        self.assertFalse(report.cycles)

    def test_static_cycles_have_real_edges_and_deterministic_witnesses(self):
        sources = {
            "src/a.py": "import b\n",
            "src/b.py": "import c\n",
            "src/c.py": "import a\n",
            "src/d.py": "pass\n",
        }
        report = self.evaluate(sources)
        self.assertEqual(len(report.cycles), 1)
        cycle = report.cycles[0]
        self.assertEqual(cycle.nodes, ("src/a.py", "src/b.py", "src/c.py"))
        self.assertEqual(cycle.witness[0], cycle.witness[-1])
        links = {(e.source_path, e.target_path) for e in report.pairs}
        self.assertTrue(all((a, b) in links for a, b in zip(cycle.witness, cycle.witness[1:])))
        self.assertEqual(report.to_document(),
                         self.evaluate(dict(reversed(list(sources.items())))).to_document())
        self.assertEqual(report.interpretation, "STATIC_POTENTIAL_ONLY")

    def test_self_loop_is_explicit_in_synthetic_language_neutral_graph(self):
        deps = DependencyGraph("sha:1", ("a.py",), (), (
            StaticDependency("a.py", "a.py", 1, "import self", "top_level"),
        ), ())
        report = evaluate_dependency_metrics(deps, self.profile)
        self.assertEqual(report.cycles[0].witness, ("a.py", "a.py"))
        self.assertEqual((report.files[0].fan_in, report.files[0].fan_out), (1, 1))

    def test_unknown_is_not_imputed_to_outdegree(self):
        report = self.evaluate({
            "src/a.py": "import outside\nfrom . import missing\n__import__('b')\n",
            "src/b.py": "pass\n",
        })
        a = next(f for f in report.files if f.path == "src/a.py")
        self.assertEqual(a.fan_out, 0)
        self.assertGreaterEqual(a.unknown_statements, 2)
        self.assertEqual(sum(dict(report.unknown_by_reason).values()), a.unknown_statements)
        self.assertFalse(report.cycles)

    def test_profile_is_versioned_and_strict(self):
        for change in (
            {"schema_version": "0.2"},
            {"max_out_degree_review": -1},
            {"max_cycle_nodes_review": True},
            {"added_option": "invalid"},
        ):
            with self.subTest(change=change), self.assertRaises(DependencyMetricsError):
                DependencyMetricsProfile.from_mapping({
                    **ResourceRegistry(ROOT).load_json("dependency_metrics_profile"),
                    **change,
                })
        self.assertEqual(self.profile.schema_version, "0.1")

    def test_partial_coverage_and_unprocessed_sources_cannot_be_hidden(self):
        graph = DependencyGraph(
            "sha:pinned", ("a.py",), ("bad.py",),
            (), (UnknownDependency("a.py", 3, "import x", "outside_snapshot"),),
        )
        report = evaluate_dependency_metrics(graph, self.profile)
        self.assertEqual(report.unprocessed_paths, ("bad.py",))
        self.assertEqual(report.unknown_by_reason, (("outside_snapshot", 1),))
        for damaged in (
            DependencyGraph("sha", ("a.py",), ("a.py",), (), ()),
            DependencyGraph("sha", ("a.py",), (), (
                StaticDependency("a.py", "not-present.py", 1, "import y", "top_level"),
            ), ()),
            DependencyGraph("sha", ("../escape.py",), (), (), ()),
            DependencyGraph("sha", ("a.py",), (), (), (
                UnknownDependency("external.py", 1, "import x", "unseen"),)),
        ):
            with self.subTest(damaged=damaged), self.assertRaises(DependencyMetricsError):
                evaluate_dependency_metrics(damaged, self.profile)

    def test_does_not_mutate_existing_dependency_facts(self):
        sources = {"src/a.py": "import b\n", "src/b.py": "pass\n"}
        deps = extract_python_dependencies(sources, snapshot_id="sha", analyzed_paths=tuple(sources))
        original = deepcopy(deps)
        evaluate_dependency_metrics(deps, self.profile)
        self.assertEqual(original, deps)


if __name__ == "__main__":
    unittest.main()
