"""Read-only C++ tree-sitter *syntax* evidence, including partial MOOSE sources.

No C++ semantic override, compiled ABI, MOOSE SDK or input-DSL certification.
The parser is optional and pinned by an independent CI job, not core codeQA.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
import json
import re


class CppParserEvidenceError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class CppDeclaration:
    kind: str
    spelling: str
    line: int
    container: str | None


@dataclass(frozen=True, slots=True)
class CppSyntaxEvidence:
    schema_version: str
    producer: str
    source_repository: str
    source_revision: str
    source_path: str
    source_sha256: str
    parse_status: str
    declarations: tuple[CppDeclaration, ...]
    unknowns: tuple[str, ...]
    authority: str = "PARSER_SYNTAX_ONLY_NO_COMPILER_ABI_OR_MOOSE_DSL_AUTHORITY"

    def canonical_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False)


def parse_cpp_syntax(
    source: bytes, *,
    source_repository: str,
    source_revision: str,
    source_path: str,
    expected_source_sha256: str,
    require_complete_parse: bool = True,
) -> CppSyntaxEvidence:
    """Pin exact bytes and emit lexical declarations with fail-closed gaps.

    Partial syntax is an explicit PARTIAL result, never a supported language
    pipeline or a compiler-verified override. No headers are resolved.
    """
    if (type(source) is not bytes or len(source) > 1_000_000
            or not isinstance(source_repository, str)
            or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", source_repository)
            or not isinstance(source_revision, str)
            or not re.fullmatch(r"[0-9a-f]{40}", source_revision)
            or not isinstance(source_path, str)
            or not re.fullmatch(
                r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*\\.(?:C|cc|cpp|h|hpp)",
                source_path,
            )
            or not isinstance(expected_source_sha256, str)
            or not re.fullmatch(r"[0-9a-f]{64}", expected_source_sha256)
            or type(require_complete_parse) is not bool):
        raise CppParserEvidenceError("exact source/revision/path/digest and strict mode required")
    if sha256(source).hexdigest() != expected_source_sha256:
        raise CppParserEvidenceError("C++ source bytes do not match selected digest")
    try:
        from tree_sitter import Language, Parser
        import tree_sitter_cpp
        core_version = version("tree-sitter")
        grammar_version = version("tree-sitter-cpp")
    except (ImportError, PackageNotFoundError) as exc:
        raise CppParserEvidenceError("optional pinned C++ grammar unavailable") from exc
    if (core_version, grammar_version) != ("0.25.2", "0.23.4"):
        raise CppParserEvidenceError("unreviewed C++ parser/grammar version")
    parser = Parser(Language(tree_sitter_cpp.language()))
    root = parser.parse(source).root_node
    if root.has_error and require_complete_parse:
        raise CppParserEvidenceError("incomplete C++ syntax; no complete parse claim")

    unknowns = {
        "COMPILER_OVERRIDE_AND_ABI_NOT_EVALUATED",
        "DEPENDENCY_HEADERS_AND_MACROS_NOT_RESOLVED",
        "TEMPLATE_INSTANTIATION_NOT_EVALUATED",
        "MOOSE_FRAMEWORK_AND_INPUT_DSL_NOT_EVALUATED",
        "DYNAMIC_PUBLIC_CONSUMERS_NOT_EVALUATED",
    }
    if root.has_error:
        unknowns.add("SYNTAX_ERRORS_PARTIAL_SOURCE_ONLY")
    declarations: list[CppDeclaration] = []
    kinds = {
        "class_specifier": "class",
        "struct_specifier": "struct",
        "enum_specifier": "enum",
        "namespace_definition": "namespace",
        "function_definition": "function_definition",
        "field_declaration": "field",
    }

    def decode(node) -> str:
        return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")

    def declarator_name(node):
        if node is None:
            return None
        if node.type in ("identifier", "field_identifier", "qualified_identifier",
                         "destructor_name", "operator_name"):
            return decode(node)
        child = node.child_by_field_name("declarator")
        if child is not None:
            return declarator_name(child)
        for child in node.named_children:
            result = declarator_name(child)
            if result:
                return result
        return None

    def visit(node, context: str | None = None):
        local = context
        if node.type in ("preproc_include", "preproc_def", "preproc_call",
                         "preproc_if", "preproc_ifdef"):
            unknowns.add("PREPROCESSOR_EXPANSION_NOT_EVALUATED")
        if node.type == "template_declaration":
            unknowns.add("TEMPLATE_BINDING_NOT_EVALUATED")
        if node.type in kinds:
            named = (node.child_by_field_name("name")
                     if node.type != "function_definition" else None)
            if node.type in ("function_definition", "field_declaration"):
                named = node.child_by_field_name("declarator")
            spelling = declarator_name(named)
            if spelling:
                declarations.append(CppDeclaration(
                    kind=kinds[node.type], spelling=spelling,
                    line=node.start_point.row + 1, container=context,
                ))
                if node.type in ("class_specifier", "struct_specifier",
                                 "namespace_definition"):
                    local = spelling
        for child in node.named_children:
            visit(child, local)

    visit(root)
    return CppSyntaxEvidence(
        schema_version="0.1",
        producer=f"tree-sitter@{core_version}/tree-sitter-cpp@{grammar_version}",
        source_repository=source_repository,
        source_revision=source_revision,
        source_path=source_path,
        source_sha256=expected_source_sha256,
        parse_status=("PARTIAL_SYNTAX_ERRORS_NOT_EVALUATED" if root.has_error
                      else "PARSED_SYNTAX_ONLY"),
        declarations=tuple(sorted(declarations,
                                  key=lambda d: (d.line, d.kind, d.spelling,
                                                 d.container or ""))),
        unknowns=tuple(sorted(unknowns)),
    )
