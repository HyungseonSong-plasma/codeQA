"""Offline consumer regression of pinned Samuel init + branch deletion route."""
from __future__ import annotations

import json
from pathlib import Path
import re
import runpy
import unittest


ROOT = Path(__file__).resolve().parents[1]
PIN = "059050330a549fce0b543687e2e9d4dca6c3f624"
MANIFEST = ROOT / "docs/operating_system/central_skills.json"
REQUEST = ROOT / ".github/requests/branch-delete-request.json"
WORKFLOW = ROOT / ".github/workflows/samuel-branch-delete.yml"
VALIDATOR = ROOT / ".github/scripts/validate_branch_delete_request.py"


class CodeQaInitCapabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.validate_request = staticmethod(runpy.run_path(str(VALIDATOR))["validate_request"])

    def test_exact_samuel_source_and_skill_binding(self) -> None:
        manifest = self.manifest
        self.assertEqual(manifest["schema_version"], 2)
        self.assertEqual(manifest["source_repository"], "HyungseonSong-plasma/chatgpt-operation")
        os = manifest["operating_system"]
        self.assertEqual(os["revision"], PIN)
        self.assertEqual(os["expected_version"], "Samuel")
        for record in [os["index"], os["essential_rules"],
                       manifest["skill_catalog"], manifest["capability_registry"]]:
            self.assertRegex(record["expected_blob_sha"], r"^[0-9a-f]{40}$")
        by_name = {entry["name"]: entry for entry in manifest["skills"]}
        self.assertEqual(set(by_name), {"session-bootstrap", "state-refresh", "repository-mutation", "pull-request-create"})
        self.assertEqual(by_name["session-bootstrap"]["load_on"], ["INIT"])
        self.assertEqual(by_name["state-refresh"]["load_on"], ["INIT", "SCHEDULED_CONTROLLER"])
        self.assertEqual(by_name["repository-mutation"]["load_on"], [
            "MUTATE", "GITHUB_BRANCH_DELETE", "GITHUB_MUTATION_CAPABILITY_VERDICT",
            "GITHUB_FILE_CREATE", "GITHUB_FILE_UPDATE", "GITHUB_BRANCH_CREATE"
        ])
        self.assertEqual(by_name["pull-request-create"]["load_on"], ["GITHUB_PR_CREATE"])
        for item in by_name.values():
            self.assertEqual(item["revision"], PIN)
            self.assertRegex(item["expected_blob_sha"], r"^[0-9a-f]{40}$")

    def test_init_always_warms_capability_without_mutating(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        docs = [ROOT / "docs/operating_system" / x
                for x in ("README.md", "BOOTSTRAP.md", "CENTRAL_SKILLS.md")]
        texts = [path.read_text(encoding="utf-8") for path in docs]
        self.assertIn("codeQA-init", readme)
        self.assertIn("BOOTSTRAP.md", readme)
        for term in ("skills/catalog.json", "skills/capability-registry.json",
                     "GITHUB_BRANCH_DELETE", "GITHUB_MUTATION_CAPABILITY_VERDICT",
                     "GITHUB_CAPABILITY_ROUTING=READY|BLOCKED",
                     "GITHUB_MUTATION_PREFLIGHT=TRIGGER_REQUIRED"):
            self.assertTrue(any(term in text for text in texts), term)
        bootstrap = texts[1]
        self.assertIn("Always", bootstrap)
        self.assertIn("repository-mutation", bootstrap)
        self.assertIn("read-only", bootstrap)
        self.assertIn("assert_capability_exhausted", bootstrap)
        self.assertIn("samuel-branch-delete.yml", bootstrap)

    def test_persistent_route_is_not_stale_one_shot(self) -> None:
        content = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", content)
        self.assertIn("branch-delete-request.json", content)
        self.assertIn("needs.prepare.outputs.has_targets == 'true'", content)
        self.assertIn("validate_branch_delete_request.py", content)
        self.assertIn("chatgpt-operation/.github/actions/branch-delete@" + PIN, content)
        self.assertIn("expected-sha: ${{ matrix.expected_sha }}", content)
        self.assertFalse((ROOT / ".github/workflows/codeqa-merged-branch-cleanup.yml").exists())
        self.assertEqual(self.validate_request(json.loads(REQUEST.read_text(encoding="utf-8"))), [])

    def test_valid_request_and_negative_cases(self) -> None:
        sha = "a" * 40
        safe = {"targets": [{"branch": "feat/some-work", "expected_sha": sha}]}
        self.assertEqual(self.validate_request(safe), safe["targets"])
        bad = [
            {}, {"targets": None}, {"targets": "bad"},
            {"targets": [dict(branch="main", expected_sha=sha)]},
            {"targets": [dict(branch="feat/../main", expected_sha=sha)]},
            {"targets": [dict(branch="feat/x", expected_sha=sha.upper())]},
            {"targets": [dict(branch="feat/x", expected_sha=sha[:-1])]},
            {"targets": [dict(branch="feat/x", expected_sha=sha)] * 2},
            {"targets": [dict(branch="feat/x", expected_sha=sha, force=True)]},
            {"targets": [dict(branch="feat/x", expected_sha=sha)] * 51},
        ]
        for case in bad:
            with self.subTest(case=str(case)[:80]):
                with self.assertRaises(ValueError):
                    self.validate_request(case)


if __name__ == "__main__":
    unittest.main()
