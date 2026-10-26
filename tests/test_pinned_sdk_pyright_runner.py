"""Parser-side fail-closed controls; real Pyright is exercised separately in CI.

Synthetic JSON here is only for testing rejection logic, never external evidence.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github/scripts/pinned_python_sdk_conformance.py"
spec = importlib.util.spec_from_file_location("pinned_sdk_script", SCRIPT)
assert spec is not None and spec.loader is not None
sdk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sdk)


class PyrightRunnerFailClosedTests(unittest.TestCase):
    def run_parser(self, document: dict, *, exit_code: int, negative: bool = True,
                   extra_source: Path | None = None) -> None:
        fake = subprocess.CompletedProcess(
            args=["synthetic-unit-test-only"], returncode=exit_code,
            stdout=json.dumps(document), stderr="",
        )
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(sdk.subprocess, "run", return_value=fake):
                sdk.pyright_scan(
                    Path(sys.executable), Path(tmp) / "scan",
                    sdk.FIXTURE / ("invalid_advanced_contract.py" if negative
                                   else "valid_advanced_contract.py"),
                    expect_errors=negative,
                    required_rules=("reportIncompatibleMethodOverride",
                                    "reportAssignmentType", "reportCallIssue"),
                    extra_source=extra_source,
                )

    @staticmethod
    def report(*rules: str, fatal: bool = False, config_error: bool = False) -> dict:
        return {
            "version": sdk.PIN["pyright"],
            "generalDiagnostics": [
                {"severity": "error", "rule": rule, "file": "contract.py",
                 "message": "synthetic parser-control diagnostic",
                 "range": {"start": {"line": index}}}
                for index, rule in enumerate(rules)
            ],
            "summary": {"errorCount": len(rules), "filesAnalyzed": 1},
            "fatalErrorOccurred": fatal,
            "configParseErrorOccurred": config_error,
        }

    def test_missing_one_required_rule_rejected(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "NEGATIVE_REQUIRED_TYPE_DIAGNOSTICS_MISSING"):
            self.run_parser(self.report("reportIncompatibleMethodOverride",
                                        "reportAssignmentType"), exit_code=1)

    def test_incomplete_tool_run_rejected_despite_diagnostics(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "PYRIGHT_INCOMPLETE_OR_CONFIG_ERROR"):
            self.run_parser(self.report("reportIncompatibleMethodOverride",
                                        "reportAssignmentType", "reportCallIssue",
                                        fatal=True), exit_code=1)

    def test_clean_exit_with_error_diagnostics_rejected(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "NEGATIVE_SDK_SIGNATURE_NOT_REJECTED"):
            self.run_parser(self.report("reportIncompatibleMethodOverride",
                                        "reportAssignmentType", "reportCallIssue"),
                            exit_code=0)

    def test_positive_with_any_error_rejected(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "VALID_SDK_TYPES_REJECTED"):
            self.run_parser(self.report("reportAssignmentType"), exit_code=1,
                            negative=False)

    def test_unattested_same_basename_outside_project_rejected(self) -> None:
        report = self.report("reportIncompatibleMethodOverride",
                             "reportAssignmentType", "reportCallIssue")
        report["generalDiagnostics"][0]["file"] = "/tmp/other/contract.py"
        with self.assertRaisesRegex(RuntimeError, "PYRIGHT_DIAGNOSTIC_OUTSIDE_ATTESTED_SOURCE"):
            self.run_parser(report, exit_code=1)

    def test_path_traversal_with_matching_basename_rejected(self) -> None:
        report = self.report("reportIncompatibleMethodOverride",
                             "reportAssignmentType", "reportCallIssue")
        report["generalDiagnostics"][0]["file"] = "../contract.py"
        with self.assertRaisesRegex(RuntimeError, "PYRIGHT_DIAGNOSTIC_OUTSIDE_ATTESTED_SOURCE"):
            self.run_parser(report, exit_code=1)

    def test_unselected_warning_source_rejected_before_gate(self) -> None:
        report = self.report("reportIncompatibleMethodOverride",
                             "reportAssignmentType", "reportCallIssue")
        report["generalDiagnostics"].append({
            "severity": "warning", "rule": "reportUnknownMemberType",
            "file": "/tmp/foreign.py", "range": {"start": {"line": 0}},
        })
        with self.assertRaisesRegex(RuntimeError, "PYRIGHT_DIAGNOSTIC_OUTSIDE_ATTESTED_SOURCE"):
            self.run_parser(report, exit_code=1)

    def test_forged_summary_count_rejected(self) -> None:
        report = self.report("reportIncompatibleMethodOverride",
                             "reportAssignmentType", "reportCallIssue")
        report["summary"]["errorCount"] = 1
        with self.assertRaisesRegex(RuntimeError, "PYRIGHT_ERROR_COUNT_MISMATCH"):
            self.run_parser(report, exit_code=1)

    def test_missing_scan_count_rejected(self) -> None:
        report = self.report("reportIncompatibleMethodOverride",
                             "reportAssignmentType", "reportCallIssue")
        del report["summary"]["filesAnalyzed"]
        with self.assertRaisesRegex(RuntimeError, "PYRIGHT_INCOMPLETE_SCAN_COUNT"):
            self.run_parser(report, exit_code=1)

    def test_unknown_diagnostic_severity_rejected(self) -> None:
        report = self.report("reportIncompatibleMethodOverride",
                             "reportAssignmentType", "reportCallIssue")
        report["generalDiagnostics"][0]["severity"] = "pass"
        with self.assertRaisesRegex(RuntimeError, "PYRIGHT_UNKNOWN_DIAGNOSTIC_SEVERITY"):
            self.run_parser(report, exit_code=1)

    def test_missing_diagnostic_range_rejected(self) -> None:
        report = self.report("reportIncompatibleMethodOverride",
                             "reportAssignmentType", "reportCallIssue")
        del report["generalDiagnostics"][0]["range"]
        with self.assertRaisesRegex(RuntimeError, "PYRIGHT_MALFORMED_DIAGNOSTIC_RANGE"):
            self.run_parser(report, exit_code=1)

    def test_out_of_bounds_diagnostic_line_rejected(self) -> None:
        report = self.report("reportIncompatibleMethodOverride",
                             "reportAssignmentType", "reportCallIssue")
        report["generalDiagnostics"][0]["range"]["start"]["line"] = 100000
        with self.assertRaisesRegex(RuntimeError, "PYRIGHT_DIAGNOSTIC_LINE_OUTSIDE_SOURCE"):
            self.run_parser(report, exit_code=1)

    def test_scanned_source_mutation_during_tool_run_rejected(self) -> None:
        report = self.report("reportIncompatibleMethodOverride",
                             "reportAssignmentType", "reportCallIssue")
        fake = subprocess.CompletedProcess(
            args=["synthetic-unit-test-only"], returncode=1,
            stdout=json.dumps(report), stderr="",
        )
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "scan"
            def tamper(*_args, **_kwargs):
                (project / "contract.py").write_text("def changed(): pass\n")
                return fake
            with patch.object(sdk.subprocess, "run", side_effect=tamper):
                with self.assertRaisesRegex(RuntimeError, "PYRIGHT_SCANNED_SOURCE_BYTES_DRIFT"):
                    sdk.pyright_scan(
                        Path(sys.executable), project,
                        sdk.FIXTURE / "invalid_advanced_contract.py",
                        expect_errors=True,
                        required_rules=("reportIncompatibleMethodOverride",
                                        "reportAssignmentType", "reportCallIssue"),
                    )

    def test_extra_source_outside_pinned_fixture_rejected(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "UNTRUSTED_EXTRA_SDK_SOURCE"):
            self.run_parser(self.report(), exit_code=0, negative=False,
                            extra_source=Path("/tmp/public_sdk.py"))


if __name__ == "__main__":
    unittest.main()
