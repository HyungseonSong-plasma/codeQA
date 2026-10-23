"""Offline consumer regression of pinned Samuel init + branch deletion route."""
from __future__ import annotations

import json
from pathlib import Path
import re
import runpy
import unittest


ROOT = Path(__file__).resolve().parents[1]
PIN = "9b335e3fbb9c5e8e323e382daeec56fa25336822"
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
        self.assertEqual(set(by_name), {"session-bootstrap", "state-refresh", "repository-mutation"})
        self.assertEqual(by_name["session-bootstrap"]["load_on"], ["INIT"])
        self.assertEqual(by_name["state-refresh"]["load_on"], ["INIT", "SCHEDULED_CONTROLLER"])
        self.assertEqual(by_name["repository-mutation"]["load_on"], [
            "MUTATE", "GITHUB_BRANCH_DELETE", "GITHUB_MUTATION_CAPABILITY_VERDICT"
        ])
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
        # Temporary 2026-10-23 exact-SHA cleanup exception.
        # The manifest AND this whitelist must be restored to empty after the run.
        current = self.validate_request(json.loads(REQUEST.read_text(encoding="utf-8")))
        approved_once = [
                  {
                            "branch": "chore/archive-codeqa-experiments-20261023",
                            "expected_sha": "b8bb223770fca4254a54e537bbd5244f23a69f9a"
                  },
                  {
                            "branch": "docs/issue-27-canonical-architecture-principles-adrs",
                            "expected_sha": "e0b84e97d1bf18ba48f115026217c8bf1fadfbb4"
                  },
                  {
                            "branch": "experiment/codeqa-self-refactor-coderabbit-evaluation",
                            "expected_sha": "2177742fd7246dc3d00a73e3ff25e1c106000486"
                  },
                  {
                            "branch": "experiment/moose-production-field-20261023",
                            "expected_sha": "d754e50eda5048f7a90d0a8ee66be7216181359f"
                  },
                  {
                            "branch": "experiment/moose-refactor-comparison-20261023",
                            "expected_sha": "b294cb50bf23a57a5d73ae67cb95c6dfd1e61bad"
                  },
                  {
                            "branch": "feat/codeqa-init-samuel-delete-routing",
                            "expected_sha": "a6ef42cea0641682e70f5e4c1908e75244cf2d25"
                  },
                  {
                            "branch": "feat/issue-24-pinned-samuel-conformance",
                            "expected_sha": "abf7d6b0c2da2ef2bded6ed76b19709432bb91cd"
                  },
                  {
                            "branch": "feat/issue-28-qa-result-delta-v01",
                            "expected_sha": "e08d2adea33811c707e91b8183d6934a2c3fd642"
                  },
                  {
                            "branch": "feat/issue-29-language-adapter-contract-v01",
                            "expected_sha": "44ecd11a443ae47b9cbecbf5d7f391f55a65fe70"
                  },
                  {
                            "branch": "feat/issue-36-static-dependency-metrics",
                            "expected_sha": "019a433613b431abee77ddca9f3eeb2fd15a4d49"
                  },
                  {
                            "branch": "feat/issue-37-python-complexity-v01",
                            "expected_sha": "d54083788077a7c222ba7077d979e892121ff187"
                  },
                  {
                            "branch": "feat/issue-38-source-grounded-duplication",
                            "expected_sha": "9613560951166f32363ee083c815540059c843cf"
                  },
                  {
                            "branch": "feat/issue-39-declared-architecture-rules",
                            "expected_sha": "f3f3bfb522851397ad102c87e8a960259fdc9ac6"
                  },
                  {
                            "branch": "feat/issue-40-evidence-delta-v02",
                            "expected_sha": "d60f041f3b769dc0b1b6a63616ff24cc73ce7704"
                  },
                  {
                            "branch": "feat/issue-41-mixed-language-coverage",
                            "expected_sha": "47e1d1bd60be2bb08cbb328f305c00d2af22a24e"
                  },
                  {
                            "branch": "feat/issue-48-p3-extraction-aware-metrics",
                            "expected_sha": "519afba3aa916c30041b431f5420e7624a1be111"
                  },
                  {
                            "branch": "feat/issue-49-body-only-p6",
                            "expected_sha": "e35b60721ab52ff4c39b52d121b5c18c8621c661"
                  },
                  {
                            "branch": "feat/issue-53-local-statement-similarity",
                            "expected_sha": "956c920368411a67bca02eafd9ff5a25a9cff75f"
                  },
                  {
                            "branch": "feat/issue-54-structural-p3-delta",
                            "expected_sha": "6f18bdb33fa813eb67e5c648eef80eda2df8b570"
                  },
                  {
                            "branch": "test/issue-30-pinned-rust-ccg-v01",
                            "expected_sha": "c52a023676625b3b3a8243ca09e339b339fbba89"
                  }
        ]
        self.assertIn(current, ([], approved_once))

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
