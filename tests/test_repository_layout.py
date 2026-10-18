"""Self-audit the checked-out repository against its registered JSON policy."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codeqa.evaluation.layout import evaluate_layout  # noqa: E402
from codeqa.resources import ResourceRegistry  # noqa: E402


def tracked_files(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "-z"],
        check=True, capture_output=True, cwd=root,
    ).stdout
    return [
        p.decode("utf-8", errors="surrogateescape")
        for p in result.split(b"\0") if p
    ]


class RepositoryLayoutTests(unittest.TestCase):
    def test_registered_policy_matches_tracked_root(self) -> None:
        policy = ResourceRegistry(ROOT).load_json("repository_layout")
        result = evaluate_layout(tracked_files(ROOT), policy)
        self.assertTrue(result.passed, result)


if __name__ == "__main__":
    unittest.main()
