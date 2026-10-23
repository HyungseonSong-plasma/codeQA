"""Opt-in pinned external ancestor declaration facts, separate from Naming v0.1."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from collections.abc import Mapping
from typing import Any


class ExternalAncestorError(ValueError):
    """A claimed provider declaration or source witness is not grounded."""


@dataclass(frozen=True, slots=True)
class ExternalProvider:
    qualified_class: str
    source_path: str
    source_sha256: str
    revision: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ExternalProvider:
        if not isinstance(value, Mapping) or set(value) != set(cls.__dataclass_fields__):
            raise ExternalAncestorError("invalid external provider declaration")
        name, path, digest, revision = (value[k] for k in cls.__dataclass_fields__)
        if (not all(isinstance(x, str) and x for x in (name, path, digest, revision))
                or not re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+", name, re.ASCII)
                or path.startswith("/") or "\\" in path
                or any(x in ("", ".", "..") for x in path.split("/"))
                or not re.fullmatch("[a-f0-9]{64}", digest)):
            raise ExternalAncestorError("invalid provider name, source path or SHA-256")
        return cls(name, path, digest, revision)


@dataclass(frozen=True, slots=True)
class ExternalAncestorProfile:
    schema_version: str
    profile_id: str
    providers: tuple[ExternalProvider, ...]

    @classmethod
    def from_mapping(cls, obj: Mapping[str, Any]) -> ExternalAncestorProfile:
        if not isinstance(obj, Mapping) or set(obj) != {"schema_version", "profile_id", "providers"}:
            raise ExternalAncestorError("invalid ancestor profile")
        if (obj["schema_version"] != "0.1"
                or obj["profile_id"] != "codeqa.naming.pinned-ancestor.v0.1"
                or not isinstance(obj["providers"], list)):
            raise ExternalAncestorError("unsupported ancestor profile version")
        entries = tuple(ExternalProvider.from_mapping(p) for p in obj["providers"])
        names = [x.qualified_class for x in entries]
        if len(set(names)) != len(names):
            raise ExternalAncestorError("multiple provider declarations for one ancestor")
        return cls("0.1", obj["profile_id"], tuple(sorted(entries, key=lambda p:p.qualified_class)))

    def fingerprint(self) -> str:
        serialized = {"schema_version": self.schema_version,
                      "profile_id": self.profile_id,
                      "providers": [asdict(p) for p in self.providers]}
        return sha256(json.dumps(serialized, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class ExternalMemberWitness:
    path: str
    owner: str
    name: str
    line: int
    column: int
    ancestor: str
    external_source_sha256: str
    external_declaration_line: int | None
    state: str  # PINNED_MEMBER_DECLARED / PINNED_MEMBER_NOT_DECLARED / UNRESOLVED
    explanation: str


@dataclass(frozen=True, slots=True)
class ExternalAncestorEvidence:
    snapshot_id: str
    profile_fingerprint: str
    source_sha256: tuple[tuple[str, str], ...]
    provider_sha256: tuple[tuple[str, str], ...]
    witnesses: tuple[ExternalMemberWitness, ...]
    producer: str = "python-ast-pinned-ancestor-v0.1"
