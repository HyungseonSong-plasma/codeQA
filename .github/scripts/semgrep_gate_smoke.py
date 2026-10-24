#!/usr/bin/env python3
"""Pinned Semgrep 1.182.1 external-process smoke: real clean/finding Gate.

Runs only self-generated local synthetic fixtures in a temporary directory.
Semgrep is installed only in a disposable GitHub Actions environment and
never runs codeQA's target projects or fetches cloud configurations.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from codeqa.adapters.semgrep_json import parse_semgrep_json
from codeqa.core.external_evidence import ToolIdentity
from codeqa.evaluation.evidence_gate import (
    EvidenceRun, evaluate_gate, parse_gate_policy,
)
from codeqa.infrastructure.resources import ResourceRegistry


ROOT = Path(__file__).resolve().parents[2]
VERSION = "1.182.1"
RULE_ID = "security.eval"
RULE = b"""rules:
  - id: security.eval
    message: "Do not call eval"
    severity: ERROR
    languages: [python]
    pattern: eval(...)
"""


def checksum(blob: bytes) -> str:
    return sha256(blob).hexdigest()


def instant() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run_one(
    executable: str, *, case_name: str, source: bytes,
    expected_verdict: str,
    evidence_schema: dict, gate_schema: dict,
) -> None:
    with tempfile.TemporaryDirectory(prefix="codeqa-semgrep-") as temp:
        directory = Path(temp)
        (directory / "src").mkdir()
        (directory / "rules").mkdir()
        (directory / "src" / "sample.py").write_bytes(source)
        (directory / "rules" / "scan.yml").write_bytes(RULE)
        args = [
            executable, "scan", "--json",
            "--config=rules/scan.yml",
            "--metrics=off", "--disable-version-check",
            "--no-git-ignore", "--no-rewrite-rule-ids",
            "src/sample.py",
        ]
        env = {
            "PATH": os.environ["PATH"],
            "HOME": str(directory),
            "LANG": "C.UTF-8",
            "SEMGREP_SEND_METRICS": "off",
            "SEMGREP_ENABLE_VERSION_CHECK": "0",
            "DO_NOT_TRACK": "1",
        }
        start = instant()
        result = subprocess.run(
            args, cwd=directory, env=env, capture_output=True,
            timeout=90, check=False,
        )
        end = instant()
        if result.returncode != 0:
            raise AssertionError(
                f"pinned semgrep {case_name} process failed "
                f"exit={result.returncode} stderr={result.stderr.decode(errors='replace')[-2500:]}"
            )
        # Source bytes, local config, CLI and invocation are attested by this
        # controlled harness. The adapter never interprets empty JSON alone.
        if (directory / "src" / "sample.py").read_bytes() != source:
            raise AssertionError("source changed during scan")
        snapshot = f"fixture:sha256:{checksum(source)}"
        command_identity = [
            "semgrep", VERSION, "scan", "--json", "--no-rewrite-rule-ids",
            "--no-git-ignore", "--metrics=off", "--disable-version-check",
            RULE_ID, checksum(RULE), "src/sample.py", checksum(source),
        ]
        identity = ToolIdentity(
            name="Semgrep", version=VERSION,
            binary_sha256=checksum(Path(executable).read_bytes()),
            adapter_version="semgrep-json-v0.1",
            invocation_sha256=checksum(
                json.dumps(command_identity, separators=(",", ":")).encode()
            ),
            ruleset_sha256=checksum((directory / "rules" / "scan.yml").read_bytes()),
            exit_classifier="semgrep-1.182.1-json-scan-v1",
        )
        expected = {"src/sample.py": checksum(source)}
        envelope = parse_semgrep_json(
            result.stdout,
            schema=evidence_schema,
            snapshot_id=snapshot,
            expected_sources=expected,
            tool=identity,
            attested_rules=(RULE_ID,),
            started_at=start,
            finished_at=end,
            exit_code=result.returncode,
            local_ruleset_verified=True,
            artifact_uri=f"artifact://{case_name}/semgrep.json",
        )
        policy_doc = {
            "schema_version": "0.1",
            "policy_id": "codeqa.semgrep.integration.fixture",
            "snapshot_id": snapshot,
            "source_files": [
                {"path": "src/sample.py", "sha256": checksum(source)}
            ],
            "requirements": [{
                "id": "security", "scope": "src/sample.py",
                "tool": asdict(identity), "rule_ids": [RULE_ID],
                "predicate": "STATIC_NO_HIGH_FINDINGS", "exceptions": [],
            }],
        }
        policy = parse_gate_policy(policy_doc, gate_schema)
        decision = evaluate_gate(
            policy,
            runs={"security": EvidenceRun(envelope, result.stdout)},
            expected_policy_sha256=policy.fingerprint(),
            expected_snapshot_id=snapshot, expected_sources=expected,
            evaluated_at=end,
        )
        if decision.status != expected_verdict:
            raise AssertionError(
                f"unexpected Semgrep Gate decision: {decision.canonical_json()} "
                f"stderr={result.stderr.decode(errors='replace')[-2500:]}"
            )
        if decision.requirements[0].admission_status != "ADMISSIBLE":
            raise AssertionError("real Semgrep native output was not admissible")
        if expected_verdict == "FAIL" and not envelope.observations:
            raise AssertionError("real Semgrep did not report any issue")

        # These precise E2E counterexamples MUST be blocked despite the
        # genuine baseline result and matching source/ruleset artifact.
        untrusted = evaluate_gate(
            policy,
            runs={"security": EvidenceRun(envelope, None)},
            expected_policy_sha256=policy.fingerprint(),
            expected_snapshot_id=snapshot, expected_sources=expected,
            evaluated_at=end,
        )
        if untrusted.authorization != "BLOCK" or untrusted.status != "UNKNOWN":
            raise AssertionError("missing Semgrep raw artifact falsely cleared")
        print(
            f"SEMGREP_GATE=PASS case={case_name} expected={expected_verdict} "
            f"findings={len(envelope.observations)} "
            f"scanned={len(envelope.scope.scanned_files)} "
            f"rules={list(envelope.scope.evaluated_rules)} "
            f"artifact_sha256={checksum(result.stdout)}"
        )


def main() -> None:
    binary = shutil.which("semgrep")
    if not binary:
        raise RuntimeError("pinned Semgrep is not installed")
    probe = subprocess.run(
        [binary, "--version"], capture_output=True, text=True,
        timeout=15, check=True,
    )
    if probe.stdout.strip() != VERSION:
        raise AssertionError(
            f"wrong semgrep version: {probe.stdout!r}; expected {VERSION}"
        )
    reg = ResourceRegistry(ROOT)
    evidence_schema = reg.load_json("external_evidence_envelope_schema")
    gate_schema = reg.load_json("evidence_gate_schema")
    run_one(
        binary, case_name="clean", source=b"result = 1\n",
        expected_verdict="PASS",
        evidence_schema=evidence_schema, gate_schema=gate_schema,
    )
    run_one(
        binary, case_name="unsafe-eval",
        source=b"result = eval('1')\n",
        expected_verdict="FAIL",
        evidence_schema=evidence_schema, gate_schema=gate_schema,
    )
    print(f"PINNED_SEMGREP_E2E=PASS version={VERSION} cases=2")


if __name__ == "__main__":
    main()
