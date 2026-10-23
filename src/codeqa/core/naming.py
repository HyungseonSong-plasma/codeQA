"""Immutable, source-backed naming observations and versioned safe Python profile.

Only source syntax and caller-attested interface contracts are represented.
No dynamic imports, runtime inheritance inference or automatic renaming.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any


class NamingContractError(ValueError):
    """Naming profile, source evidence or applicability could not be verified."""


STYLES = ("snake_case", "PascalCase", "UPPER_SNAKE_CASE", "off")
KINDS = ("module", "class", "function", "method", "parameter", "field", "import_alias")
RELATIONS = (
    "LOCAL", "IMPORTED_ORIGINAL", "LOCAL_OVERRIDE_MATCH",
    "INVALID_OVERRIDE_INTENT", "EXTERNAL_BASE_UNRESOLVED",
    "DECORATED_EXTERNAL_UNRESOLVED", "DTO_DIRECT_FIELD_UNRESOLVED",
    "DTO_FIELD_ALIAS_DECLARED", "DTO_FIELD_MAPPING_UNRESOLVED",
)
CONTRACT_KINDS = ("interface", "field", "callback", "import_alias")


@dataclass(frozen=True, slots=True)
class NamingContract:
    kind: str
    path: str
    owner: str
    name: str
    provider: str
    revision: str
    reason: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> NamingContract:
        keys = set(cls.__dataclass_fields__)
        if not isinstance(value, Mapping) or set(value) != keys:
            raise NamingContractError("invalid exact external naming contract")
        if (value["kind"] not in CONTRACT_KINDS
                or any(not isinstance(value[k], str) or not value[k].strip()
                       for k in keys - {"kind"})
                or value["path"].startswith("/")
                or any(p in (".", "..", "") for p in value["path"].split("/"))):
            raise NamingContractError("unsafe or incomplete external contract identity")
        return cls(**value)


@dataclass(frozen=True, slots=True)
class NamingProfile:
    schema_version: str
    profile_id: str
    rules: tuple[tuple[str, str], ...]
    excluded_prefixes: tuple[str, ...]
    external_contracts: tuple[NamingContract, ...]

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> NamingProfile:
        if not isinstance(value, Mapping) or set(value) != {
            "schema_version", "profile_id", "rules", "excluded_prefixes", "external_contracts"
        }:
            raise NamingContractError("invalid naming profile shape")
        if value["schema_version"] != "0.1" or value["profile_id"] != "codeqa.naming.python.safe.v0.1":
            raise NamingContractError("unsupported naming profile identity")
        rules = value["rules"]
        prefixes = value["excluded_prefixes"]
        contracts = value["external_contracts"]
        if (not isinstance(rules, dict) or set(rules) != set(KINDS)
                or any(v not in STYLES for v in rules.values())
                or not isinstance(prefixes, list)
                or len(set(prefixes)) != len(prefixes)
                or any(not isinstance(p, str) or not p or
                       not p.endswith("/") or p.startswith("/") or "\\" in p
                       or ".." in p.split("/") for p in prefixes)
                or not isinstance(contracts, list)):
            raise NamingContractError("unsupported naming rule or exclusion")
        parsed = tuple(NamingContract.from_mapping(x) for x in contracts)
        identities = [(x.kind, x.path, x.owner, x.name) for x in parsed]
        if len(identities) != len(set(identities)):
            raise NamingContractError("ambiguous duplicate external contracts")
        return cls("0.1", value["profile_id"], tuple(sorted(rules.items())),
                   tuple(prefixes), tuple(sorted(parsed, key=lambda x: (
                       x.path, x.owner, x.name, x.kind
                   ))))

    def fingerprint(self) -> str:
        value = {
            "schema_version": self.schema_version, "profile_id": self.profile_id,
            "rules": dict(self.rules), "excluded_prefixes": list(self.excluded_prefixes),
            "external_contracts": [asdict(x) for x in self.external_contracts],
        }
        return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class NamingSymbol:
    path: str
    owner: str
    name: str
    kind: str
    line: int
    column: int
    relation: str
    contract_name: str | None
    detail: str


@dataclass(frozen=True, slots=True)
class NamingEvidence:
    snapshot_id: str
    analyzed_paths: tuple[str, ...]
    unprocessed: tuple[tuple[str, str], ...]
    source_sha256: tuple[tuple[str, str], ...]
    symbols: tuple[NamingSymbol, ...]
    producer: str = "python-ast-naming-safe-v0.1"
