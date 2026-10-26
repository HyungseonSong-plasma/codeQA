"""Separate structural denominator and exact-git-source negatives for #91."""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import os
from pathlib import Path
import unittest

from codeqa.core.naming_snapshot_coverage_v03 import (
    NamingSnapshotCoverageError, scan_pinned_git, scan_selected_python,
)


REV = "a" * 40
PATH = "src/codeqa/physics/sample.py"
SOURCE = b"""from typing import ClassVar
from somewhere import *
class Sample:
    shared: ClassVar[int] = 1
    field: int = 2
    def work(self, x, /, *args, flag=True, **kwargs):
        local = x
        setattr(self, "dynamic", local)
        def nested(y):
            return y
        return nested(x)
async def run(value):
    return value
"""


def census(source: bytes = SOURCE, *, path: str = PATH,
           revision: str = REV, digest: str | None = None):
    return scan_selected_python(
        revision=revision, sources={path: source},
        expected_digests={path: digest or sha256(source).hexdigest()},
    )


class PinnedNamingSnapshotCensusTests(unittest.TestCase):
    def test_independent_ast_function_method_parameter_denominator(self):
        r = census()
        # 1 method + 2 functions + 7 parameters
        self.assertEqual(r.examined_files, 1)
        self.assertEqual(r.expected_structural_sites, 10)
        self.assertEqual(r.matched_sites, r.expected_structural_sites)
        self.assertEqual(r.observed_structural_sites, r.expected_structural_sites)
        self.assertFalse(r.missing_sites)
        self.assertFalse(r.unexpected_sites)
        self.assertEqual(r.source_digests[0], (PATH, sha256(SOURCE).hexdigest()))
        self.assertEqual(r.status, "NOT_EVALUATED")
        self.assertEqual(r.semantic_false_negative_rate, "NOT_EVALUATED")
        self.assertFalse(r.rename_authorized)
        self.assertIn(("wildcard_import", 1), r.uncertainty_categories)
        self.assertIn(("dynamic_call_requires_resolution", 1), r.uncertainty_categories)
        self.assertTrue(any(k == "field_ownership_not_in_denominator"
                            for k, _ in r.uncertainty_categories))

    def test_empty_and_incomplete_selected_paths_fail_closed(self):
        with self.assertRaises(NamingSnapshotCoverageError):
            scan_selected_python(revision=REV, sources={}, expected_digests={})
        with self.assertRaises(NamingSnapshotCoverageError):
            scan_selected_python(revision=REV, sources={PATH: SOURCE}, expected_digests={})
        with self.assertRaises(NamingSnapshotCoverageError):
            scan_selected_python(revision=REV, sources={PATH: SOURCE},
                                 expected_digests={PATH: "f"*64, "extra": "0"*64})

    def test_changed_bytes_stale_digest_and_unsafe_path_fail(self):
        with self.assertRaisesRegex(NamingSnapshotCoverageError, "SHA-256"):
            census(digest="f"*64)
        for path in ("/src/codeqa/x.py", "src/codeqa/../evil.py",
                     "src/codeqa/x.py/../y.py", "src/codeqa/name\\bad.py",
                     "src/codeqa/file.txt", "tests/test.py"):
            with self.subTest(path=path):
                with self.assertRaises(NamingSnapshotCoverageError):
                    census(path=path)
        with self.assertRaises(NamingSnapshotCoverageError):
            census(revision="main")

    def test_bad_syntax_and_non_utf8_are_not_silently_skipped(self):
        for body in (b"def f(:\n", b"\xff\xfe\x00"):
            with self.subTest(body=body):
                with self.assertRaisesRegex(NamingSnapshotCoverageError, "unparseable"):
                    census(source=body)

    def test_deterministic_permutation_and_cross_file_duplicate_names(self):
        other = "src/codeqa/extra/sample.py"
        common = b"def same(name):\n    return name\n"
        mapping = {PATH: common, other: common}
        hashes = {p: sha256(s).hexdigest() for p, s in mapping.items()}
        a = scan_selected_python(revision=REV, sources=mapping, expected_digests=hashes)
        b = scan_selected_python(revision=REV, sources=dict(reversed(list(mapping.items()))),
                                 expected_digests=dict(reversed(list(hashes.items()))))
        self.assertEqual(a, b)
        self.assertEqual(a.examined_files, 2)
        self.assertEqual(a.expected_structural_sites, 4)
        self.assertEqual(a.matched_sites, 4)
        self.assertFalse(a.missing_sites)

    def test_unresolved_unicode_dunder_and_binding_imports(self):
        source = ("from .module import item\n"
                  "global_name = 1\n"
                  "def __getattr__(key):\n    return 1\n"
                  "def λambda(x):\n    global global_name\n    return x\n")
        r = census(source=source.encode())
        uncertainty = dict(r.uncertainty_categories)
        self.assertEqual(uncertainty["relative_import_requires_resolution"], 1)
        self.assertEqual(uncertainty["dunder_public_binding"], 1)
        self.assertEqual(uncertainty["unicode_identifier"], 1)
        self.assertEqual(uncertainty["global_nonlocal_binding"], 1)
        self.assertEqual(r.semantic_false_positive_rate, "NOT_EVALUATED")

    def test_claimed_semantic_approval_is_not_an_output(self):
        r = census()
        self.assertFalse(r.rename_authorized)
        self.assertEqual(r.external_compatibility, "NOT_EVALUATED")
        self.assertFalse(hasattr(r, "naming_pass"))


class ExactRepositoryTreeCensus(unittest.TestCase):
    def test_actual_pinned_git_tree_without_worktree_fallback(self):
        revision = os.environ.get("CODEQA_NAMING_PINNED_REV")
        if revision is None:
            self.skipTest("strict actual Git witness runs with pinned SHA in CI")
        root = Path(__file__).resolve().parents[1]
        result = scan_pinned_git(root, revision=revision)
        self.assertEqual(result.revision, revision)
        self.assertGreater(result.examined_files, 1)
        self.assertEqual(len(result.source_digests), result.examined_files)
        self.assertEqual(result.expected_structural_sites, result.matched_sites,
                         f"missing={result.missing_sites[:8]}")
        self.assertEqual(result.observed_structural_sites, result.matched_sites,
                         f"unexpected={result.unexpected_sites[:8]}")
        self.assertFalse(result.rename_authorized)
        self.assertEqual(result.status, "NOT_EVALUATED")
        print("NAMING_PINNED_CENSUS",
              "revision=" + result.revision,
              "files=" + str(result.examined_files),
              "structural_denominator=" + str(result.expected_structural_sites),
              "matched=" + str(result.matched_sites),
              "uncertainty=" + repr(result.uncertainty_categories),
              "semantic_fp_fn=NOT_EVALUATED")


if __name__ == "__main__":
    unittest.main()
