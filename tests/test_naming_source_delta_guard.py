"""#75 adversarial guard tests for the opt-in source-scoped comparator."""
from __future__ import annotations

from pathlib import Path
import unittest

from codeqa.adapters.python_snapshot import parse_python_snapshot
from codeqa.adapters.python_naming import extract_python_naming
from codeqa.core.naming import NamingProfile
from codeqa.evaluation.naming_source_delta import (
    NamingDeltaError, NamingDeltaManifest, compare_naming_snapshots,
)
from codeqa.infrastructure.resources import ResourceRegistry

ROOT = Path(__file__).resolve().parents[1]
FIRST = "git:owner/repo@" + "a" * 40
SECOND = "git:owner/repo@" + "b" * 40


class DeclaredRenameGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = NamingProfile.from_mapping(
            ResourceRegistry(ROOT).load_json("python_naming_safe_profile")
        )

    def compare(self, before, after, renames):
        manifest = NamingDeltaManifest.from_mapping({
            "schema_version": "0.1",
            "baseline_snapshot_id": FIRST,
            "candidate_snapshot_id": SECOND,
            "profile_fingerprint": self.profile.fingerprint(),
            "path_renames": [],
            "symbol_renames": renames,
        })
        base = extract_python_naming(
            parse_python_snapshot(before), before, snapshot_id=FIRST
        )
        candidate = extract_python_naming(
            parse_python_snapshot(after), after, snapshot_id=SECOND
        )
        return compare_naming_snapshots(
            base, candidate, before, after,
            profile=self.profile, manifest=manifest,
        )

    @staticmethod
    def rename(old, new):
        return {
            "before_path": "src/model.py", "before_owner": "",
            "before_name": old, "after_path": "src/model.py",
            "after_owner": "", "after_name": new, "kind": "function",
        }

    def test_coexisting_functions_unchanged_file_other_file_changed(self):
        before = {
            "src/model.py": "def BadName(): return 1\ndef good_name(): return 2\n",
            "src/other.py": "def helper(): return 1\n",
        }
        after = dict(before, **{"src/other.py": "def helper(): return 2\n"})
        with self.assertRaisesRegex(NamingDeltaError, "unverified or ambiguous"):
            self.compare(before, after, [self.rename("BadName", "good_name")])

    def test_old_identity_survives_new_symbol_added(self):
        before = {"src/model.py": "def BadName(): return 1\n"}
        after = {
            "src/model.py": "def BadName(): return 1\ndef good_name(): return 1\n"
        }
        with self.assertRaisesRegex(NamingDeltaError, "unverified or ambiguous"):
            self.compare(before, after, [self.rename("BadName", "good_name")])

    def test_target_identity_already_existed_in_baseline(self):
        before = {
            "src/model.py": "def BadName(): return 1\ndef good_name(): return 2\n"
        }
        after = {"src/model.py": "def good_name(): return 1\n"}
        with self.assertRaisesRegex(NamingDeltaError, "unverified or ambiguous"):
            self.compare(before, after, [self.rename("BadName", "good_name")])

    def test_true_changed_source_explicit_rename_is_still_supported(self):
        before = {"src/model.py": "def BadName(): return 1\n"}
        after = {"src/model.py": "def good_name(): return 1\n"}
        report = self.compare(before, after, [self.rename("BadName", "good_name")])
        self.assertEqual(report.status, "COMPARABLE_STATIC_DECLARATIONS")
        self.assertTrue(any(
            x.relationship == "RENAMED_DECLARED" for x in report.observations
        ))


if __name__ == "__main__":
    unittest.main()
