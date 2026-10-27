"""Real default-vs-opt-in Naming boundary and negative evidence tests (#120)."""
from __future__ import annotations

from pathlib import Path
import unittest

from jsonschema import Draft202012Validator

from codeqa.core.naming import NamingContractError
from codeqa.infrastructure.resources import ResourceRegistry
from codeqa.pipeline.naming_product import analyze_python_naming_opt_in
from codeqa.pipeline.python import analyze_python


ROOT = Path(__file__).resolve().parents[1]


class NamingProductBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.resources = ResourceRegistry(ROOT)
        cls.ccg = cls.resources.load_json("ccg_schema")
        cls.mechanical = cls.resources.load_json("mechanical_profile")
        cls.naming = cls.resources.load_json("python_naming_safe_profile")
        cls.naming_schema = cls.resources.load_json("naming_report_schema")

    def test_default_mechanical_unchanged_after_explicit_naming(self):
        sources = {"src/a.py": "class Thing:\n    def BadMethod(self):\n        return 1\n"}
        before = analyze_python(
            sources, snapshot_id="git:fixture", ccg_schema=self.ccg,
            mechanical_profile=self.mechanical,
        )
        self.assertNotIn("naming", before.to_document())
        self.assertNotIn("naming", before.summary_document())
        report = analyze_python_naming_opt_in(
            sources, snapshot_id="git:fixture", naming_profile=self.naming,
        )
        Draft202012Validator(self.naming_schema).validate(report.to_document())
        self.assertEqual(report.status, "REVIEW_REQUIRED")
        self.assertTrue(any(f.name == "BadMethod" for f in report.findings))
        after = analyze_python(
            sources, snapshot_id="git:fixture", ccg_schema=self.ccg,
            mechanical_profile=self.mechanical,
        )
        self.assertEqual(before.graph.to_document(), after.graph.to_document())
        self.assertEqual(before.quality.to_document(), after.quality.to_document())
        self.assertEqual(before.summary_document(), after.summary_document())

    def test_unresolved_external_override_is_not_compatibility_pass(self):
        sources = {"a.py": (
            "from vendor_sdk import ExternalBase\n"
            "class Child(ExternalBase):\n"
            "    def ExternalHook(self): pass\n"
        )}
        report = analyze_python_naming_opt_in(
            sources, snapshot_id="git:fixture", naming_profile=self.naming,
        )
        self.assertEqual(report.status, "NOT_EVALUATED")
        self.assertTrue(any(f.status == "NOT_EVALUATED" for f in report.findings))

    def test_invalid_profile_fails_closed(self):
        with self.assertRaises(NamingContractError):
            analyze_python_naming_opt_in(
                {"a.py": "def fine_name(): pass\n"}, snapshot_id="git:fixture",
                naming_profile={**self.naming, "schema_version": "unapproved"},
            )

    def test_empty_snapshot_rejected(self):
        with self.assertRaises(ValueError):
            analyze_python_naming_opt_in(
                {"a.py": "def fine_name(): pass\n"}, snapshot_id="",
                naming_profile=self.naming,
            )

    def test_unparseable_source_not_silently_passed(self):
        report = analyze_python_naming_opt_in(
            {"broken.py": "def ("}, snapshot_id="git:fixture",
            naming_profile=self.naming,
        )
        self.assertEqual(report.status, "NOT_EVALUATED")
        self.assertEqual(report.coverage_status, "none")


if __name__ == "__main__":
    unittest.main()
