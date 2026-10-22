"""Ground-truth contracts and current source for semantic directory roles."""
from __future__ import annotations

from pathlib import Path
import unittest
import subprocess

from codeqa.adapters.python_snapshot import parse_python_snapshot
from codeqa.adapters.python_dependencies import extract_parsed_dependencies
from codeqa.evaluation.semantic_layout import evaluate_semantic_layout
from codeqa.infrastructure.git import GitReader
from codeqa.infrastructure.resources import ResourceRegistry


ROOT = Path(__file__).resolve().parents[1]


class SemanticRoleTests(unittest.TestCase):
    def setUp(self):
        self.policy = {
            "scope": "src/qa",
            "policy_id": "fixture",
            "roles": {
                "core": {"responsibility": "fact models", "forbidden_imports": ["api"]},
                "api": {"responsibility": "presentation", "forbidden_imports": []},
            },
            "exceptions": [{"source": "src/qa/core/legacy.py",
                            "target": "src/qa/api/entry.py",
                            "status": "TRANSITIONAL_REVIEW",
                            "rationale": "pre-existing migration"}],
        }
        self.paths = ["src/qa/core/base.py", "src/qa/core/legacy.py",
                      "src/qa/api/entry.py"]

    def test_known_transitional_edge_is_review_not_pass(self):
        report = evaluate_semantic_layout(
            self.paths, [("src/qa/core/legacy.py", "src/qa/api/entry.py")],
            self.policy,
        )
        self.assertEqual(report.status, "REVIEW_REQUIRED")
        self.assertEqual([f.code for f in report.findings], ["DECLARED_TRANSITIONAL_EDGE"])

    def test_new_edge_is_a_violation(self):
        result = evaluate_semantic_layout(self.paths, [
            ("src/qa/core/base.py", "src/qa/api/entry.py"),
            ("src/qa/core/legacy.py", "src/qa/api/entry.py"),
        ], self.policy)
        self.assertEqual(result.status, "VIOLATION")
        self.assertIn("FORBIDDEN_ROLE_DEPENDENCY", [f.code for f in result.findings])

    def test_missing_unclassified_and_dead_exception_are_visible(self):
        result = evaluate_semantic_layout(
            ["src/qa/core/base.py", "src/qa/unknown/f.py"], [], self.policy,
        )
        codes = {f.code for f in result.findings}
        self.assertEqual(codes, {"MISSING_DECLARED_ROLE", "UNCLASSIFIED_ROLE",
                                 "EXCEPTION_NOT_OBSERVED"})

    def test_policy_cannot_approve_unrelated_or_duplicate_exception(self):
        import copy
        for change in ("no-reason", "unrelated", "duplicate"):
            policy = copy.deepcopy(self.policy)
            if change == "no-reason":
                policy["exceptions"][0]["rationale"] = ""
            if change == "unrelated":
                policy["exceptions"][0]["source"] = "src/qa/api/a.py"
            if change == "duplicate":
                policy["exceptions"].append(policy["exceptions"][0])
            with self.subTest(change=change), self.assertRaises(ValueError):
                evaluate_semantic_layout(self.paths, [], policy)

    def test_invalid_paths_and_unknown_targets_fail_closed(self):
        for path in ("../src/a.py", "/etc/passwd", "a//b.py", "a\\b.py"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                evaluate_semantic_layout([path], [], self.policy)
        bad = dict(self.policy)
        bad["roles"] = {"core": {"responsibility": "x", "forbidden_imports": ["missing"]}}
        with self.assertRaises(ValueError):
            evaluate_semantic_layout([], [], bad)

    def test_repository_exact_preexisting_exception_is_reviewed(self):
        """Freeze only current observed exceptions, not the whole layout."""
        import json
        policy = json.loads(
            (ROOT / "profiles/semantic-directory-roles-v0.1.json").read_text()
        )
        reader = GitReader(ROOT)
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        all_paths = reader.tracked_paths()
        sources = {
            p: reader.read_file(head, p).decode("utf-8")
            for p in all_paths if p.startswith("src/codeqa/") and p.endswith(".py")
        }
        parsed = parse_python_snapshot(sources)
        deps = extract_parsed_dependencies(parsed, snapshot_id="HEAD")
        pairs = [(e.source_path, e.target_path) for e in deps.edges]
        result = evaluate_semantic_layout(all_paths, pairs, policy)
        unexpected = [f for f in result.findings
                      if f.code != "DECLARED_TRANSITIONAL_EDGE"]
        self.assertEqual(unexpected, [], unexpected)
        self.assertEqual(
            [(f.source, f.target) for f in result.findings],
            [("src/codeqa/evaluation/contextual.py",
              "src/codeqa/adapters/python_context.py")],
        )
        self.assertEqual(result.status, "REVIEW_REQUIRED")


if __name__ == "__main__":
    unittest.main()
