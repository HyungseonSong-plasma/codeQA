"""#92: source-vs-target repository identity controls for Samuel E2E."""
from dataclasses import asdict
from copy import deepcopy
import unittest

from codeqa.governance.samuel_target_preflight import evaluate_handoff, verify_origin_workflow, PreflightError


SRC = "HyungseonSong-plasma/chatgpt-operation"
DST = "HyungseonSong-plasma/codeQA"


def issue(repo, number):
    return {"number": number, "url": f"https://api.github.com/repos/{repo}/issues/{number}",
            "state": "open", "title": "controlled issue"}


class SamuelCrossRepositoryHandoffTests(unittest.TestCase):
    def setUp(self):
        self.params = dict(source_issue=issue(SRC, 220), target_issue=issue(DST, 92),
            source_repository=SRC, target_repository=DST,
            work_id="github:HyungseonSong-plasma/codeQA:issue:92",
            controller_sha="a" * 40, expected_target_sha="b" * 40,
            actual_target_sha="b" * 40, actor="HyungseonSong-plasma", github_run_id="123", source_run_id="100")

    def test_authorized_read_only_handoff(self):
        got = evaluate_handoff(**self.params)
        self.assertEqual(got.status, "READ_ONLY_PREFLIGHT_CONFIRMED")
        self.assertEqual(got.execution_mode, "READ_ONLY_NO_PR_NO_MERGE")
        self.assertEqual(got.allowed_mutations, ())
        self.assertEqual(len(got.evidence_sha256), 64)
        self.assertEqual(got.to_document(), asdict(got))

    def test_work_id_is_repository_scoped_even_for_same_issue_number(self):
        with self.assertRaisesRegex(PreflightError, "work ID"):
            evaluate_handoff(**{**self.params, "work_id": "issue:92"})

    def test_cross_repository_substitution_rejected(self):
        for field, value in (("target_repository", SRC), ("source_repository", DST)):
            with self.subTest(field=field):
                with self.assertRaises(PreflightError):
                    evaluate_handoff(**{**self.params, field: value})
        wrong = deepcopy(self.params["target_issue"])
        wrong["url"] = wrong["url"].replace("codeQA", "chatgpt-operation")
        with self.assertRaisesRegex(PreflightError, "repository identity"):
            evaluate_handoff(**{**self.params, "target_issue": wrong})

    def test_missing_closed_issue_and_pr_are_not_accepted(self):
        for field in ("source_issue", "target_issue"):
            data = deepcopy(self.params[field])
            data["state"] = "closed"
            with self.assertRaises(PreflightError):
                evaluate_handoff(**{**self.params, field: data})
            data["state"] = "open"
            data["pull_request"] = {"url": "example"}
            with self.assertRaises(PreflightError):
                evaluate_handoff(**{**self.params, field: data})

    def test_stale_or_unpinned_code_head_fails_closed(self):
        with self.assertRaisesRegex(PreflightError, "stale"):
            evaluate_handoff(**{**self.params, "actual_target_sha": "c" * 40})
        with self.assertRaisesRegex(PreflightError, "SHA"):
            evaluate_handoff(**{**self.params, "controller_sha": ""})

    def test_actor_and_run_identity_required(self):
        with self.assertRaisesRegex(PreflightError, "actor"):
            evaluate_handoff(**{**self.params, "actor": "unknown-bot[bot]"})
        with self.assertRaisesRegex(PreflightError, "run identity"):
            evaluate_handoff(**{**self.params, "github_run_id": "0"})

    def test_missing_source_run_provenance_rejected(self):
        with self.assertRaisesRegex(PreflightError, "source workflow run identity"):
            evaluate_handoff(**{**self.params, "source_run_id": "0"})

    def test_actual_samuel_origin_run_readback(self):
        original = {
            "id": 100, "event": "workflow_dispatch",
            "head_sha": "a" * 40,
            "path": ".github/workflows/samuel-codeqa-preflight.yml@refs/heads/main",
            "repository": {"full_name": SRC},
            "actor": {"login": "HyungseonSong-plasma"},
        }
        verify_origin_workflow(original, source_run_id="100", controller_sha="a" * 40)
        controls = [
            ("event", "push"), ("head_sha", "b" * 40),
            ("path", ".github/workflows/samuel-bootstrap.yml@refs/heads/main"),
            ("path", ".github/workflows/samuel-codeqa-preflight.yml@refs/tags/v1"),
            ("repository", {"full_name": DST}),
            ("actor", {"login": "unauthorized"}),
            ("id", 101),
        ]
        for name, substitute in controls:
            with self.subTest(name=name):
                wrong = deepcopy(original)
                wrong[name] = substitute
                with self.assertRaises(PreflightError):
                    verify_origin_workflow(wrong, source_run_id="100",
                                           controller_sha="a" * 40)

    def test_same_handoff_produces_deterministic_evidence(self):
        self.assertEqual(evaluate_handoff(**self.params), evaluate_handoff(**self.params))


if __name__ == "__main__":
    unittest.main()
