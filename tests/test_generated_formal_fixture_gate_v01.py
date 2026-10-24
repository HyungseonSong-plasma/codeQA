"""#102: generated-only fixture Gate is not the public production Formal Gate."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
import json
import unittest

from codeqa.core.external_evidence import parse_external_evidence, ToolIdentity
from codeqa.evaluation.formal_binding import parse_binding
from codeqa.evaluation.formal_generated_gate import (
    evaluate_generated_fixture_gate, parse_generated_fixture_policy,
    python_tree_manifest,
)
from codeqa.infrastructure.resources import ResourceRegistry


ROOT = Path(__file__).resolve().parents[1]


def digest(data):
    return sha256(data).hexdigest()


class GeneratedFormalFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = ResourceRegistry(ROOT).load_json("external_evidence_envelope_schema")

    def setUp(self):
        self.source = b"method Example(x: int) returns (y: int) ensures y == x + 1 { y := x + 1; }\n"
        self.path = "fixtures/formal/example.dfy"
        self.sha = digest(self.source)
        self.snapshot = "git:fixture@0123456789abcdef0123456789abcdef01234567"
        self.tool = {
            "name": "Dafny", "version": "4.11.0",
            "binary_sha256": "1" * 64,
            "adapter_version": "0.1",
            "invocation_sha256": "2" * 64,
            "ruleset_sha256": "3" * 64,
            "exit_classifier": "dafny-4.11.0-verify-summary-v1",
        }
        self.log = b"Dafny program verifier finished with 2 verified, 0 errors\n"
        self.gen = {
            "module_.py": b"def f(x): return x+1\n",
            "__main__.py": b"print(42)\n",
        }
        self.dep = dict(self.gen)
        self.proof = {
            "schema_version": "0.1", "snapshot_id": self.snapshot,
            "tool": deepcopy(self.tool),
            "execution": {"state": "COMPLETED", "exit_code": 0,
                          "exit_classification": "VALID_RESULT",
                          "started_at": "2026-10-24T12:00:00+00:00",
                          "finished_at": "2026-10-24T12:00:03+00:00"},
            "scope": {
                "expected_files": [{"path": self.path, "sha256": self.sha}],
                "scanned_files": [{"path": self.path, "sha256": self.sha}],
                "skipped_files": [], "parser_errors": [],
                "required_rules": ["dafny.program"],
                "evaluated_rules": ["dafny.program"],
            },
            "raw_artifact": {"uri": "artifact://run/verified.log",
                             "sha256": digest(self.log), "media_type": "text/plain"},
            "observations": [{
                "kind": "FORMAL_PROOF_RESULT",
                "obligation_id": "Example.postcondition",
                "path": self.path, "source_sha256": self.sha,
                "native_status": "VERIFIED", "assumptions": ["Trusted Dafny 4.11.0"],
                "counterexample_sha256": None,
            }],
        }
        self.record = {
            "schema_version": "0.1", "mode": "GENERATED_CODE_MATCH",
            "specification": {"role": "specification", "path": self.path, "sha256": self.sha},
            "generated": {"role": "generated", "path": "generated", "sha256": digest(python_tree_manifest(self.gen))},
            "deployed": {"role": "deployed", "path": "deployment", "sha256": digest(python_tree_manifest(self.dep))},
            "toolchain_id": "dafny@4.11.0:target=py",
            "toolchain_sha256": self.tool["binary_sha256"],
            "build_configuration_sha256": "4" * 64,
            "attestation_id": "trusted-fixture-run",
            "attested_properties": ["Example.postcondition"],
        }
        self.policy = {
            "version": "0.1",
            "scope": "CONTROLLED_GENERATED_PYTHON_FIXTURE",
            "snapshot_id": self.snapshot, "specification_path": self.path,
            "specification_sha256": self.sha,
            "required_properties": ["Example.postcondition"],
            "required_rule_ids": ["dafny.program"],
            "accepted_assumptions": ["Trusted Dafny 4.11.0"],
            "required_generated_paths": sorted(self.gen),
            "tool": deepcopy(self.tool),
            "expected_build_configuration_sha256": "4" * 64,
            "attestation_id": "trusted-fixture-run",
        }

    def decide(self, **overrides):
        policy = parse_generated_fixture_policy(self.policy)
        inputs = {
            "policy": policy,
            "expected_policy_sha256": policy.fingerprint(),
            "expected_snapshot_id": self.snapshot,
            "expected_tool": ToolIdentity(**self.tool),
            "evidence": parse_external_evidence(self.proof, self.schema),
            "raw_verifier_log": self.log,
            "specification_bytes": self.source,
            "generated_files": self.gen, "deployed_files": self.dep,
            "binding": parse_binding(self.record),
        }
        inputs.update(overrides)
        return evaluate_generated_fixture_gate(**inputs)

    def test_bounded_fixture_accepts_pinned_complete_chain(self):
        outcome = self.decide()
        self.assertEqual((outcome.status, outcome.authorization),
                         ("PASS", "ALLOW_FIXTURE_ONLY"))
        self.assertEqual(outcome.reasons, ())
        self.assertEqual(outcome.generated_manifest_sha256, outcome.deployed_manifest_sha256)
        self.assertEqual(json.loads(outcome.canonical_json())["scope"],
                         "CONTROLLED_GENERATED_PYTHON_FIXTURE")
        self.assertNotIn('"ALLOW"', outcome.canonical_json())

    def test_mutated_deployment_does_not_reuse_old_proof(self):
        self.dep["__main__.py"] += b"# changed\n"
        outcome = self.decide()
        self.assertEqual((outcome.status, outcome.authorization), ("UNKNOWN", "BLOCK"))
        self.assertIn("GENERATED_DEPLOYED_CONTENT_MISMATCH", outcome.reasons)

    def test_stale_spec_source_blocked(self):
        outcome = self.decide(specification_bytes=self.source + b"\n// drift")
        self.assertEqual(outcome.status, "UNKNOWN")
        self.assertIn("SPECIFICATION_BYTES_CHANGED", outcome.reasons)

    def test_wrong_tool_policy_snapshot_or_configuration_blocked(self):
        for key, change in (
            ("expected_policy_sha256", "e" * 64),
            ("expected_snapshot_id", "foreign-repo"),
            ("expected_tool", None),
        ):
            with self.subTest(key=key):
                outcome = self.decide(**{key: change})
                self.assertEqual(outcome.authorization, "BLOCK")
        self.policy["expected_build_configuration_sha256"] = "9" * 64
        self.assertEqual(self.decide().authorization, "BLOCK")

    def test_missing_extra_or_changed_generated_file_cannot_pass(self):
        for kind in ("missing", "extra", "modified"):
            with self.subTest(kind=kind):
                g = dict(self.gen)
                if kind == "missing":
                    g.pop("__main__.py")
                if kind == "extra":
                    g["other.py"] = b"pass\n"
                if kind == "modified":
                    g["module_.py"] += b"# changed\n"
                decision = self.decide(generated_files=g)
                self.assertEqual(decision.authorization, "BLOCK")

    def test_forged_proof_status_or_counterexample_blocked(self):
        self.proof["observations"][0]["native_status"] = "VERIFICATION_FAILED"
        self.assertEqual(self.decide().authorization, "BLOCK")
        self.proof["observations"][0]["native_status"] = "VERIFIED"
        self.proof["observations"][0]["counterexample_sha256"] = "a" * 64
        self.assertEqual(self.decide().authorization, "BLOCK")

    def test_missing_rule_coverage_or_wrong_obligation_blocked(self):
        self.proof["scope"]["evaluated_rules"] = []
        self.assertEqual(self.decide().authorization, "BLOCK")
        self.proof["scope"]["evaluated_rules"] = ["dafny.program"]
        self.proof["observations"][0]["obligation_id"] = "SomeOther.claim"
        self.assertEqual(self.decide().authorization, "BLOCK")

    def test_untrusted_or_changed_assumptions_blocked(self):
        self.proof["observations"][0]["assumptions"] = ["Unreviewed compiler assumption"]
        self.assertEqual(self.decide().authorization, "BLOCK")

    def test_crashed_verifier_empty_log_never_passes(self):
        self.proof["execution"]["state"] = "FAILED"
        self.proof["execution"]["exit_code"] = 137
        self.proof["execution"]["exit_classification"] = "EXECUTION_FAILURE"
        self.assertEqual(self.decide().authorization, "BLOCK")
        self.proof["execution"].update(state="COMPLETED", exit_code=0,
                                       exit_classification="VALID_RESULT")
        self.log = b"0 verified, 0 errors\n"
        self.proof["raw_artifact"]["sha256"] = digest(self.log)
        self.assertEqual(self.decide().authorization, "BLOCK")

    def test_extra_or_absent_raw_receipt_blocked(self):
        self.assertEqual(self.decide(raw_verifier_log=None).authorization, "BLOCK")
        self.assertEqual(self.decide(raw_verifier_log=b"forged").authorization, "BLOCK")

    def test_manual_translation_and_in_situ_are_not_supported(self):
        self.record["mode"] = "MANUAL_TRANSLATION_UNVERIFIED"
        self.record["generated"] = None
        self.assertEqual(self.decide().authorization, "BLOCK")

    def test_production_scope_is_rejected_at_policy_parse(self):
        self.policy["scope"] = "PRODUCTION_IMPLEMENTATION"
        with self.assertRaises(ValueError):
            parse_generated_fixture_policy(self.policy)

    def test_invalid_unsafe_source_or_generated_paths(self):
        self.policy["required_generated_paths"] = ["../secret.py"]
        with self.assertRaises(ValueError):
            parse_generated_fixture_policy(self.policy)

    def test_identities_are_stable_across_policy_key_order(self):
        p1 = parse_generated_fixture_policy(self.policy)
        p2 = parse_generated_fixture_policy(dict(reversed(list(self.policy.items()))))
        self.assertEqual(p1.fingerprint(), p2.fingerprint())


if __name__ == "__main__":
    unittest.main()
