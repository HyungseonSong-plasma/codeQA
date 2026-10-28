"""#187: immutable Git tree access is infrastructure-owned, not pipeline subprocess."""
from __future__ import annotations

import ast
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from codeqa.infrastructure.git import GitReadError, GitReader
from codeqa.pipeline.naming_scope_discovery_v04 import _tree_manifest
from codeqa.pipeline.naming_snapshot_coverage_v03 import scan_pinned_git


ROOT = Path(__file__).resolve().parents[1]
PIN = "667a5f17f9890c5588d4f1c8ae079aba241501f3"
TREE = "e9a78ccc3a5ccf75f6ee4818289549f39f526d2d"
MANIFEST = ROOT / "fixtures/naming-governance/codeqa-source-scope-manifest-v04.json"


class PinnedGitTreeReaderTests(unittest.TestCase):
    def test_historical_tree_and_complete_blob_denominator(self):
        reader = GitReader(ROOT)
        self.assertEqual(reader.tree_sha(PIN), TREE)
        entries = reader.tree_entries(PIN, "src/codeqa")
        selected = {e.path: e.object_sha for e in entries if e.path.endswith(".py")}
        fixture = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(selected, {
            row["path"]: row["git_blob_sha"] for row in fixture["files"]
        })
        self.assertEqual(len(selected), 95)
        self.assertEqual(_tree_manifest(ROOT, PIN), (TREE, selected))
        census = scan_pinned_git(ROOT, revision=PIN)
        self.assertEqual(census.examined_files, len(selected))
        self.assertEqual(census.revision, PIN)
        self.assertEqual(census.status, "NOT_EVALUATED")

    def test_invalid_revision_prefix_and_unavailable_commit_fail_closed(self):
        reader = GitReader(ROOT)
        for bad in ("main", "", "0" * 39, "x" * 40):
            with self.subTest(bad=bad), self.assertRaises(GitReadError):
                reader.tree_sha(bad)
            with self.subTest(bad=bad), self.assertRaises(GitReadError):
                reader.tree_entries(bad, "src/codeqa")
        for prefix in ("", "/src/codeqa", "src/../codeqa", "src\\codeqa"):
            with self.subTest(prefix=prefix), self.assertRaises(GitReadError):
                reader.tree_entries(PIN, prefix)
        with self.assertRaises(GitReadError):
            reader.tree_sha("0" * 40)

    def test_malformed_duplicate_escaped_and_non_utf8_tree_entries_fail(self):
        reader = GitReader(ROOT)
        good = b"100644 blob " + b"a" * 40 + b"\tsrc/codeqa/a.py\0"
        for raw in (
            b"malformed\0",
            good + good,
            b"100644 blob " + b"a" * 40 + b"\tsrc/codeqa/../escape.py\0",
            b"100644 blob " + b"a" * 40 + b"\tsrc/codeqa/\xff.py\0",
            b"100644 blob " + b"z" * 40 + b"\tsrc/codeqa/a.py\0",
            b"100644 blob " + b"a" * 40 + b"\ttests/outside.py\0",
        ):
            with self.subTest(raw=raw), patch.object(reader, "_run", return_value=raw):
                with self.assertRaises(GitReadError):
                    reader.tree_entries(PIN, "src/codeqa")
        with patch.object(reader, "_run", return_value=good):
            self.assertEqual(reader.tree_entries(PIN, "src/codeqa")[0].path,
                             "src/codeqa/a.py")

    def test_same_pipeline_selection_has_no_direct_subprocess_imports(self):
        reader = GitReader(ROOT)
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
        paths = sorted(path for path in reader.tracked_paths()
                       if path.startswith("src/codeqa/pipeline/")
                       and path.endswith(".py"))
        self.assertEqual(len(paths), 12)
        offenders = []
        for path in paths:
            module = ast.parse(reader.read_file(head, path), filename=path)
            for node in ast.walk(module):
                if isinstance(node, ast.Import) and any(
                    alias.name == "subprocess" for alias in node.names
                ):
                    offenders.append((path, node.lineno))
                if isinstance(node, ast.ImportFrom) and node.module == "subprocess":
                    offenders.append((path, node.lineno))
        self.assertEqual(offenders, [], "pipeline Git subprocess must be infrastructure-owned")


if __name__ == "__main__":
    unittest.main()
