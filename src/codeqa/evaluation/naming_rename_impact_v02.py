"""Issue #76: opt-in, non-mutating rename impact *candidates*.

This is a bounded source-witness evaluator, not a parser, patcher or proof of
safe migration. Caller-provided lexical references are never promoted to
verified runtime/API/ABI bindings.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from collections.abc import Mapping
import ast
import io
import keyword
import re
import tokenize

_REV = re.compile(r"git:[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_POLICY = re.compile(r"[a-z0-9][a-z0-9._-]*\Z")
_BOUNDARIES = frozenset({
    "internal", "public_api", "external_sdk", "override", "dynamic_call",
    "dto_inbound", "dto_outbound", "db_physical", "rust_trait",
    "cpp_virtual_abi", "moose_reserved_dsl", "generated_code", "unknown",
})
_CONTRACT = _BOUNDARIES - {"internal", "dynamic_call", "generated_code", "unknown"}
_CLASSES = frozenset({"verified_lexical", "unresolved_dynamic", "external_unknown"})


class RenameImpactError(ValueError):
    """Invalid or unverifiable source identity."""


@dataclass(frozen=True, slots=True)
class SymbolWitness:
    path: str
    name: str
    kind: str
    line: int
    source_sha256: str
    boundary: str
    binding_verified: bool = False
    contract_revision: str = ""


@dataclass(frozen=True, slots=True)
class ReferenceWitness:
    path: str
    line: int
    source_sha256: str
    classification: str
    target_name: str


@dataclass(frozen=True, slots=True)
class RenameImpactReport:
    schema_version: str
    revision: str
    policy_id: str
    selected_paths: tuple[str, ...]
    old_name: str
    proposed_name: str
    verdict: str
    blockers: tuple[str, ...]
    unknowns: tuple[str, ...]
    lexical_reference_count: int
    migration_plan: str = "HUMAN_REVIEW_REQUIRED"
    mutation_performed: bool = False

    def to_document(self) -> dict[str, object]:
        raw = asdict(self)
        for key in ("selected_paths", "blockers", "unknowns"):
            raw[key] = list(raw[key])
        return raw


def _valid_path(value: str) -> bool:
    return (isinstance(value, str) and bool(value)
            and not value.startswith("/") and "\\" not in value
            and all(p not in {"", ".", ".."} for p in value.split("/"))
            and all(ord(c) >= 32 and ord(c) != 127 for c in value))


def _line(source: str, number: int) -> str:
    lines = source.splitlines()
    if not isinstance(number, int) or isinstance(number, bool) or number < 1 or number > len(lines):
        raise RenameImpactError("invalid source line witness")
    return lines[number - 1]


def _lexical_name(line: str, name: str) -> bool:
    # Word boundaries avoid matching foo as part of foo_bar or myfoo.
    # Even a positive result is only lexical, and may occur in comments.
    return bool(re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", line))


def _python_name_token_at(source: str, line: int, name: str) -> bool:
    """Require a real NAME token on a parseable Python source line.

    This is still lexical evidence: it cannot establish declaration identity,
    runtime binding, API consumers or a safe rename.
    """
    try:
        ast.parse(source)
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        return any(t.type == tokenize.NAME and t.string == name
                   and t.start[0] == line for t in tokens)
    except (SyntaxError, IndentationError, tokenize.TokenError, ValueError):
        return False


def _verify_source(path: str, digest: str, sources: Mapping[str, str]) -> str:
    if not _valid_path(path) or path not in sources or not isinstance(sources[path], str):
        raise RenameImpactError("unverified path or incomplete source scope")
    if not isinstance(digest, str) or not _HASH.fullmatch(digest):
        raise RenameImpactError("invalid source digest")
    if sha256(sources[path].encode("utf-8")).hexdigest() != digest:
        raise RenameImpactError("source digest mismatch")
    return sources[path]


def assess_rename_impact(
    *, revision: str, sources: Mapping[str, str], symbol: SymbolWitness,
    proposed_name: str, references: tuple[ReferenceWitness, ...],
    source_selection_complete: bool, policy_id: str,
) -> RenameImpactReport:
    if not isinstance(revision, str) or not _REV.fullmatch(revision):
        raise RenameImpactError("exact immutable Git revision required")
    if not isinstance(policy_id, str) or not _POLICY.fullmatch(policy_id):
        raise RenameImpactError("versioned policy identity required")
    if not isinstance(sources, Mapping) or not sources:
        raise RenameImpactError("nonempty source selection required")
    if not isinstance(symbol, SymbolWitness) or not isinstance(references, tuple):
        raise RenameImpactError("typed source and reference witnesses required")
    if not all(_valid_path(p) and isinstance(s, str) for p, s in sources.items()):
        raise RenameImpactError("invalid source selection")
    if symbol.boundary not in _BOUNDARIES or not isinstance(symbol.binding_verified, bool):
        raise RenameImpactError("unrecognized symbol contract boundary")
    if not isinstance(symbol.name, str) or not symbol.name or not isinstance(symbol.kind, str) or not symbol.kind:
        raise RenameImpactError("invalid declaration identity")
    if not isinstance(proposed_name, str) or not proposed_name or proposed_name == symbol.name:
        raise RenameImpactError("proposal must change an identifier")
    # Python source migration suggestions must at least be syntactically
    # expressible as identifiers; this is not a binding or public API proof.
    if symbol.path.endswith((".py", ".pyi")) and (
        not proposed_name.isidentifier() or keyword.iskeyword(proposed_name)
    ):
        raise RenameImpactError("invalid Python rename target identifier")
    source = _verify_source(symbol.path, symbol.source_sha256, sources)
    symbol_line = _line(source, symbol.line)
    if not (_python_name_token_at(source, symbol.line, symbol.name)
            if symbol.path.endswith((".py", ".pyi"))
            else _lexical_name(symbol_line, symbol.name)):
        raise RenameImpactError("declaration lexical witness missing")

    blockers: set[str] = set()
    unknowns: set[str] = set()
    if not isinstance(source_selection_complete, bool) or not source_selection_complete:
        unknowns.add("incomplete_source_selection")
    if symbol.boundary in _CONTRACT:
        blockers.add("external_or_persisted_contract:" + symbol.boundary)
        if not symbol.contract_revision or not symbol.binding_verified:
            unknowns.add("unverified_boundary_contract")
    if symbol.boundary in {"unknown", "dynamic_call", "generated_code"}:
        unknowns.add("unresolved_symbol_boundary:" + symbol.boundary)
    if symbol.boundary == "internal" and not symbol.binding_verified:
        unknowns.add("unverified_symbol_binding")

    seen: set[tuple[str, int, str]] = set()
    lexical_count = 0
    for ref in references:
        if not isinstance(ref, ReferenceWitness) or ref.classification not in _CLASSES:
            raise RenameImpactError("invalid reference evidence")
        ref_source = _verify_source(ref.path, ref.source_sha256, sources)
        line = _line(ref_source, ref.line)
        if not isinstance(ref.target_name, str) or ref.target_name != symbol.name:
            raise RenameImpactError("reference target mismatch")
        key = (ref.path, ref.line, ref.classification)
        if key in seen:
            raise RenameImpactError("duplicate reference witness")
        seen.add(key)
        if ref.classification == "verified_lexical":
            if not (_python_name_token_at(ref_source, ref.line, symbol.name)
                    if ref.path.endswith((".py", ".pyi"))
                    else _lexical_name(line, symbol.name)):
                raise RenameImpactError("reference lexical token missing")
            lexical_count += 1
        else:
            unknowns.add("unresolved_reference:" + ref.classification)

    # The 'review' verdict never certifies that any rename is safe.
    verdict = "BLOCKED_CONTRACT_REVIEW" if blockers else "UNVERIFIED_PROPOSAL"
    return RenameImpactReport(
        schema_version="0.2-draft", revision=revision, policy_id=policy_id,
        selected_paths=tuple(sorted(sources)), old_name=symbol.name,
        proposed_name=proposed_name, verdict=verdict,
        blockers=tuple(sorted(blockers)), unknowns=tuple(sorted(unknowns)),
        lexical_reference_count=lexical_count,
    )
