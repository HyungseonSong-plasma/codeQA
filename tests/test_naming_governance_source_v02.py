"""#74 verify real pinned source witnesses without claiming human acceptance."""
from __future__ import annotations

import ast
from hashlib import sha1, sha256
import json
from pathlib import Path
import unittest

from codeqa.infrastructure.git import GitReader

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures/naming-governance/codeqa-negative-control-review-candidates-v02.json"


class PinnedNegativeControlCandidates(unittest.TestCase):
    def test_real_git_blob_and_ast_locations(self):
        witness = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(witness["review_status"], "AWAITING_HUMAN_REVIEW")
        self.assertEqual(witness["source_repository"], "HyungseonSong-plasma/codeQA")
        body = GitReader(ROOT).read_file(
            witness["source_commit"], witness["source_path"])
        blob_sha = sha1(f"blob {len(body)}\0".encode() + body).hexdigest()
        self.assertEqual(blob_sha, witness["source_git_blob_sha"])
        self.assertEqual(sha256(body).hexdigest(), witness["source_sha256"])
        tree = ast.parse(body.decode("utf-8"))
        declarations = {(n.name, n.lineno) for n in ast.walk(tree)
                        if isinstance(n, (ast.ClassDef, ast.FunctionDef,
                                          ast.AsyncFunctionDef))}
        assigns = {(n.targets[0].id, n.lineno) for n in ast.walk(tree)
                   if isinstance(n, ast.Assign) and len(n.targets) == 1
                   and isinstance(n.targets[0], ast.Name)}
        self.assertEqual(len(witness["candidates"]), 7)
        for c in witness["candidates"]:
            with self.subTest(name=c["name"]):
                key = (c["name"], c["line"])
                self.assertIn(key, assigns if c["kind"] == "module_constant"
                              else declarations)
                self.assertIsNone(c["human_review_outcome"])
                self.assertTrue(c["reason"])

    def test_source_candidate_is_not_approved_policy(self):
        witness = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertIn("CANDIDATES", witness["coverage_claim"])
        self.assertFalse(any(c["human_review_outcome"]
                             for c in witness["candidates"]))


if __name__ == "__main__":
    unittest.main()
