"""Check the tracked repository root against its registered JSON layout policy."""
from pathlib import Path
import unittest

from codeqa.evaluation.layout import evaluate_layout
from codeqa.infrastructure.git import GitReader
from codeqa.infrastructure.resources import ResourceRegistry


ROOT = Path(__file__).resolve().parents[1]


class RepositoryLayoutTests(unittest.TestCase):
    def test_registered_policy_matches_tracked_root(self) -> None:
        policy = ResourceRegistry(ROOT).load_json("repository_layout")
        result = evaluate_layout(GitReader(ROOT).tracked_paths(), policy)
        self.assertTrue(result.passed, result)


if __name__ == "__main__":
    unittest.main()
