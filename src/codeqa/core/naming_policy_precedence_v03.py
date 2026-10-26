"""Opt-in Naming v0.3 draft policy precedence for issue #91.

Domain-scoped rule selection only, NOT a generic policy Gate, a human approval,
a semantic naming verdict, or an authorization to rename any source.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
import json
import re
from typing import Any


class NamingPrecedenceError(ValueError):
    """A policy or its attested source/profile identity is not trustworthy."""


_HEX = re.compile(r"[0-9a-f]{64}\Z")
_REV = re.compile(r"git:([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@([0-9a-f]{40})\Z")
_REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
_TOKEN = re.compile(r"[a-z][a-z0-9_]*\Z")
_ID = re.compile(r"[a-z][a-z0-9_.-]{2,100}\Z")
_LEVELS = ("catalog", "language", "repository", "path_symbol", "exception")
_ACTIONS = frozenset({"CHECK_CANDIDATE", "EXCLUDE_CANDIDATE", "REVIEW_REQUIRED"})
_SELECTORS = {
    "catalog": frozenset(),
    "language": frozenset({"language"}),
    "repository": frozenset({"language", "repository"}),
    "path_symbol": frozenset({"language", "repository", "path_prefix", "symbol_kind"}),
    "exception": frozenset({"language", "repository", "path", "symbol_kind", "symbol"}),
}


def _path(value: object) -> str:
    if (not isinstance(value, str) or not value or value.startswith("/")
            or "\\" in value or any(ord(c) < 32 or ord(c) == 127 for c in value)
            or any(part in {"", ".", ".."} for part in value.split("/"))):
        raise NamingPrecedenceError("unsafe or unnormalized source path")
    return value


def _digest(value: object, field: str) -> str:
    if not isinstance(value, str) or not _HEX.fullmatch(value):
        raise NamingPrecedenceError(field + " must be exact SHA-256")
    return value


def _token(value: object, field: str) -> str:
    if not isinstance(value, str) or not _TOKEN.fullmatch(value):
        raise NamingPrecedenceError(field + " must be a normalized ASCII token")
    return value


def _symbol(value: object) -> str:
    if (not isinstance(value, str)
            or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value)):
        raise NamingPrecedenceError("symbol must be an ASCII Python-style identifier")
    return value


def _repository(value: object) -> str:
    if (not isinstance(value, str) or not _REPO.fullmatch(value)
            or any(x in {".", ".."} for x in value.split("/"))):
        raise NamingPrecedenceError("repository must be an exact owner/name")
    return value


def _nonempty(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise NamingPrecedenceError(field + " must be nonempty normalized text")
    return value


@dataclass(frozen=True, slots=True)
class NamingRule:
    rule_id: str
    level: str
    action: str
    selector: tuple[tuple[str, str], ...]
    owner: str = ""
    reason: str = ""
    expires_on: date | None = None

    def matches(self, *, language: str, repository: str, path: str,
                symbol_kind: str, symbol: str) -> bool:
        values = dict(self.selector)
        return all(
            (language if key == "language" else
             repository if key == "repository" else
             symbol_kind if key == "symbol_kind" else
             symbol if key == "symbol" else
             path if key == "path" else
             (val if path == val or path.startswith(val + "/") else None))
            == val
            for key, val in values.items()
        )


@dataclass(frozen=True, slots=True)
class NamingPrecedenceResult:
    status: str
    selected_level: str | None
    selected_rule_id: str | None
    matched_rule_ids: tuple[str, ...]
    policy_sha256: str
    source_sha256: str
    reason: str
    semantic_proven: bool = False
    human_review_required: bool = True


@dataclass(frozen=True, slots=True)
class NamingPrecedencePolicy:
    schema_version: str
    policy_id: str
    catalog_sha256: str
    profile_sha256: str
    rules: tuple[NamingRule, ...]
    policy_sha256: str
    review_status: str = "AWAITING_HUMAN_REVIEW"

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> NamingPrecedencePolicy:
        if (not isinstance(raw, Mapping)
                or set(raw) != {"schema_version", "policy_id", "catalog_sha256",
                                "profile_sha256", "review_status", "rules"}
                or raw["schema_version"] != "0.3-draft"
                or raw["review_status"] != "AWAITING_HUMAN_REVIEW"):
            raise NamingPrecedenceError("exact unapproved Naming policy envelope required")
        policy_id = _nonempty(raw["policy_id"], "policy_id")
        if not _ID.fullmatch(policy_id):
            raise NamingPrecedenceError("policy_id must be a versioned identifier")
        catalog = _digest(raw["catalog_sha256"], "catalog_sha256")
        profile = _digest(raw["profile_sha256"], "profile_sha256")
        if not isinstance(raw["rules"], list) or not raw["rules"]:
            raise NamingPrecedenceError("explicit policy rules required")

        rules: list[NamingRule] = []
        ids: set[str] = set()
        selectors: set[tuple[str, tuple[tuple[str, str], ...]]] = set()
        for item in raw["rules"]:
            if not isinstance(item, Mapping):
                raise NamingPrecedenceError("rule must be an object")
            level = item.get("level")
            if not isinstance(level, str) or level not in _SELECTORS:
                raise NamingPrecedenceError("unsupported Naming precedence level")
            required = {"rule_id", "level", "action", "selector"}
            if level == "exception":
                required |= {"owner", "reason", "expires_on"}
            if set(item) != required:
                raise NamingPrecedenceError("rule fields must match its precedence level")
            rule_id = item["rule_id"]
            if not isinstance(rule_id, str) or not _ID.fullmatch(rule_id):
                raise NamingPrecedenceError("rule_id must be a normalized identifier")
            if rule_id in ids:
                raise NamingPrecedenceError("duplicate rule identity")
            ids.add(rule_id)
            if not isinstance(item["action"], str) or item["action"] not in _ACTIONS:
                raise NamingPrecedenceError("no PASS/ALLOW or automatic rename actions")
            selector = item["selector"]
            if not isinstance(selector, Mapping) or set(selector) != _SELECTORS[level]:
                raise NamingPrecedenceError("exact scoped selector fields required")
            selected: dict[str, str] = {}
            for key, value in selector.items():
                if key == "repository":
                    selected[key] = _repository(value)
                elif key in {"path", "path_prefix"}:
                    selected[key] = _path(value)
                elif key == "symbol":
                    selected[key] = _symbol(value)
                else:
                    selected[key] = _token(value, key)
            identity = (level, tuple(sorted(selected.items())))
            if identity in selectors:
                raise NamingPrecedenceError("conflicting equal-precedence rule selectors")
            selectors.add(identity)
            owner, reason, expiry = "", "", None
            if level == "exception":
                owner = _nonempty(item["owner"], "exception owner")
                reason = _nonempty(item["reason"], "exception reason")
                if (not isinstance(item["expires_on"], str)
                        or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", item["expires_on"])):
                    raise NamingPrecedenceError("exception requires canonical expiry date")
                try:
                    expiry = date.fromisoformat(item["expires_on"])
                except ValueError as exc:
                    raise NamingPrecedenceError("invalid exception expiry") from exc
            rules.append(NamingRule(
                rule_id, level, item["action"], identity[1], owner, reason, expiry,
            ))

        catalog_rules = [r for r in rules if r.level == "catalog"]
        if len(catalog_rules) != 1:
            raise NamingPrecedenceError("exactly one catalog baseline required")
        scoped = [r for r in rules if r.level == "path_symbol"]
        for rule in rules:
            if rule.level != "exception":
                continue
            sel = dict(rule.selector)
            if not any(
                (lambda base: (
                    base["language"] == sel["language"]
                    and base["repository"] == sel["repository"]
                    and base["symbol_kind"] == sel["symbol_kind"]
                    and (sel["path"] == base["path_prefix"]
                         or sel["path"].startswith(base["path_prefix"] + "/"))
                ))(dict(parent.selector))
                for parent in scoped
            ):
                raise NamingPrecedenceError("exact exception must lie in an explicit path/symbol scope")

        canonical = json.dumps(raw, sort_keys=True, ensure_ascii=False,
                               separators=(",", ":"), allow_nan=False)
        fingerprint = sha256(canonical.encode("utf-8")).hexdigest()
        return cls("0.3-draft", policy_id, catalog, profile,
                   tuple(sorted(rules, key=lambda r: (_LEVELS.index(r.level), r.rule_id))),
                   fingerprint)

    def resolve(self, *, revision: str, repository: str, sources: Mapping[str, str],
                path: str, language: str, symbol_kind: str, symbol: str,
                as_of: date, catalog_sha256: str, profile_sha256: str,
                expected_policy_sha256: str, expected_source_sha256: str) -> NamingPrecedenceResult:
        if not isinstance(revision, str) or not (m := _REV.fullmatch(revision)):
            raise NamingPrecedenceError("exact immutable repository revision required")
        repo = _repository(repository)
        if m.group(1) != repo:
            raise NamingPrecedenceError("source repository/revision identity drift")
        _path(path)
        _token(language, "language")
        _token(symbol_kind, "symbol_kind")
        _symbol(symbol)
        if not isinstance(as_of, date) or isinstance(as_of, type):
            raise NamingPrecedenceError("explicit review date required")
        if (not isinstance(sources, Mapping) or path not in sources
                or not isinstance(sources[path], str)
                or not all(isinstance(k, str) and isinstance(v, str)
                           and _path(k) for k, v in sources.items())):
            raise NamingPrecedenceError("source selection or exact file bytes unavailable")
        if (_digest(catalog_sha256, "catalog_sha256") != self.catalog_sha256
                or _digest(profile_sha256, "profile_sha256") != self.profile_sha256
                or _digest(expected_policy_sha256, "policy_sha256") != self.policy_sha256):
            raise NamingPrecedenceError("stale catalog, profile or policy identity")
        source_sha = sha256(sources[path].encode("utf-8")).hexdigest()
        if _digest(expected_source_sha256, "source_sha256") != source_sha:
            raise NamingPrecedenceError("stale source file identity")
        # A policy selector is not an inventory extractor. Even its lexical
        # candidate action requires the named token in the pinned file bytes;
        # comments/strings may match, so a hit still proves no declaration.
        if not re.search(r"(?<![A-Za-z0-9_])" + re.escape(symbol)
                         + r"(?![A-Za-z0-9_])", sources[path]):
            return NamingPrecedenceResult(
                "NOT_EVALUATED", None, None, (), self.policy_sha256, source_sha,
                "symbol not lexically observed in selected source",
            )
        matches: dict[str, list[NamingRule]] = {level: [] for level in _LEVELS}
        for rule in self.rules:
            if rule.matches(language=language, repository=repo, path=path,
                            symbol_kind=symbol_kind, symbol=symbol):
                matches[rule.level].append(rule)
        if not all(matches[level] for level in ("catalog", "language",
                                                "repository", "path_symbol")):
            return NamingPrecedenceResult(
                "NOT_EVALUATED", None, None, (), self.policy_sha256, source_sha,
                "missing explicit language/repository/path-symbol scope",
            )
        trace: list[str] = []
        winner: NamingRule | None = None
        for level in _LEVELS:
            applicable = matches[level]
            if not applicable:
                continue
            if level == "path_symbol":
                length = max(len(dict(r.selector)["path_prefix"]) for r in applicable)
                applicable = [r for r in applicable
                              if len(dict(r.selector)["path_prefix"]) == length]
            if len(applicable) != 1:
                raise NamingPrecedenceError("ambiguous equal-precedence applicable rules")
            winner = applicable[0]
            trace.append(winner.rule_id)
        assert winner is not None
        if winner.level == "exception" and winner.expires_on < as_of:
            raise NamingPrecedenceError("expired exact exception requires human reapproval")
        return NamingPrecedenceResult(
            winner.action, winner.level, winner.rule_id, tuple(trace),
            self.policy_sha256, source_sha, "lexical policy selection only",
        )
