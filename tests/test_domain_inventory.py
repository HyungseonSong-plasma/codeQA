"""Synthetic negative controls for source-backed domain mapping (#119)."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from codeqa.core.dependency import DependencyGraph, StaticDependency, UnknownDependency
from codeqa.evaluation.domain_inventory import DomainInventoryError, analyze_domain_inventory


ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / "profiles/domain-grouping-v0.1.json").read_text())
ROLES = json.loads((ROOT / "profiles/semantic-directory-roles-v0.1.json").read_text())


class DomainInventoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sources = {
            "src/codeqa/core/naming.py": "from codeqa.core import graph\n",
            "src/codeqa/core/graph.py": "class Graph:\n    pass\n",
            "src/codeqa/evaluation/mechanical.py": "from codeqa.core.naming import NamingProfile\n",
            "src/codeqa/adapters/python.py": "from codeqa.core.graph import Graph\n",
            "src/codeqa/evaluation/formal_evidence.py": "x = 1\n",
            "src/codeqa/core/__init__.py": "from .graph import Graph\n",
            "src/codeqa/pipeline/__init__.py": "",
            "src/codeqa/governance/__init__.py": "",
            "src/codeqa/infrastructure/__init__.py": "",
        }
        self.edges = (
            StaticDependency("src/codeqa/evaluation/mechanical.py", "src/codeqa/core/naming.py", 1, "from codeqa.core.naming import NamingProfile", "top_level"),
            StaticDependency("src/codeqa/adapters/python.py", "src/codeqa/core/graph.py", 1, "from codeqa.core.graph import Graph", "top_level"),
        )

    def _graph(self, edges=None, unknown=()) -> DependencyGraph:
        return DependencyGraph(
            snapshot_id="git:fixture",
            analyzed_paths=tuple(sorted(self.sources)),
            unprocessed_paths=(),
            edges=self.edges if edges is None else edges,
            unknown=unknown,
        )

    def test_deterministic_inventory_and_explicit_ambiguity(self) -> None:
        overlapping = deepcopy(POLICY)
        overlapping["rules"][2]["pattern"] += r"|(?:^|/)formal_evidence\.py$"
        left = analyze_domain_inventory(self.sources, self._graph(), overlapping, ROLES)
        right = analyze_domain_inventory(dict(reversed(list(self.sources.items()))), self._graph(), overlapping, ROLES)
        self.assertEqual(left, right)
        by_path = {x["path"]: x for x in left["inventory"]}
        self.assertEqual(by_path["src/codeqa/evaluation/formal_evidence.py"]["domain"], "AMBIGUOUS")
        self.assertEqual(by_path["src/codeqa/core/graph.py"]["domain"], "UNCLASSIFIED")
        self.assertEqual(left["status"], "NOT_EVALUATED")
        self.assertTrue(left["init_import_candidates"])

    def test_forbidden_core_to_outer_import_is_a_violation(self) -> None:
        bad = self.edges + (
            StaticDependency("src/codeqa/core/graph.py", "src/codeqa/adapters/python.py", 1, "import codeqa.adapters.python", "top_level"),
        )
        report = analyze_domain_inventory(self.sources, self._graph(edges=bad), POLICY, ROLES)
        self.assertEqual(report["status"], "VIOLATION")
        self.assertTrue(any(x["code"] == "FORBIDDEN_ROLE_DEPENDENCY" for x in report["role_findings"]))

    def test_forbidden_evaluation_to_adapter_import_is_a_violation(self) -> None:
        bad = self.edges + (
            StaticDependency("src/codeqa/evaluation/mechanical.py", "src/codeqa/adapters/python.py", 1, "import codeqa.adapters.python", "top_level"),
        )
        report = analyze_domain_inventory(self.sources, self._graph(edges=bad), POLICY, ROLES)
        self.assertEqual(report["status"], "VIOLATION")

    def test_unknown_dynamic_import_remains_unknown(self) -> None:
        unknown = (UnknownDependency("src/codeqa/core/graph.py", 1, "__import__(name)", "dynamic_import"),)
        report = analyze_domain_inventory(self.sources, self._graph(unknown=unknown), POLICY, ROLES)
        self.assertEqual(report["unknown_reasons"], {"dynamic_import": 1})
        self.assertNotEqual(report["status"], "PASS")

    def test_duplicate_or_ambiguous_policy_not_silently_accepted(self) -> None:
        bad = deepcopy(POLICY)
        bad["rules"].append(deepcopy(bad["rules"][0]))
        with self.assertRaises(DomainInventoryError):
            analyze_domain_inventory(self.sources, self._graph(), bad, ROLES)

    def test_missing_dependency_source_rejected(self) -> None:
        with self.assertRaises(DomainInventoryError):
            analyze_domain_inventory(self.sources, DependencyGraph(
                "git:fixture", ("src/codeqa/core/graph.py",), (), (), (),
            ), POLICY, ROLES)

    def test_nonportable_product_source_paths_rejected(self) -> None:
        for bad in ("src/codeqa/core/unsafe\n.py",
                    "src/codeqa/core/file:stream.py",
                    "src/codeqa/core/trailing./name.py",
                    "src/codeqa/core/unsafe\x7f.py"):
            with self.subTest(path=repr(bad)):
                sources = {**self.sources, bad: "x = 1\n"}
                with self.assertRaisesRegex(DomainInventoryError, "product Python sources"):
                    analyze_domain_inventory(sources, self._graph(), POLICY, ROLES)

    def test_out_of_scope_dependency_rejected(self) -> None:
        bad = self.edges + (StaticDependency(
            "src/codeqa/core/graph.py", "outside.py", 1, "import outside", "top_level",
        ),)
        with self.assertRaises(DomainInventoryError):
            analyze_domain_inventory(self.sources, self._graph(edges=bad), POLICY, ROLES)


if __name__ == "__main__":
    unittest.main()
