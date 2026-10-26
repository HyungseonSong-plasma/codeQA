"""Adversarial typed Gate→consumer propagation controls (#121)."""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import unittest

from codeqa.evaluation.authority_audit import audit_authority_propagation
from codeqa.evaluation.evidence_gate import GateDecision, RequirementDecision
from codeqa.evaluation.formal_generated_gate import GeneratedFixtureDecision


POLICY = "a" * 64
SOURCE = "b" * 40
SNAPSHOT = "git:HyungseonSong-plasma/codeQA@" + SOURCE
CI_URL = "https://github.com/HyungseonSong-plasma/codeQA/actions/runs/40242127832"


class AuthorityPropagationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gate = GateDecision(
            schema_version="0.1", policy_id="test", policy_fingerprint=POLICY,
            snapshot_id=SNAPSHOT, evaluated_at="2026-10-25T00:00:00Z",
            status="PASS", authorization="ALLOW",
            requirements=(RequirementDecision(
                id="scope-gate", status="PASS", admission_status="ADMISSIBLE",
                scope=("a.py",), reasons=(), observed_violations=0,
                waived_violations=0, evidence_sha256="d"*64,
            ),), reasons=(),
        )
        self.fixture = GeneratedFixtureDecision(
            version="0.1", scope="CONTROLLED_GENERATED_PYTHON_FIXTURE",
            snapshot_id=SNAPSHOT, policy_fingerprint=POLICY, status="PASS",
            authorization="ALLOW_FIXTURE_ONLY", reasons=(),
            evidence_artifact_sha256="c" * 64,
            generated_manifest_sha256="d" * 64,
            deployed_manifest_sha256="d" * 64,
            requirement_ids=("proof",),
        )

    def receipt(self, decision, producer):
        return {
            "schema_version": "0.1", "producer": producer,
            "decision_sha256": sha256(decision.canonical_json().encode()).hexdigest(),
            "snapshot_id": SNAPSHOT, "policy_fingerprint": POLICY,
            "source_sha": SOURCE, "ci_run_url": CI_URL,
        }

    def check(self, decision, receipt):
        return audit_authority_propagation(
            decision, expected_snapshot_id=SNAPSHOT,
            expected_policy_fingerprint=POLICY,
            expected_source_sha=SOURCE, receipt=receipt,
        )

    def test_scoped_gate_allow_is_not_merge_authorization(self) -> None:
        result = self.check(self.gate, self.receipt(self.gate, "codeqa.evidence_gate"))
        self.assertEqual(result.consumer_authorization, "SCOPED_GATE_ALLOW")
        self.assertFalse(result.production_merge_authorized)
        self.assertEqual(result.status, "LIMITED")

    def test_formal_fixture_only_never_becomes_production_allow(self) -> None:
        result = self.check(self.fixture, self.receipt(self.fixture, "codeqa.formal_generated_gate"))
        self.assertEqual(result.consumer_authorization, "FIXTURE_ONLY")
        self.assertFalse(result.production_merge_authorized)
        self.assertIn("PRODUCTION_AUTHORITY_NOT_ESTABLISHED_BY_FIXTURE", result.reasons)


    def test_empty_gate_pass_fails_closed_for_missing_evidence(self) -> None:
        empty = replace(self.gate, requirements=())
        result = self.check(empty, self.receipt(empty, "codeqa.evidence_gate"))
        self.assertEqual(result.consumer_authorization, "BLOCK")
        self.assertIn("GATE_REQUIREMENTS_OR_ADMITTED_EVIDENCE_MISSING", result.reasons)
        self.assertFalse(result.production_merge_authorized)

    def test_non_admitted_gate_requirement_does_not_authorize(self) -> None:
        rejected = replace(
            self.gate, requirements=(replace(
                self.gate.requirements[0], admission_status="NOT_EVALUATED",
            ),),
        )
        result = self.check(rejected, self.receipt(rejected, "codeqa.evidence_gate"))
        self.assertEqual(result.consumer_authorization, "BLOCK")

    def test_forged_gate_requirement_with_violations_cannot_allow(self) -> None:
        forged = replace(self.gate, requirements=(replace(
            self.gate.requirements[0], observed_violations=1,
        ),))
        result = self.check(forged, self.receipt(forged, "codeqa.evidence_gate"))
        self.assertEqual(result.consumer_authorization, "BLOCK")
        self.assertIn("GATE_REQUIREMENTS_OR_ADMITTED_EVIDENCE_MISSING", result.reasons)

    def test_duplicate_gate_requirement_ids_cannot_allow(self) -> None:
        forged = replace(self.gate, requirements=self.gate.requirements * 2)
        self.assertEqual(
            self.check(forged, self.receipt(forged, "codeqa.evidence_gate")).consumer_authorization,
            "BLOCK",
        )

    def test_forged_fixture_scope_cannot_promote_authority(self) -> None:
        forged = replace(self.fixture, scope="PRODUCTION_DEPLOYMENT")
        result = self.check(forged, self.receipt(forged, "codeqa.formal_generated_gate"))
        self.assertEqual(result.consumer_authorization, "BLOCK")
        self.assertFalse(result.production_merge_authorized)

    def test_fixture_broken_manifest_identity_cannot_allow(self) -> None:
        forged = replace(self.fixture, deployed_manifest_sha256="e" * 64)
        self.assertEqual(
            self.check(forged, self.receipt(forged, "codeqa.formal_generated_gate")).consumer_authorization,
            "BLOCK",
        )

    def test_fixture_missing_requirements_cannot_allow(self) -> None:
        forged = replace(self.fixture, requirement_ids=())
        self.assertEqual(
            self.check(forged, self.receipt(forged, "codeqa.formal_generated_gate")).consumer_authorization,
            "BLOCK",
        )

    def test_coherent_receipt_cannot_bind_wrong_source_revision(self) -> None:
        stale = "git:HyungseonSong-plasma/codeQA@" + "c" * 40
        gate = replace(self.gate, snapshot_id=stale)
        receipt = self.receipt(gate, "codeqa.evidence_gate")
        receipt["snapshot_id"] = stale
        result = audit_authority_propagation(
            gate, expected_snapshot_id=stale,
            expected_policy_fingerprint=POLICY,
            expected_source_sha=SOURCE, receipt=receipt,
        )
        self.assertEqual(result.consumer_authorization, "BLOCK")
        self.assertIn("SNAPSHOT_SOURCE_BINDING_UNVERIFIED", result.reasons)

    def test_opaque_snapshot_cannot_authorize_even_with_matching_receipt(self) -> None:
        opaque = "git:fixture-without-commit"
        gate = replace(self.gate, snapshot_id=opaque)
        receipt = self.receipt(gate, "codeqa.evidence_gate")
        receipt["snapshot_id"] = opaque
        result = audit_authority_propagation(
            gate, expected_snapshot_id=opaque,
            expected_policy_fingerprint=POLICY,
            expected_source_sha=SOURCE, receipt=receipt,
        )
        self.assertEqual(result.consumer_authorization, "BLOCK")
        self.assertIn("SNAPSHOT_SOURCE_BINDING_UNVERIFIED", result.reasons)

    def test_missing_receipt_blocks_even_when_gate_passes(self) -> None:
        self.assertEqual(self.check(self.gate, None).consumer_authorization, "BLOCK")

    def test_replayed_decision_digest_blocks(self) -> None:
        receipt = self.receipt(self.gate, "codeqa.evidence_gate")
        receipt["decision_sha256"] = "f" * 64
        self.assertEqual(self.check(self.gate, receipt).consumer_authorization, "BLOCK")

    def test_wrong_issuer_blocks(self) -> None:
        receipt = self.receipt(self.gate, "codeqa.formal_generated_gate")
        self.assertEqual(self.check(self.gate, receipt).consumer_authorization, "BLOCK")

    def test_wrong_source_sha_blocks(self) -> None:
        receipt = self.receipt(self.gate, "codeqa.evidence_gate")
        receipt["source_sha"] = "e" * 40
        self.assertEqual(self.check(self.gate, receipt).consumer_authorization, "BLOCK")

    def test_unknown_gate_cannot_be_promoted(self) -> None:
        unknown = replace(self.gate, status="UNKNOWN", authorization="BLOCK")
        self.assertEqual(
            self.check(unknown, self.receipt(unknown, "codeqa.evidence_gate")).consumer_authorization,
            "BLOCK",
        )

    def test_policy_mismatch_blocks(self) -> None:
        receipt = self.receipt(self.gate, "codeqa.evidence_gate")
        result = audit_authority_propagation(
            self.gate, expected_snapshot_id=SNAPSHOT,
            expected_policy_fingerprint="e" * 64,
            expected_source_sha=SOURCE, receipt=receipt,
        )
        self.assertEqual(result.consumer_authorization, "BLOCK")

    def test_missing_remote_run_reference_blocks(self) -> None:
        receipt = self.receipt(self.gate, "codeqa.evidence_gate")
        receipt["ci_run_url"] = "https://example.com/pretend"
        self.assertEqual(self.check(self.gate, receipt).consumer_authorization, "BLOCK")

    def test_other_repository_ci_url_cannot_attest_this_source(self) -> None:
        receipt = self.receipt(self.gate, "codeqa.evidence_gate")
        receipt["ci_run_url"] = "https://github.com/another/repo/actions/runs/40242127832"
        result = self.check(self.gate, receipt)
        self.assertEqual(result.consumer_authorization, "BLOCK")
        self.assertIn("RECEIPT_CI_REPOSITORY_MISMATCH", result.reasons)
        self.assertFalse(result.production_merge_authorized)

    def test_dot_segment_ci_repository_is_not_a_valid_receipt(self) -> None:
        receipt = self.receipt(self.gate, "codeqa.evidence_gate")
        receipt["ci_run_url"] = "https://github.com/../repo/actions/runs/40242127832"
        result = self.check(self.gate, receipt)
        self.assertEqual(result.consumer_authorization, "BLOCK")
        self.assertIn("RECEIPT_CI_LINK_UNVERIFIED", result.reasons)

    def test_untyped_json_cannot_be_a_trusted_decision(self) -> None:
        with self.assertRaises(TypeError):
            self.check(self.gate.to_document(), self.receipt(self.gate, "codeqa.evidence_gate"))


if __name__ == "__main__":
    unittest.main()
