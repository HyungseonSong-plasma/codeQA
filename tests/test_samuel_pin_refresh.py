"""Consumer-local Samuel immutable-pin migration invariants (Phase A).

No GitHub calls, no real mutation, and no automatic document-QA adoption.
Cross-repository SHA/blob provenance must be checked by the PR operator.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
PIN = ROOT / "docs/operating_system/central_skills.json"
NEW_REVISION = "28abfb4d640e433818f3a9f75312721f9f195a52"
OLD_REVISION = "c803cd6b77c6d112df33d8679bac32f993a658b0"
SHA = re.compile(r"^[0-9a-f]{40}$")
CHANGED_BLOBS = {
    "skills/repository-mutation/README.md":
        "a015776c54d6dc6f507c8da0ca09a36554f6a9de",
    "skills/pull-request-create/README.md":
        "38b53644b2c9a846cab9387afb7c8c7fcdb8c7a4",
    "skills/catalog.json":
        "d1abedc2800b2acb1bfe08182995b51d7dea1770",
}
DOC_PATHS = (
    "docs/operating_system/README.md",
    "docs/operating_system/BOOTSTRAP.md",
    "docs/operating_system/CENTRAL_SKILLS.md",
)


class SamuelPinRefreshTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pin = json.loads(PIN.read_text(encoding="utf-8"))

    def test_pinned_revision_is_single_immutable_merged_commit(self):
        pin = self.pin
        self.assertEqual(pin["schema_version"], 2)
        self.assertEqual(pin["source_repository"],
                         "HyungseonSong-plasma/chatgpt-operation")
        os = pin["operating_system"]
        self.assertEqual(os["expected_version"], "Samuel")
        self.assertEqual(os["revision"], NEW_REVISION)
        self.assertRegex(os["revision"], SHA)
        self.assertEqual({skill["revision"] for skill in pin["skills"]},
                         {NEW_REVISION})
        self.assertNotEqual(os["revision"], OLD_REVISION)

    def test_all_pinned_sources_have_valid_sha_and_unique_paths(self):
        pin = self.pin
        os = pin["operating_system"]
        resources = [os["index"], os["essential_rules"],
                     pin["skill_catalog"], pin["capability_registry"]]
        resources += [
            item for skill in pin["skills"]
            for item in ([skill] + ([skill["contract"]]
                                    if "contract" in skill else []))
        ]
        paths = [entry["path"] for entry in resources]
        self.assertEqual(len(resources), 14)
        self.assertEqual(len(paths), len(set(paths)))
        for item in resources:
            with self.subTest(path=item["path"]):
                self.assertRegex(item["expected_blob_sha"], SHA)
                self.assertNotIn("..", Path(item["path"]).parts)
                self.assertFalse(item["path"].startswith("/"))
        recorded = {item["path"]: item["expected_blob_sha"]
                    for item in resources}
        for path, sha in CHANGED_BLOBS.items():
            self.assertEqual(recorded[path], sha)

    def test_bootstrap_and_operator_docs_use_same_revision(self):
        for path in DOC_PATHS:
            with self.subTest(path=path):
                doc = (ROOT / path).read_text(encoding="utf-8")
                self.assertIn(NEW_REVISION, doc)
                self.assertNotIn(OLD_REVISION, doc)

    def test_branch_delete_action_is_pinned_to_same_revision(self):
        path = ".github/workflows/samuel-branch-delete.yml"
        workflow = (ROOT / path).read_text(encoding="utf-8")
        action_ref = ("HyungseonSong-plasma/chatgpt-operation/"
                      ".github/actions/branch-delete@" + NEW_REVISION)
        self.assertIn(action_ref, workflow)
        self.assertNotIn(OLD_REVISION, workflow)
        self.assertIn("expected-sha:", workflow)
        self.assertIn("branch:", workflow)
        self.assertIn("github-token:", workflow)
        request = json.loads((
            ROOT / ".github/requests/branch-delete-request.json"
        ).read_text(encoding="utf-8"))
        # Reviewed short-lived nonempty batches are also valid.
        # This read-only test does not execute or authorize deletion.
        import runpy
        validate = runpy.run_path(str(
            ROOT / ".github/scripts/validate_branch_delete_request.py"
        ))["validate_request"]
        validated = validate(request)
        self.assertLessEqual(len(validated), 50)

    def test_samuel_init_contract_is_retained(self):
        pin = self.pin
        skills = {item["name"]: item for item in pin["skills"]}
        self.assertEqual(
            {name for name, item in skills.items()
             if "INIT" in item["load_on"]},
            {"session-bootstrap", "state-refresh", "problem-oriented-response"},
        )
        contract = skills["problem-oriented-response"]["contract"]
        self.assertEqual(contract["expected_contract_id"],
                         "samuel.problem-first-response.v1")
        self.assertEqual(contract["expected_mode"], "problem_first")
        self.assertEqual(contract["expected_detail_policy"], "on_request")
        self.assertIs(contract["human_review_requires_question"], True)
        self.assertIn("GITHUB_BRANCH_DELETE",
                      skills["repository-mutation"]["load_on"])

    def test_generic_cross_repo_native_mutation_is_not_asserted_ready(self):
        central = (ROOT / "docs/operating_system/CENTRAL_SKILLS.md").read_text(
            encoding="utf-8")
        intro = (ROOT / "docs/operating_system/README.md").read_text(
            encoding="utf-8")
        for marker in (
            "TARGET_POLICY_NOT_ESTABLISHED",
            "REPOSITORY_MUTATION",
            "Issue #264",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, central)
        self.assertIn("TARGET_POLICY_NOT_ESTABLISHED", intro)
        self.assertIn("unsupported for cross-repository", intro)
        self.assertIn("Gate 2", intro)
        # This separately governed target-owned executor must remain disabled
        # and cannot stand in for the Samuel generic native execution route.
        local = json.loads((
            ROOT / "profiles/samuel-issue92-target-executor-v1.json"
        ).read_text(encoding="utf-8"))
        self.assertIs(local["enabled"], False)
        self.assertEqual(local["repository"], "HyungseonSong-plasma/codeQA")

    def test_phase_b_documentation_activation_is_trigger_only(self):
        entries = {skill["name"]: skill for skill in self.pin["skills"]}
        self.assertIn("document-consistency", entries)
        qa = entries["document-consistency"]
        self.assertEqual(qa["load_on"], ["DOCUMENTATION_CONSISTENCY_QA"])
        self.assertEqual(qa["revision"], NEW_REVISION)
        self.assertEqual(qa["expected_blob_sha"],
                         "1a63010c3cb8ef43e4a7abd8b2d093f8c26a6d90")
        self.assertEqual(qa["contract"], {
            "path": "skills/document-consistency/contract-v0.1.json",
            "expected_blob_sha": "753ab44591160c9c68643b62ba03b4a1e8dc2e05",
            "expected_contract_id": "samuel.documentation-consistency.v0.1",
            "expected_execution_mode": "READ_ONLY",
            "expected_trigger": "DOCUMENTATION_CONSISTENCY_QA",
        })
        self.assertEqual(
            {name for name, skill in entries.items()
             if "INIT" in skill["load_on"]},
            {"session-bootstrap", "state-refresh", "problem-oriented-response"},
        )


if __name__ == "__main__":
    unittest.main()
