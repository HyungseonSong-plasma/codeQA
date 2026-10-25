"""Adversarial support-surface and consumer truth boundary tests (#118)."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from codeqa.governance.support_surface import (
    SupportSurfaceError, audit_repository, audit_support_surface,
    render_support_table,
)


ROOT = Path(__file__).resolve().parents[1]


class SupportSurfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(
            (ROOT / "docs/support-surface-v0.1.json").read_text(encoding="utf-8")
        )
        cls.readme = (ROOT / "README.md").read_text(encoding="utf-8")

    def test_exact_repo_inventory_and_readme(self) -> None:
        audit_repository(ROOT)
        self.assertIn("| python_mechanical | DEFAULT_SCOPED | Python |", render_support_table(self.manifest))

    def _rejected(self, mutation) -> None:
        data = deepcopy(self.manifest)
        mutation(data)
        with self.assertRaises(SupportSurfaceError):
            audit_support_surface(ROOT, data, readme=self.readme)

    def test_unimplemented_p4_cannot_be_promoted(self) -> None:
        self._rejected(lambda d: next(f for f in d["features"] if f["id"] == "mechanical_p2_p4_p8").update(
            mode="DEFAULT_SCOPED", authority="HEURISTIC_REVIEW"
        ))

    def test_unverified_rust_cpp_moose_pipeline_cannot_pass(self) -> None:
        self._rejected(lambda d: next(f for f in d["features"] if f["id"] == "non_python_mechanical").update(
            mode="DEFAULT_SCOPED", authority="HEURISTIC_REVIEW"
        ))

    def test_formal_fixture_cannot_be_production_allow(self) -> None:
        self._rejected(lambda d: next(f for f in d["features"] if f["id"] == "formal_generated_fixture").update(
            authority="PRODUCTION_ALLOW"
        ))

    def test_missing_resource_is_not_ignored(self) -> None:
        self._rejected(lambda d: next(f for f in d["features"] if f["id"] == "python_mechanical")["resources"].pop())

    def test_invented_resource_rejected(self) -> None:
        self._rejected(lambda d: next(f for f in d["features"] if f["id"] == "python_mechanical")["resources"].append("invented_profile"))

    def test_duplicate_resource_rejected(self) -> None:
        self._rejected(lambda d: next(f for f in d["features"] if f["id"] == "python_mechanical")["resources"].append("ccg_schema"))

    def test_nonexistent_source_symbol_rejected(self) -> None:
        self._rejected(lambda d: next(f for f in d["features"] if f["id"] == "python_mechanical").update(
            entrypoint="codeqa.pipeline.python:imaginary_pipeline"
        ))

    def test_forged_release_rejected(self) -> None:
        self._rejected(lambda d: d.update(release="9.9.9"))

    def test_readme_drift_rejected(self) -> None:
        with self.assertRaises(SupportSurfaceError):
            audit_support_surface(ROOT, self.manifest, readme=self.readme.replace(
                "| python_mechanical | DEFAULT_SCOPED |",
                "| python_mechanical | PRODUCTION_PASS |",
            ))

    def test_unsafe_or_escaped_evidence_path_rejected(self) -> None:
        self._rejected(lambda d: next(f for f in d["features"] if f["id"] == "python_mechanical")["evidence"].append("../../outside"))

    def test_unknown_status_cannot_be_admitted(self) -> None:
        self._rejected(lambda d: next(f for f in d["features"] if f["id"] == "python_mechanical").update(mode="CERTIFIED"))

    def test_optional_naming_not_default(self) -> None:
        self.assertEqual(next(f for f in self.manifest["features"] if f["id"] == "python_naming_safe")["mode"], "OPT_IN")


if __name__ == "__main__":
    unittest.main()
