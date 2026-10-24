"""#98: source- and artifact-attested external evidence conformance.

This is NOT the policy Gate, and an ADMISSIBLE finding is not a clean PASS.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator

from codeqa.core.external_evidence import (
    ExternalEvidenceError, ToolIdentity, assess_external_evidence,
    canonical_external_json, parse_external_evidence,
)
from codeqa.infrastructure.resources import ResourceRegistry


ROOT = Path(__file__).resolve().parents[1]


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


class ExternalEvidenceV01Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = ResourceRegistry(ROOT).load_json(
            "external_evidence_envelope_schema"
        )
        Draft202012Validator.check_schema(cls.schema)
        cls.artifact = b'{"tool": "sample", "results": []}\n'

    def example(self):
        source = b"def example():\n    pass\n"
        return {
            "schema_version": "0.1",
            "snapshot_id": "git:source@abc123",
            "tool": {
                "name": "Semgrep", "version": "1.test",
                "binary_sha256": "1" * 64, "adapter_version": "0.1",
                "invocation_sha256": "2" * 64,
                "ruleset_sha256": "3" * 64,
                "exit_classifier": "semgrep-json-1.test-checks-v1",
            },
            "execution": {
                "state": "COMPLETED", "exit_code": 0,
                "exit_classification": "VALID_RESULT",
                "started_at": "2026-10-24T20:00:00+00:00",
                "finished_at": "2026-10-24T20:00:02+00:00",
            },
            "scope": {
                "expected_files": [{"path": "src/sample.py", "sha256": digest(source)}],
                "scanned_files": [{"path": "src/sample.py", "sha256": digest(source)}],
                "skipped_files": [], "parser_errors": [],
                "required_rules": ["security.one"],
                "evaluated_rules": ["security.one"],
            },
            "raw_artifact": {
                "uri": "artifact://exact-run/semgrep.json",
                "sha256": digest(self.artifact),
                "media_type": "application/json",
            },
            "observations": [],
        }

    def admission(self, doc, **changes):
        kwargs = {
            "expected_snapshot_id": "git:source@abc123",
            "expected_files": {
                "src/sample.py": digest(b"def example():\n    pass\n"),
            },
            "expected_tool": ToolIdentity(**self.example()["tool"]),
            "expected_rules": ["security.one"],
            "raw_artifact": self.artifact,
        }
        kwargs.update(changes)
        return assess_external_evidence(
            parse_external_evidence(doc, self.schema), **kwargs
        )

    def assert_reason(self, doc, status, reason, **changes):
        got = self.admission(doc, **changes)
        self.assertEqual(got.status, status, got)
        self.assertIn(reason, got.reasons)

    def test_exact_unmodified_evidence_is_admissible_but_not_qa_pass(self):
        envelope = parse_external_evidence(self.example(), self.schema)
        self.assertEqual(self.admission(self.example()).status, "ADMISSIBLE")
        self.assertNotIn("verdict", envelope.to_document())
        self.assertEqual(envelope.schema_version, "0.1")
        self.assertEqual(self.schema["$id"],
                         "urn:codeqa:evidence:external-envelope:v0.1")

    def test_schema_round_trip_is_json_compatible(self):
        original = self.example()
        parsed = parse_external_evidence(original, self.schema)
        restored = json.loads(canonical_external_json(parsed))
        Draft202012Validator(self.schema).validate(restored)
        self.assertEqual(parse_external_evidence(restored, self.schema), parsed)

    def test_execution_timestamp_order_and_timezone_are_validated(self):
        base = self.example()
        for bad in ("bad time", "2026-10-24T20:00:00"):
            with self.subTest(bad=bad):
                doc = deepcopy(base)
                doc["execution"]["started_at"] = bad
                with self.assertRaises(ExternalEvidenceError):
                    parse_external_evidence(doc, self.schema)
        doc = deepcopy(base)
        doc["execution"]["finished_at"] = "2026-10-24T19:59:59+00:00"
        with self.assertRaises(ExternalEvidenceError):
            parse_external_evidence(doc, self.schema)

    def test_missing_end_receipt_is_indeterminate(self):
        doc = self.example()
        doc["execution"]["finished_at"] = None
        self.assert_reason(doc, "INDETERMINATE", "EXECUTION_END_UNRECORDED")

    def test_nonzero_exit_with_pinned_valid_classifier_is_not_automatic_crash(self):
        doc = self.example()
        doc["execution"]["exit_code"] = 1
        doc["execution"]["exit_classification"] = "VALID_RESULT"
        self.assertEqual(self.admission(doc).status, "ADMISSIBLE")

    def test_crash_oom_timeout_cancel_and_unknown_do_not_make_clean_evidence(self):
        for state in ("FAILED", "TIMED_OUT", "CANCELLED", "UNKNOWN"):
            with self.subTest(state=state):
                doc = self.example()
                doc["execution"]["state"] = state
                doc["execution"]["exit_code"] = 137
                doc["execution"]["exit_classification"] = "EXECUTION_FAILURE"
                self.assert_reason(doc, "INDETERMINATE", "EXECUTION_NOT_COMPLETED")

    def test_adapter_did_not_attest_success(self):
        for kind in ("EXECUTION_FAILURE", "UNDETERMINED"):
            with self.subTest(kind=kind):
                doc = self.example()
                doc["execution"]["exit_classification"] = kind
                self.assert_reason(doc, "INDETERMINATE", "TOOL_RESULT_NOT_ATTESTED_COMPLETE")

    def test_empty_scanned_scope_is_not_clearance(self):
        doc = self.example()
        doc["scope"]["scanned_files"] = []
        self.assert_reason(doc, "INDETERMINATE", "INCOMPLETE_SOURCE_COVERAGE")

    def test_same_file_count_wrong_file_cannot_claim_complete(self):
        doc = self.example()
        doc["scope"]["expected_files"].append({
            "path": "src/second.py", "sha256": "4" * 64,
        })
        doc["scope"]["scanned_files"].append({
            "path": "src/third.py", "sha256": "4" * 64,
        })
        with self.assertRaises(ExternalEvidenceError):
            parse_external_evidence(doc, self.schema)

    def test_scanned_source_digest_conflict_is_inadmissible(self):
        doc = self.example()
        doc["scope"]["scanned_files"][0]["sha256"] = "9" * 64
        self.assert_reason(doc, "INADMISSIBLE", "SCANNED_SOURCE_DIGEST_MISMATCH")

    def test_explicit_skip_or_parse_error_blocks_clean(self):
        for key in ("skipped_files", "parser_errors"):
            with self.subTest(key=key):
                doc = self.example()
                doc["scope"]["scanned_files"] = []
                doc["scope"][key] = [{
                    "path": "src/sample.py", "reason": "unsupported_syntax",
                }]
                self.assert_reason(
                    doc, "INDETERMINATE",
                    "SKIPPED_SOURCE_PATHS" if key == "skipped_files" else "PARSER_ERRORS",
                )

    def test_dropped_or_disabled_rules_preclude_admission(self):
        doc = self.example()
        doc["scope"]["evaluated_rules"] = []
        self.assert_reason(doc, "INDETERMINATE", "INCOMPLETE_RULE_COVERAGE")

    def test_unexpected_rule_and_wrong_expected_rules_fail_closed(self):
        doc = self.example()
        doc["scope"]["evaluated_rules"].append("extra.rule")
        self.assert_reason(doc, "INADMISSIBLE", "UNDECLARED_EXECUTED_RULE")
        self.assert_reason(
            self.example(), "INADMISSIBLE", "REQUIRED_RULE_SET_MISMATCH",
            expected_rules=["security.other"],
        )

    def test_raw_missing_or_forged_is_never_admissible(self):
        self.assert_reason(
            self.example(), "INDETERMINATE", "RAW_ARTIFACT_UNAVAILABLE",
            raw_artifact=None,
        )
        self.assert_reason(
            self.example(), "INADMISSIBLE", "RAW_ARTIFACT_DIGEST_MISMATCH",
            raw_artifact=b"tampered",
        )

    def test_source_snapshot_and_tool_mismatch(self):
        self.assert_reason(
            self.example(), "INADMISSIBLE", "SNAPSHOT_MISMATCH",
            expected_snapshot_id="git:source@different",
        )
        self.assert_reason(
            self.example(), "INADMISSIBLE", "EXPECTED_SOURCE_MANIFEST_MISMATCH",
            expected_files={"src/sample.py": "9" * 64},
        )
        self.assert_reason(
            self.example(), "INADMISSIBLE", "TOOL_OR_CONFIG_IDENTITY_MISMATCH",
            expected_tool=ToolIdentity(**{**self.example()["tool"], "version": "2.0"}),
        )

    def test_no_caller_attestation_is_never_admissible(self):
        self.assert_reason(
            self.example(), "INDETERMINATE", "TRUSTED_SOURCE_MANIFEST_UNAVAILABLE",
            expected_files=None,
        )
        self.assert_reason(
            self.example(), "INDETERMINATE", "TRUSTED_TOOL_EXPECTATION_UNAVAILABLE",
            expected_tool=None,
        )

    def test_retains_partial_findings_even_when_run_not_complete(self):
        doc = self.example()
        doc["execution"]["state"] = "TIMED_OUT"
        doc["execution"]["exit_classification"] = "EXECUTION_FAILURE"
        doc["observations"].append({
            "kind": "STATIC_FINDING",
            "rule_id": "security.one",
            "severity": "HIGH",
            "path": "src/sample.py", "line": 1,
            "message": "observed issue", "native_status": "error",
        })
        result = self.admission(doc)
        self.assertEqual(result.status, "INDETERMINATE")
        self.assertEqual(result.retained_observations, 1)
        self.assertEqual(len(parse_external_evidence(doc, self.schema).observations), 1)

    def test_typed_diagnostics_do_not_become_generic_confidence(self):
        doc = self.example()
        doc["observations"] = [{
            "kind": "TYPECHECK_DIAGNOSTIC",
            "rule_id": "security.one", "severity": "ERROR",
            "path": "src/sample.py", "line": 1,
            "message": "type mismatch", "native_status": "reportGeneralTypeIssues",
        }]
        report = parse_external_evidence(doc, self.schema)
        self.assertEqual(self.admission(doc).status, "ADMISSIBLE")
        self.assertNotIn("confidence", report.to_document()["observations"][0])

    def test_proof_does_not_certify_implementation_without_binding(self):
        doc = self.example()
        doc["scope"]["expected_files"][0]["path"] = "src/spec.dfy"
        doc["scope"]["scanned_files"][0]["path"] = "src/spec.dfy"
        doc["observations"] = [{
            "kind": "FORMAL_PROOF_RESULT", "obligation_id": "payment.invariant",
            "path": "src/spec.dfy",
            "source_sha256": doc["scope"]["scanned_files"][0]["sha256"],
            "native_status": "VERIFIED", "assumptions": ["bounded-model"],
            "counterexample_sha256": None,
        }]
        result = self.admission(
            doc,
            expected_files={"src/spec.dfy": doc["scope"]["scanned_files"][0]["sha256"]},
            purpose="IMPLEMENTATION_PROOF",
        )
        self.assertEqual(result.status, "INDETERMINATE")
        self.assertIn("FORMAL_IMPLEMENTATION_BINDING_NOT_VERIFIED", result.reasons)

    def test_forged_proof_source_is_inadmissible(self):
        doc = self.example()
        doc["observations"] = [{
            "kind": "FORMAL_PROOF_RESULT", "obligation_id": "spec",
            "path": "src/sample.py", "source_sha256": "f" * 64,
            "native_status": "VERIFIED", "assumptions": [],
            "counterexample_sha256": None,
        }]
        self.assert_reason(doc, "INADMISSIBLE", "PROOF_SOURCE_DIGEST_MISMATCH")

    def test_observation_with_unknown_rule_fails(self):
        doc = self.example()
        doc["observations"] = [{
            "kind": "STATIC_FINDING", "rule_id": "other",
            "severity": "HIGH", "path": "src/sample.py", "line": 1,
            "message": "wrong rule", "native_status": "error",
        }]
        self.assert_reason(doc, "INADMISSIBLE", "OBSERVATION_RULE_NOT_EVALUATED")

    def test_unsafe_path_and_malformed_records_rejected_by_schema(self):
        for value in ("../secret.py", "/etc/passwd", "src/../sample.py",
                      "C:\\workspace\\x.py", "src//x.py"):
            with self.subTest(value=value):
                doc = self.example()
                doc["scope"]["expected_files"][0]["path"] = value
                with self.assertRaises(ExternalEvidenceError):
                    parse_external_evidence(doc, self.schema)
        for part in ("tool", "execution", "scope", "raw_artifact"):
            doc = self.example()
            doc[part]["invented_property"] = "x"
            with self.assertRaises(ExternalEvidenceError):
                parse_external_evidence(doc, self.schema)

    def test_duplicate_sources_and_observations_are_rejected(self):
        doc = self.example()
        doc["scope"]["expected_files"].append(deepcopy(
            doc["scope"]["expected_files"][0]
        ))
        with self.assertRaises(ExternalEvidenceError):
            parse_external_evidence(doc, self.schema)
        doc = self.example()
        doc["observations"] = [{
            "kind": "STATIC_FINDING", "rule_id": "security.one",
            "severity": "HIGH", "path": "src/sample.py", "line": 1,
            "message": "issue", "native_status": "reported",
        }] * 2
        with self.assertRaises(ExternalEvidenceError):
            parse_external_evidence(doc, self.schema)

    def test_canonical_serialization_is_order_independent(self):
        first = self.example()
        first["scope"]["expected_files"].append({
            "path": "src/z.py", "sha256": "4" * 64,
        })
        first["scope"]["scanned_files"].append({
            "path": "src/z.py", "sha256": "4" * 64,
        })
        second = deepcopy(first)
        second["scope"]["expected_files"].reverse()
        second["scope"]["scanned_files"].reverse()
        self.assertEqual(canonical_external_json(
            parse_external_evidence(first, self.schema)
        ), canonical_external_json(
            parse_external_evidence(second, self.schema)
        ))


if __name__ == "__main__":
    unittest.main()
