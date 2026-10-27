"""Read-only parser-backed Rust *syntax* witnesses for #93.

Optional tree-sitter dependencies are pinned in dedicated conformance CI.
No trait resolution, compiler/ABI assertion, macro expansion or source edit.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
import json
import re


class RustParserEvidenceError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RustDeclaration:
    kind: str
    name: str
    line: int
    container: str | None


@dataclass(frozen=True, slots=True)
class RustSyntaxEvidence:
    schema_version: str
    producer: str
    source_repository: str
    source_revision: str
    source_path: str
    source_sha256: str
    declarations: tuple[RustDeclaration, ...]
    unknowns: tuple[str, ...]
    authority: str = "PARSER_SYNTAX_ONLY_NOT_COMPILER_OR_TRAIT_PROOF"

    def canonical_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False)


def parse_rust_syntax(
    source: bytes, *,
    source_repository: str,
    source_revision: str,
    source_path: str,
    expected_source_sha256: str,
) -> RustSyntaxEvidence:
    """Exact source-bound declarations with explicit unresolved semantics."""
    if (type(source) is not bytes or len(source) > 1_000_000
            or not isinstance(source_repository, str)
            or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", source_repository)
            or any(part in (".", "..") for part in source_repository.split("/"))
            or not isinstance(source_revision, str)
            or not re.fullmatch(r"[a-f0-9]{40}", source_revision)
            or not isinstance(source_path, str)
            or not re.fullmatch(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*\.rs", source_path)
            or any(part in (".", "..") for part in source_path.split("/"))
            or not isinstance(expected_source_sha256, str)
            or not re.fullmatch(r"[a-f0-9]{64}", expected_source_sha256)):
        raise RustParserEvidenceError("exact source repository/revision/path/digest required")
    if sha256(source).hexdigest() != expected_source_sha256:
        raise RustParserEvidenceError("Rust source digest differs from independently selected bytes")
    try:
        from tree_sitter import Language, Parser
        import tree_sitter_rust
        core_version = version("tree-sitter")
        grammar_version = version("tree-sitter-rust")
    except (ImportError, PackageNotFoundError) as exc:
        raise RustParserEvidenceError("optional pinned tree-sitter Rust parser unavailable") from exc
    if (core_version, grammar_version) != ("0.25.2", "0.24.0"):
        raise RustParserEvidenceError("unreviewed Rust parser/grammar version")
    parser = Parser(Language(tree_sitter_rust.language()))
    root = parser.parse(source).root_node
    if root.has_error:
        raise RustParserEvidenceError("Rust parse error or incomplete source; no partial PASS")
    declarations: list[RustDeclaration] = []
    unknowns = {"COMPILER_AND_ABI_NOT_EVALUATED", "RUNTIME_DISPATCH_NOT_EVALUATED"}
    decl_kinds = {
        "function_item": "function",
        "function_signature_item": "function_signature",
        "trait_item": "trait",
        "struct_item": "struct",
        "enum_item": "enum",
        "mod_item": "module",
    }

    def name_of(node):
        name = node.child_by_field_name("name")
        return source[name.start_byte:name.end_byte].decode("utf-8") if name else None

    def visit(node, context: str | None = None):
        local = context
        if node.type == "impl_item":
            # The literal header is a source witness, NOT a resolved trait ID.
            header = source[node.start_byte:node.end_byte].split(b"{", 1)[0]
            local = header.decode("utf-8", errors="replace").strip()[:180]
            unknowns.add("TRAIT_IMPL_RESOLUTION_NOT_EVALUATED")
        elif node.type == "trait_item":
            local = "trait " + (name_of(node) or "<unresolved>")
        if node.type in decl_kinds:
            name = name_of(node)
            if name is None:
                raise RustParserEvidenceError("parser declaration without name")
            kind = decl_kinds[node.type]
            if node.type in ("function_item", "function_signature_item") and context:
                kind = "trait_or_impl_method" if context.startswith(("trait ", "impl")) else kind
            declarations.append(RustDeclaration(
                kind=kind, name=name, line=node.start_point.row + 1, container=context,
            ))
            if name.startswith("r#"):
                unknowns.add("RAW_IDENTIFIER_EQUIVALENCE_NOT_EVALUATED")
        if node.type in ("macro_invocation", "macro_definition"):
            unknowns.add("MACRO_EXPANSION_NOT_EVALUATED")
        if node.type in ("use_declaration", "extern_crate_declaration"):
            unknowns.add("EXTERNAL_REEXPORT_OR_ALIAS_NOT_EVALUATED")
        if node.type == "attribute_item":
            unknowns.add("ATTRIBUTE_MACRO_EFFECT_NOT_EVALUATED")
        for child in node.children:
            visit(child, local)

    visit(root)
    return RustSyntaxEvidence(
        schema_version="0.1",
        producer=f"tree-sitter@{core_version}/tree-sitter-rust@{grammar_version}",
        source_repository=source_repository, source_revision=source_revision,
        source_path=source_path, source_sha256=expected_source_sha256,
        declarations=tuple(sorted(declarations,
                                  key=lambda d: (d.line, d.kind, d.name, d.container or ""))),
        unknowns=tuple(sorted(unknowns)),
    )


@dataclass(frozen=True, slots=True)
class RustLocalTraitMethodComparison:
    """Same-file literal spelling comparison; NEVER trait implementation proof."""

    schema_version: str
    source_sha256: str
    trait_name: str
    type_name: str
    declared_trait_methods: tuple[str, ...]
    observed_impl_methods: tuple[str, ...]
    absent_lexical_impl_methods: tuple[str, ...]
    status: str
    unknowns: tuple[str, ...]
    authorization: str = "NONE_SOURCE_SYNTAX_ONLY"

    def canonical_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False)


def compare_local_trait_method_spellings(
    evidence: RustSyntaxEvidence, *, trait_name: str, type_name: str,
) -> RustLocalTraitMethodComparison:
    """Compare literal same-file method names, without resolving a Rust trait.

    Exact simple 'impl Trait for Type' textual headers only. Generic, qualified,
    macro-generated or external trait obligations remain NOT_EVALUATED.
    """
    if not isinstance(evidence, RustSyntaxEvidence):
        raise RustParserEvidenceError("typed Rust parser evidence required")
    if (evidence.authority != "PARSER_SYNTAX_ONLY_NOT_COMPILER_OR_TRAIT_PROOF"
            or evidence.producer != "tree-sitter@0.25.2/tree-sitter-rust@0.24.0"):
        raise RustParserEvidenceError("unreviewed syntax evidence authority")
    for item in (trait_name, type_name):
        if not isinstance(item, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", item):
            raise RustParserEvidenceError("simple explicit trait/type spelling required")

    trait_owners = [
        d for d in evidence.declarations
        if d.kind == "trait" and d.name == trait_name and d.container is None
    ]
    trait_header = "trait " + trait_name
    impl_header = f"impl {trait_name} for {type_name}"
    trait_methods = [
        d.name for d in evidence.declarations
        if d.kind == "trait_or_impl_method" and d.container == trait_header
    ]
    impl_methods = [
        d.name for d in evidence.declarations
        if d.kind == "trait_or_impl_method" and d.container == impl_header
    ]
    declarations = tuple(sorted(trait_methods))
    implementations = tuple(sorted(impl_methods))
    valid = (len(trait_owners) == 1 and bool(declarations)
             and bool(implementations)
             and len(declarations) == len(set(declarations))
             and len(implementations) == len(set(implementations)))
    absent = tuple(sorted(set(declarations) - set(implementations))) if valid else ()
    status = ("NOT_EVALUATED" if not valid else
              "LEXICAL_NAMES_ABSENT_FROM_IMPL" if absent else
              "LEXICAL_METHOD_NAME_SET_PRESENT")
    unknowns = {
        "TRAIT_RESOLUTION_NOT_EVALUATED",
        "RUST_COMPILER_TRAIT_SATISFACTION_NOT_EVALUATED",
        "MACRO_AND_DEFAULT_METHOD_EFFECTS_NOT_EVALUATED",
        "EXTERNAL_CRATE_AND_ABI_NOT_EVALUATED",
        "SOURCE_IDENTITY_REQUIRES_INDEPENDENT_CI_PIN",
    }
    if not valid:
        unknowns.add("EXACT_LOCAL_DECLARATION_PAIR_NOT_ESTABLISHED")
    return RustLocalTraitMethodComparison(
        schema_version="0.1", source_sha256=evidence.source_sha256,
        trait_name=trait_name, type_name=type_name,
        declared_trait_methods=declarations,
        observed_impl_methods=implementations,
        absent_lexical_impl_methods=absent, status=status,
        unknowns=tuple(sorted(unknowns)),
    )
