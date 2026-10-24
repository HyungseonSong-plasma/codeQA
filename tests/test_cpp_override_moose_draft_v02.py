"""#73 compiler-backed synthetic C++ override fixtures (not MOOSE SDK)."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import unittest

from codeqa.evaluation.moose_dsl_naming_v02 import (
    MooseNamingContractError, classify_moose_identifier,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures/cpp-override"
PROFILE = ROOT / "profiles/cpp-moose-naming-v0.2-draft.json"
EXPECTED = {
    "valid_override.cpp": True,
    "valid_covariant.cpp": True,
    "invalid_no_base_member.cpp": False,
    "invalid_overload.cpp": False,
    "invalid_nonvirtual.cpp": False,
    "invalid_noexcept_mismatch.cpp": False,
    "invalid_return_type.cpp": False,
    "invalid_const_mismatch.cpp": False,
}


class CppOverrideFixtureTests(unittest.TestCase):
    def test_compiler_matrix_when_toolchain_is_available(self):
        compilers = [path for path in
                     (shutil.which("g++"), shutil.which("clang++")) if path]
        if not compilers:
            self.skipTest("no C++ compiler available; NOT_EVALUATED")
        for compiler in compilers:
            version = subprocess.run(
                [compiler, "--version"], capture_output=True,
                text=True, timeout=15, check=False)
            self.assertEqual(version.returncode, 0)
            self.assertTrue(version.stdout.strip())
            for filename, expected in EXPECTED.items():
                with self.subTest(compiler=compiler, source=filename):
                    result = subprocess.run(
                        [compiler, "-std=c++17", "-fsyntax-only",
                         "-Werror", str(FIXTURES / filename)],
                        capture_output=True, text=True, timeout=15, check=False)
                    self.assertEqual(result.returncode == 0, expected,
                        (filename, compiler, version.stdout.splitlines()[0],
                         result.stderr[:800]))
                    if not expected:
                        self.assertTrue(result.stderr.strip())

    def test_declared_dsl_keywords_are_case_sensitive(self):
        profile = json.loads(PROFILE.read_text(encoding="utf-8"))
        self.assertEqual(classify_moose_identifier(profile, "Kernels"),
                         "PRESERVE_DECLARED_RESERVED_KEY")
        self.assertEqual(classify_moose_identifier(profile, "kernels"),
                         "NOT_EVALUATED")
        self.assertEqual(classify_moose_identifier(profile, "SomeCustomKey"),
                         "NOT_EVALUATED")

    def test_no_grammar_or_sdk_proof_is_fabricated(self):
        profile = json.loads(PROFILE.read_text(encoding="utf-8"))
        for field in ("cpp_parser_status", "moose_grammar_status",
                      "moose_framework_revision_status"):
            self.assertEqual(profile[field], "NOT_EVALUATED")
        copy = dict(profile, moose_grammar_status="VERIFIED")
        with self.assertRaises(MooseNamingContractError):
            classify_moose_identifier(copy, "Kernels")
        copy = dict(profile, automatic_rename=True)
        with self.assertRaises(MooseNamingContractError):
            classify_moose_identifier(copy, "Kernels")


if __name__ == "__main__":
    unittest.main()
