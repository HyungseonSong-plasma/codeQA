"""#93: optional real Rust grammar parser, not a compiler or trait resolver."""
from __future__ import annotations

from hashlib import sha256
from importlib.util import find_spec
from pathlib import Path
import unittest

from codeqa.adapters.rust_parser_evidence import (
    RustParserEvidenceError, parse_rust_syntax,
    compare_local_trait_method_spellings,
)


ROOT = Path(__file__).resolve().parents[1]
REVISION = "ce40af4ffda17feaef99f4de328c9a37b6019553"
REPOSITORY = "HyungseonSong-plasma/sol-adapter-moose"
PARSER_AVAILABLE = find_spec("tree_sitter") is not None and find_spec("tree_sitter_rust") is not None


@unittest.skipUnless(PARSER_AVAILABLE, "optional Rust parser not installed; dedicated CI must run unskipped")
class RustParserEvidenceTests(unittest.TestCase):
    def parse(self, source: bytes, **changes):
        kwargs = {
            "source_repository": REPOSITORY, "source_revision": REVISION,
            "source_path": "src/example.rs",
            "expected_source_sha256": sha256(source).hexdigest(),
        }
        kwargs.update(changes)
        return parse_rust_syntax(source, **kwargs)

    def test_real_pinned_rust_source_fixture_is_parser_backed(self):
        path = ROOT / "fixtures/rust/sol-adapter-moose/src/lib.rs.txt"
        data = path.read_bytes()
        result = self.parse(data, source_path="src/lib.rs")
        self.assertEqual(result.source_sha256, sha256(data).hexdigest())
        self.assertTrue(result.declarations)
        self.assertIn("TRAIT_IMPL_RESOLUTION_NOT_EVALUATED", result.unknowns)
        self.assertEqual(result.authority, "PARSER_SYNTAX_ONLY_NOT_COMPILER_OR_TRAIT_PROOF")

    def test_trait_and_impl_method_spelling_is_lexical_only(self):
        source = b"trait Action { fn processInput(&self); }\nstruct Engine;\nimpl Action for Engine { fn processInput(&self) {} }\n"
        result = self.parse(source)
        names = [(d.name, d.kind, d.line) for d in result.declarations]
        self.assertTrue(any(x[0] == "processInput" and x[2] == 1 for x in names))
        self.assertTrue(any(x[0] == "processInput" and x[2] == 3 for x in names))
        self.assertIn("TRAIT_IMPL_RESOLUTION_NOT_EVALUATED", result.unknowns)

    def test_macro_and_reexport_do_not_claim_resolution(self):
        result = self.parse(b"pub use crate::engine as external_engine;\nfoo!();\n")
        self.assertIn("EXTERNAL_REEXPORT_OR_ALIAS_NOT_EVALUATED", result.unknowns)
        self.assertIn("MACRO_EXPANSION_NOT_EVALUATED", result.unknowns)

    def test_raw_identifier_preserves_source_spelling(self):
        result = self.parse(b"fn r#type() {}\n")
        self.assertTrue(any(d.name == "r#type" for d in result.declarations))
        self.assertIn("RAW_IDENTIFIER_EQUIVALENCE_NOT_EVALUATED", result.unknowns)

    def test_invalid_source_fails_without_partial_declarations(self):
        with self.assertRaises(RustParserEvidenceError):
            self.parse(b"fn broken( {\n")

    def test_fabricated_source_hash_or_revision_is_rejected(self):
        with self.assertRaises(RustParserEvidenceError):
            self.parse(b"fn good() {}\n", expected_source_sha256="0" * 64)
        with self.assertRaises(RustParserEvidenceError):
            self.parse(b"fn good() {}\n", source_revision="main")

    def test_repository_and_path_must_be_scoped_and_traversal_free(self):
        source = b"fn good() {}\n"
        for repository in ("", "unqualified", "owner/repo/extra",
                           "https://github.com/owner/repo", "../repo", "./repo", "owner/..", "owner/."):
            with self.subTest(repository=repository):
                with self.assertRaisesRegex(RustParserEvidenceError, "exact source"):
                    self.parse(source, source_repository=repository)
        for path in ("../outside.rs", "src/../outside.rs", "src/./lib.rs",
                     "./lib.rs", "src//lib.rs", "/src/lib.rs"):
            with self.subTest(path=path):
                with self.assertRaisesRegex(RustParserEvidenceError, "exact source"):
                    self.parse(source, source_path=path)

    def test_oversized_source_is_rejected_before_parser(self):
        source = b" " * 1_000_001
        with self.assertRaisesRegex(RustParserEvidenceError, "exact source"):
            self.parse(source)

    def test_nested_source_line_and_producer_are_deterministic(self):
        source = b"struct Engine;\nimpl Engine {\n  fn internal_helper(&self) {}\n}\n"
        first = self.parse(source)
        second = self.parse(source)
        self.assertEqual(first.canonical_json(), second.canonical_json())
        self.assertTrue(any(d.name == "internal_helper" and d.line == 3 for d in first.declarations))
        self.assertEqual(first.producer, "tree-sitter@0.25.2/tree-sitter-rust@0.24.0")



    def test_local_trait_method_spellings_match_without_trait_proof(self):
        source = (
            b"trait Action { fn processInput(&self); fn tick(&self); }\n"
            b"struct Engine;\n"
            b"impl Action for Engine { fn tick(&self) {} fn processInput(&self) {} }\n"
        )
        report = self.parse(source)
        a = compare_local_trait_method_spellings(
            report, trait_name="Action", type_name="Engine")
        b = compare_local_trait_method_spellings(
            report, trait_name="Action", type_name="Engine")
        self.assertEqual(a.canonical_json(), b.canonical_json())
        self.assertEqual(a.status, "LEXICAL_METHOD_NAME_SET_PRESENT")
        self.assertEqual(a.declared_trait_methods, ("processInput", "tick"))
        self.assertEqual(a.absent_lexical_impl_methods, ())
        self.assertEqual(a.authorization, "NONE_SOURCE_SYNTAX_ONLY")
        self.assertIn("RUST_COMPILER_TRAIT_SATISFACTION_NOT_EVALUATED", a.unknowns)

    def test_local_missing_method_is_syntax_gap_not_compiler_verdict(self):
        report = self.parse(
            b"trait Action { fn run(&self); fn stop(&self); }\n"
            b"struct Engine;\nimpl Action for Engine { fn run(&self) {} }\n")
        result = compare_local_trait_method_spellings(
            report, trait_name="Action", type_name="Engine")
        self.assertEqual(result.status, "LEXICAL_NAMES_ABSENT_FROM_IMPL")
        self.assertEqual(result.absent_lexical_impl_methods, ("stop",))
        self.assertEqual(result.authorization, "NONE_SOURCE_SYNTAX_ONLY")

    def test_external_trait_not_promoted_to_local_match(self):
        report = self.parse(
            b"struct Engine;\nimpl external::Action for Engine { fn run(&self) {} }\n")
        result = compare_local_trait_method_spellings(
            report, trait_name="Action", type_name="Engine")
        self.assertEqual(result.status, "NOT_EVALUATED")
        self.assertIn("EXACT_LOCAL_DECLARATION_PAIR_NOT_ESTABLISHED", result.unknowns)

    def test_trait_without_impl_never_counts_as_match(self):
        report = self.parse(b"trait Action { fn run(&self); }\nstruct Engine;\n")
        result = compare_local_trait_method_spellings(
            report, trait_name="Action", type_name="Engine")
        self.assertEqual(result.status, "NOT_EVALUATED")

    def test_generic_implementation_not_guessed_as_simple_impl(self):
        report = self.parse(
            b"trait Action { fn run(&self); }\n"
            b"struct Engine<T>(T);\n"
            b"impl<T> Action for Engine<T> { fn run(&self) {} }\n")
        result = compare_local_trait_method_spellings(
            report, trait_name="Action", type_name="Engine")
        self.assertEqual(result.status, "NOT_EVALUATED")

    def test_bad_trait_identity_and_untrusted_producer_rejected(self):
        from dataclasses import replace
        report = self.parse(
            b"trait Action { fn run(&self); }\n"
            b"struct Engine;\nimpl Action for Engine { fn run(&self) {} }\n")
        for bad in ("", "external::Action", "Action<T>", "A B"):
            with self.subTest(bad=bad), self.assertRaises(RustParserEvidenceError):
                compare_local_trait_method_spellings(
                    report, trait_name=bad, type_name="Engine")
        with self.assertRaises(RustParserEvidenceError):
            compare_local_trait_method_spellings(
                replace(report, producer="unknown/parser"),
                trait_name="Action", type_name="Engine")


if __name__ == "__main__":
    unittest.main()
