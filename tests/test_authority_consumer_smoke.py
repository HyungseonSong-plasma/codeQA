"""#121: real-receipt consumer serialization and authority negative controls."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import unittest

from codeqa.evaluation.evidence_gate import GateDecision, RequirementDecision
from codeqa.evaluation.formal_generated_gate import GeneratedFixtureDecision
from codeqa.evaluation.authority_audit import audit_authority_propagation
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / ".github/scripts/authority_consumer_smoke.py"
spec = spec_from_file_location("authority_consumer_smoke", SCRIPT)
module = module_from_spec(spec)
spec.loader.exec_module(module)

SOURCE = "a" * 40
SNAPSHOT = "git:HyungseonSong-plasma/codeQA@" + SOURCE
RUN = "40246531767"


class AuthorityConsumerSmokeTests(unittest.TestCase):
    def setUp(self):
        gate = GateDecision(
            schema_version="0.1", policy_id="test", policy_fingerprint="b" * 64,
            snapshot_id=SNAPSHOT, evaluated_at="2026-10-25T12:00:00+00:00",
            status="UNKNOWN", authorization="BLOCK",
            requirements=(RequirementDecision(
                id="proof", status="UNKNOWN", admission_status="ADMISSIBLE",
                scope=("fixtures/formal/example.dfy",),
                reasons=("FORMAL_GATE_REQUIRES_IMPLEMENTATION_BINDING",),
                observed_violations=0, waived_violations=0,
                evidence_sha256="c" * 64,
            ),), reasons=(),
        )
        fixture = GeneratedFixtureDecision(
            version="0.1", scope="CONTROLLED_GENERATED_PYTHON_FIXTURE",
            snapshot_id=SNAPSHOT, policy_fingerprint="d" * 64,
            status="PASS", authorization="ALLOW_FIXTURE_ONLY", reasons=(),
            evidence_artifact_sha256="e" * 64,
            generated_manifest_sha256="f" * 64,
            deployed_manifest_sha256="f" * 64,
            requirement_ids=("Example.postcondition",),
        )
        self.document = {
            "gate": gate.to_document(),
            "generated_fixture_gate": asdict(fixture),
        }

    def evaluate(self, **kwargs):
        return module.consume_dafny_authority_artifact(
            self.document, source_sha=kwargs.get("source_sha", SOURCE),
            run_id=kwargs.get("run_id", RUN),
        )

    def test_real_shape_round_trip_is_limited_and_never_merge(self):
        result = self.evaluate()
        self.assertEqual(result["general_gate"]["consumer_authorization"], "BLOCK")
        self.assertEqual(result["generated_fixture_gate"]["consumer_authorization"], "FIXTURE_ONLY")
        self.assertFalse(result["production_merge_authorized"])
        self.assertIn("NOT_REMOTE_ATTESTATION", result["artifact_authority"])

    def test_forged_production_allow_rejected(self):
        self.document["gate"]["status"] = "PASS"
        self.document["gate"]["authorization"] = "ALLOW"
        with self.assertRaises(ValueError):
            self.evaluate()

    def test_forged_fixture_production_allow_rejected(self):
        self.document["generated_fixture_gate"]["authorization"] = "ALLOW"
        with self.assertRaises(ValueError):
            self.evaluate()

    def test_missing_fixture_or_unknown_fields_rejected(self):
        self.document.pop("generated_fixture_gate")
        with self.assertRaises(ValueError):
            self.evaluate()

    def test_snapshot_and_source_sha_mismatch_rejected(self):
        self.document["gate"]["snapshot_id"] = "git:other@sha"
        with self.assertRaises(ValueError):
            self.evaluate()
        with self.assertRaises(ValueError):
            self.evaluate(source_sha="not-a-sha")

    def test_invalid_run_identity_rejected(self):
        with self.assertRaises(ValueError):
            self.evaluate(run_id="not-a-run")

    def test_requirement_shape_roundtrip_drift_rejected(self):
        self.document["gate"]["requirements"][0]["unexpected"] = "unsafe"
        with self.assertRaises(TypeError):
            self.evaluate()


if __name__ == "__main__":
    unittest.main()
