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
        allowed = decision.status == "PASS" and decision.authorization == "ALLOW"
    elif isinstance(decision, GeneratedFixtureDecision):
        producer = "codeqa.formal_generated_gate"
        decision_type = "FORMAL_GENERATED_FIXTURE_V0_1"
        scope = "CONTROLLED_GENERATED_PYTHON_FIXTURE"
        allowed = decision.status == "PASS" and decision.authorization == "ALLOW_FIXTURE_ONLY"
    else:
        raise TypeError("only actual typed Gate or GeneratedFixture decisions are accepted")
    digest = _sha256(decision.canonical_json().encode("utf-8"))
    reasons: set[str] = set()
    if not expected_snapshot_id or decision.snapshot_id != expected_snapshot_id:
        reasons.add("SNAPSHOT_MISMATCH_OR_UNPINNED")
    if (not re.fullmatch(r"[0-9a-f]{64}", expected_policy_fingerprint or "")
            or decision.policy_fingerprint != expected_policy_fingerprint):
        reasons.add("POLICY_MISMATCH_OR_UNPINNED")
    if not re.fullmatch(r"[0-9a-f]{40}", expected_source_sha or ""):
        reasons.add("SOURCE_SHA_UNPINNED")
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
        if (not isinstance(url, str)
                or not re.fullmatch(
                    r"https://github\.com/[^/]+/[^/]+/actions/runs/[1-9][0-9]*", url
                )):
            reasons.add("RECEIPT_CI_LINK_UNVERIFIED")
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
        source_sha=expected_source_sha if re.fullmatch(r"[0-9a-f]{40}", expected_source_sha or "") else None,
        ci_run_url=url if isinstance(url, str) else None,
        original_authorization=decision.authorization,
        consumer_authorization=consumer,
        production_merge_authorized=False,
        status="LIMITED" if consumer != "BLOCK" else "NOT_EVALUATED",
        reasons=tuple(sorted(reasons)),
    )
