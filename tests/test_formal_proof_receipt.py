"""#102: source proof receipt does not authorize an implementation."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import json
import unittest

from codeqa.core.external_evidence import ToolIdentity, parse_external_evidence
from codeqa.evaluation.formal_proof_receipt import (
    SolverIdentity, assess_formal_proof_evidence,
)
from codeqa.infrastructure.resources import ResourceRegistry


ROOT = Path(__file__).resolve().parents[1]


def digest(value: bytes) -> str:
    return sha256(value).hexdigest()


class FormalProofReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = ResourceRegistry(ROOT).load_json("external_evidence_envelope_schema")

    def setUp(self):
        self.path = "fixtures/formal/example.dfy"
        self.source = b"method Example(x: int) returns (y: int) ensures y == x + 1 { y := x + 1; }\n"
        self.log = b"Dafny program verifier finished with 2 verified, 0 errors\n"
        self.snapshot = "git:fixture@0123456789abcdef0123456789abcdef01234567"
        self.tool = {
            "name": "Dafny", "version": "4.11.0",
            "binary_sha256": "a" * 64, "adapter_version": "0.1",
            "invocation_sha256": "b" * 64, "ruleset_sha256": "c" * 64,
            "exit_classifier": "dafny-4.11.0-verify-summary-v1",
        }
        self.solver = SolverIdentity("Z3", "4.13.0", "d" * 64)
        self.document = {
            "schema_version": "0.1", "snapshot_id": self.snapshot,
            "tool": deepcopy(self.tool),
            "execution": {
                "state": "COMPLETED", "exit_code": 0,
                "exit_classification": "VALID_RESULT",
                "started_at": "2026-10-24T12:00:00+00:00",
                "finished_at": "2026-10-24T12:00:01+00:00",
            },
            "scope": {
                "expected_files": [{"path": self.path, "sha256": digest(self.source)}],
                "scanned_files": [{"path": self.path, "sha256": digest(self.source)}],
                "skipped_files": [], "parser_errors": [],
                "required_rules": ["dafny.program"], "evaluated_rules": ["dafny.program"],
            },
            "raw_artifact": {
                "uri": "artifact://ci/verification.log", "sha256": digest(self.log),
                "media_type": "text/plain",
            },
            "observations": [{
                "kind": "FORMAL_PROOF_RESULT",
                "obligation_id": "Example.postcondition",
                "path": self.path, "source_sha256": digest(self.source),
                "native_status": "VERIFIED", "assumptions": ["Pinned Dafny trusted base"],
                "counterexample_sha256": None,
            }],
        }

    def assess(self, **changes):
        arguments = {
            "evidence": parse_external_evidence(self.document, self.schema),
            "expected_snapshot_id": self.snapshot,
            "expected_specification_path": self.path,
            "expected_specification_sha256": digest(self.source),
            "expected_tool": ToolIdentity(**self.tool),
            "expected_rules": ("dafny.program",),
            "required_obligations": ("Example.postcondition",),
            "accepted_assumptions": ("Pinned Dafny trusted base",),
            "raw_verifier_log": self.log,
            "observed_solver": self.solver,
            "expected_solver": self.solver,
        }
        arguments.update(changes)
        return assess_formal_proof_evidence(**arguments)

    def test_complete_pinned_source_receipt_still_blocks_implementation(self):
        receipt = self.assess()
        self.assertEqual(receipt.status, "SOURCE_RECEIPT_CONSISTENT")
        self.assertEqual(receipt.implementation_authorization, "BLOCK")
        self.assertEqual(receipt.evidence_scope, "VERIFIED_SPECIFICATION_ONLY")
        self.assertEqual(receipt.reasons, ())
        self.assertEqual(json.loads(receipt.canonical_json())["solver"]["name"], "Z3")

    def test_missing_solver_is_not_evaluated_even_with_verified_source(self):
        receipt = self.assess(observed_solver=None, expected_solver=None)
        self.assertEqual(receipt.status, "NOT_EVALUATED")
        self.assertIn("SOLVER_PROVENANCE_NOT_EVALUATED", receipt.reasons)
        self.assertEqual(receipt.implementation_authorization, "BLOCK")

    def test_caller_asserted_solver_without_independent_pin_is_unknown(self):
        receipt = self.assess(expected_solver=None)
        self.assertEqual(receipt.status, "NOT_EVALUATED")
        self.assertIn("INDEPENDENT_SOLVER_EXPECTATION_MISSING", receipt.reasons)

    def test_changed_solver_version_and_binary_are_rejected(self):
        for solver in (SolverIdentity("Z3", "4.14.0", "d" * 64),
                       SolverIdentity("Z3", "4.13.0", "e" * 64)):
            with self.subTest(solver=solver):
                receipt = self.assess(observed_solver=solver)
                self.assertEqual(receipt.status, "BLOCK")
                self.assertIn("SOLVER_IDENTITY_MISMATCH", receipt.reasons)

    def test_changed_specification_and_wrong_tool_are_rejected(self):
        self.assertEqual(self.assess(
            expected_specification_sha256="e" * 64).status, "BLOCK")
        self.assertEqual(self.assess(
            expected_tool=ToolIdentity(**{**self.tool, "version": "4.12.0"})).status, "BLOCK")

    def test_ambiguous_or_forged_summary_is_rejected(self):
        for log in (
            b"0 verified, 0 errors\n",
            b"not actually a Dafny summary: 2 verified, 0 errors\n",
            self.log + self.log,
            b"Dafny program verifier finished with 2 verified, 1 error\n",
        ):
            with self.subTest(log=log):
                self.document["raw_artifact"]["sha256"] = digest(log)
                receipt = self.assess(raw_verifier_log=log)
                self.assertEqual(receipt.status, "BLOCK")
                self.assertIn("VERIFIER_SUMMARY_NOT_UNAMBIGUOUS_SUCCESS", receipt.reasons)

    def test_crashed_or_nonzero_verifier_never_verifies(self):
        self.document["execution"]["exit_code"] = 1
        self.assertIn("VERIFIER_EXIT_NOT_SUCCESS", self.assess().reasons)
        self.document["execution"]["exit_code"] = 0
        self.document["execution"]["exit_classification"] = "EXECUTION_FAILURE"
        self.assertEqual(self.assess().status, "BLOCK")

    def test_unverified_or_missing_obligation_cannot_pass(self):
        self.document["observations"][0]["native_status"] = "TIMEOUT"
        self.assertEqual(self.assess().status, "BLOCK")
        self.document["observations"][0]["native_status"] = "VERIFIED"
        self.assertEqual(self.assess(required_obligations=("Missing.postcondition",)).status, "BLOCK")

    def test_changed_assumption_or_counterexample_rejected(self):
        self.document["observations"][0]["assumptions"] = ["Unreviewed axiom"]
        self.assertIn("UNREVIEWED_PROOF_ASSUMPTIONS", self.assess().reasons)
        self.document["observations"][0]["assumptions"] = ["Pinned Dafny trusted base"]
        self.document["observations"][0]["counterexample_sha256"] = "f" * 64
        self.assertEqual(self.assess().status, "BLOCK")

    def test_missing_raw_receipt_is_unknown_not_positive(self):
        self.assertEqual(self.assess(raw_verifier_log=None).status, "NOT_EVALUATED")

    def test_noncanonical_specification_paths_rejected(self):
        for path in (
            "../engine.dfy",
            "models/../engine.dfy",
            "./engine.dfy",
            "models/./engine.dfy",
        ):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.assess(expected_specification_path=path)

    def test_bad_solver_identity_or_unpinned_requirement_fails_closed(self):
        with self.assertRaises(ValueError):
            SolverIdentity("Z3", "", "d" * 64)
        with self.assertRaises(ValueError):
            self.assess(required_obligations=())
        with self.assertRaises(ValueError):
            self.assess(expected_specification_path="../engine.py")


if __name__ == "__main__":
    unittest.main()
