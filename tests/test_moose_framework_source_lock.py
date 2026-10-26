"""Source-identity and adversarial MOOSE lock checks; no ABI claims."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from codeqa.adapters.moose_framework_source import (
    APPLICATION_REPO, FRAMEWORK_REPO, REQUIRED_FILES,
    MooseFrameworkSourceError, git_blob_sha, verify_framework_source_lock,
)


ROOT = Path(__file__).resolve().parents[1]
APP_SHA = "b" * 40
FRAMEWORK_SHA = "a" * 40


class MooseFrameworkSourceLockTests(unittest.TestCase):
    def setUp(self):
        self.files = {path: ("// pinned " + path + "\n").encode() for path in REQUIRED_FILES}
        self.lock = {
            "schema_version": "0.1",
            "framework_repository": FRAMEWORK_REPO,
            "framework_revision": FRAMEWORK_SHA,
            "application_repository": APPLICATION_REPO,
            "application_revision": APP_SHA,
            "authority": "PINNED_SOURCE_IDENTITY_ONLY",
            "files": {p: git_blob_sha(raw) for p, raw in self.files.items()},
        }
        self.deps = "CRANE=other\nMOOSE=" + FRAMEWORK_SHA + "\n"

    def check(self, *, lock=None, files=None, deps=None, app=APP_SHA):
        return verify_framework_source_lock(
            self.lock if lock is None else lock,
            self.deps if deps is None else deps,
            self.files if files is None else files,
            application_revision=app,
        )

    def test_source_identity_positive_is_not_abi_or_dsl_proof(self):
        receipt = self.check()
        self.assertEqual(receipt["authority"], "PINNED_SOURCE_IDENTITY_ONLY")
        for field in ("framework_release", "input_dsl_grammar",
                      "reserved_vs_customizable_names", "build_abi_and_runtime"):
            self.assertEqual(receipt[field], "NOT_EVALUATED")
        self.assertEqual(set(receipt["files"]), REQUIRED_FILES)

    def test_official_pinned_source_contract_has_three_exact_files(self):
        lock = json.loads((ROOT / "fixtures/moose-framework/source-lock-v0.1.json").read_text())
        self.assertEqual(lock["framework_revision"], "9f388366ccf38b9c34542ec5561198249fde0ac9")
        self.assertEqual(lock["application_revision"], "1977ad5559e5aa7a1c8d04c83735c15e007130d5")
        self.assertEqual(set(lock["files"]), REQUIRED_FILES)

    def test_modified_upstream_header_rejected(self):
        altered = dict(self.files)
        key = sorted(REQUIRED_FILES)[0]
        altered[key] += b"// unreviewed edit\n"
        with self.assertRaisesRegex(MooseFrameworkSourceError, "stale or altered"):
            self.check(files=altered)

    def test_missing_or_extra_source_rejected(self):
        for bad in ({}, {**self.files, "framework/unknown.h": b""}):
            with self.subTest(paths=list(bad)):
                with self.assertRaises(MooseFrameworkSourceError):
                    self.check(files=bad)

    def test_stale_or_duplicate_dependency_pin_rejected(self):
        for bad in ("MOOSE=" + "c" * 40, self.deps + "MOOSE=" + FRAMEWORK_SHA + "\n",
                    self.deps + "MOOSE=main\n", self.deps + "MOOSE=" + "c" * 40 + "\n",
                    "MOOSE=main\n", ""):
            with self.subTest(deps=bad):
                with self.assertRaises(MooseFrameworkSourceError):
                    self.check(deps=bad)

    def test_different_application_revision_rejected(self):
        with self.assertRaises(MooseFrameworkSourceError):
            self.check(app="c" * 40)

    def test_forged_framework_repository_or_authority_rejected(self):
        for key, value in (("framework_repository", "untrusted/moose"),
                           ("application_repository", "untrusted/app"),
                           ("authority", "PRODUCTION_ABI_VERIFIED")):
            bad = deepcopy(self.lock)
            bad[key] = value
            with self.subTest(key=key):
                with self.assertRaises(MooseFrameworkSourceError):
                    self.check(lock=bad)

    def test_unpinned_or_forged_blob_rejected(self):
        bad = deepcopy(self.lock)
        bad["files"][sorted(REQUIRED_FILES)[0]] = "0" * 40
        with self.assertRaises(MooseFrameworkSourceError):
            self.check(lock=bad)

    def test_non_byte_source_rejected(self):
        bad = dict(self.files)
        bad[sorted(REQUIRED_FILES)[0]] = "not bytes"
        with self.assertRaises(MooseFrameworkSourceError):
            self.check(files=bad)


if __name__ == "__main__":
    unittest.main()
