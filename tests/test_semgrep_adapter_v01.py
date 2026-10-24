"""#100: Semgrep JSON adapter and Gate conformance; no CLI needed for unit suite."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import unittest

from codeqa.adapters.semgrep_json import (SemgrepAdapterError, parse_semgrep_json, link_semgrep_ccg, validate_semgrep_sarif_parity)
from codeqa.core.external_evidence import ToolIdentity, assess_external_evidence
from codeqa.core.evidence import EvidenceIndex, EvidenceFact
from codeqa.evaluation.evidence_gate import (
    EvidenceRun, evaluate_gate, parse_gate_policy,
)
from codeqa.infrastructure.resources import ResourceRegistry

ROOT = Path(__file__).resolve().parents[1]
START = "2026-10-24T20:00:00Z"
END = "2026-10-24T20:00:01Z"
SOURCE = b"x = 1\n"
DIGEST = sha256(SOURCE).hexdigest()


class SemgrepAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        registry = ResourceRegistry(ROOT)
        cls.evidence_schema = registry.load_json("external_evidence_envelope_schema")
        cls.gate_schema = registry.load_json("evidence_gate_schema")

    def tool(self):
        return ToolIdentity(
            name="Semgrep", version="1.182.1", binary_sha256="a" * 64,
            adapter_version="semgrep-json-v0.1",
            invocation_sha256="b" * 64, ruleset_sha256="c" * 64,
            exit_classifier="semgrep-1.182.1-json-scan-v1",
        )

    def native(self, *, issue=False):
        document = {
            "results": [], "errors": [],
            "paths": {"scanned": ["src/test.py"], "skipped": []},
        }
        if issue:
            document["results"] = [self.finding()]
        return document

    def finding(self, **overrides):
        return {
            "check_id": "security.high", "path": "src/test.py",
            "start": {"line": 1, "col": 1},
            "extra": {"severity": "ERROR", "message": "dangerous"},
            **overrides,
        }

    def adapted(self, native=None, **options):
        raw = json.dumps(self.native() if native is None else native,
                         sort_keys=True).encode()
        kwargs = {
            "schema": self.evidence_schema,
            "snapshot_id": "git:repo@pinned",
            "expected_sources": {"src/test.py": DIGEST},
            "tool": self.tool(),
            "attested_rules": ("security.high",),
            "started_at": START, "finished_at": END,
            "exit_code": 0, "interrupted": False,
            "local_ruleset_verified": True,
            "artifact_uri": "artifact://semgrep/native.json",
        }
        kwargs.update(options)
        envelope = parse_semgrep_json(raw, **kwargs)
        return envelope, raw

    def gate(self, envelope, raw):
        policy = {
            "schema_version": "0.1", "policy_id": "test",
            "snapshot_id": "git:repo@pinned",
            "source_files": [{"path": "src/test.py", "sha256": DIGEST}],
            "requirements": [{
                "id": "security", "scope": "src/test.py",
                "tool": self.tool().__dict__ if hasattr(self.tool(), "__dict__") else {
                    "name": "Semgrep", "version": "1.182.1",
                    "binary_sha256": "a" * 64, "adapter_version": "semgrep-json-v0.1",
                    "invocation_sha256": "b" * 64, "ruleset_sha256": "c" * 64,
                    "exit_classifier": "semgrep-1.182.1-json-scan-v1",
                },
                "rule_ids": ["security.high"], "predicate": "STATIC_NO_HIGH_FINDINGS",
                "exceptions": [],
            }],
        }
        parsed = parse_gate_policy(policy, self.gate_schema)
        return evaluate_gate(
            parsed, runs={"security": EvidenceRun(envelope, raw)},
            expected_policy_sha256=parsed.fingerprint(),
            expected_snapshot_id="git:repo@pinned",
            expected_sources={"src/test.py": DIGEST},
            evaluated_at=END,
        )

    def test_clean_attested_native_scan_yields_admissible_gate_pass(self):
        envelope, raw = self.adapted()
        self.assertEqual(len(envelope.observations), 0)
        self.assertEqual(self.gate(envelope, raw).status, "PASS")

    def test_native_error_severity_maps_high_and_blocks(self):
        envelope, raw = self.adapted(self.native(issue=True))
        self.assertEqual(envelope.observations[0].severity, "HIGH")
        self.assertEqual(envelope.observations[0].native_status, "ERROR")
        self.assertEqual(self.gate(envelope, raw).status, "FAIL")

    def test_multiple_findings_remain_unmerged(self):
        native = self.native(issue=True)
        native["results"].append(self.finding(start={"line": 2, "col": 1}))
        env, raw = self.adapted(native)
        self.assertEqual(len(env.observations), 2)
        self.assertEqual(self.gate(env, raw).requirements[0].observed_violations, 2)

    def test_nonzero_unsupported_exit_never_clean(self):
        env, raw = self.adapted(exit_code=1)
        self.assertEqual(env.execution.state, "FAILED")
        self.assertEqual(self.gate(env, raw).status, "UNKNOWN")

    def test_interruption_or_missing_ruleset_attestation_never_clean(self):
        for options in ({"interrupted": True}, {"local_ruleset_verified": False},
                        {"exit_code": 137}):
            with self.subTest(options=options):
                env, raw = self.adapted(**options)
                self.assertEqual(self.gate(env, raw).authorization, "BLOCK")

    def test_scanner_reported_error_even_with_zero_findings_blocks(self):
        native = self.native()
        native["errors"] = [{"type": "Syntax error", "path": "src/test.py"}]
        env, raw = self.adapted(native)
        self.assertEqual(env.execution.state, "FAILED")
        self.assertEqual(self.gate(env, raw).status, "UNKNOWN")

    def test_partial_scanned_list_prevents_fake_zero_findings_pass(self):
        native = self.native()
        native["paths"]["scanned"] = []
        env, raw = self.adapted(native)
        self.assertEqual(self.gate(env, raw).status, "UNKNOWN")

    def test_changed_source_digest_rejected_by_gate(self):
        env, raw = self.adapted()
        env = parse_semgrep_json(
            raw, schema=self.evidence_schema, snapshot_id="git:repo@pinned",
            expected_sources={"src/test.py": "f" * 64}, tool=self.tool(),
            attested_rules=("security.high",), started_at=START,
            finished_at=END, exit_code=0, local_ruleset_verified=True,
            artifact_uri="artifact://semgrep/native.json",
        )
        self.assertEqual(self.gate(env, raw).status, "UNKNOWN")

    def test_changed_tool_config_or_binary_identity_rejected_by_gate(self):
        modified = ToolIdentity(
            **{name: getattr(self.tool(), name) if name != "ruleset_sha256" else "e" * 64
               for name in self.tool().__dataclass_fields__}
        )
        env, raw = self.adapted(tool=modified)
        self.assertEqual(self.gate(env, raw).status, "UNKNOWN")

    def test_malformed_or_absent_report_never_becomes_empty_clean(self):
        raw_examples = (b"", b"{}", b"{bad", b"[]",
                        b'{"results":[],"errors":[]}',
                        b'{"results":null,"errors":[],"paths":{"scanned":[]}}')
        for raw in raw_examples:
            with self.subTest(raw=raw):
                with self.assertRaises(SemgrepAdapterError):
                    parse_semgrep_json(
                        raw, schema=self.evidence_schema,
                        snapshot_id="s", expected_sources={"src/test.py": DIGEST},
                        tool=self.tool(), attested_rules=("security.high",),
                        started_at=START, finished_at=END, exit_code=0,
                        artifact_uri="artifact://semgrep/output",
                    )

    def test_wrong_file_same_count_or_unsafe_path_does_not_pass(self):
        for path in ("src/other.py", "../escape.py", "/etc/passwd"):
            with self.subTest(path=path):
                n = self.native()
                n["paths"]["scanned"] = [path]
                with self.assertRaises(SemgrepAdapterError):
                    self.adapted(n)

    def test_observed_finding_remains_when_scan_interrupted(self):
        env, raw = self.adapted(self.native(issue=True), interrupted=True)
        self.assertEqual(len(env.observations), 1)
        self.assertEqual(self.gate(env, raw).status, "UNKNOWN")

    def test_untrusted_rule_id_cannot_be_silent_pass(self):
        native = self.native(issue=True)
        native["results"][0]["check_id"] = "other.rule"
        with self.assertRaises(SemgrepAdapterError):
            self.adapted(native)


    def test_semgrep_json_sarif_parity_clean_and_single_finding(self):
        clean, _ = self.adapted()
        clean_sarif = json.dumps({
            "version": "2.1.0", "runs": [{"results": []}]
        }).encode()
        self.assertEqual(validate_semgrep_sarif_parity(clean, clean_sarif), 0)

        finding, _ = self.adapted(self.native(issue=True))
        result = {
            "ruleId": "security.high", "level": "error",
            "locations": [{
                "physicalLocation": {
                    "artifactLocation": {"uri": "src/test.py"},
                    "region": {"startLine": 1},
                },
            }],
        }
        document = {"version": "2.1.0", "runs": [{"results": [result]}]}
        self.assertEqual(
            validate_semgrep_sarif_parity(
                finding, json.dumps(document).encode()
            ), 1,
        )
        document["runs"][0]["results"][0]["ruleId"] = "unexpected"
        with self.assertRaises(SemgrepAdapterError):
            validate_semgrep_sarif_parity(finding, json.dumps(document).encode())

    def test_semgrep_ccg_source_link_is_opt_in_exact_and_not_runtime(self):
        envelope, _ = self.adapted(self.native(issue=True))
        evidence = EvidenceIndex(
            snapshot_id="git:repo@pinned",
            facts=(EvidenceFact("syntax-witness", "src/test.py", 1, 0,
                                "call", "eval"),),
            relations=(),
        )
        links = link_semgrep_ccg(envelope, evidence)
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].evidence_id, "syntax-witness")
        self.assertEqual(links[0].resolution, "EXACT_SOURCE_LINE")
        missing = link_semgrep_ccg(envelope, EvidenceIndex(
            snapshot_id="git:repo@pinned", facts=(), relations=(),
        ))
        self.assertEqual(missing[0].resolution, "NO_SOURCE_FACT")
        ambiguous = link_semgrep_ccg(envelope, EvidenceIndex(
            snapshot_id="git:repo@pinned",
            facts=(*evidence.facts, EvidenceFact("other", "src/test.py", 1, 8,
                                                "call", "second")),
            relations=(),
        ))
        self.assertIsNone(ambiguous[0].evidence_id)
        self.assertEqual(ambiguous[0].resolution, "AMBIGUOUS_LINE")
        with self.assertRaises(SemgrepAdapterError):
            link_semgrep_ccg(envelope, EvidenceIndex(
                snapshot_id="different", facts=evidence.facts, relations=(),
            ))


if __name__ == "__main__":
    unittest.main()
