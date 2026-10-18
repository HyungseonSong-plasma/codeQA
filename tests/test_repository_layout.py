"""Verify the versioned, frozen root layout using a logical policy ID.

Run: python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codeqa.resources import ResourceRegistry  # noqa: E402


# Independent baseline: changing the resource registry or policy JSON alone
# must not permit a change in the frozen top-level layout.
FROZEN_DIRECTORIES = frozenset({
    ".github", "contracts", "docs", "fixtures",
    "profiles", "skills", "src", "tests",
})
FROZEN_FILES = frozenset({".gitignore", "README.md", "pyproject.toml"})


def root_names(tracked_paths: list[str]) -> set[str]:
    """Extract root entries from tracked POSIX paths."""
    return {path.partition("/")[0] for path in tracked_paths if path}


def layout_errors(tracked_paths: list[str], allowed: set[str]) -> list[str]:
    """Report all unexpected and missing top-level entries."""
    actual = root_names(tracked_paths)
    return (
        [f"unexpected root entry: {entry}" for entry in sorted(actual - allowed)]
        + [f"missing root entry: {entry}" for entry in sorted(allowed - actual)]
    )


def tracked_files() -> list[str]:
    output = subprocess.run(
        ["git", "ls-files", "--cached", "-z"],
        check=True, capture_output=True, cwd=ROOT,
    ).stdout
    return [path.decode("utf-8", errors="surrogateescape") for path in output.split(b"\0") if path]


class RepositoryLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = ResourceRegistry(ROOT).load_json("repository_layout")

    def test_layout_policy_is_frozen(self) -> None:
        self.assertEqual(self.policy["policy_id"], "codeqa.repository.root-layout")
        self.assertEqual(self.policy["schema_version"], 1)
        self.assertEqual(self.policy["status"], "frozen")
        self.assertEqual(set(self.policy["root_directories"]), FROZEN_DIRECTORIES)
        self.assertEqual(set(self.policy["root_files"]), FROZEN_FILES)
        self.assertEqual(len(self.policy["root_directories"]), len(FROZEN_DIRECTORIES))
        self.assertEqual(len(self.policy["root_files"]), len(FROZEN_FILES))
        self.assertTrue(self.policy["change_control"]["issue_required"])
        self.assertTrue(self.policy["change_control"]["architecture_decision_record_required"])
        self.assertTrue(self.policy["change_control"]["reviewer_approval_required"])

    def test_tracked_root_contains_exactly_allowed_entries(self) -> None:
        expected = FROZEN_DIRECTORIES | FROZEN_FILES
        self.assertEqual(layout_errors(tracked_files(), expected), [])

    def test_expected_directory_and_file_types(self) -> None:
        for name in FROZEN_DIRECTORIES:
            with self.subTest(directory=name):
                self.assertTrue((ROOT / name).is_dir(), name)
        for name in FROZEN_FILES:
            with self.subTest(file=name):
                self.assertTrue((ROOT / name).is_file(), name)

    def test_rejects_unexpected_root_directory(self) -> None:
        paths = [f"{name}/.gitkeep" for name in FROZEN_DIRECTORIES]
        paths += list(FROZEN_FILES)
        paths.append("adapters/python/parser.py")
        self.assertIn(
            "unexpected root entry: adapters",
            layout_errors(paths, FROZEN_DIRECTORIES | FROZEN_FILES),
        )

    def test_rejects_missing_root_directory(self) -> None:
        paths = [f"{name}/.gitkeep" for name in FROZEN_DIRECTORIES - {"fixtures"}]
        paths += list(FROZEN_FILES)
        self.assertIn(
            "missing root entry: fixtures",
            layout_errors(paths, FROZEN_DIRECTORIES | FROZEN_FILES),
        )


if __name__ == "__main__":
    unittest.main()
