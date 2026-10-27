"""Pure parser-side negatives for real external Pyright receipt provenance.

No upstream repository, SDK, wheel or webhook is executed by these tests.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".github/scripts"))
from public_python_sdk_benchmark import (validate_full_source_diagnostic,
                                         unprivileged_analyzer_env)
from public_api_benchmark import request_headers, _RejectRedirects


class FullSourcePyrightDiagnosticTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "checkout"
        self.root.mkdir()
        (self.root / "sample.py").write_text("x = 1\ny = x\n", encoding="utf-8")
        (Path(self.temp.name) / "outside.py").write_text("x = 1\n", encoding="utf-8")

    def witness(self, **changes: object) -> dict:
        value = {"severity": "error", "file": "sample.py",
                 "range": {"start": {"line": 1}}}
        value.update(changes)
        return value

    def test_in_tree_source_line_accepted_as_location_only(self) -> None:
        self.assertIsNone(validate_full_source_diagnostic(self.witness(), self.root))

    def test_missing_range_rejected(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "FULL_SOURCE_PYRIGHT_MALFORMED_RANGE"):
            validate_full_source_diagnostic(self.witness(range=None), self.root)

    def test_out_of_bounds_and_bool_lines_rejected(self) -> None:
        for bad in (2, -1, True, "1"):
            with self.subTest(line=bad):
                with self.assertRaisesRegex(RuntimeError, "FULL_SOURCE_PYRIGHT_RANGE_OUTSIDE_SOURCE"):
                    validate_full_source_diagnostic(
                        self.witness(range={"start": {"line": bad}}), self.root)

    def test_foreign_or_missing_source_rejected(self) -> None:
        for bad in ("../outside.py", "missing.py"):
            with self.subTest(path=bad):
                with self.assertRaisesRegex(RuntimeError, "FULL_SOURCE_PYRIGHT_FOREIGN_DIAGNOSTIC"):
                    validate_full_source_diagnostic(self.witness(file=bad), self.root)

    def test_malformed_diagnostic_rejected(self) -> None:
        for bad in (None, {}, self.witness(severity="pass"), self.witness(file="")):
            with self.subTest(value=bad):
                with self.assertRaisesRegex(RuntimeError, "FULL_SOURCE_PYRIGHT_MALFORMED_DIAGNOSTIC"):
                    validate_full_source_diagnostic(bad, self.root)


class ReadOnlyGitHubRESTCredentialBoundaryTests(unittest.TestCase):
    def test_builtin_token_only_goes_to_exact_github_rest_host(self) -> None:
        with patch.dict(os.environ, {"GITHUB_TOKEN": "unit-test-only",
                                     "GH_TOKEN": "unit-test-only-other"}):
            rest = request_headers("https://api.github.com/repos/fastapi/example/git/commits/abc")
            raw = request_headers("https://raw.githubusercontent.com/fastapi/example/abc/README.md")
            self.assertEqual(rest["Authorization"], "Bearer unit-test-only")
            self.assertNotIn("Authorization", raw)
            self.assertNotIn("GITHUB_TOKEN", unprivileged_analyzer_env())
            self.assertNotIn("GH_TOKEN", unprivileged_analyzer_env())

    def test_untrusted_api_hostname_userinfo_scheme_and_port_rejected(self) -> None:
        for url in ("http://api.github.com/repos/a/b",
                    "https://api.github.com.evil.example/repos/a/b",
                    "https://someone@api.github.com/repos/a/b",
                    "https://api.github.com:443/repos/a/b"):
            with self.subTest(url=url):
                with self.assertRaisesRegex(RuntimeError, "UNTRUSTED_UPSTREAM_URL"):
                    request_headers(url)

    def test_http_redirects_cannot_forward_rest_token(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "UPSTREAM_REDIRECT_REJECTED"):
            _RejectRedirects().redirect_request(
                None, None, 302, "redirect", {},
                "https://other.example/steal")


if __name__ == "__main__":
    unittest.main()
