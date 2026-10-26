"""Cross-boundary negative controls: a coherent table must not create authority."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from codeqa.governance.support_surface import (
    SupportSurfaceError, audit_support_surface, render_support_table,
)

ROOT = Path(__file__).resolve().parents[1]


class SupportSurfaceEscalationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ROOT / "docs/support-surface-v0.1.json").read_text())
        cls.readme = (ROOT / "README.md").read_text()

    def assert_rejected_even_with_matching_readme(self, change):
        manifest = deepcopy(self.manifest)
        change({f["id"]: f for f in manifest["features"]})
        coherent_readme = self.readme.replace(
            render_support_table(self.manifest), render_support_table(manifest)
        )
        with self.assertRaises(SupportSurfaceError):
            audit_support_surface(ROOT, manifest, readme=coherent_readme)

    def test_adopted_naming_v05_stays_exact_field_opt_in(self):
        self.assert_rejected_even_with_matching_readme(
            lambda f: f["official_naming_v05_exact_field"].update(
                mode="DEFAULT_SCOPED", authority="HEURISTIC_REVIEW"
            )
        )
        self.assert_rejected_even_with_matching_readme(
            lambda f: f["official_naming_v05_exact_field"].update(
                scope="ALL_INTERNAL_DECLARATIONS"
            )
        )
        self.assert_rejected_even_with_matching_readme(
            lambda f: f["official_naming_v05_exact_field"].update(
                entrypoint="codeqa.evaluation.naming:evaluate_naming",
                source="src/codeqa/evaluation/naming.py",
            )
        )

    def test_second_default_pipeline_is_not_implicitly_authorized(self):
        self.assert_rejected_even_with_matching_readme(
            lambda f: f["mechanical_companions"].update(
                mode="DEFAULT_SCOPED", authority="HEURISTIC_REVIEW"
            )
        )

    def test_second_scoped_gate_is_not_implicitly_authorized(self):
        self.assert_rejected_even_with_matching_readme(
            lambda f: f["mechanical_companions"].update(authority="SCOPED_GATE")
        )

    def test_second_formal_fixture_cannot_be_promoted(self):
        self.assert_rejected_even_with_matching_readme(
            lambda f: f["semantic_companions"].update(
                mode="FIXTURE_ONLY", authority="FIXTURE_ONLY"
            )
        )

    def test_default_pipeline_cannot_be_repointed_to_existing_naming_symbol(self):
        self.assert_rejected_even_with_matching_readme(
            lambda f: f["python_mechanical"].update(
                source="src/codeqa/evaluation/naming.py",
                entrypoint="codeqa.evaluation.naming:evaluate_naming",
            )
        )

    def test_safe_naming_cannot_claim_rust_via_manifest_only(self):
        self.assert_rejected_even_with_matching_readme(
            lambda f: f["python_naming_safe"].update(languages=["Rust"])
        )

    def test_formal_fixture_cannot_repoint_to_gate_implementation(self):
        self.assert_rejected_even_with_matching_readme(
            lambda f: f["formal_generated_fixture"].update(
                source="src/codeqa/evaluation/evidence_gate.py",
                entrypoint="codeqa.evaluation.evidence_gate:evaluate_gate",
            )
        )


if __name__ == "__main__":
    unittest.main()
