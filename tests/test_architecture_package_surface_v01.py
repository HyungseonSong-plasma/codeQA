"""#184: package discovery is not an external import or public API guarantee."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import unittest

from codeqa.core.dependency import StaticDependency
from codeqa.evaluation.architecture.internal_consumers import census_internal_consumers
from codeqa.evaluation.architecture.opportunities import discover_architecture_opportunities
from codeqa.evaluation.architecture.package_surface import (
    PackageSurfaceEvidenceError,
    census_package_surface,
    render_package_surface_markdown,
)
from codeqa.evaluation.architecture.policy_triage import triage_cross_role_concentration
from test_architecture_opportunities_v01 import POLICY, SOURCES, make_report
from test_architecture_policy_triage_v01 import CONCENTRATED


PYPROJECT = """[project]
name = "orchard"
version = "0.1"
[tool.setuptools.packages.find]
where = ["src"]
include = ["orchard*"]
"""


def evidence(*, pyproject=PYPROJECT, edges=CONCENTRATED):
    sources = {
        **SOURCES,
        "pyproject.toml": pyproject,
        "src/orchard/__init__.py": "",
        "src/orchard/sky/__init__.py": "",
        "tests/test_view.py": "from orchard.sky.view import view\n",
    }
    if edges:
        edges = (*edges, StaticDependency(
            "tests/test_view.py", "src/orchard/sky/view.py", 1,
            "from orchard.sky.view import view", "top_level",
        ))
    inventory, metrics = make_report(
        sources=sources, edges=edges,
        analyzed=tuple(p for p in sources if p.endswith(".py")),
    )
    opportunities = discover_architecture_opportunities(inventory, metrics)
    triage = triage_cross_role_concentration(
        inventory, metrics, opportunities, POLICY,
    )
    consumers = census_internal_consumers(inventory, metrics, triage)
    return inventory, consumers


class PackageSurfaceEvidenceTests(unittest.TestCase):
    def test_declared_package_and_test_importers_are_not_public_api_proof(self):
        inv, consumers = evidence()
        report = census_package_surface(inv, consumers, PYPROJECT)
        self.assertEqual(len(report["modules"]), 2)
        self.assertEqual(report["declared_discovery_candidates"], 2)
        view = next(m for m in report["modules"]
                    if m["module_path"] == "src/orchard/sky/view.py")
        self.assertEqual(view["potential_import_name"], "orchard.sky.view")
        self.assertEqual(view["package_initializer_paths"], [
            "src/orchard/__init__.py", "src/orchard/sky/__init__.py",
        ])
        self.assertEqual(view["known_test_path_importer_pairs"], 1)
        self.assertEqual(view["declared_discovery_status"], "DECLARED_DISCOVERY_CANDIDATE")
        self.assertEqual(report["public_api_compatibility"], "NOT_EVALUATED")
        self.assertEqual(report["installed_distribution"], "NOT_EVALUATED")
        self.assertEqual(report["decision"], "NOT_EVALUATED")
        markdown = render_package_surface_markdown(report)
        self.assertIn("orchard.sky.view", markdown)
        self.assertIn("NOT supported public API", markdown)

    def test_no_signal_produces_no_preseeded_package_targets(self):
        inv, consumers = evidence(edges=())
        report = census_package_surface(inv, consumers, PYPROJECT)
        self.assertEqual(report["modules"], [])
        self.assertEqual(report["declared_discovery_candidates"], 0)
        self.assertEqual(report["decision"], "NOT_EVALUATED")

    def test_declaration_not_matching_source_scope_is_unknown(self):
        mismatched = PYPROJECT.replace('include = ["orchard*"]', 'include = ["other*"]')
        inv, consumers = evidence(pyproject=mismatched)
        report = census_package_surface(inv, consumers, mismatched)
        self.assertEqual(report["declared_discovery_candidates"], 0)
        self.assertTrue(all(
            m["declared_discovery_status"] == "NOT_EVALUATED"
            for m in report["modules"]
        ))
        self.assertEqual(report["external_consumers"], "NOT_EVALUATED")

    def test_pyproject_content_must_match_tracked_sha(self):
        inv, consumers = evidence()
        with self.assertRaises(PackageSurfaceEvidenceError):
            census_package_surface(inv, consumers, PYPROJECT + "\n# forged\n")
        self.assertEqual(
            next(f for f in inv["files"] if f["path"] == "pyproject.toml")["source_sha256"],
            sha256(PYPROJECT.encode()).hexdigest(),
        )

    def test_stale_consumer_or_modified_report_fails_closed(self):
        inv, consumers = evidence()
        stale = deepcopy(consumers)
        stale["source_identity"]["snapshot_sha"] = "f" * 40
        with self.assertRaises(PackageSurfaceEvidenceError):
            census_package_surface(inv, stale, PYPROJECT)
        report = census_package_surface(inv, consumers, PYPROJECT)
        tampered = deepcopy(report)
        tampered["declared_discovery_candidates"] = 0
        with self.assertRaises(PackageSurfaceEvidenceError):
            render_package_surface_markdown(tampered)


if __name__ == "__main__":
    unittest.main()
