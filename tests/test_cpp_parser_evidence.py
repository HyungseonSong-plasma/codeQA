"""#93 pinned C++ parser source witnesses, not compiler/ABI/MOOSE grammar proof."""
from __future__ import annotations

from hashlib import sha256
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

from codeqa.adapters.cpp_parser_evidence import (
    CppParserEvidenceError, parse_cpp_syntax,
)

ROOT = Path(__file__).resolve().parents[1]
CPP = ROOT / "fixtures/cpp-override"
MOOSE = ROOT / "fixtures/mixed/cpp/PhysicsApp.C.txt"
REV = "1977ad5559e5aa7a1c8d04c83735c15e007130d5"


@unittest.skipUnless(
    importlib.util.find_spec("tree_sitter") is not None
    and importlib.util.find_spec("tree_sitter_cpp") is not None,
    "optional C++ grammar absent; independent pinned CI must run without skips",
)
class CppParserEvidenceTests(unittest.TestCase):
    def parse(self, source: bytes, *, path: str = "fixtures/valid_override.cpp",
              revision: str = REV, expected_digest: str | None = None,
              strict: bool = True):
        return parse_cpp_syntax(
            source, source_repository="HyungseonSong-plasma/moose-test-repo",
            source_revision=revision, source_path=path,
            expected_source_sha256=expected_digest or sha256(source).hexdigest(),
            require_complete_parse=strict,
        )

    def test_controlled_struct_and_methods_are_parser_witnesses(self):
        report = self.parse((CPP / "valid_override.cpp").read_bytes())
        self.assertEqual(report.parse_status, "PARSED_SYNTAX_ONLY")
        self.assertIn("Base", [x.spelling for x in report.declarations])
        self.assertIn("Child", [x.spelling for x in report.declarations])
        self.assertIn("COMPILER_OVERRIDE_AND_ABI_NOT_EVALUATED", report.unknowns)
        self.assertNotIn("PRODUCTION_ABI_VERIFIED", report.canonical_json())

    def test_semantically_invalid_override_is_not_parser_rejection(self):
        report = self.parse((CPP / "invalid_nonvirtual.cpp").read_bytes(),
                            path="fixtures/invalid_nonvirtual.cpp")
        self.assertEqual(report.parse_status, "PARSED_SYNTAX_ONLY")
        self.assertIn("COMPILER_OVERRIDE_AND_ABI_NOT_EVALUATED", report.unknowns)

    def test_real_pinned_moose_source_is_not_sdk_or_dsl_proof(self):
        report = self.parse(MOOSE.read_bytes(),
                            path="physics_app/src/base/PhysicsApp.C",
                            strict=False)
        self.assertIn(report.parse_status,
                      ("PARSED_SYNTAX_ONLY", "PARTIAL_SYNTAX_ERRORS_NOT_EVALUATED"))
        self.assertTrue(any("PhysicsApp" in d.spelling for d in report.declarations))
        self.assertIn("MOOSE_FRAMEWORK_AND_INPUT_DSL_NOT_EVALUATED", report.unknowns)
        self.assertIn("PREPROCESSOR_EXPANSION_NOT_EVALUATED", report.unknowns)

    def test_invalid_cpp_fails_closed_in_strict_mode(self):
        with self.assertRaisesRegex(CppParserEvidenceError, "incomplete C\\+\\+ syntax"):
            self.parse(b"struct Broken { void f( {", path="fixtures/broken.cpp")

    def test_partial_mode_cannot_be_mistaken_for_full_parse(self):
        report = self.parse(b"struct Broken { void f( {",
                            path="fixtures/broken.cpp", strict=False)
        self.assertEqual(report.parse_status, "PARTIAL_SYNTAX_ERRORS_NOT_EVALUATED")
        self.assertIn("SYNTAX_ERRORS_PARTIAL_SOURCE_ONLY", report.unknowns)

    def test_changed_source_digest_is_rejected(self):
        with self.assertRaisesRegex(CppParserEvidenceError, "source bytes"):
            self.parse(b"struct A {};", expected_digest="0" * 64)

    def test_unpinned_revision_and_path_traversal_are_rejected(self):
        with self.assertRaises(CppParserEvidenceError):
            self.parse(b"struct A {};", revision="main")
        with self.assertRaises(CppParserEvidenceError):
            self.parse(b"struct A {};", path="../outside.cpp")

    def test_repository_dot_segment_identity_is_rejected(self):
        source = b"struct A {};"
        for repository in ("../repo", "./repo", "owner/..", "owner/."):
            with self.subTest(repository=repository):
                with self.assertRaisesRegex(CppParserEvidenceError, "exact source"):
                    parse_cpp_syntax(
                        source, source_repository=repository,
                        source_revision=REV, source_path="fixtures/valid.cpp",
                        expected_source_sha256=sha256(source).hexdigest(),
                    )

    def test_grammar_version_drift_rejected(self):
        with patch("codeqa.adapters.cpp_parser_evidence.version", return_value="99.99"):
            with self.assertRaisesRegex(CppParserEvidenceError, "unreviewed C\\+\\+ parser"):
                self.parse(b"struct A {};")

    def test_same_bytes_and_parser_yield_deterministic_receipt(self):
        source = (CPP / "valid_covariant.cpp").read_bytes()
        self.assertEqual(self.parse(source).canonical_json(),
                         self.parse(source).canonical_json())


if __name__ == "__main__":
    unittest.main()
