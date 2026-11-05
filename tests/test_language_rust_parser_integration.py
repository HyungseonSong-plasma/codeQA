"""Retained Rust parser integration: distinguish optional syntax from supported product."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

from codeqa.governance.language_matrix import (
    LanguageMatrixError, audit_language_matrix, validate_language_matrix,
)

ROOT = Path(__file__).resolve().parents[1]


class RustParserIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(
            (ROOT / "profiles/language-execution-matrix-v0.1.json").read_text()
        )
        rust = next(x for x in self.manifest["languages"]
                    if x["language"] == "Rust")
        self.parser = next(x for x in rust["layers"] if x["layer"] == "parser")
        self.mechanical = next(x for x in rust["layers"]
                               if x["layer"] == "mechanical_p1p3")

    def test_real_optional_parser_does_not_override_capability_declaration(self):
        audit_language_matrix(ROOT)
        self.assertTrue((ROOT / "src/codeqa/adapters/rust_parser_evidence.py").is_file())
        self.assertEqual(self.parser["status"], "PARTIAL_FIXTURE")
        self.assertEqual(self.parser["source"], "tests/test_rust_ccg_reference.py")
        self.assertIsNone(self.parser["entrypoint"])
        self.assertEqual(self.parser["workflow"],
                         ".github/workflows/rust-ccg-conformance.yml")
        self.assertEqual(self.mechanical["status"], "NOT_EVALUATED")

    def test_rust_parser_cannot_be_promoted_to_full_support(self):
        self.parser["status"] = "SUPPORTED_SCOPED"
        with self.assertRaises(LanguageMatrixError):
            validate_language_matrix(ROOT, self.manifest)

    def test_rust_production_abi_not_attested(self):
        rust = next(x for x in self.manifest["languages"]
                    if x["language"] == "Rust")
        abi = next(x for x in rust["layers"] if x["layer"] == "production_abi")
        self.assertEqual(abi["status"], "NOT_EVALUATED")
        self.assertIsNone(abi["source"])
        self.assertIsNone(abi["entrypoint"])


if __name__ == "__main__":
    unittest.main()
