"""Opt-in Python naming coverage extension v0.2; v0.1 contracts are immutable.

Data only: source facts, explicit policy, source-limited uncertainty.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from collections.abc import Mapping
from typing import Any

class NamingCoverageError(ValueError):
    pass

EXTENDED_KINDS = ("module_constant", "class_constant", "instance_attribute")
STYLES = ("snake_case", "UPPER_SNAKE_CASE", "off")

def _path(path: Any, *, prefix: bool = False) -> bool:
    return (isinstance(path, str) and bool(path)
            and not path.startswith("/") and "\\" not in path
            and all(p not in ("", ".", "..") for p in path.rstrip("/").split("/"))
            and (path.endswith("/") if prefix else not path.endswith("/")))

@dataclass(frozen=True, slots=True)
class PathOverride:
    prefix: str
    kind: str
    style: str

@dataclass(frozen=True, slots=True)
class ExactException:
    path: str
    owner: str
    kind: str
    name: str
    provider: str
    revision: str
    reason: str

@dataclass(frozen=True, slots=True)
class NamingCoveragePolicy:
    schema_version: str
    profile_id: str
    styles: tuple[tuple[str, str], ...]
    path_overrides: tuple[PathOverride, ...]
    exact_exceptions: tuple[ExactException, ...]
    excluded_prefixes: tuple[str, ...]

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> NamingCoveragePolicy:
        if not isinstance(raw, Mapping) or set(raw) != {
            "schema_version", "profile_id", "styles", "path_overrides",
            "exact_exceptions", "excluded_prefixes",
        }:
            raise NamingCoverageError("invalid naming extension policy shape")
        if (raw["schema_version"] != "0.2"
                or raw["profile_id"] != "codeqa.naming.python.coverage.v0.2"):
            raise NamingCoverageError("wrong immutable policy identity")
        if (not isinstance(raw["styles"], dict)
                or set(raw["styles"]) != set(EXTENDED_KINDS)
                or any(v not in STYLES for v in raw["styles"].values())):
            raise NamingCoverageError("unsupported declaration style")
        overrides = []
        for item in raw["path_overrides"]:
            if not isinstance(item, Mapping) or set(item) != {"prefix", "kind", "style"}:
                raise NamingCoverageError("invalid path override")
            if (not _path(item["prefix"], prefix=True)
                    or item["kind"] not in EXTENDED_KINDS
                    or item["style"] not in STYLES):
                raise NamingCoverageError("unsafe path override")
            overrides.append(PathOverride(**item))
        keys = [(x.prefix, x.kind) for x in overrides]
        if len(keys) != len(set(keys)):
            raise NamingCoverageError("conflicting equal-precedence path rules")
        exceptions = []
        for item in raw["exact_exceptions"]:
            if not isinstance(item, Mapping) or set(item) != {
                "path", "owner", "kind", "name", "provider", "revision", "reason",
            }:
                raise NamingCoverageError("invalid exact exception")
            if (not _path(item["path"])
                    or item["kind"] not in EXTENDED_KINDS
                    or not isinstance(item["owner"], str)
                    or any(not isinstance(item[k], str) or not item[k].strip()
                           for k in ("name", "provider", "revision", "reason"))):
                raise NamingCoverageError("unscoped or missing exception provenance")
            exceptions.append(ExactException(**item))
        identities = [(x.path, x.owner, x.kind, x.name) for x in exceptions]
        if len(identities) != len(set(identities)):
            raise NamingCoverageError("duplicated exact exception")
        prefixes = raw["excluded_prefixes"]
        if (not isinstance(prefixes, list)
                or len(prefixes) != len(set(prefixes))
                or any(not _path(p, prefix=True) for p in prefixes)):
            raise NamingCoverageError("invalid exclusion prefixes")
        return cls("0.2", raw["profile_id"],
                   tuple(sorted(raw["styles"].items())),
                   tuple(sorted(overrides, key=lambda x:(x.prefix,x.kind))),
                   tuple(sorted(exceptions,key=lambda x:(x.path,x.owner,x.kind,x.name))),
                   tuple(sorted(prefixes)))

    def fingerprint(self) -> str:
        doc=asdict(self)
        return sha256(json.dumps(doc,sort_keys=True,separators=(",",":")).encode()).hexdigest()

    def effective_style(self, path: str, kind: str) -> tuple[str, str]:
        if kind not in EXTENDED_KINDS:
            raise NamingCoverageError("unsupported declaration kind")
        matches=[x for x in self.path_overrides
                 if x.kind==kind and path.startswith(x.prefix)]
        if matches:
            top=max(matches,key=lambda x:len(x.prefix))
            return top.style, f"path:{top.prefix}:{kind}"
        return dict(self.styles)[kind], f"default:{kind}"

@dataclass(frozen=True, slots=True)
class NamingExtendedSymbol:
    path: str
    owner: str
    name: str
    kind: str
    line: int
    column: int
    relation: str  # DECLARED_FINAL / ASSIGNMENT_IN_INIT / UNRESOLVED_SOURCE
    reason: str

@dataclass(frozen=True, slots=True)
class NamingUncertainty:
    path: str
    owner: str
    line: int
    category: str
    reason: str

@dataclass(frozen=True, slots=True)
class NamingExtendedEvidence:
    snapshot_id: str
    source_sha256: tuple[tuple[str,str],...]
    analyzed_paths: tuple[str,...]
    unprocessed: tuple[tuple[str,str],...]
    declarations: tuple[NamingExtendedSymbol,...]
    uncertainty: tuple[NamingUncertainty,...]
    producer: str = "python-ast-naming-coverage-v0.2"

@dataclass(frozen=True, slots=True)
class NamingExtendedFinding:
    path: str
    owner: str
    name: str
    kind: str
    line: int
    column: int
    status: str
    expected_style: str
    applied_rule: str
    explanation: str
    exception_origin: str | None

@dataclass(frozen=True, slots=True)
class NamingExtendedReport:
    schema_version: str
    snapshot_id: str
    profile_id: str
    profile_fingerprint: str
    coverage: str
    evaluated: int
    uncertain: int
    excluded: int
    counts_by_kind: tuple[tuple[str,int],...]
    findings: tuple[NamingExtendedFinding,...]
    uncertainty: tuple[NamingUncertainty,...]
    status: str
    interpretation: str = "EXTENDED_DECLARATION_STYLE_ONLY_NOT_COMPLETE_PYTHON_OR_RUNTIME_CONTRACTS"

    def to_document(self) -> dict[str,Any]:
        def serialize(x:Any)->Any:
            if isinstance(x,(list,tuple)):
                return [serialize(v) for v in x]
            if isinstance(x,dict):
                return {k:serialize(v) for k,v in x.items()}
            return x
        return serialize(asdict(self))
