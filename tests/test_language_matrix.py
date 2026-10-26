"""Negative language capability promotions must fail closed (#122)."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from codeqa.governance.language_matrix import (
    LanguageMatrixError, audit_language_matrix, validate_language_matrix,
)


ROOT = Path(__file__).resolve().parents[1]


class LanguageMatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ROOT / "profiles/language-execution-matrix-v0.1.json").read_text())

    def test_current_source_witnesses(self):
        audit_language_matrix(ROOT)

    def _cell(self, data, language, layer):
        return next(c for row in data["languages"] if row["language"] == language
                    for c in row["layers"] if c["layer"] == layer)

    def _reject(self, mutator):
        data = deepcopy(self.manifest)
        mutator(data)
        with self.assertRaises(LanguageMatrixError):
            validate_language_matrix(ROOT, data)

    def test_rust_mechanical_cannot_be_marked_supported(self):
        self._reject(lambda d: self._cell(d, "Rust", "mechanical_p1p3").update(status="SUPPORTED_SCOPED"))

    def test_moose_p3_fixture_cannot_be_promoted_to_full_pipeline(self):
        self._reject(lambda d: self._cell(d, "C++/MOOSE", "mechanical_p1p3").update(status="SUPPORTED_SCOPED"))

    def test_fictional_production_abi_is_not_supported(self):
        self._reject(lambda d: self._cell(d, "Python", "production_abi").update(status="SUPPORTED_SCOPED"))

    def test_formal_fixture_cannot_be_production_support(self):
        self._reject(lambda d: self._cell(d, "Dafny-generated Python", "formal_gate").update(status="SUPPORTED_SCOPED"))

    def test_missing_real_python_source_is_rejected(self):
        self._reject(lambda d: self._cell(d, "Python", "parser").update(source="src/codeqa/adapters/imaginary.py"))

    def test_nonportable_evidence_path_rejected_before_lookup(self):
        for path in ("src/codeqa/adapters/unsafe\r.py",
                     "src/codeqa/adapters/file:stream.py",
                     "src/codeqa/adapters/trailing./module.py"):
            with self.subTest(path=repr(path)):
                data = deepcopy(self.manifest)
                self._cell(data, "Python", "parser")["source"] = path
                with self.assertRaisesRegex(LanguageMatrixError, "invalid evidence path"):
                    validate_language_matrix(ROOT, data)

    def test_missing_language_layer_rejected(self):
        self._reject(lambda d: next(row for row in d["languages"] if row["language"] == "Rust")["layers"].pop())

    def test_fake_workflow_proof_rejected(self):
        self._reject(lambda d: self._cell(d, "Python", "ccg").update(workflow=".github/workflows/nonexistent.yml"))


    def test_runtime_dispatch_can_not_be_claimed_from_python_ccg(self):
        self._reject(lambda d: self._cell(d, "Python", "ccg").update(
            limitation="verified dynamic method dispatch and runtime call resolution"
        ))

    def test_mechanical_p1p8_cannot_be_claimed_by_limitation_edit(self):
        self._reject(lambda d: self._cell(d, "Python", "mechanical_p1p3").update(
            limitation="complete P1-P8 static and semantic certification"
        ))

    def test_no_unsupported_quality_pass_enum(self):
        self._reject(lambda d: self._cell(d, "Python", "ccg").update(status="PASS"))


if __name__ == "__main__":
    unittest.main()
