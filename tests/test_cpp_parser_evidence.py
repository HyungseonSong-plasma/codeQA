"""#93 pinned C++ parser source witnesses, not compiler/ABI/MOOSE grammar proof."""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
import shutil
import subprocess
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


    def test_nested_namespace_class_owner_is_not_overwritten(self):
        source = b"""namespace outer {
namespace inner {
struct Box { int value; void run() {} };
}
}
namespace other { struct Box { void run() {} }; }
"""
        report = self.parse(source)
        got = {(x.kind, x.spelling, x.container) for x in report.declarations}
        self.assertIn(("function_definition", "run", "outer::inner::Box"), got)
        self.assertIn(("function_definition", "run", "other::Box"), got)
        self.assertIn(("field", "value", "outer::inner::Box"), got)

    def test_method_declarations_and_overloads_keep_owner(self):
        source = b"""namespace n {
struct Engine {
  Engine() {}
  ~Engine() {}
  void run(int);
  void run(double);
};
}
"""
        report = self.parse(source)
        methods = [d for d in report.declarations if d.spelling == "run"]
        self.assertEqual(len(methods), 2)
        self.assertTrue(all(d.kind == "method_declaration" for d in methods))
        self.assertTrue(all(d.container == "n::Engine" for d in methods))
        self.assertTrue(any(d.spelling == "Engine" for d in report.declarations))
        self.assertTrue(any(d.spelling == "~Engine" for d in report.declarations))

    def test_out_of_class_qualified_definition_is_not_resolved(self):
        source = b"""namespace outer {
struct Engine { void run(); };
void Engine::run() {}
}
"""
        report = self.parse(source)
        self.assertTrue(any(
            x.kind == "function_definition"
            and x.spelling == "Engine::run" and x.container == "outer"
            for x in report.declarations
        ))
        self.assertIn("QUALIFIED_MEMBER_BINDING_NOT_EVALUATED", report.unknowns)

    def test_free_function_prototype_and_nested_namespace(self):
        source = b"""void global_run(int);
namespace tools { void local_run(double); }
"""
        report = self.parse(source)
        self.assertTrue(any(x.kind == "function_declaration"
                            and x.spelling == "global_run" and x.container is None
                            for x in report.declarations))
        self.assertTrue(any(x.kind == "function_declaration"
                            and x.spelling == "local_run" and x.container == "tools"
                            for x in report.declarations))

    def test_macro_spelling_is_not_expansion_or_abi_proof(self):
        source = b"""#define FUNCTION_NAME generated
void FUNCTION_NAME() {}
"""
        report = self.parse(source)
        self.assertTrue(any(x.kind == "macro_definition"
                            and x.spelling == "FUNCTION_NAME"
                            for x in report.declarations))
        self.assertIn("PREPROCESSOR_EXPANSION_NOT_EVALUATED", report.unknowns)
        self.assertIn("DEPENDENCY_HEADERS_AND_MACROS_NOT_RESOLVED", report.unknowns)

    def test_anonymous_namespace_keeps_distinct_lexical_owner(self):
        source = b"""namespace { struct Hidden { void work() {} }; }
"""
        report = self.parse(source)
        self.assertTrue(any(
            x.spelling == "work"
            and x.container == "<unnamed-namespace_definition@1>::Hidden"
            for x in report.declarations
        ))
        self.assertIn("UNNAMED_OWNER_SCOPE_NOT_EVALUATED", report.unknowns)

    def test_template_or_extern_c_does_not_promote_semantics(self):
        source = b"""template <typename T> struct Box { T value; };
extern "C" int c_api() { return 0; }
"""
        report = self.parse(source)
        self.assertTrue(any(x.kind == "struct" and x.spelling == "Box"
                            for x in report.declarations))
        self.assertIn("TEMPLATE_BINDING_NOT_EVALUATED", report.unknowns)
        self.assertIn("EXPORT_VISIBILITY_AND_ABI_NOT_EVALUATED", report.unknowns)
        self.assertIn("DYNAMIC_PUBLIC_CONSUMERS_NOT_EVALUATED", report.unknowns)


    def test_clang_ast_independent_declaration_oracle(self):
        """Compare the *same bytes* using Clang and tree-sitter, without ABI claims."""
        clang = shutil.which("clang++")
        self.assertIsNotNone(clang, "D2 Clang AST oracle needs real clang++; no skip")
        source = b"""namespace outer {
namespace inner {
template<typename T> struct Box { T value; void set(T v) { value=v; } };
struct Engine { Engine() {} ~Engine() {} void run(int); void run(double); };
void Engine::run(int) {}
void Engine::run(double) {}
}
}
#define FUNCTION_NAME generated
void FUNCTION_NAME() {}
"""
        result = subprocess.run(
            [clang, "-x", "c++", "-std=c++17", "-fsyntax-only", "-Werror",
             "-Xclang", "-ast-dump=json", "-"],
            input=source, capture_output=True, timeout=30, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace")[:2000])
        ast = json.loads(result.stdout)
        observed = []

        def compiler_walk(node, owners=()):
            if not isinstance(node, dict) or node.get("isImplicit"):
                return
            kind, name = node.get("kind"), node.get("name")
            context = "::".join(owners) or None
            mapped = None
            if kind == "NamespaceDecl":
                mapped = "namespace"
            elif kind == "CXXRecordDecl" and name in ("Box", "Engine"):
                mapped = "struct"
            elif kind == "FieldDecl":
                mapped = "field"
            elif kind == "CXXMethodDecl":
                body = any(ch.get("kind") == "CompoundStmt"
                           for ch in node.get("inner", []))
                mapped = "function_definition" if body else "method_declaration"
            if mapped and name:
                observed.append((mapped, name, context))
            local = owners
            if kind in ("NamespaceDecl", "CXXRecordDecl") and name:
                local = (*owners, name)
            for child in node.get("inner", []):
                compiler_walk(child, local)

        compiler_walk(ast)
        parser = self.parse(source)
        syntax = Counter((x.kind, x.spelling, x.container)
                         for x in parser.declarations)
        # Independently derive the Clang reference on every run. A focused
        # selection avoids treating generated/specialized AST children as
        # equivalent to source-text declarations.
        selected = {
            ("namespace", "outer", None),
            ("namespace", "inner", "outer"),
            ("struct", "Box", "outer::inner"),
            ("struct", "Engine", "outer::inner"),
            ("field", "value", "outer::inner::Box"),
            ("function_definition", "set", "outer::inner::Box"),
            ("method_declaration", "run", "outer::inner::Engine"),
        }
        compiler = Counter(x for x in observed if x in selected)
        self.assertEqual(set(compiler), selected,
                         f"Clang oracle selection incomplete: {set(compiler) ^ selected}")
        self.assertEqual(
            Counter({x: syntax[x] for x in selected}), compiler,
            f"Clang/tree-sitter declaration mismatch on source SHA256 {sha256(source).hexdigest()}",
        )
        # Compiler sees macro-expanded identity; parser sees literal spelling.
        # Neither source-spelling nor ABI can be promoted to resolved here.
        def has_expanded_function(node):
            return isinstance(node, dict) and (
                (node.get("kind") == "FunctionDecl" and node.get("name") == "generated")
                or any(has_expanded_function(c) for c in node.get("inner", []))
            )
        self.assertTrue(has_expanded_function(ast))
        self.assertTrue(any(d.spelling == "FUNCTION_NAME" for d in parser.declarations))
        self.assertIn("PREPROCESSOR_EXPANSION_NOT_EVALUATED", parser.unknowns)
        self.assertIn("TEMPLATE_BINDING_NOT_EVALUATED", parser.unknowns)
        self.assertIn("COMPILER_OVERRIDE_AND_ABI_NOT_EVALUATED", parser.unknowns)
        print(f"D2_CLANG_ORACLE=PASS source_sha256={sha256(source).hexdigest()} "
              f"declarations={sum(compiler.values())} compiler=clang++ observed-not-pinned")



if __name__ == "__main__":
    unittest.main()
