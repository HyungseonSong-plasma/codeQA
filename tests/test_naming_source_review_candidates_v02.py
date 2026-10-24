"""#69 pin source candidates for independent human inventory adjudication."""
from __future__ import annotations

import ast
from hashlib import sha1, sha256
import json
from pathlib import Path
import re
import unittest

from codeqa.infrastructure.git import GitReader

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "fixtures/naming-governance/codeqa-python-inventory-review-candidates-v02.json"


class SourceInventoryReviewCandidates(unittest.TestCase):
    def test_revision_and_each_line_are_real_and_not_approved(self):
        record = json.loads(FILE.read_text(encoding="utf-8"))
        self.assertEqual(record["review_status"], "AWAITING_HUMAN_REVIEW")
        self.assertIsNone(record["false_positive_adjudication"])
        self.assertIsNone(record["false_negative_adjudication"])
        body = GitReader(ROOT).read_file(record["source_commit"], record["source_path"])
        self.assertEqual(sha1(f"blob {len(body)}\0".encode() + body).hexdigest(),
                         record["source_git_blob_sha"])
        self.assertEqual(sha256(body).hexdigest(), record["source_sha256"])
        tree = ast.parse(body.decode("utf-8"))
        self.assertIsInstance(tree, ast.Module)
        lines = body.decode("utf-8").splitlines()
        self.assertEqual(len(record["candidates"]), 26)
        seen = set()
        for c in record["candidates"]:
            with self.subTest(symbol=c["name"], line=c["line"]):
                identity = (c["name"], c["kind"], c["line"], c["owner"])
                self.assertNotIn(identity, seen)
                seen.add(identity)
                self.assertGreater(c["line"], 0)
                line = lines[c["line"] - 1]
                if c["kind"] == "decorator":
                    self.assertIn(c["name"], line)
                else:
                    self.assertIsNotNone(re.search(
                        r"(?<!\w)" + re.escape(c["name"]) + r"(?!\w)", line))
                self.assertIsNone(c["adjudication"])

    def test_not_an_approved_ground_truth_or_runtime_resolution(self):
        record = json.loads(FILE.read_text(encoding="utf-8"))
        self.assertIn("CANDIDATES", record["schema_version"].upper())
        self.assertEqual(record["coverage_claim"],
                         "ONE_PINNED_FILE_LEXICAL_DECLARATIONS_ONLY")


if __name__ == "__main__":
    unittest.main()
