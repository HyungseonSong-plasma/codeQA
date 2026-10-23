"""Pure direction-specific naming-contract comparator, no serializer execution."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Any

from codeqa.core.naming import NamingEvidence
from codeqa.core.naming_fields import (
    DIRECTIONS, DirectionalFieldEvidence, FieldMappingError, FieldMappingProfile,
)


@dataclass(frozen=True, slots=True)
class DirectionalMappingFinding:
    path: str
    owner: str
    field: str
    line: int
    direction: str
    internal_name: str
    expected_external_name: str
    declared_external_name: str | None
    status: str
    reason: str


@dataclass(frozen=True, slots=True)
class DirectionalMappingReport:
    schema_version: str
    snapshot_id: str
    profile_fingerprint: str
    findings: tuple[DirectionalMappingFinding, ...]
    missing_source_contracts: tuple[tuple[str,str,str], ...]
    status: str
    limitations: tuple[str, ...]
    interpretation: str = "DECLARED_DIRECTIONAL_MAPPING_NOT_EFFECTIVE_RUNTIME_SERIALIZATION_OR_DATABASE_PROOF"

    def to_document(self) -> dict[str,Any]:
        def convert(v:Any)->Any:
            if isinstance(v,(tuple,list)):
                return [convert(x) for x in v]
            if isinstance(v,dict):
                return {k:convert(x) for k,x in v.items()}
            return v
        return convert(asdict(self))


def evaluate_directional_fields(
    naming: NamingEvidence,
    evidence: DirectionalFieldEvidence,
    profile: FieldMappingProfile,
) -> DirectionalMappingReport:
    if (not isinstance(naming,NamingEvidence)
            or not isinstance(evidence,DirectionalFieldEvidence)
            or not isinstance(profile,FieldMappingProfile)
            or evidence.producer!="python-ast-directional-field-v0.1"
            or evidence.snapshot_id!=naming.snapshot_id
            or evidence.source_sha256!=naming.source_sha256
            or evidence.profile_fingerprint!=profile.fingerprint()
            or evidence.schema_sha256!=profile.schema_sha256):
        raise FieldMappingError("source/profile/contract provenance drift")
    symbols={(x.path,x.owner,x.name,x.line,x.column) for x in naming.symbols if x.kind=="field"}
    if len(symbols)!=sum(x.kind=="field" for x in naming.symbols):
        raise FieldMappingError("duplicate declared field symbols")
    bound={(b.path,b.owner,b.field) for b in profile.bindings}
    if set(evidence.skipped_contracts)&{(x.path,x.owner,x.name) for x in evidence.witnesses}:
        raise FieldMappingError("contract is both found and missing")
    if (len(set(evidence.skipped_contracts))!=len(evidence.skipped_contracts)
            or not set(evidence.skipped_contracts)<=bound):
        raise FieldMappingError("unverified missing-field claim")
    findings=[]
    observed=set()
    for item in evidence.witnesses:
        key=(item.path,item.owner,item.name)
        if (key not in bound or key in observed
                or item.producer!="python-ast-directional-field-v0.1"
                or (item.path,item.owner,item.name,item.line,item.column) not in symbols):
            raise FieldMappingError("mismatched field declaration or source location")
        observed.add(key)
        values=dict(item.declared)
        expected=dict(item.expected)
        if (len(values)!=len(item.declared) or set(values)!=set(DIRECTIONS)
                or len(expected)!=len(item.expected)
                or any(k not in DIRECTIONS or not isinstance(v,str) or not v
                       for k,v in expected.items())):
            raise FieldMappingError("ambiguous directional mapping observations")
        for direction,external in sorted(expected.items()):
            value=values[direction]
            if value is not None and (not isinstance(value,str) or not value):
                raise FieldMappingError("invalid literal external alias")
            findings.append(DirectionalMappingFinding(
                item.path,item.owner,item.name,item.line,direction,item.name,
                external,value,
                "NOT_EVALUATED" if value is None
                else "DECLARED_MATCH_NOT_RUNTIME_VERIFIED" if value==external
                else "DECLARED_MISMATCH",
                "mapping_constructor_not_verified" if value is None
                else "external_contract_syntax_matches_but_runtime_config_unknown"
                if value==external else "declared_external_key_differs_from_pinned_schema",
            ))
    if observed|set(evidence.skipped_contracts)!=bound:
        raise FieldMappingError("incomplete caller-declared field inventory")
    # Distinct fields declaring the same outgoing or incoming name can collide.
    collisions=defaultdict(list)
    for i,record in enumerate(findings):
        if record.declared_external_name is not None:
            collisions[(record.path,record.owner,record.direction,
                        record.declared_external_name)].append(i)
    duplicates={i for group in collisions.values() if len(group)>1 for i in group}
    if duplicates:
        findings=[DirectionalMappingFinding(
            x.path,x.owner,x.field,x.line,x.direction,x.internal_name,
            x.expected_external_name,x.declared_external_name,
            "ALIAS_COLLISION" if i in duplicates else x.status,
            "multiple_fields_declare_same_directional_external_key" if i in duplicates
            else x.reason) for i,x in enumerate(findings)]
    states={x.status for x in findings}
    status=("REVIEW_REQUIRED" if states & {"DECLARED_MISMATCH","ALIAS_COLLISION"}
            else "NOT_EVALUATED" if "NOT_EVALUATED" in states
            or evidence.skipped_contracts or not findings
            else "DECLARED_MAPPING_OBSERVED")
    return DirectionalMappingReport(
        "0.1",evidence.snapshot_id,profile.fingerprint(),
        tuple(sorted(findings,key=lambda x:(x.path,x.owner,x.field,x.direction))),
        evidence.skipped_contracts,status,
        ("effective_input_output_database_binding_not_runtime_verified",),
    )
