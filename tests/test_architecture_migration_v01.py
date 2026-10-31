"""B5 adversarial static migration evidence; no automatic source rewriting."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import unittest

from codeqa.core.dependency import DependencyGraph
from codeqa.evaluation.architecture.inventory import analyze_architecture_inventory
from codeqa.evaluation.architecture.metrics import analyze_architecture_metrics
from codeqa.evaluation.architecture.opportunities import discover_architecture_opportunities
from codeqa.evaluation.architecture.scenarios import generate_virtual_layout_scenarios
from codeqa.evaluation.architecture.migration import (
    ArchitectureMigrationError, assess_architecture_migration,
)
from test_architecture_scenarios_v01 import (
    SHA, POLICY, PROFILE, SOURCES, CONCENTRATED,
)


def setup(*, extra=None, missing=(), edges=CONCENTRATED, policy=POLICY):
    sources = {
        **SOURCES,
        "src/orchard/sky/view.py":
            "from orchard.earth.model import Model\nfrom . import other\nclass View: pass\n",
        **(extra or {}),
    }
    provided = {p: v for p, v in sources.items() if p not in missing}
    inventory = analyze_architecture_inventory(SHA, sorted(sources), provided, policy)
    analyzed = tuple(sorted(p for p in provided if p.endswith(".py")))
    graph = DependencyGraph(SHA, analyzed, (), tuple(edges), ())
    metrics = analyze_architecture_metrics(inventory, graph, policy, PROFILE)
    opportunities = discover_architecture_opportunities(inventory, metrics)
    scenarios = generate_virtual_layout_scenarios(inventory, metrics, opportunities, policy)
    return inventory, scenarios, provided


class MigrationImpactTests(unittest.TestCase):
    def test_static_alias_relative_init_export_and_external_unknown(self):
        extra = {
            "src/orchard/earth/consumer.py":
                "import orchard.sky.view as alias\nimport orchard.sky.view\n"
                "from orchard.sky.view import View as Named\n"
                "from orchard.sky import view\n"
                "from orchard.sky import *\n"
                "import importlib\n"
                "x = importlib.import_module('orchard.sky.view')\n"
                "y = importlib.import_module(module_name)\n",
            "src/orchard/sky/__init__.py":
                "from .view import View\n__all__ = ['View']\n",
            "tests/test_consumer.py": "from orchard.sky.view import View\n",
            "pyproject.toml": '[project.scripts]\nrunner = "orchard.sky.view:View"\n',
            "docs/example.md": "Import orchard.sky.view for a demonstration.\n",
        }
        inv, scenarios, sources = setup(extra=extra)
        self.assertEqual(len(scenarios["candidates"]), 1)
        before = deepcopy((inv, scenarios, sources))
        report = assess_architecture_migration(inv, scenarios, sources)
        self.assertEqual((inv, scenarios, sources), before)
        self.assertEqual(report, assess_architecture_migration(inv, scenarios, sources))
        impact = report["candidates"][0]
        kinds = {site["kind"] for site in impact["observed_sites"]}
        self.assertTrue({
            "STATIC_IMPORT", "ALIASED_IMPORT", "ALIASED_FROM_IMPORT",
            "STAR_IMPORT",
            "FROM_IMPORT", "RELATIVE_IMPORT", "DYNAMIC_IMPORT_LITERAL",
            "PACKAGING_REFERENCE", "CONFIG_OR_DOC_REFERENCE",
            "TEST_OR_SCRIPT_REFERENCE",
        } <= kinds)
        self.assertIn("EXTERNAL_CONSUMERS_UNOBSERVED", impact["unknowns"])
        self.assertIn("DYNAMIC_IMPORT_TARGET_UNKNOWN", impact["unknowns"])
        self.assertIn("CLI_ENTRYPOINT_REVIEW", impact["unknowns"])
        self.assertIn("STAR_IMPORT_REVIEW", impact["unknowns"])
        self.assertIn("INIT_REEXPORT_REVIEW", impact["unknowns"])
        self.assertIn("src/orchard/sky/__init__.py", impact["initializer_export_paths"])
        self.assertGreater(impact["observed_site_count"], 5)
        self.assertEqual(impact["compatibility_status"], "NOT_EVALUATED")
        self.assertEqual(report["decision"], "NOT_EVALUATED")
        self.assertEqual(report["evidence_status"], "INCOMPLETE")
        self.assertTrue(all(s["rewrite_status"] == "REVIEW_REQUIRED"
                            for s in impact["observed_sites"]))

    def test_aliased_dynamic_imports_are_migration_consumer_witnesses(self):
        # Static evidence must include import helpers brought into scope via
        # from-imports or module aliases, without claiming runtime binding.
        inv, scenarios, sources = setup(extra={
            "src/orchard/earth/dynamic_client.py": (
                "from importlib import import_module as load\n"
                "import importlib as module_loader\n"
                "from pkgutil import resolve_name as resolve\n"
                "first = load('orchard.sky.view')\n"
                "second = module_loader.import_module('orchard.sky.view')\n"
                "third = resolve('orchard.sky.view:View')\n"
                "fourth = load(dynamic_name)\n"
            ),
            "src/orchard/earth/unrelated.py": (
                "def import_module(name): return name\n"
                "value = import_module('orchard.sky.view')\n"
            ),
        })
        impact = assess_architecture_migration(inv, scenarios, sources)["candidates"][0]
        sites = [site for site in impact["observed_sites"]
                 if site["kind"] == "DYNAMIC_IMPORT_LITERAL"]
        self.assertEqual(
            [(site["path"], site["line"], site["expression"]) for site in sites],
            [
                ("src/orchard/earth/dynamic_client.py", 4, "orchard.sky.view"),
                ("src/orchard/earth/dynamic_client.py", 5, "orchard.sky.view"),
                ("src/orchard/earth/dynamic_client.py", 6, "orchard.sky.view:View"),
            ],
        )
        self.assertIn("DYNAMIC_IMPORT_TARGET_UNKNOWN", impact["unknowns"])
        self.assertIn("DYNAMIC_IMPORT_REVIEW", impact["unknowns"])
        self.assertIn("EXTERNAL_CONSUMERS_UNOBSERVED", impact["unknowns"])
        self.assertEqual(impact["compatibility_status"], "NOT_EVALUATED")

    def test_no_question_means_no_candidate(self):
        inv, scenarios, sources = setup(edges=())
        self.assertEqual(scenarios["candidates"], [])
        report = assess_architecture_migration(inv, scenarios, sources)
        self.assertEqual(report["candidates"], [])
        self.assertEqual(report["rejected_scenarios"], [])
        self.assertEqual(report["decision"], "NOT_EVALUATED")

    def test_namespace_collision_with_package_initializer_blocks(self):
        inv, scenarios, sources = setup(extra={
            "src/orchard/earth/view/__init__.py": "x = 1\n",
        })
        self.assertEqual(len(scenarios["candidates"]), 1)
        impact = assess_architecture_migration(inv, scenarios, sources)["candidates"][0]
        self.assertEqual(impact["cost_band"], "BLOCKED")
        self.assertEqual(impact["compatibility_status"], "BLOCKED")
        self.assertEqual(impact["namespace_collisions"], ["orchard.earth.view"])

    def test_namespace_directory_shadows_child_imports_even_without_init(self):
        # B4 sees an unoccupied view.py target, but creating that module can
        # shadow the existing namespace directory and its importable child.
        inv, scenarios, sources = setup(extra={
            "src/orchard/earth/view/child.py": "value = 1\n",
        })
        self.assertEqual(len(scenarios["candidates"]), 1)
        impact = assess_architecture_migration(inv, scenarios, sources)["candidates"][0]
        self.assertEqual(impact["namespace_collisions"], ["orchard.earth.view"])
        self.assertEqual(impact["cost_band"], "BLOCKED")
        self.assertEqual(impact["compatibility_status"], "BLOCKED")
        self.assertIn("DOTTED_MODULE_NAMESPACE_COLLISION", impact["unknowns"])

    def test_similarly_named_sibling_directory_is_not_namespace_collision(self):
        inv, scenarios, sources = setup(extra={
            "src/orchard/earth/view_helpers/child.py": "value = 1\n",
        })
        impact = assess_architecture_migration(inv, scenarios, sources)["candidates"][0]
        self.assertEqual(impact["namespace_collisions"], [])
        self.assertNotEqual(impact["cost_band"], "BLOCKED")

    def test_missing_sources_do_not_claim_zero_external_references(self):
        inv, scenarios, sources = setup(extra={
            "tests/test_external.py": "from orchard.sky.view import View\n",
        })
        partial = dict(sources)
        partial.pop("tests/test_external.py")
        report = assess_architecture_migration(inv, scenarios, partial)
        self.assertIn("tests/test_external.py",
                      report["source_coverage"]["missing_read_source_texts"])
        self.assertEqual(report["candidates"][0]["confidence"], "INSUFFICIENT_EVIDENCE")
        self.assertIn("SOURCE_COVERAGE_GAPS", report["candidates"][0]["unknowns"])

    def test_mismatched_hash_or_tampered_scenario_rejected(self):
        inv, scenarios, sources = setup()
        bad = dict(sources)
        bad["src/orchard/sky/view.py"] = "pass\n"
        with self.assertRaises(ArchitectureMigrationError):
            assess_architecture_migration(inv, scenarios, bad)
        altered = deepcopy(scenarios)
        altered["candidates"][0]["path_mapping"][0]["to"] = "src/orchard/earth/fake.py"
        with self.assertRaises(ArchitectureMigrationError):
            assess_architecture_migration(inv, altered, sources)
        altered = deepcopy(scenarios)
        altered["snapshot_sha"] = "0" * 40
        with self.assertRaises(ArchitectureMigrationError):
            assess_architecture_migration(inv, altered, sources)

    def test_unread_moved_source_rejected_and_parser_gap_reported(self):
        inv, scenarios, sources = setup()
        bad = dict(sources)
        bad.pop("src/orchard/sky/view.py")
        with self.assertRaises(ArchitectureMigrationError):
            assess_architecture_migration(inv, scenarios, bad)
        inv, scenarios, sources = setup(extra={
            "tests/broken.py": "def bad(:\n",
        })
        report = assess_architecture_migration(inv, scenarios, sources)
        self.assertEqual(report["source_coverage"]["python_parse_failures"],
                         ["tests/broken.py"])
        self.assertEqual(report["candidates"][0]["confidence"], "INSUFFICIENT_EVIDENCE")

    def test_renamed_isomorphic_package_not_preseeded(self):
        new_sources = {
            p.replace("orchard", "woodland"): value.replace("orchard", "woodland")
            for p, value in SOURCES.items()
        }
        new_sources["src/woodland/sky/view.py"] = (
            "from woodland.earth.model import Model\nclass View: pass\n"
        )
        policy = deepcopy(POLICY)
        policy["scope"] = "src/woodland"
        from codeqa.core.dependency import StaticDependency
        edges = tuple(StaticDependency(
            e.source_path.replace("orchard", "woodland"),
            e.target_path.replace("orchard", "woodland"),
            e.line, e.expression.replace("orchard", "woodland"), e.execution,
        ) for e in CONCENTRATED)
        inventory = analyze_architecture_inventory(SHA, sorted(new_sources),
                                                    new_sources, policy)
        graph = DependencyGraph(SHA, tuple(sorted(new_sources)), (), edges, ())
        metrics = analyze_architecture_metrics(inventory, graph, policy, PROFILE)
        opp = discover_architecture_opportunities(inventory, metrics)
        scenarios = generate_virtual_layout_scenarios(inventory, metrics, opp, policy)
        report = assess_architecture_migration(inventory, scenarios, new_sources)
        self.assertEqual(len(report["candidates"]), 1)
        self.assertEqual(report["candidates"][0]["path_mapping"][0]["to"],
                         "src/woodland/earth/view.py")
        self.assertIn("EXTERNAL_CONSUMERS_UNOBSERVED",
                      report["candidates"][0]["unknowns"])


if __name__ == "__main__":
    unittest.main()
