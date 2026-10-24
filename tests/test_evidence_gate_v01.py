"""#99: scoped fail-closed three-valued Gate over independently admitted evidence."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import json
import unittest

from codeqa.infrastructure.resources import ResourceRegistry
from codeqa.core.external_evidence import parse_external_evidence
from codeqa.evaluation.evidence_gate import (
    EvidenceRun, GateContractError, evaluate_gate, parse_gate_policy,
)

ROOT = Path(__file__).resolve().parents[1]
STAMP = "2026-10-24T20:00:00Z"
NOW = "2026-10-24T21:00:00Z"


def digest(data: bytes) -> str:
    return sha256(data).hexdigest()


class EvidenceGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        registry = ResourceRegistry(ROOT)
        cls.policy_schema = registry.load_json("evidence_gate_schema")
        cls.evidence_schema = registry.load_json("external_evidence_envelope_schema")

    def fixture(self):
        sources = {
            "src/api/app.py": digest(b"def app(): pass\n"),
            "src/payment/pay.py": digest(b"def pay(): pass\n"),
        }
        semgrep_tool = {
            "name": "Semgrep", "version": "1.pin",
            "binary_sha256": "1" * 64, "adapter_version": "v0.1",
            "invocation_sha256": "2" * 64,
            "ruleset_sha256": "3" * 64,
            "exit_classifier": "semgrep-json-pinned",
        }
        pyright_tool = {
            **semgrep_tool, "name": "Pyright",
            "binary_sha256": "4" * 64,
            "exit_classifier": "pyright-json-pinned",
        }
        policy = {
            "schema_version": "0.1", "policy_id": "test.policy",
            "snapshot_id": "git:owner/repo@pinned",
            "source_files": [
                {"path": path, "sha256": source_sha}
                for path, source_sha in sources.items()
            ],
            "requirements": [
                {
                    "id": "api.security", "scope": "src/api/**",
                    "tool": semgrep_tool, "rule_ids": ["security.high"],
                    "predicate": "STATIC_NO_HIGH_FINDINGS", "exceptions": [],
                },
                {
                    "id": "api.types", "scope": "src/api/**",
                    "tool": pyright_tool, "rule_ids": ["reportTypeIssues"],
                    "predicate": "TYPE_NO_ERRORS", "exceptions": [],
                },
            ],
        }
        raw = b'{"results":[],"errors":[]}\n'
        def envelope(tool, rule):
            return {
                "schema_version": "0.1", "snapshot_id": policy["snapshot_id"],
                "tool": deepcopy(tool),
                "execution": {
                    "state": "COMPLETED", "exit_code": 0,
                    "exit_classification": "VALID_RESULT",
                    "started_at": STAMP, "finished_at": "2026-10-24T20:00:01Z",
                },
                "scope": {
                    "expected_files": [{"path": "src/api/app.py", "sha256": sources["src/api/app.py"]}],
                    "scanned_files": [{"path": "src/api/app.py", "sha256": sources["src/api/app.py"]}],
                    "skipped_files": [], "parser_errors": [],
                    "required_rules": [rule], "evaluated_rules": [rule],
                },
                "raw_artifact": {
                    "uri": "artifact://ci/raw.json",
                    "sha256": digest(raw), "media_type": "application/json",
                },
                "observations": [],
            }
        envelopes = {
            "api.security": envelope(semgrep_tool, "security.high"),
            "api.types": envelope(pyright_tool, "reportTypeIssues"),
        }
        return policy, sources, envelopes, raw

    def run_gate(self, policy, sources, envelopes, raw, **opts):
        typed_policy = parse_gate_policy(policy, self.policy_schema)
        runs = {
            key: EvidenceRun(
                parse_external_evidence(value, self.evidence_schema),
                raw if not isinstance(raw, dict) else raw.get(key),
            )
            for key, value in envelopes.items()
        }
        kwargs = {
            "expected_policy_sha256": typed_policy.fingerprint(),
            "expected_snapshot_id": policy["snapshot_id"],
            "expected_sources": sources,
            "evaluated_at": NOW,
        }
        kwargs.update(opts)
        return evaluate_gate(typed_policy, runs=runs, **kwargs)

    def test_admitted_exact_clean_scan_passes_only_scoped_requirements(self):
        p, files, envelopes, raw = self.fixture()
        result = self.run_gate(p, files, envelopes, raw)
        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.authorization, "ALLOW")
        self.assertEqual([r.id for r in result.requirements],
                         ["api.security", "api.types"])
        self.assertEqual(result.requirements[0].scope, ("src/api/app.py",))
        self.assertEqual(result.requirements[0].admission_status, "ADMISSIBLE")
        self.assertNotIn("P1", result.to_document())

    def test_high_security_finding_blocks_merge(self):
        p, files, envelopes, raw = self.fixture()
        envelopes["api.security"]["observations"].append({
            "kind": "STATIC_FINDING", "rule_id": "security.high",
            "severity": "HIGH", "path": "src/api/app.py", "line": 1,
            "message": "dangerous", "native_status": "finding",
        })
        result = self.run_gate(p, files, envelopes, raw)
        self.assertEqual(result.status, "FAIL")
        self.assertEqual(result.authorization, "BLOCK")
        self.assertEqual(result.requirements[0].observed_violations, 1)

    def test_low_severity_not_high_violation(self):
        p, files, envelopes, raw = self.fixture()
        envelopes["api.security"]["observations"].append({
            "kind": "STATIC_FINDING", "rule_id": "security.high",
            "severity": "LOW", "path": "src/api/app.py", "line": 1,
            "message": "low", "native_status": "finding",
        })
        self.assertEqual(self.run_gate(p, files, envelopes, raw).status, "PASS")

    def test_type_error_fail_and_nonzero_typechecker_exit_supported(self):
        p, files, envelopes, raw = self.fixture()
        envelopes["api.types"]["execution"]["exit_code"] = 1
        envelopes["api.types"]["observations"] = [{
            "kind": "TYPECHECK_DIAGNOSTIC", "rule_id": "reportTypeIssues",
            "severity": "ERROR", "path": "src/api/app.py", "line": 1,
            "message": "type mismatch", "native_status": "reportTypeIssues",
        }]
        result = self.run_gate(p, files, envelopes, raw)
        self.assertEqual(result.status, "FAIL")
        self.assertEqual(result.requirements[1].admission_status, "ADMISSIBLE")

    def test_missing_required_tool_is_unknown_and_blocked(self):
        p, files, envelopes, raw = self.fixture()
        del envelopes["api.types"]
        d = self.run_gate(p, files, envelopes, raw)
        self.assertEqual(d.status, "UNKNOWN")
        self.assertEqual(d.authorization, "BLOCK")
        self.assertIn("REQUIRED_EVIDENCE_MISSING", d.requirements[1].reasons)

    def test_semgrep_oom_with_empty_findings_never_passes(self):
        p, files, envelopes, raw = self.fixture()
        e = envelopes["api.security"]
        e["execution"].update(state="FAILED", exit_code=137,
                              exit_classification="EXECUTION_FAILURE")
        d = self.run_gate(p, files, envelopes, raw)
        self.assertEqual(d.status, "UNKNOWN")
        self.assertIn("EXECUTION_NOT_COMPLETED", d.requirements[0].reasons)

    def test_missing_raw_or_source_is_unknown_or_rejected(self):
        p, files, envelopes, raw = self.fixture()
        d = self.run_gate(p, files, envelopes, {"api.security": None, "api.types": raw})
        self.assertEqual(d.status, "UNKNOWN")
        self.assertIn("RAW_ARTIFACT_UNAVAILABLE", d.requirements[0].reasons)
        del envelopes["api.security"]["scope"]["scanned_files"][:]
        self.assertEqual(self.run_gate(p, files, envelopes, raw).status, "UNKNOWN")

    def test_unexpected_rule_version_and_source_drift_never_passes(self):
        p, files, envelopes, raw = self.fixture()
        envelopes["api.security"]["tool"]["ruleset_sha256"] = "f" * 64
        d = self.run_gate(p, files, envelopes, raw)
        self.assertEqual(d.status, "UNKNOWN")
        self.assertIn("TOOL_OR_CONFIG_IDENTITY_MISMATCH", d.requirements[0].reasons)

    def test_pinned_policy_sha_missing_and_source_identity_change(self):
        p, files, envelopes, raw = self.fixture()
        d = self.run_gate(p, files, envelopes, raw, expected_policy_sha256=None)
        self.assertEqual(d.status, "UNKNOWN")
        self.assertIn("TRUSTED_POLICY_FINGERPRINT_MISSING", d.reasons)
        d = self.run_gate(p, files, envelopes, raw,
                          expected_sources={**files, "src/payment/pay.py": "f" * 64})
        self.assertEqual(d.status, "UNKNOWN")
        self.assertIn("TRUSTED_SOURCE_SET_MISMATCH", d.reasons)

    def test_overlapping_scopes_conjunctive_and_known_violation_wins(self):
        p, files, envelopes, raw = self.fixture()
        p["requirements"][1]["scope"] = "src/api/app.py"
        envelopes["api.security"]["observations"] = [{
            "kind": "STATIC_FINDING", "rule_id": "security.high",
            "severity": "CRITICAL", "path": "src/api/app.py", "line": 1,
            "message": "break", "native_status": "finding",
        }]
        envelopes["api.types"]["execution"]["state"] = "TIMED_OUT"
        d = self.run_gate(p, files, envelopes, raw)
        self.assertEqual(d.status, "FAIL")
        self.assertEqual([x.status for x in d.requirements], ["FAIL", "UNKNOWN"])

    def test_approved_waiver_is_scoped_and_expires(self):
        p, files, envelopes, raw = self.fixture()
        p["requirements"][0]["exceptions"] = [{
            "path": "src/api/app.py", "rule_id": "security.high",
            "ticket": "RISK-123", "approved_by": "reviewer",
            "reason": "owner accepted a scoped exception",
            "expires_at": "2026-11-24T20:00:00Z",
        }]
        envelopes["api.security"]["observations"] = [{
            "kind": "STATIC_FINDING", "rule_id": "security.high",
            "severity": "HIGH", "path": "src/api/app.py", "line": 1,
            "message": "finding", "native_status": "finding",
        }]
        d = self.run_gate(p, files, envelopes, raw)
        self.assertEqual(d.status, "PASS")
        self.assertEqual(d.requirements[0].waived_violations, 1)
        expired = self.run_gate(
            p, files, envelopes, raw, evaluated_at="2026-12-01T00:00:00Z",
        )
        self.assertEqual(expired.status, "FAIL")
        self.assertIn("EXPIRED_EXCEPTION", expired.requirements[0].reasons)

    def test_untrusted_or_outside_scope_waiver_cannot_be_used(self):
        p, files, envelopes, raw = self.fixture()
        entry = {
            "path": "src/payment/pay.py", "rule_id": "security.high",
            "ticket": "X", "approved_by": "owner", "reason": "bad",
            "expires_at": NOW,
        }
        p["requirements"][0]["exceptions"] = [entry]
        with self.assertRaises(GateContractError):
            self.run_gate(p, files, envelopes, raw)

    def test_dafny_verified_spec_not_bound_to_implementation(self):
        p, files, envelopes, raw = self.fixture()
        dafny = {**p["requirements"][0]["tool"], "name": "Dafny",
                 "exit_classifier": "dafny-pinned"}
        p["requirements"] = [{
            "id": "payments.formal", "scope": "src/payment/**",
            "tool": dafny, "rule_ids": ["payment.invariant"],
            "predicate": "FORMAL_IMPLEMENTATION_VERIFIED", "exceptions": [],
        }]
        spec_sha = files["src/payment/pay.py"]
        envelopes = {"payments.formal": {
            **self.fixture()[2]["api.security"],
            "tool": dafny,
            "scope": {
                **envelopes["api.security"]["scope"],
                "expected_files": [{"path": "src/payment/pay.py", "sha256": spec_sha}],
                "scanned_files": [{"path": "src/payment/pay.py", "sha256": spec_sha}],
                "required_rules": ["payment.invariant"],
                "evaluated_rules": ["payment.invariant"],
            },
            "observations": [{
                "kind": "FORMAL_PROOF_RESULT", "obligation_id": "payment.invariant",
                "path": "src/payment/pay.py", "source_sha256": spec_sha,
                "native_status": "VERIFIED", "assumptions": ["spec_only"],
                "counterexample_sha256": None,
            }],
        }}
        d = self.run_gate(p, files, envelopes, raw)
        self.assertEqual(d.status, "UNKNOWN")
        self.assertEqual(d.authorization, "BLOCK")
        self.assertIn("FORMAL_IMPLEMENTATION_BINDING_NOT_VERIFIED",
                      d.requirements[0].reasons)

    def test_ambiguous_or_unsupported_scope_rejected(self):
        p, files, envelopes, raw = self.fixture()
        for bad in ("src/**/api.py", "../**", "src/api/*"):
            with self.subTest(bad=bad):
                test = deepcopy(p)
                test["requirements"][0]["scope"] = bad
                with self.assertRaises(GateContractError):
                    self.run_gate(test, files, envelopes, raw)
        p["requirements"][0]["id"] = p["requirements"][1]["id"]
        with self.assertRaises(GateContractError):
            self.run_gate(p, files, envelopes, raw)

    def test_schema_rejects_extra_scripting_logic(self):
        p, files, envelopes, raw = self.fixture()
        p["eval"] = "__import__('os').system('echo bad')"
        with self.assertRaises(GateContractError):
            self.run_gate(p, files, envelopes, raw)

    def test_same_semantics_deterministic_across_policy_input_order(self):
        p, files, envelopes, raw = self.fixture()
        first = self.run_gate(p, files, envelopes, raw)
        alt = deepcopy(p)
        alt["source_files"].reverse()
        alt["requirements"].reverse()
        second = self.run_gate(alt, files, envelopes, raw)
        self.assertEqual(first.canonical_json(), second.canonical_json())


if __name__ == "__main__":
    unittest.main()
