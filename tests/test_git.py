"""Conformance tests for local Git snapshot reader."""
from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from codeqa.infrastructure.git import GitReader, GitReadError


class GitReaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self._git("init", "-q")
        self._git("config", "user.name", "test")
        self._git("config", "user.email", "test@example.org")
        (self.root / "a.txt").write_text("original", encoding="utf-8")
        (self.root / "sub").mkdir()
        (self.root / "sub" / "b.py").write_text("pass", encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-qm", "initial")
        self.sha = self._git("rev-parse", "HEAD").strip()

    def _git(self, *args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=self.root, check=True, capture_output=True, text=True
        ).stdout

    def test_tracked_paths_exclude_untracked_files(self) -> None:
        (self.root / "untracked.txt").write_text("x", encoding="utf-8")
        self.assertEqual(GitReader(self.root).tracked_paths(), ["a.txt", "sub/b.py"])

    def test_reads_exact_committed_blob_not_uncommitted_file(self) -> None:
        (self.root / "a.txt").write_text("modified", encoding="utf-8")
        self.assertEqual(GitReader(self.root).read_file(self.sha, "a.txt"), b"original")

    def test_invalid_revision_and_paths_fail_closed(self) -> None:
        reader = GitReader(self.root)
        for rev, path in (
            ("HEAD", "a.txt"), (self.sha, "../a.txt"),
            (self.sha, "/tmp/a.txt"), (self.sha, "sub//b.py"),
            (self.sha, "missing.txt"),
        ):
            with self.subTest(revision=rev, path=path):
                with self.assertRaises(GitReadError):
                    reader.read_file(rev, path)

    def test_non_git_directory_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(GitReadError):
                GitReader(Path(directory)).tracked_paths()


if __name__ == "__main__":
    unittest.main()
