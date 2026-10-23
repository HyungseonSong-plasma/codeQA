"""Language-neutral source witnesses and policy for intra-function statement similarity.

The model intentionally stores syntax candidates, not behavioral clones.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any


class StatementSimilarityError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class StatementPatternProfile:
    schema_version: str
    profile_id: str
    min_statement_tokens: int
    normalize_identifiers: bool
    normalize_literals: bool
    statement_kinds: tuple[str, ...]
    excluded_prefixes: tuple[str, ...]

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> StatementPatternProfile:
        keys = {"schema_version", "profile_id", "min_statement_tokens",
                "normalize_identifiers", "normalize_literals",
                "statement_kinds", "excluded_prefixes"}
        if not isinstance(value, Mapping) or set(value) != keys:
            raise StatementSimilarityError("invalid statement similarity profile shape")
        kinds = value["statement_kinds"]
        prefixes = value["excluded_prefixes"]
        if (value["schema_version"] != "0.2"
                or value["profile_id"] != "python-direct-statement-patterns-v0.2"
                or type(value["min_statement_tokens"]) is not int
                or value["min_statement_tokens"] < 12
                or type(value["normalize_identifiers"]) is not bool
                or type(value["normalize_literals"]) is not bool
                or not isinstance(kinds, list) or not kinds
                or len(set(kinds)) != len(kinds)
                or any(k not in {"if","for","while","try","with","match"}
                       for k in kinds)
                or not isinstance(prefixes,list) or len(set(prefixes)) != len(prefixes)
                or any(not isinstance(p,str) or not p or not p.endswith("/")
                       or p.startswith("/") or "\\" in p or ".." in p.split("/")
                       for p in prefixes)):
            raise StatementSimilarityError("unsupported or unsafe statement profile")
        return cls(
            "0.2",value["profile_id"],value["min_statement_tokens"],
            value["normalize_identifiers"],value["normalize_literals"],
            tuple(kinds),tuple(prefixes),
        )

    def fingerprint(self) -> str:
        mapping = {
            **asdict(self), "statement_kinds": list(self.statement_kinds),
            "excluded_prefixes": list(self.excluded_prefixes),
        }
        return sha256(json.dumps(mapping, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class StatementWitness:
    owner_id: str
    path: str
    line: int
    end_line: int
    statement_kind: str
    token_count: int
    source_sha256: str
    normalized_syntax_sha256: str
    producer: str = "python-direct-statement-ast-v0.2"


@dataclass(frozen=True, slots=True)
class StatementPatternEvidence:
    snapshot_id: str
    profile_fingerprint: str
    analyzed_paths: tuple[str, ...]
    unprocessed: tuple[tuple[str, str], ...]
    source_hashes: tuple[tuple[str, str], ...]
    skipped: tuple[tuple[str, str], ...]
    witnesses: tuple[StatementWitness, ...]
    producer: str = "python-direct-statement-ast-v0.2"
