"""Synthetic parser rejection controls; real installed-wheel Pyright runs in CI."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github/scripts/package_typecheck_smoke.py"
spec = importlib.util.spec_from_file_location("package_typecheck_smoke", SCRIPT)
assert spec is not None and spec.loader is not None
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class InstalledConsumerTypecheckRunnerTests(unittest.TestCase):
    @staticmethod
    def report(*rules: str, fatal: bool = False, wrong_file: bool = False) -> dict:
        return {
            "version": "1.1.414",
            "fatalErrorOccurred": fatal,
            "configParseErrorOccurred": False,
            "summary": {"errorCount": len(rules)},
            "generalDiagnostics": [
                {"severity": "error", "rule": rule,
                 "file": "outside.py" if wrong_file else "consumer.py",
                 "message": "synthetic parser control"}
                for rule in rules
            ],
        }

    def parse(self, document: dict, *, negative: bool = True,
              exit_code: int = 1) -> dict:
        fake = subprocess.CompletedProcess(
            args=["synthetic-only"], returncode=exit_code,
            stdout=json.dumps(document), stderr="",
        )
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(runner.subprocess, "run", return_value=fake):
                return runner.run_typecheck(
                    Path(sys.executable), root / "venv",
                    ROOT / "fixtures/installed-consumer" /
                    ("invalid.py" if negative else "valid.py"),
                    root / "project", negative=negative,
                )

    def test_missing_assignment_rule_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "NEGATIVE_CONTROLS_MISSING"):
            self.parse(self.report(*(["reportArgumentType"] * 4)))

    def test_too_few_argument_errors_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "NEGATIVE_CONTROLS_MISSING"):
            self.parse(self.report("reportArgumentType", "reportArgumentType",
                                   "reportAssignmentType"))

    def test_positive_with_native_error_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "POSITIVE_REJECTED"):
            self.parse(self.report("reportArgumentType"),
                       negative=False, exit_code=1)

    def test_incomplete_tool_rejected_even_with_expected_rules(self):
        with self.assertRaisesRegex(RuntimeError, "INCOMPLETE"):
            self.parse(self.report(*(["reportArgumentType"] * 3),
                                   "reportAssignmentType", fatal=True))

    def test_wrong_source_diagnostic_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "OUT_OF_SCOPE"):
            self.parse(self.report(*(["reportArgumentType"] * 3),
                                   "reportAssignmentType", wrong_file=True))

    def test_wrong_version_rejected(self):
        doc = self.report(*(["reportArgumentType"] * 3), "reportAssignmentType")
        doc["version"] = "1.1.1"
        with self.assertRaisesRegex(RuntimeError, "VERSION_DRIFT"):
            self.parse(doc)


if __name__ == "__main__":
    unittest.main()
