"""Read-only scoped authorization consumer boundary (#121).

This never grants a production merge, deploy, or semantic preservation claim.
Receipts are independently caller-pinned input, not verified remote CI facts.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from typing import Any, Mapping

from codeqa.evaluation.evidence_gate import GateDecision
from codeqa.evaluation.formal_generated_gate import GeneratedFixtureDecision


@dataclass(frozen=True, slots=True)
class AuthorityPropagationAudit:
    schema_version: str
    decision_type: str
    decision_scope: str
    snapshot_id: str
    policy_fingerprint: str
    decision_sha256: str
    producer: str
    source_sha: str | None
    ci_run_url: str | None
    original_authorization: str
    consumer_authorization: str
    production_merge_authorized: bool
    status: str
    reasons: tuple[str, ...]
    evidence_level: str = "CALLER_PINNED_RECEIPT_ONLY_NOT_INDEPENDENT_CI_VERIFICATION"

    def to_document(self) -> dict[str, Any]:
        return asdict(self)


def _sha256(value: bytes) -> str:
    return sha256(value).hexdigest()


def audit_authority_propagation(
    decision: GateDecision | GeneratedFixtureDecision,
    *,
    expected_snapshot_id: str,
    expected_policy_fingerprint: str,
    expected_source_sha: str,
    receipt: Mapping[str, str] | None,
) -> AuthorityPropagationAudit:
    """Require independently selected context and exact decision serialization.

    A self-supplied receipt does not attest remote GitHub Actions execution.
    Downstream must independently fetch exact-head CI and policy approval.
    """
    if isinstance(decision, GateDecision):
        producer = "codeqa.evidence_gate"
        decision_type = "EVIDENCE_GATE_V0_1"
        scope = "PINNED_POLICY_REQUIREMENTS_ONLY"
        ids = [entry.id for entry in decision.requirements]
        gate_claims_covered = (
            decision.schema_version == "0.1"
            and isinstance(decision.policy_id, str) and bool(decision.policy_id)
            and bool(ids) and len(ids) == len(set(ids))
            and not decision.reasons
            and all(
                isinstance(entry.id, str) and bool(entry.id)
                and entry.status == "PASS" and entry.admission_status == "ADMISSIBLE"
                and isinstance(entry.scope, tuple) and bool(entry.scope)
                and all(isinstance(path, str) and bool(path) for path in entry.scope)
                and type(entry.observed_violations) is int and entry.observed_violations == 0
                and type(entry.waived_violations) is int and entry.waived_violations == 0
                and not entry.reasons
                and isinstance(entry.evidence_sha256, str)
                and re.fullmatch(r"[0-9a-f]{64}", entry.evidence_sha256)
                for entry in decision.requirements
            )
        )
        allowed = (
            decision.status == "PASS" and decision.authorization == "ALLOW"
            and gate_claims_covered
        )
    elif isinstance(decision, GeneratedFixtureDecision):
        producer = "codeqa.formal_generated_gate"
        decision_type = "FORMAL_GENERATED_FIXTURE_V0_1"
        scope = "CONTROLLED_GENERATED_PYTHON_FIXTURE"
        fixture_digests = (
            decision.evidence_artifact_sha256,
            decision.generated_manifest_sha256,
            decision.deployed_manifest_sha256,
        )
        allowed = (
            decision.version == "0.1"
            and decision.scope == "CONTROLLED_GENERATED_PYTHON_FIXTURE"
            and decision.status == "PASS"
            and decision.authorization == "ALLOW_FIXTURE_ONLY"
            and not decision.reasons
            and all(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
                    for value in fixture_digests)
            and decision.generated_manifest_sha256 == decision.deployed_manifest_sha256
            and isinstance(decision.requirement_ids, tuple)
            and bool(decision.requirement_ids)
            and len(set(decision.requirement_ids)) == len(decision.requirement_ids)
            and all(isinstance(value, str) and bool(value)
                    for value in decision.requirement_ids)
        )
    else:
        raise TypeError("only actual typed Gate or GeneratedFixture decisions are accepted")
    digest = _sha256(decision.canonical_json().encode("utf-8"))
    reasons: set[str] = set()
    if decision_type == "EVIDENCE_GATE_V0_1" and not gate_claims_covered:
        reasons.add("GATE_REQUIREMENTS_OR_ADMITTED_EVIDENCE_MISSING")
    if not expected_snapshot_id or decision.snapshot_id != expected_snapshot_id:
        reasons.add("SNAPSHOT_MISMATCH_OR_UNPINNED")
    if (not isinstance(expected_policy_fingerprint, str)
            or not re.fullmatch(r"[0-9a-f]{64}", expected_policy_fingerprint)
            or decision.policy_fingerprint != expected_policy_fingerprint):
        reasons.add("POLICY_MISMATCH_OR_UNPINNED")
    if (not isinstance(expected_source_sha, str)
            or not re.fullmatch(r"[0-9a-f]{40}", expected_source_sha)):
        reasons.add("SOURCE_SHA_UNPINNED")
    # A matching opaque snapshot string and separately matching source SHA do
    # not establish that the decision was evaluated against those source bytes.
    # Require one canonical Git revision identity before emitting scoped allow.
    # This is syntactic binding, NOT independent GitHub/run authentication.
    snapshot_match = (
        re.fullmatch(
            r"git:([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@([0-9a-f]{40})",
            expected_snapshot_id,
        )
        if isinstance(expected_snapshot_id, str) else None
    )
    if (snapshot_match is None or not isinstance(expected_source_sha, str)
            or snapshot_match.group(2) != expected_source_sha):
        reasons.add("SNAPSHOT_SOURCE_BINDING_UNVERIFIED")

    url = None
    if receipt is None:
        reasons.add("INDEPENDENT_RECEIPT_MISSING")
    elif not isinstance(receipt, Mapping) or set(receipt) != {
        "schema_version", "producer", "decision_sha256", "snapshot_id",
        "policy_fingerprint", "source_sha", "ci_run_url",
    }:
        reasons.add("RECEIPT_SCHEMA_UNVERIFIED")
    else:
        url = receipt["ci_run_url"]
        if receipt["schema_version"] != "0.1" or receipt["producer"] != producer:
            reasons.add("RECEIPT_PRODUCER_UNVERIFIED")
        if receipt["decision_sha256"] != digest:
            reasons.add("RECEIPT_DECISION_BYTES_MISMATCH")
        if receipt["snapshot_id"] != expected_snapshot_id:
            reasons.add("RECEIPT_SNAPSHOT_MISMATCH")
        if receipt["policy_fingerprint"] != expected_policy_fingerprint:
            reasons.add("RECEIPT_POLICY_MISMATCH")
        if receipt["source_sha"] != expected_source_sha:
            reasons.add("RECEIPT_SOURCE_MISMATCH")
        ci_match = (
            re.fullmatch(
                r"https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/actions/runs/[1-9][0-9]*",
                url,
            )
            if isinstance(url, str) else None
        )
        if ci_match is None or any(
            part in {".", ".."} for part in ci_match.groups()[:2]
        ):
            reasons.add("RECEIPT_CI_LINK_UNVERIFIED")
        elif (snapshot_match is not None
              and ci_match.group(1) + "/" + ci_match.group(2) != snapshot_match.group(1)):
            reasons.add("RECEIPT_CI_REPOSITORY_MISMATCH")
    if not allowed:
        reasons.add("DECISION_NOT_AUTHORIZED_WITHIN_OWN_SCOPE")
    if decision_type == "FORMAL_GENERATED_FIXTURE_V0_1":
        reasons.add("PRODUCTION_AUTHORITY_NOT_ESTABLISHED_BY_FIXTURE")
    else:
        reasons.add("PRODUCTION_MERGE_POLICY_NOT_EVALUATED")
    verified_receipt = not any(x for x in reasons if x not in {
        "PRODUCTION_AUTHORITY_NOT_ESTABLISHED_BY_FIXTURE",
        "PRODUCTION_MERGE_POLICY_NOT_EVALUATED",
    })
    consumer = (
        ("SCOPED_GATE_ALLOW" if decision_type == "EVIDENCE_GATE_V0_1" else "FIXTURE_ONLY")
        if allowed and verified_receipt else "BLOCK"
    )
    return AuthorityPropagationAudit(
        schema_version="0.1", decision_type=decision_type,
        decision_scope=scope, snapshot_id=decision.snapshot_id,
        policy_fingerprint=decision.policy_fingerprint,
        decision_sha256=digest, producer=producer,
        source_sha=(expected_source_sha if isinstance(expected_source_sha, str)
                    and re.fullmatch(r"[0-9a-f]{40}", expected_source_sha) else None),
        ci_run_url=url if isinstance(url, str) else None,
        original_authorization=decision.authorization,
        consumer_authorization=consumer,
        production_merge_authorized=False,
        status="LIMITED" if consumer != "BLOCK" else "NOT_EVALUATED",
        reasons=tuple(sorted(reasons)),
    )
