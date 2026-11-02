"""#166/#184: matched-source re-audit of the independently justified #187 cleanup.

This is a *narrow* subprocess-ownership metric, not a B7 structural KEEP or
external API/semantic-ownership certification. Both snapshots are read from Git
and the identical 12-file pipeline selection is checked before comparison.
"""
from __future__ import annotations

import ast
from hashlib import sha1, sha256
import json
from pathlib import Path
import re
import subprocess
import unittest

from codeqa.infrastructure.git import GitReader


ROOT = Path(__file__).resolve().parents[1]
BEFORE = "fb54b6c92363476b07a726008fbe8c1ab35f1a6a"
PIPELINE_PREFIX = "src/codeqa/pipeline/"
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SUBPROCESS_CALLS = frozenset({"run", "Popen", "call", "check_call", "check_output"})
BEFORE_BLOBS = {
    "src/codeqa/pipeline/naming_scope_discovery_v04.py":
        "45cd68ce8ffd2fbb4005827f5932c70818fcaf6b",
    "src/codeqa/pipeline/naming_snapshot_coverage_v03.py":
        "d73d9c8637d30ab667dac79046156044309463f3",
}


def _scan_subprocess(source: bytes, path: str) -> dict[str, object]:
    """Count only AST-direct subprocess calls; dynamic dispatch stays unknown.

    An observed literal 'git' argv is a narrower claim than arbitrary
    subprocess invocation. Aliases imported directly from subprocess count.
    """
    tree = ast.parse(source, filename=path)
    module_aliases: set[str] = set()
    function_aliases: set[str] = set()
    import_lines: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "subprocess":
                    module_aliases.add(alias.asname or alias.name)
                    import_lines.append(node.lineno)
        elif isinstance(node, ast.ImportFrom) and node.module == "subprocess":
            import_lines.append(node.lineno)
            function_aliases.update(
                alias.asname or alias.name for alias in node.names
                if alias.name in SUBPROCESS_CALLS
            )

    git_calls: list[int] = []
    unclassified_direct_calls: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        callee = node.func
        is_direct = (
            isinstance(callee, ast.Attribute)
            and isinstance(callee.value, ast.Name)
            and callee.value.id in module_aliases
            and callee.attr in SUBPROCESS_CALLS
        ) or (isinstance(callee, ast.Name) and callee.id in function_aliases)
        if not is_direct:
            continue
        argv = node.args[0] if node.args else None
        is_literal_git = (
            isinstance(argv, (ast.List, ast.Tuple))
            and bool(argv.elts)
            and isinstance(argv.elts[0], ast.Constant)
            and argv.elts[0].value == "git"
        )
        (git_calls if is_literal_git else unclassified_direct_calls).append(node.lineno)
    return {
        "path": path,
        "source_sha256": sha256(source).hexdigest(),
        "subprocess_import_lines": sorted(import_lines),
        "direct_literal_git_call_lines": sorted(git_calls),
        "other_direct_subprocess_call_lines": sorted(unclassified_direct_calls),
    }


def _pinned_pipeline_sources(reader: GitReader, revision: str) -> dict[str, bytes]:
    if not SHA40.fullmatch(revision):
        raise ValueError("an immutable 40-character revision is required")
    entries = reader.tree_entries(revision, "src/codeqa/pipeline")
    sources: dict[str, bytes] = {}
    for entry in entries:
        path = entry.path
        if not path.endswith(".py"):
            continue
        if (not path.startswith(PIPELINE_PREFIX)
                or entry.object_type != "blob"
                or entry.mode not in ("100644", "100755")
                or path in sources):
            raise ValueError("unsafe or duplicate pipeline source")
        raw = reader.read_file(revision, path)
        actual_blob = sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        if actual_blob != entry.object_sha:
            raise ValueError("Git tree/blob identity mismatch")
        sources[path] = raw
    if not sources:
        raise ValueError("empty pipeline source selection")
    return sources


class MatchedScopeGitOwnershipReauditTests(unittest.TestCase):
    def test_historical_ownership_cleanup_same_12_paths(self):
        reader = GitReader(ROOT)
        after = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
        ).strip()
        self.assertRegex(after, SHA40)
        before_sources = _pinned_pipeline_sources(reader, BEFORE)
        after_sources = _pinned_pipeline_sources(reader, after)
        self.assertEqual(set(before_sources), set(after_sources))
        self.assertEqual(len(before_sources), 12)
        for path, expected_blob in BEFORE_BLOBS.items():
            raw = before_sources[path]
            self.assertEqual(
                sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest(),
                expected_blob,
            )

        before_rows = [_scan_subprocess(raw, path)
                       for path, raw in sorted(before_sources.items())]
        after_rows = [_scan_subprocess(raw, path)
                      for path, raw in sorted(after_sources.items())]
        before_sites = [(row["path"], line)
                        for row in before_rows
                        for line in row["direct_literal_git_call_lines"]]
        after_sites = [(row["path"], line)
                       for row in after_rows
                       for line in row["direct_literal_git_call_lines"]]
        self.assertEqual(before_sites, [
            ("src/codeqa/pipeline/naming_scope_discovery_v04.py", 37),
            ("src/codeqa/pipeline/naming_snapshot_coverage_v03.py", 28),
        ])
        self.assertEqual(after_sites, [])
        self.assertEqual(sum(len(r["subprocess_import_lines"]) for r in before_rows), 2)
        self.assertEqual(sum(len(r["subprocess_import_lines"]) for r in after_rows), 0)
        self.assertEqual(sum(len(r["other_direct_subprocess_call_lines"])
                             for r in after_rows), 0)

        # Removal alone is insufficient: the two pipeline entrypoints must
        # still delegate pinned tree enumeration to the infrastructure reader.
        for path in BEFORE_BLOBS:
            tree = ast.parse(after_sources[path], filename=path)
            self.assertTrue(any(
                isinstance(n, ast.ImportFrom)
                and n.module == "codeqa.infrastructure.git"
                and any(a.name == "GitReader" for a in n.names)
                for n in ast.walk(tree)
            ), path)
            self.assertTrue(any(
                isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "tree_entries"
                for n in ast.walk(tree)
            ), path)

        print("ARCHITECTURE_GIT_OWNERSHIP_REAUDIT " + json.dumps({
            "baseline_sha": BEFORE, "post_sha": after,
            "matched_pipeline_files": len(before_sources),
            "before_literal_git_subprocess_sites": before_sites,
            "after_literal_git_subprocess_sites": after_sites,
            "semantic_ownership": "NOT_EVALUATED",
            "external_consumer_compatibility": "NOT_EVALUATED",
            "architecture_keep_or_move": "NOT_EVALUATED",
            "evidence_scope": "DIRECT_AST_SUBPROCESS_CALLS_ONLY",
        }, sort_keys=True))

    def test_aliases_and_from_import_are_counted_without_dynamic_claims(self):
        raw = (
            "import subprocess as sp\n"
            "from subprocess import run as execute\n"
            "sp.run(('git', 'status'))\n"
            "execute(['git', 'rev-parse', 'HEAD'])\n"
            "sp.run(command)\n"
        ).encode()
        record = _scan_subprocess(raw, "src/example.py")
        self.assertEqual(record["subprocess_import_lines"], [1, 2])
        self.assertEqual(record["direct_literal_git_call_lines"], [3, 4])
        self.assertEqual(record["other_direct_subprocess_call_lines"], [5])

    def test_strings_comments_and_other_commands_are_not_git_sites(self):
        raw = (
            "# subprocess.run(['git', 'status'])\n"
            "message = \"subprocess.run(['git', 'status'])\"\n"
            "import subprocess\n"
            "subprocess.run(['echo', 'hello'])\n"
        ).encode()
        record = _scan_subprocess(raw, "src/example.py")
        self.assertEqual(record["direct_literal_git_call_lines"], [])
        self.assertEqual(record["other_direct_subprocess_call_lines"], [4])

    def test_missing_or_malformed_source_fails_closed(self):
        with self.assertRaises(SyntaxError):
            _scan_subprocess(b"def broken(", "src/example.py")
        with self.assertRaises(ValueError):
            _pinned_pipeline_sources(GitReader(ROOT), "main")


if __name__ == "__main__":
    unittest.main()
