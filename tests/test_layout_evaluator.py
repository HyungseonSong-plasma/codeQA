"""Pure, repository-neutral layout evaluator conformance tests."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from codeqa.evaluation.layout import evaluate_layout  # noqa: E402


class LayoutEvaluatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = {
            "root_directories": ["assets", "lib"],
            "root_files": ["LICENSE", "manifest.toml"],
        }
        self.paths = [
            "assets/sample.bin", "lib/core/module.py",
            "LICENSE", "manifest.toml",
        ]

    def test_matches_synthetic_repository(self) -> None:
        self.assertTrue(evaluate_layout(self.paths, self.policy).passed)

    def test_finds_missing_and_unexpected_entries_by_type(self) -> None:
        report = evaluate_layout(
            ["assets/x", "other/x", "LICENSE", "junk.cfg"], self.policy,
        )
        self.assertFalse(report.passed)
        self.assertEqual(report.missing_directories, ("lib",))
        self.assertEqual(report.unexpected_directories, ("other",))
        self.assertEqual(report.missing_files, ("manifest.toml",))
        self.assertEqual(report.unexpected_files, ("junk.cfg",))

    def test_directory_file_type_swaps_are_rejected(self) -> None:
        report = evaluate_layout(
            ["assets", "lib/module.py", "LICENSE/x", "manifest.toml"],
            self.policy,
        )
        self.assertFalse(report.passed)
        self.assertIn("assets", report.missing_directories)
        self.assertIn("assets", report.unexpected_files)
        self.assertIn("LICENSE", report.missing_files)
        self.assertIn("LICENSE", report.unexpected_directories)

    def test_empty_repository_does_not_pass(self) -> None:
        self.assertFalse(evaluate_layout([], self.policy).passed)

    def test_malformed_policies_fail_closed(self) -> None:
        malformed = [
            {"root_directories": [], "root_files": ["R"]},
            {"root_directories": ["x", "x"], "root_files": ["R"]},
            {"root_directories": ["x"], "root_files": ["x"]},
            {"root_directories": ["x/y"], "root_files": ["R"]},
            {"root_directories": ["x"], "root_files": "README"},
            {"root_directories": [".."], "root_files": ["R"]},
        ]
        for bad in malformed:
            with self.subTest(policy=bad), self.assertRaises(ValueError):
                evaluate_layout(self.paths, bad)

    def test_malformed_tracked_paths_fail_closed(self) -> None:
        for bad in ("", "../x", "/etc/x", "a//b", "a/./b", "a\\b"):
            with self.subTest(path=bad), self.assertRaises(ValueError):
                evaluate_layout([bad], self.policy)

    def test_policy_names_are_not_hard_coded_in_evaluator(self) -> None:
        different = {
            "root_directories": ["components"],
            "root_files": ["project.yml"],
        }
        self.assertTrue(
            evaluate_layout(["components/x.rs", "project.yml"], different).passed
        )


if __name__ == "__main__":
    unittest.main()
