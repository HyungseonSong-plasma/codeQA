"""Additive typed external evidence and fail-closed admission checks (v0.1).

NOT a quality Gate. Does not modify CCG, Mechanical or QA Result semantics.
The caller must independently attest the source/tool/rules and supply the raw
artifact bytes. Exit-code interpretation belongs to a pinned tool adapter;
the classifier ID must match an independent expected identity.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any, Literal

from jsonschema import Draft202012Validator


class ExternalEvidenceError(ValueError):
    """Envelope violates schema or fundamental cross-record invariants."""


@dataclass(frozen=True, slots=True)
class SourceFile:
    path: str
    sha256: str


@dataclass(frozen=True, slots=True)
class SkippedFile:
    path: str
    reason: str


@dataclass(frozen=True, slots=True)
class ToolIdentity:
    name: str
    version: str
    binary_sha256: str
    adapter_version: str
    invocation_sha256: str
    ruleset_sha256: str
    exit_classifier: str


@dataclass(frozen=True, slots=True)
class Execution:
    state: str
    exit_code: int | None
    exit_classification: str


@dataclass(frozen=True, slots=True)
class Scope:
    expected_files: tuple[SourceFile, ...]
    scanned_files: tuple[SourceFile, ...]
    skipped_files: tuple[SkippedFile, ...]
    parser_errors: tuple[SkippedFile, ...]
    required_rules: tuple[str, ...]
    evaluated_rules: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RawArtifact:
    uri: str
    sha256: str
    media_type: str


@dataclass(frozen=True, slots=True)
class StaticFinding:
    kind: Literal["STATIC_FINDING"]
    rule_id: str
    severity: str
    path: str
    line: int
    message: str
    native_status: str


@dataclass(frozen=True, slots=True)
class TypeDiagnostic:
    kind: Literal["TYPECHECK_DIAGNOSTIC"]
    rule_id: str
    severity: str
    path: str
    line: int
    message: str
    native_status: str


@dataclass(frozen=True, slots=True)
class FormalProof:
    kind: Literal["FORMAL_PROOF_RESULT"]
    obligation_id: str
    path: str
    source_sha256: str
    native_status: str
    assumptions: tuple[str, ...]
    counterexample_sha256: str | None


TypedObservation = StaticFinding | TypeDiagnostic | FormalProof


@dataclass(frozen=True, slots=True)
class ExternalEvidence:
    schema_version: str
    snapshot_id: str
    tool: ToolIdentity
    execution: Execution
    scope: Scope
    raw_artifact: RawArtifact
    observations: tuple[TypedObservation, ...]

    def to_document(self) -> dict[str, Any]:
        def normalize(value: Any) -> Any:
            if isinstance(value, tuple):
                return [normalize(item) for item in value]
            if isinstance(value, list):
                return [normalize(item) for item in value]
            if isinstance(value, dict):
                return {key: normalize(item) for key, item in value.items()}
            return value
        return normalize(asdict(self))


@dataclass(frozen=True, slots=True)
class Admission:
    status: Literal["ADMISSIBLE", "INADMISSIBLE", "INDETERMINATE"]
    reasons: tuple[str, ...]
    retained_observations: int

    def to_document(self) -> dict[str, Any]:
        return asdict(self)


def canonical_external_json(envelope: ExternalEvidence) -> str:
    """Deterministic semantic record; the native raw tool artifact is separate."""
    if not isinstance(envelope, ExternalEvidence):
        raise TypeError("expected typed external evidence")
    return json.dumps(envelope.to_document(), sort_keys=True,
                      separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _sorted_file_records(values: Sequence[Mapping[str, Any]]) -> tuple[SourceFile, ...]:
    return tuple(sorted((SourceFile(**value) for value in values),
                        key=lambda x: x.path))


def _unique_paths(values: Sequence[SourceFile | SkippedFile]) -> bool:
    paths = [x.path for x in values]
    return len(paths) == len(set(paths))


def parse_external_evidence(
    document: Mapping[str, Any], schema: Mapping[str, Any],
) -> ExternalEvidence:
    """Validate the JSON Schema and produce an immutable, canonical DTO."""
    if not isinstance(document, Mapping) or not isinstance(schema, Mapping):
        raise ExternalEvidenceError("expected document and registered schema mappings")
    Draft202012Validator.check_schema(schema)
    if schema.get("$id") != "urn:codeqa:evidence:external-envelope:v0.1":
        raise ExternalEvidenceError("unsupported external evidence schema authority")
    violations = sorted(Draft202012Validator(schema).iter_errors(document),
                        key=lambda e: (tuple(str(x) for x in e.absolute_path), e.message))
    if violations:
        raise ExternalEvidenceError("invalid external evidence: " + violations[0].message)

    scope = document["scope"]
    expected = _sorted_file_records(scope["expected_files"])
    scanned = _sorted_file_records(scope["scanned_files"])
    skipped = tuple(sorted((SkippedFile(**x) for x in scope["skipped_files"]),
                           key=lambda x: (x.path, x.reason)))
    parse_errors = tuple(sorted((SkippedFile(**x) for x in scope["parser_errors"]),
                                key=lambda x: (x.path, x.reason)))
    if not all(_unique_paths(x) for x in (expected, scanned, skipped, parse_errors)):
        raise ExternalEvidenceError("duplicate source identity in a coverage set")
    if set(x.path for x in skipped) & set(x.path for x in scanned):
        raise ExternalEvidenceError("a source cannot be scanned and skipped")
    if set(x.path for x in parse_errors) - set(x.path for x in expected):
        raise ExternalEvidenceError("parser errors must refer to selected sources")
    if any(x.path not in {y.path for y in expected} for x in scanned):
        raise ExternalEvidenceError("scanned source is not in selected source scope")

    by_kind = {
        "STATIC_FINDING": StaticFinding,
        "TYPECHECK_DIAGNOSTIC": TypeDiagnostic,
        "FORMAL_PROOF_RESULT": FormalProof,
    }
    observations: list[TypedObservation] = []
    for item in document["observations"]:
        payload = dict(item)
        if payload["kind"] == "FORMAL_PROOF_RESULT":
            payload["assumptions"] = tuple(sorted(payload["assumptions"]))
        observations.append(by_kind[payload["kind"]](**payload))
    normalized = tuple(sorted(observations, key=lambda x: json.dumps(
        asdict(x), sort_keys=True, separators=(",", ":"), ensure_ascii=False)))
    if len({json.dumps(asdict(x), sort_keys=True) for x in normalized}) != len(normalized):
        raise ExternalEvidenceError("duplicate tool observations")

    result = ExternalEvidence(
        schema_version=document["schema_version"],
        snapshot_id=document["snapshot_id"],
        tool=ToolIdentity(**document["tool"]),
        execution=Execution(**document["execution"]),
        scope=Scope(
            expected_files=expected,
            scanned_files=scanned,
            skipped_files=skipped,
            parser_errors=parse_errors,
            required_rules=tuple(sorted(scope["required_rules"])),
            evaluated_rules=tuple(sorted(scope["evaluated_rules"])),
        ),
        raw_artifact=RawArtifact(**document["raw_artifact"]),
        observations=normalized,
    )
    return result


def assess_external_evidence(
    envelope: ExternalEvidence,
    *,
    expected_snapshot_id: str | None,
    expected_files: Mapping[str, str] | None,
    expected_tool: ToolIdentity | None,
    expected_rules: Sequence[str] | None,
    raw_artifact: bytes | None,
    purpose: Literal["SOURCE_ANALYSIS", "IMPLEMENTATION_PROOF"] = "SOURCE_ANALYSIS",
) -> Admission:
    """Assess admissibility against INDEPENDENT caller-owned expectations.

    ADMISSIBLE never means findings absent, type-valid or implementation proven.
    The future Policy Gate decides that separately with rule-specific semantics.
    """
    if not isinstance(envelope, ExternalEvidence):
        raise TypeError("expected parsed ExternalEvidence")
    if purpose not in ("SOURCE_ANALYSIS", "IMPLEMENTATION_PROOF"):
        raise ValueError("unknown evidence purpose")

    invalid: set[str] = set()
    unknown: set[str] = set()
    scope = envelope.scope
    if not expected_snapshot_id:
        unknown.add("SNAPSHOT_EXPECTATION_UNAVAILABLE")
    elif envelope.snapshot_id != expected_snapshot_id:
        invalid.add("SNAPSHOT_MISMATCH")

    if expected_tool is None:
        unknown.add("TRUSTED_TOOL_EXPECTATION_UNAVAILABLE")
    elif envelope.tool != expected_tool:
        invalid.add("TOOL_OR_CONFIG_IDENTITY_MISMATCH")

    if expected_files is None:
        unknown.add("TRUSTED_SOURCE_MANIFEST_UNAVAILABLE")
    else:
        if dict((x.path, x.sha256) for x in scope.expected_files) != dict(expected_files):
            invalid.add("EXPECTED_SOURCE_MANIFEST_MISMATCH")
    if expected_rules is None:
        unknown.add("TRUSTED_RULE_SET_UNAVAILABLE")
    elif set(scope.required_rules) != set(expected_rules) or len(expected_rules) != len(set(expected_rules)):
        invalid.add("REQUIRED_RULE_SET_MISMATCH")

    if raw_artifact is None:
        unknown.add("RAW_ARTIFACT_UNAVAILABLE")
    elif sha256(raw_artifact).hexdigest() != envelope.raw_artifact.sha256:
        invalid.add("RAW_ARTIFACT_DIGEST_MISMATCH")

    if envelope.execution.state != "COMPLETED":
        unknown.add("EXECUTION_NOT_COMPLETED")
    if envelope.execution.exit_classification != "VALID_RESULT":
        unknown.add("TOOL_RESULT_NOT_ATTESTED_COMPLETE")
    if envelope.execution.state == "COMPLETED" and envelope.execution.exit_code is None:
        unknown.add("EXIT_CODE_NOT_RECORDED")

    selected = {x.path: x.sha256 for x in scope.expected_files}
    scanned = {x.path: x.sha256 for x in scope.scanned_files}
    extra = set(scanned) - set(selected)
    if extra:
        invalid.add("SCANNED_PATH_OUTSIDE_SELECTED_SCOPE")
    if any(selected.get(p) != digest for p, digest in scanned.items()):
        invalid.add("SCANNED_SOURCE_DIGEST_MISMATCH")
    if set(scanned) != set(selected):
        unknown.add("INCOMPLETE_SOURCE_COVERAGE")
    if scope.skipped_files:
        unknown.add("SKIPPED_SOURCE_PATHS")
    if scope.parser_errors:
        unknown.add("PARSER_ERRORS")
    if set(scope.evaluated_rules) - set(scope.required_rules):
        invalid.add("UNDECLARED_EXECUTED_RULE")
    if set(scope.evaluated_rules) != set(scope.required_rules):
        unknown.add("INCOMPLETE_RULE_COVERAGE")

    for item in envelope.observations:
        if item.path not in scanned:
            invalid.add("OBSERVATION_OUTSIDE_SCANNED_SCOPE")
        if isinstance(item, (StaticFinding, TypeDiagnostic)):
            if item.rule_id not in scope.evaluated_rules:
                invalid.add("OBSERVATION_RULE_NOT_EVALUATED")
        else:
            if item.source_sha256 != scanned.get(item.path):
                invalid.add("PROOF_SOURCE_DIGEST_MISMATCH")
            if purpose == "IMPLEMENTATION_PROOF":
                # #102 owns trusted verification-to-implementation binding.
                # No v0.1 formal result can certify arbitrary target code.
                unknown.add("FORMAL_IMPLEMENTATION_BINDING_NOT_VERIFIED")
    if purpose == "IMPLEMENTATION_PROOF" and not any(
        isinstance(x, FormalProof) for x in envelope.observations
    ):
        unknown.add("FORMAL_PROOF_EVIDENCE_MISSING")

    status: Literal["ADMISSIBLE", "INADMISSIBLE", "INDETERMINATE"]
    if invalid:
        status = "INADMISSIBLE"
    elif unknown:
        status = "INDETERMINATE"
    else:
        status = "ADMISSIBLE"
    return Admission(status, tuple(sorted(invalid | unknown)), len(envelope.observations))
