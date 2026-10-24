"""Fail-closed, opt-in, versioned External Evidence Gate v0.1 (#99).

Only pinned, admitted evidence can grant PASS. It is not a P1-P8 quality verdict,
does not execute code/policies and never modifies a repository.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
import json
import re
from typing import Any, Literal

from jsonschema import Draft202012Validator

from codeqa.core.external_evidence import (
    Admission, ExternalEvidence, ToolIdentity, StaticFinding, TypeDiagnostic,
    assess_external_evidence,
)


class GateContractError(ValueError):
    """Invalid source, scope, policy or rule contract."""


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def _when(value: str) -> datetime:
    if not isinstance(value, str):
        raise GateContractError("offset-aware timestamp required")
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise GateContractError("invalid policy time") from exc
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise GateContractError("policy time must be offset aware")
    return timestamp


def _scope(path: str, pattern: str) -> bool:
    """Only exact files or anchored directory-prefix/**; no wildcard DSL."""
    if pattern.endswith("/**"):
        return path.startswith(pattern[:-2])
    return path == pattern


def _validate_scope(pattern: str) -> None:
    stem = pattern[:-3] if pattern.endswith("/**") else pattern
    if not re.fullmatch(r"[a-zA-Z0-9_.-]+(?:/[a-zA-Z0-9_.-]+)*", stem):
        raise GateContractError("only exact paths or safe directory/** scopes are supported")
    if any(part in (".", "..") for part in stem.split("/")):
        raise GateContractError("unsafe policy scope")


@dataclass(frozen=True, slots=True)
class Waiver:
    path: str
    rule_id: str
    ticket: str
    approved_by: str
    reason: str
    expires_at: str


@dataclass(frozen=True, slots=True)
class Requirement:
    id: str
    scope: str
    tool: ToolIdentity
    rule_ids: tuple[str, ...]
    predicate: str
    exceptions: tuple[Waiver, ...]


@dataclass(frozen=True, slots=True)
class GatePolicy:
    schema_version: str
    policy_id: str
    snapshot_id: str
    source_files: tuple[tuple[str, str], ...]
    requirements: tuple[Requirement, ...]

    def to_document(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "snapshot_id": self.snapshot_id,
            "source_files": [
                {"path": path, "sha256": digest} for path, digest in self.source_files
            ],
            "requirements": [
                {
                    "id": item.id, "scope": item.scope, "tool": asdict(item.tool),
                    "rule_ids": list(item.rule_ids), "predicate": item.predicate,
                    "exceptions": [asdict(e) for e in item.exceptions],
                } for item in self.requirements
            ],
        }

    def fingerprint(self) -> str:
        return sha256(_canonical(self.to_document()).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class EvidenceRun:
    envelope: ExternalEvidence
    raw_artifact: bytes | None


@dataclass(frozen=True, slots=True)
class RequirementDecision:
    id: str
    status: Literal["PASS", "FAIL", "UNKNOWN"]
    admission_status: str
    scope: tuple[str, ...]
    reasons: tuple[str, ...]
    observed_violations: int
    waived_violations: int
    evidence_sha256: str | None

    def to_document(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class GateDecision:
    schema_version: str
    policy_id: str
    policy_fingerprint: str
    snapshot_id: str
    evaluated_at: str
    status: Literal["PASS", "FAIL", "UNKNOWN"]
    authorization: Literal["ALLOW", "BLOCK"]
    requirements: tuple[RequirementDecision, ...]
    reasons: tuple[str, ...]

    def to_document(self) -> dict[str, Any]:
        doc = asdict(self)
        doc["requirements"] = [x.to_document() for x in self.requirements]
        return doc

    def canonical_json(self) -> str:
        return _canonical(self.to_document())


def parse_gate_policy(document: Mapping[str, Any], schema: Mapping[str, Any]) -> GatePolicy:
    if not isinstance(document, Mapping) or not isinstance(schema, Mapping):
        raise GateContractError("expected policy and registered schema")
    if schema.get("$id") != "urn:codeqa:policy:gate:v0.1":
        raise GateContractError("unsupported gate policy schema authority")
    Draft202012Validator.check_schema(schema)
    problems = sorted(Draft202012Validator(schema).iter_errors(document),
                      key=lambda e: (tuple(str(x) for x in e.absolute_path), e.message))
    if problems:
        raise GateContractError("invalid gate policy: " + problems[0].message)

    sources = tuple(sorted((f["path"], f["sha256"]) for f in document["source_files"]))
    names = [x[0] for x in sources]
    if len(set(names)) != len(names):
        raise GateContractError("duplicate selected source paths")

    requirements: list[Requirement] = []
    seen_ids: set[str] = set()
    for raw in document["requirements"]:
        rid = raw["id"]
        if rid in seen_ids:
            raise GateContractError("duplicate requirement identity")
        seen_ids.add(rid)
        pattern = raw["scope"]
        _validate_scope(pattern)
        selected = {p for p in names if _scope(p, pattern)}
        if not selected:
            raise GateContractError("requirement scope matches no selected files")
        ids = tuple(sorted(raw["rule_ids"]))
        waivers = []
        seen_waivers: set[tuple[str, str]] = set()
        for entry in raw["exceptions"]:
            key = (entry["path"], entry["rule_id"])
            if key in seen_waivers:
                raise GateContractError("duplicate/ambiguous exception")
            seen_waivers.add(key)
            if entry["path"] not in selected or entry["rule_id"] not in ids:
                raise GateContractError("exception outside applicable scope/rules")
            _when(entry["expires_at"])
            waivers.append(Waiver(**entry))
        expected_tool_name = {
            "STATIC_NO_HIGH_FINDINGS": "Semgrep",
            "TYPE_NO_ERRORS": "Pyright",
            "FORMAL_IMPLEMENTATION_VERIFIED": "Dafny",
        }[raw["predicate"]]
        if raw["tool"]["name"] != expected_tool_name:
            raise GateContractError("predicate needs pinned matching analysis tool")
        requirements.append(Requirement(
            id=rid, scope=pattern, tool=ToolIdentity(**raw["tool"]),
            rule_ids=ids, predicate=raw["predicate"],
            exceptions=tuple(sorted(waivers, key=lambda x: (x.path, x.rule_id))),
        ))

    return GatePolicy("0.1", document["policy_id"], document["snapshot_id"],
                      sources, tuple(sorted(requirements, key=lambda x: x.id)))


def evaluate_gate(
    policy: GatePolicy,
    *,
    runs: Mapping[str, EvidenceRun],
    expected_policy_sha256: str | None,
    expected_snapshot_id: str | None,
    expected_sources: Mapping[str, str] | None,
    evaluated_at: str,
) -> GateDecision:
    """Evaluate an explicit, independently pinned source and policy context.

    A supplied Admission object is NEVER accepted: recompute admissibility
    using independently pinned policy/tool/scope and real raw artifact bytes.
    Same-scoped requirements are conjunctive; no implicit allow precedence.
    """
    if not isinstance(policy, GatePolicy):
        raise TypeError("parsed GatePolicy required")
    now = _when(evaluated_at)
    caller_reasons: set[str] = set()
    fingerprint = policy.fingerprint()
    if expected_policy_sha256 is None:
        caller_reasons.add("TRUSTED_POLICY_FINGERPRINT_MISSING")
    elif expected_policy_sha256 != fingerprint:
        caller_reasons.add("TRUSTED_POLICY_FINGERPRINT_MISMATCH")
    if not expected_snapshot_id:
        caller_reasons.add("TRUSTED_SNAPSHOT_MISSING")
    elif expected_snapshot_id != policy.snapshot_id:
        caller_reasons.add("TRUSTED_SNAPSHOT_MISMATCH")
    if expected_sources is None:
        caller_reasons.add("TRUSTED_SOURCE_SET_MISSING")
    elif dict(policy.source_files) != dict(expected_sources):
        caller_reasons.add("TRUSTED_SOURCE_SET_MISMATCH")

    declared = {req.id for req in policy.requirements}
    if set(runs) - declared:
        raise GateContractError("unregistered run cannot influence Gate decision")

    results: list[RequirementDecision] = []
    source_map = dict(policy.source_files)
    for req in policy.requirements:
        paths = tuple(path for path in sorted(source_map) if _scope(path, req.scope))
        reasons: set[str] = set(caller_reasons)
        run = runs.get(req.id)
        admission: Admission | None = None
        artifact_digest: str | None = None
        violations = waived = 0
        if run is None:
            reasons.add("REQUIRED_EVIDENCE_MISSING")
        elif not isinstance(run, EvidenceRun):
            raise GateContractError("run must contain typed evidence and original bytes")
        else:
            if run.raw_artifact is not None:
                artifact_digest = sha256(run.raw_artifact).hexdigest()
            admission = assess_external_evidence(
                run.envelope,
                expected_snapshot_id=policy.snapshot_id,
                expected_files={path: source_map[path] for path in paths},
                expected_tool=req.tool,
                expected_rules=req.rule_ids,
                raw_artifact=run.raw_artifact,
                purpose=("IMPLEMENTATION_PROOF"
                         if req.predicate == "FORMAL_IMPLEMENTATION_VERIFIED"
                         else "SOURCE_ANALYSIS"),
            )
            reasons.update(admission.reasons)
            if admission.status != "ADMISSIBLE":
                reasons.add("EVIDENCE_NOT_ADMISSIBLE")
            else:
                allowed = {(w.path, w.rule_id): w for w in req.exceptions}
                if req.predicate == "STATIC_NO_HIGH_FINDINGS":
                    findings = [
                        item for item in run.envelope.observations
                        if isinstance(item, StaticFinding) and
                        item.path in paths and item.rule_id in req.rule_ids
                        and item.severity in ("HIGH", "CRITICAL")
                    ]
                elif req.predicate == "TYPE_NO_ERRORS":
                    findings = [
                        item for item in run.envelope.observations
                        if isinstance(item, TypeDiagnostic) and
                        item.path in paths and item.rule_id in req.rule_ids
                        and item.severity == "ERROR"
                    ]
                else:
                    findings = []
                    reasons.add("FORMAL_GATE_REQUIRES_IMPLEMENTATION_BINDING")
                for item in findings:
                    waiver = allowed.get((item.path, item.rule_id))
                    if waiver is None:
                        violations += 1
                    elif now >= _when(waiver.expires_at):
                        reasons.add("EXPIRED_EXCEPTION")
                        violations += 1
                    else:
                        waived += 1
                if waived:
                    reasons.add("APPROVED_SCOPED_EXCEPTION_APPLIED")

        # A known, admitted violation is a FAIL even if another requirement
        # is unknown. An unadmitted/forged finding is never counted as proof.
        if violations:
            status: Literal["PASS", "FAIL", "UNKNOWN"] = "FAIL"
            reasons.add("REQUIRED_PREDICATE_VIOLATED")
        elif reasons - {"APPROVED_SCOPED_EXCEPTION_APPLIED"}:
            status = "UNKNOWN"
        else:
            status = "PASS"
        results.append(RequirementDecision(
            id=req.id, status=status,
            admission_status=admission.status if admission else "MISSING",
            scope=paths, reasons=tuple(sorted(reasons)),
            observed_violations=violations, waived_violations=waived,
            evidence_sha256=artifact_digest,
        ))

    overall: Literal["PASS", "FAIL", "UNKNOWN"]
    if any(item.status == "FAIL" for item in results):
        overall = "FAIL"
    elif any(item.status == "UNKNOWN" for item in results):
        overall = "UNKNOWN"
    else:
        overall = "PASS"
    return GateDecision(
        schema_version="0.1", policy_id=policy.policy_id,
        policy_fingerprint=fingerprint, snapshot_id=policy.snapshot_id,
        evaluated_at=evaluated_at, status=overall,
        authorization="ALLOW" if overall == "PASS" else "BLOCK",
        requirements=tuple(results), reasons=tuple(sorted(caller_reasons)),
    )
