"""Regression tests for independent frozen-policy baseline comparison."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from codeqa.governance.frozen_policy import (
    FrozenPolicyError, baseline_policy, verify_frozen_policy,
    verify_policy_unchanged,
)


class FrozenPolicyGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        self._git("init", "-q")
        self._git("config", "user.name", "test")
        self._git("config", "user.email", "test@example.com")
        self._write_config("profiles/baseline.json")
        self._write_policy("profiles/baseline.json", {"root_directories": ["lib"], "root_files": ["README"]})
        (self.repo / "README").write_text("initial", encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-qm", "approved baseline")
        self.base = self._git("rev-parse", "HEAD").strip()

    def _git(self, *args: str) -> str:
        p = subprocess.run(["git", *args], cwd=self.repo, check=True, capture_output=True, text=True)
        return p.stdout

    def _write_config(self, rel: str) -> None:
        (self.repo / "pyproject.toml").write_text(
            "[tool.codeqa.resources]\nlayout = " + json.dumps(rel) + "\n",
            encoding="utf-8",
        )

    def _write_policy(self, rel: str, payload: object) -> None:
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_unchanged_policy_is_accepted(self) -> None:
        verify_frozen_policy(self.repo, self.base, "layout")

    def test_registry_relocation_without_content_change_is_accepted(self) -> None:
        target = self.repo / "policies/renamed.json"
        target.parent.mkdir(parents=True)
        (self.repo / "profiles/baseline.json").rename(target)
        self._write_config("policies/renamed.json")
        verify_frozen_policy(self.repo, self.base, "layout")
        self.assertEqual(baseline_policy(self.repo, self.base, "layout")["root_directories"], ["lib"])

    def test_policy_modification_fails(self) -> None:
        self._write_policy("profiles/baseline.json", {"root_directories": ["new"], "root_files": ["README"]})
        with self.assertRaises(FrozenPolicyError):
            verify_frozen_policy(self.repo, self.base, "layout")

    def test_coordinated_registry_and_policy_change_still_fails(self) -> None:
        self._write_policy("policies/new.json", {"root_directories": ["new"], "root_files": ["README"]})
        self._write_config("policies/new.json")
        with self.assertRaises(FrozenPolicyError):
            verify_frozen_policy(self.repo, self.base, "layout")

    def test_invalid_base_revision_fails_closed(self) -> None:
        with self.assertRaises(FrozenPolicyError):
            verify_frozen_policy(self.repo, "HEAD", "layout")

    def test_missing_current_policy_fails_closed(self) -> None:
        self._write_config("policies/missing.json")
        with self.assertRaises(FrozenPolicyError):
            verify_frozen_policy(self.repo, self.base, "layout")

    def test_pure_comparison_works_without_git(self) -> None:
        verify_policy_unchanged({"a": 1}, {"a": 1}, "layout")
        with self.assertRaises(FrozenPolicyError):
            verify_policy_unchanged({"a": 1}, {"a": 2}, "layout")

    def test_deleted_baseline_resource_fails_closed(self) -> None:
        self._git("rm", "profiles/baseline.json")
        self._git("commit", "-qm", "remove policy")
        updated = self._git("rev-parse", "HEAD").strip()
        with self.assertRaises(FrozenPolicyError):
            baseline_policy(self.repo, updated, "layout")


if __name__ == "__main__":
    unittest.main()
