"""Rule-scoped, source-AST-bound semantic *candidates* for #144.

Never guesses domain meaning, infers aliases, edits names or produces PASS.
Input source SHA-256 only binds supplied bytes, not remote Git provenance.
"""
from __future__ import annotations

import ast
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
import json
import re

from codeqa.core.naming_field_classification_v03 import (
    FieldClassificationError, classify_pinned_class_annotation,
)


class SemanticCandidateError(ValueError):
    """Malformed, conflicting, unsafe, or version-drifted candidate policy."""


_ID = re.compile(r"[a-z][a-z0-9_]*(?:_[a-z0-9]+)*\Z")
_PATH = re.compile(r"(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_KIND = frozenset({"function", "method", "parameter", "field"})


def _tokens(text: str) -> tuple[str, ...]:
    if not isinstance(text, str) or not _ID.fullmatch(text):
        raise SemanticCandidateError("strict lowercase ASCII canonical or alias required")
    return tuple(text.split("_"))


def _path(text: str) -> str:
    if (not isinstance(text, str) or not _PATH.fullmatch(text)
            or any(p in {".", ".."} or p.endswith((".", " "))
                   for p in text.split("/"))):
        raise SemanticCandidateError("unsafe or nonportable selected source path")
    return text


def _scope_contains(prefix: str, path: str) -> bool:
    return path == prefix or path.startswith(prefix + "/")


@dataclass(frozen=True, slots=True)
class Candidate:
    status: str
    reason: str
    identifier: str
    source_path: str
    rule_id: str | None = None
    owner_role: str | None = None
    observed_kind: str | None = None
    semantic_proven: bool = False
    rename_authorized: bool = False


class SemanticCandidateRules:
    """Immutable strictly drafted rules; not a policy Gate or a binding graph."""

    def __init__(self, raw: Mapping[str, object]) -> None:
        if (not isinstance(raw, Mapping)
                or set(raw) != {"schema_version", "policy_id", "adoption_status",
                                    "terms", "scopes", "excluded_inferences"}
                or raw["schema_version"] != "0.4-candidate"
                or raw["adoption_status"] != "NOT_ADOPTED"):
            raise SemanticCandidateError("exact NOT_ADOPTED candidate policy required")
        self.policy_id = _tokens(raw["policy_id"])
        terms, scopes, excluded = (raw[k] for k in
                                   ("terms", "scopes", "excluded_inferences"))
        if not isinstance(terms, list) or not terms or not isinstance(scopes, list) \
                or not isinstance(excluded, list):
            raise SemanticCandidateError("terms/scopes/exclusions must be lists")
        self.terms: tuple[tuple[str, tuple[tuple[str, ...], ...], tuple[str, ...], str], ...]
        built = []
        seen: set[tuple[str, ...]] = set()
        for item in terms:
            if not isinstance(item, Mapping) or set(item) != {
                "canonical", "aliases", "allowed_roles", "meaning_status"}:
                raise SemanticCandidateError("term schema mismatch")
            if item["meaning_status"] != "PENDING_DOMAIN_EVIDENCE":
                raise SemanticCandidateError("candidate cannot assert semantic proof")
            if not isinstance(item["aliases"], list) or not isinstance(item["allowed_roles"], list):
                raise SemanticCandidateError("term aliases/roles must be lists")
            if not item["allowed_roles"] or len(item["allowed_roles"]) != len(set(item["allowed_roles"])):
                raise SemanticCandidateError("duplicate/missing domain roles")
            roles = tuple(sorted(item["allowed_roles"]))
            for role in roles:
                _tokens(role)
            spellings = (_tokens(item["canonical"]), *(_tokens(x) for x in item["aliases"]))
            if len(spellings) != len(set(spellings)) or any(s in seen for s in spellings):
                raise SemanticCandidateError("canonical/alias lexical overlap")
            seen.update(spellings)
            built.append((item["canonical"], tuple(spellings), roles, item["meaning_status"]))
        self.terms = tuple(built)
        exclusions = [_tokens(x) for x in excluded]
        if len(exclusions) != len(set(exclusions)) or any(x in seen for x in exclusions):
            raise SemanticCandidateError("negative-control overlap or duplicate")
        self.excluded = frozenset(exclusions)
        norm_scopes = []
        used: set[tuple[str, str, str]] = set()
        for scope in scopes:
            if not isinstance(scope, Mapping) or set(scope) != {
                "path_prefix", "language", "kind", "role"}:
                raise SemanticCandidateError("scope schema mismatch")
            prefix = _path(scope["path_prefix"])
            if scope["language"] != "python" or scope["kind"] not in _KIND:
                raise SemanticCandidateError("unsupported language or symbol kind")
            role = scope["role"]
            _tokens(role)
            key = (prefix, scope["language"], scope["kind"])
            if key in used:
                raise SemanticCandidateError("conflicting exact scope selectors")
            used.add(key)
            norm_scopes.append((prefix, scope["kind"], role))
        self.scopes = tuple(norm_scopes)
        self.fingerprint = sha256(json.dumps(
            raw, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
            allow_nan=False).encode("utf-8")).hexdigest()

    def assess(self, *, source: bytes, expected_sha256: str, path: str,
               name: str, kind: str, line: int, owner: str,
               external_contract: bool = False) -> Candidate:
        """Require one exact AST declaration and unique explicit scoped rule.

        This is a syntax/lexical candidate gate only; domain semantics stay UNKNOWN.
        """
        _path(path)
        if (not isinstance(source, bytes) or not isinstance(expected_sha256, str)
                or not _SHA.fullmatch(expected_sha256)
                or sha256(source).hexdigest() != expected_sha256):
            raise SemanticCandidateError("pinned byte digest mismatch")
        if (kind not in _KIND or not isinstance(name, str) or not name.isidentifier()
                or not isinstance(owner, str) or type(line) is not int or line <= 0
                or type(external_contract) is not bool):
            raise SemanticCandidateError("invalid exact declaration identity")

        def outcome(status: str, reason: str, rule_id: str | None = None,
                    role: str | None = None) -> Candidate:
            return Candidate(status, reason, name, path, rule_id, role, kind)

        try:
            tree = ast.parse(source.decode("utf-8"), filename=path)
        except (UnicodeDecodeError, SyntaxError) as exc:
            raise SemanticCandidateError("unparseable pinned source") from exc
        observed = _declaration_exists(tree, name=name, kind=kind,
                                       line=line, owner=owner)
        if not observed:
            return outcome("UNKNOWN", "NO_EXACT_AST_DECLARATION")
        if kind == "field":
            try:
                field = classify_pinned_class_annotation(
                    source, expected_sha256=expected_sha256,
                    owner=owner, name=name, line=line)
            except FieldClassificationError:
                return outcome("UNKNOWN", "FIELD_EVIDENCE_UNSUPPORTED")
            if field.classification != "FIELD_CANDIDATE":
                return outcome("UNKNOWN", "DATACLASS_FIELD_NOT_PROVEN")
        if external_contract:
            return outcome("UNKNOWN", "EXTERNAL_CONSUMER_COMPATIBILITY_NOT_EVALUATED")
        scoped = [(p, r) for p, k, r in self.scopes if k == kind and _scope_contains(p, path)]
        if not scoped:
            return outcome("UNKNOWN", "NO_EXPLICIT_ROLE_SCOPE")
        longest = max(len(p) for p, _ in scoped)
        winners = [(p, r) for p, r in scoped if len(p) == longest]
        if len(winners) != 1:
            return outcome("UNKNOWN", "AMBIGUOUS_SCOPE")
        role = winners[0][1]
        try:
            # Strict: no CamelCase or guessed normalization and no unit conversion.
            tokens = _tokens(name)
        except SemanticCandidateError:
            return outcome("UNKNOWN", "UNSUPPORTED_IDENTIFIER_LEXEMES", role=role)
        if tokens in self.excluded:
            return outcome("EXCLUDED", "EXPLICIT_NEGATIVE_INFERENCE_CONTROL", role=role)
        matching = [(c, roles) for c, spellings, roles, _ in self.terms
                    if any(tokens[i:i+len(s)] == s for s in spellings
                           for i in range(len(tokens)-len(s)+1))]
        if not matching:
            return outcome("UNKNOWN", "NO_DECLARED_EXACT_TOKEN_RULE", role=role)
        if len(matching) != 1:
            return outcome("UNKNOWN", "MULTIPLE_MATCHED_TERM_ROLES", role=role)
        canonical, allowed_roles = matching[0]
        if role not in allowed_roles:
            return outcome("UNKNOWN", "DECLARED_ROLE_NOT_APPLICABLE", canonical, role)
        return outcome("LEXICAL_RULE_MATCH_CANDIDATE", "SEMANTIC_MEANING_UNVERIFIED",
                       canonical, role)


def _declaration_exists(tree: ast.Module, *, name: str, kind: str,
                        line: int, owner: str) -> bool:
    """Explicit lexical owner, no inferred runtime scopes/reexports."""
    found: list[tuple[str, int, str, str]] = []

    def collect(body: list[ast.stmt], parent: tuple[str, ...] = (),
                scope: str = "module") -> None:
        for node in body:
            if isinstance(node, ast.ClassDef):
                collect(node.body, parent + (node.name,), "class")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                category = "method" if scope == "class" else "function"
                found.append((node.name, node.lineno, ".".join(parent), category))
                ident = parent + (node.name,)
                args = node.args
                for p in args.posonlyargs + args.args + args.kwonlyargs + (
                    [args.vararg] if args.vararg else []) + ([args.kwarg] if args.kwarg else []):
                    found.append((p.arg, p.lineno, ".".join(ident), "parameter"))
                collect(node.body, ident, "function")
            elif (scope == "class" and isinstance(node, ast.AnnAssign)
                  and isinstance(node.target, ast.Name) and node.simple == 1):
                # Class annotation only; not yet proven standard dataclass field.
                found.append((node.target.id, node.lineno, ".".join(parent), "field"))

    collect(tree.body)
    return found.count((name, line, owner, kind)) == 1
