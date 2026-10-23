"""Immutable directional field-map source observations and explicit schema policy."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from typing import Any


class FieldMappingError(ValueError):
    pass


DIRECTIONS = ("input", "output", "database")


@dataclass(frozen=True, slots=True)
class FieldBinding:
    path: str
    owner: str
    field: str
    schema_model: str

    @classmethod
    def from_mapping(cls, x: Mapping[str, Any]) -> FieldBinding:
        if not isinstance(x, Mapping) or set(x) != set(cls.__dataclass_fields__):
            raise FieldMappingError("invalid field binding profile")
        if (any(not isinstance(v, str) or not v for v in x.values())
                or x["path"].startswith("/")
                or "\\" in x["path"] or ".." in x["path"].split("/")):
            raise FieldMappingError("unsafe exact field binding")
        return cls(**x)


@dataclass(frozen=True, slots=True)
class FieldMappingProfile:
    schema_version: str
    profile_id: str
    schema_path: str
    schema_sha256: str
    provider: str
    revision: str
    bindings: tuple[FieldBinding, ...]

    @classmethod
    def from_mapping(cls, x: Mapping[str, Any]) -> FieldMappingProfile:
        if not isinstance(x, Mapping) or set(x) != set(cls.__dataclass_fields__):
            raise FieldMappingError("invalid directional mapping profile")
        if (x["schema_version"] != "0.1"
                or x["profile_id"] != "codeqa.naming.directional-fields.v0.1"
                or not all(isinstance(x[k],str) and x[k] for k in
                           ("schema_path","schema_sha256","provider","revision"))
                or not re.fullmatch("[a-f0-9]{64}", x["schema_sha256"])
                or x["schema_path"].startswith("/")
                or "\\" in x["schema_path"] or ".." in x["schema_path"].split("/")
                or not isinstance(x["bindings"], list)):
            raise FieldMappingError("unsafe schema identity/version")
        pairs=tuple(FieldBinding.from_mapping(item) for item in x["bindings"])
        identities=[(p.path,p.owner,p.field) for p in pairs]
        if len(identities)!=len(set(identities)):
            raise FieldMappingError("duplicated exact field contract")
        return cls("0.1",x["profile_id"],x["schema_path"],x["schema_sha256"],
                   x["provider"],x["revision"],
                   tuple(sorted(pairs,key=lambda p:(p.path,p.owner,p.field))))

    def fingerprint(self) -> str:
        value=asdict(self)
        return sha256(json.dumps(value,sort_keys=True,separators=(",",":")).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class DirectionalFieldWitness:
    path: str
    owner: str
    name: str
    line: int
    column: int
    producer: str
    declared: tuple[tuple[str, str | None], ...]
    expected: tuple[tuple[str, str], ...]
    mechanism: str
    limitation: str


@dataclass(frozen=True, slots=True)
class DirectionalFieldEvidence:
    snapshot_id: str
    profile_fingerprint: str
    source_sha256: tuple[tuple[str, str], ...]
    schema_sha256: str
    witnesses: tuple[DirectionalFieldWitness, ...]
    skipped_contracts: tuple[tuple[str,str,str], ...]
    producer: str = "python-ast-directional-field-v0.1"
