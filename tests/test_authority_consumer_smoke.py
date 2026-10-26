"""#121: real-receipt consumer serialization and authority negative controls."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import json
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
        # CI reads JSON bytes, not Python tuples from dataclass.asdict.
        self.document = json.loads(json.dumps({
            "gate": gate.to_document(),
            "generated_fixture_gate": asdict(fixture),
        }))

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


class GitHubRunReadbackTests(unittest.TestCase):
    def setUp(self):
        self.head = "b" * 40
        self.run = {
            "id": int(RUN), "run_attempt": 1, "event": "pull_request",
            "path": ".github/workflows/pinned-dafny-formal.yml",
            "repository": {"full_name": "HyungseonSong-plasma/codeQA"},
            "head_repository": {"full_name": "HyungseonSong-plasma/codeQA"},
            "head_sha": self.head, "status": "in_progress",
            "pull_requests": [{"number": 141, "head": {"sha": self.head}}],
        }
        self.commit = {"sha": SOURCE, "parents": [
            {"sha": "c" * 40}, {"sha": self.head},
        ]}
        self.args = dict(source_sha=SOURCE, run_id=RUN, event="pull_request",
                         ref="refs/pull/141/merge", attempt="1")

    def check(self):
        return module.verify_github_run_source_readback(
            self.run, self.commit, **self.args)

    def test_real_shape_readback_still_not_deployment_authority(self):
        report = self.check()
        self.assertEqual(report["status"], "GITHUB_API_RUN_SOURCE_RELATIONSHIP_VERIFIED")
        self.assertFalse(report["production_merge_authorized"])
        self.assertEqual(report["runner_and_artifact_authenticity"], "NOT_EVALUATED")

    def test_mismatched_pr_merge_second_parent_rejected(self):
        self.commit["parents"][1]["sha"] = "d" * 40
        with self.assertRaisesRegex(ValueError, "MERGE_HEAD"):
            self.check()

    def test_forged_run_repo_workflow_and_attempt_rejected(self):
        for key, value in (
            ("repository", {"full_name": "other/repo"}),
            ("path", ".github/workflows/other.yml"),
            ("run_attempt", 2),
        ):
            with self.subTest(key=key):
                run = deepcopy(self.run)
                run[key] = value
                with self.assertRaisesRegex(ValueError, "REMOTE_RUN"):
                    module.verify_github_run_source_readback(
                        run, self.commit, **self.args)

    def test_wrong_pr_head_or_number_rejected(self):
        self.run["pull_requests"][0]["number"] = 140
        with self.assertRaisesRegex(ValueError, "MERGE_HEAD"):
            self.check()
        self.run["pull_requests"][0]["number"] = 141
        self.run["pull_requests"][0]["head"]["sha"] = "e" * 40
        with self.assertRaisesRegex(ValueError, "MERGE_HEAD"):
            self.check()

    def test_branch_event_requires_direct_head_identity(self):
        self.run.update(event="push", head_sha=SOURCE, pull_requests=[])
        self.args.update(event="push", ref="refs/heads/main")
        self.assertEqual(self.check()["event"], "push")
        self.commit["sha"] = "f" * 40
        with self.assertRaisesRegex(ValueError, "REMOTE_RUN"):
            self.check()

    def test_unknown_event_or_unsafe_ref_rejected(self):
        self.run["event"] = "schedule"
        self.args["event"] = "schedule"
        with self.assertRaisesRegex(ValueError, "EVENT_NOT_SUPPORTED"):
            self.check()
        self.run["event"] = "push"
        self.run["head_sha"] = SOURCE
        self.args.update(event="push", ref="refs/heads/../unsafe")
        with self.assertRaisesRegex(ValueError, "BRANCH_HEAD"):
            self.check()


if __name__ == "__main__":
    unittest.main()
