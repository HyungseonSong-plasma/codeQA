"""#122/#93: actual C++ parser syntax must not become MOOSE ABI authority."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from codeqa.governance.language_matrix import (
    LanguageMatrixError, validate_language_matrix,
)

ROOT = Path(__file__).resolve().parents[1]


class CppParserCapabilityIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(
            (ROOT / "profiles/language-execution-matrix-v0.1.json").read_text())
        self.cpp = next(x for x in self.manifest["languages"]
                        if x["language"] == "C++/MOOSE")
        self.parser = next(x for x in self.cpp["layers"] if x["layer"] == "parser")

    def test_real_parser_declared_as_partial_source_witness(self):
        validate_language_matrix(ROOT, self.manifest)
        self.assertEqual(self.parser["status"], "PARTIAL_FIXTURE")
        self.assertEqual(self.parser["entrypoint"],
                         "codeqa.adapters.cpp_parser_evidence:parse_cpp_syntax")
        self.assertEqual(self.parser["workflow"],
                         ".github/workflows/mixed-source-conformance.yml")
        self.assertIn("NOT_EVALUATED", self.parser["limitation"])

    def test_fake_full_cpp_parser_support_rejected(self):
        self.parser["status"] = "SUPPORTED_SCOPED"
        with self.assertRaises(LanguageMatrixError):
            validate_language_matrix(ROOT, self.manifest)

    def test_existing_unrelated_workflow_not_substitutable(self):
        self.parser["workflow"] = ".github/workflows/layout.yml"
        with self.assertRaisesRegex(LanguageMatrixError, "syntax-only"):
            validate_language_matrix(ROOT, self.manifest)

    def test_reworded_claim_of_moose_dsl_certification_rejected(self):
        self.parser["limitation"] = "real pinned source and fully verified MOOSE DSL and ABI"
        with self.assertRaisesRegex(LanguageMatrixError, "syntax-only"):
            validate_language_matrix(ROOT, self.manifest)

    def test_cpp_mechanical_full_parity_rejected(self):
        mechanical = next(x for x in self.cpp["layers"]
                          if x["layer"] == "mechanical_p1p3")
        mechanical["status"] = "SUPPORTED_SCOPED"
        with self.assertRaises(LanguageMatrixError):
            validate_language_matrix(ROOT, self.manifest)

    def test_cpp_production_abi_cannot_promote_from_parser(self):
        abi = next(x for x in self.cpp["layers"] if x["layer"] == "production_abi")
        abi.update(status="PARTIAL_FIXTURE",
                   source=self.parser["source"],
                   entrypoint=self.parser["entrypoint"],
                   workflow=self.parser["workflow"])
        with self.assertRaises(LanguageMatrixError):
            validate_language_matrix(ROOT, self.manifest)


if __name__ == "__main__":
    unittest.main()
