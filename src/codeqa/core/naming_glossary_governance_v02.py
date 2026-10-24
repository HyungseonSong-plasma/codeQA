"""Opt-in, conservative repository glossary governance draft (#74).

No semantic correctness is inferred from the lexical presence of a term.
The accepted v0.1 glossary and QA contracts are not imported or modified.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from collections.abc import Mapping
import re


class GlossaryGovernanceError(ValueError):
    pass


_TOKEN = re.compile(r"[a-z][a-z0-9_]*\Z")
_SAFE_SEGMENT = re.compile(r"[A-Za-z0-9_.-]+\Z")


def _token(raw: object) -> str:
    if not isinstance(raw, str) or not _TOKEN.fullmatch(raw):
        raise GlossaryGovernanceError("term must be an unambiguous ASCII canonical token")
    return raw


def _prefix(raw: object) -> str:
    if not isinstance(raw, str) or not raw:
        raise GlossaryGovernanceError("scope prefix required")
    if not all(_SAFE_SEGMENT.fullmatch(s) and s not in {".", ".."} for s in raw.split("/")):
        raise GlossaryGovernanceError("scope prefix is not safe normalized source path")
    return raw.rstrip("/")


@dataclass(frozen=True, slots=True)
class Term:
    canonical: str
    aliases: tuple[str, ...]
    owner: str
    expires_on: date
    allowed_roles: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RoleScope:
    prefix: str
    language: str
    category: str
    role: str


@dataclass(frozen=True, slots=True)
class RoleNameCandidate:
    status: str
    path: str
    identifier: str
    declared_role: str | None
    term: str | None
    reason: str
    semantic_proven: bool = False


@dataclass(frozen=True, slots=True)
class GlossaryGovernance:
    schema_version: str
    terms: tuple[Term, ...]
    scopes: tuple[RoleScope, ...]
    review_status: str

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> "GlossaryGovernance":
        if (not isinstance(raw, Mapping)
                or set(raw) != {"schema_version", "terms", "scopes", "review_status"}
                or raw["schema_version"] != "0.2-draft"
                or raw["review_status"] != "AWAITING_HUMAN_REVIEW"):
            raise GlossaryGovernanceError("unreviewed versioned policy required")
        if not isinstance(raw["terms"], list) or not isinstance(raw["scopes"], list):
            raise GlossaryGovernanceError("terms and scopes must be explicit lists")
        terms: list[Term] = []
        occupied: dict[str, str] = {}
        for item in raw["terms"]:
            if not isinstance(item, Mapping) or set(item) != {
                "canonical", "aliases", "owner", "expires_on", "allowed_roles"
            }:
                raise GlossaryGovernanceError("unrecognized term fields")
            canonical = _token(item["canonical"])
            aliases = item["aliases"]
            roles = item["allowed_roles"]
            if (not isinstance(aliases, list) or not isinstance(roles, list)
                    or not roles or len(aliases) != len(set(aliases))):
                raise GlossaryGovernanceError("ambiguous term aliases or roles")
            aliases = tuple(_token(x) for x in aliases)
            if canonical in aliases:
                raise GlossaryGovernanceError("circular term alias")
            if (not isinstance(item["owner"], str) or not item["owner"]
                    or not isinstance(item["expires_on"], str)):
                raise GlossaryGovernanceError("owner and expiration required")
            try:
                expires_on = date.fromisoformat(item["expires_on"])
            except ValueError as exc:
                raise GlossaryGovernanceError("invalid expiration date") from exc
            if not all(isinstance(x, str) and x and x.isascii() for x in roles):
                raise GlossaryGovernanceError("invalid declared domain role")
            for spelling in (canonical, *aliases):
                if spelling in occupied:
                    raise GlossaryGovernanceError("duplicate or conflicting canonical/alias token")
                occupied[spelling] = canonical
            terms.append(Term(canonical, aliases, item["owner"], expires_on, tuple(roles)))
        scopes: list[RoleScope] = []
        seen: set[tuple[str, str, str]] = set()
        for item in raw["scopes"]:
            if not isinstance(item, Mapping) or set(item) != {
                "prefix", "language", "category", "role"
            }:
                raise GlossaryGovernanceError("unknown scope identity")
            scope = RoleScope(
                _prefix(item["prefix"]),
                _token(item["language"]), _token(item["category"]),
                _token(item["role"]),
            )
            key = (scope.prefix, scope.language, scope.category)
            if key in seen:
                raise GlossaryGovernanceError("overlapping equal-precedence role scopes")
            seen.add(key)
            scopes.append(scope)
        return cls("0.2-draft", tuple(terms), tuple(scopes), "AWAITING_HUMAN_REVIEW")

    def candidate(
        self, *, path: str, identifier: str, language: str, category: str,
        as_of: date, external_contract: bool = False,
    ) -> RoleNameCandidate:
        _prefix(path)
        if not isinstance(identifier, str) or not identifier:
            raise GlossaryGovernanceError("identifier required")
        if not isinstance(as_of, date):
            raise GlossaryGovernanceError("explicit evaluation date required")
        if external_contract:
            return RoleNameCandidate("NOT_EVALUATED", path, identifier, None, None,
                                     "external API/contract spelling excluded")
        applicable = [
            s for s in self.scopes if s.language == language and s.category == category
            and (path == s.prefix or path.startswith(s.prefix + "/"))
        ]
        if not applicable:
            return RoleNameCandidate("NOT_EVALUATED", path, identifier, None, None,
                                     "no declared role scope")
        scoped = max(applicable, key=lambda s: len(s.prefix))
        words = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", identifier)
        tokens = {x.lower() for x in re.split(r"[^A-Za-z0-9]+", words) if x}
        matches = [
            t for t in self.terms if t.canonical in tokens
            or bool(tokens.intersection(t.aliases))
        ]
        if len(matches) != 1:
            return RoleNameCandidate("NOT_EVALUATED", path, identifier, scoped.role, None,
                                     "zero or ambiguous declared glossary tokens")
        term = matches[0]
        if term.expires_on < as_of:
            return RoleNameCandidate("NOT_EVALUATED", path, identifier, scoped.role,
                                     term.canonical, "expired term requires new review")
        if scoped.role in term.allowed_roles:
            return RoleNameCandidate("ROLE_NAME_MATCH_CANDIDATE", path, identifier,
                                     scoped.role, term.canonical, "lexical candidate only")
        return RoleNameCandidate("ROLE_NAME_REVIEW_CANDIDATE", path, identifier,
                                 scoped.role, term.canonical, "declared role/term discrepancy")
