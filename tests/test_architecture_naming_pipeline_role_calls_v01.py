"""#184: real pinned Naming wrappers exercise bounded core/Git responsibilities.

These are *direct Python frame-call* observations for six source-import
pairs. A successful call is not semantic ownership, import execution,
external API compatibility, or authorization for a package relocation.
"""
from __future__ import annotations

import ast
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import unittest

from codeqa.evaluation.architecture.runtime_call_pairs import (
    capture_unittest_call_pairs,
)
from codeqa.pipeline.naming_field_evidence_v03 import project_pinned_field_evidence
from codeqa.pipeline.naming_rule_inventory_v03 import evaluate_pinned_rule_inventory


ROOT = Path(__file__).resolve().parents[1]
PROPOSAL = ROOT / "fixtures/naming-governance/codeqa-ast-review-v03-proposal.json"
FIELD = "src/codeqa/pipeline/naming_field_evidence_v03.py"
RULE = "src/codeqa/pipeline/naming_rule_inventory_v03.py"
REVIEW = "src/codeqa/core/naming_review_worklist_v03.py"
FIELD_CORE = "src/codeqa/core/naming_field_evidence_v03.py"
RULE_CORE = "src/codeqa/core/naming_rule_inventory_v03.py"
GIT = "src/codeqa/infrastructure/git.py"

# All six positive pairs are real, direct import relationships in the two
# wrappers; reverse controls are deliberately not static import edges.
POSITIVE = (
    (FIELD, REVIEW), (FIELD, FIELD_CORE), (FIELD, GIT),
    (RULE, REVIEW), (RULE, RULE_CORE), (RULE, GIT),
)
REVERSE = ((GIT, FIELD), (RULE_CORE, RULE))


def _module(path: str) -> str:
    return path.removeprefix("src/").removesuffix(".py").replace("/", ".")


class NamingPipelineRoleCallsTests(unittest.TestCase):
    def test_real_pinned_naming_wrappers_call_declared_collaborators(self):
        proposal = json.loads(PROPOSAL.read_text(encoding="utf-8"))

        class PinnedCases(unittest.TestCase):
            def test_field_projection(self):
                packet = project_pinned_field_evidence(ROOT, proposal)
                self.assertEqual(packet["projected_field_sites"], 7)
                self.assertEqual(packet["policy_adoption"], "NOT_ADOPTED")
                self.assertEqual(packet["runtime_field_verification"], "NOT_EVALUATED")

            def test_rule_inventory(self):
                packet = evaluate_pinned_rule_inventory(ROOT, proposal)
                self.assertEqual(packet["total_sites"], 50)
                self.assertEqual(packet["closure_gate"], "PASS")
                self.assertEqual(packet["semantic_glossary"], "NOT_ADOPTED")

        # Fail if a refactor silently changes a measured source import; a
        # runtime call alone cannot authenticate the static B2 relationship.
        for source, target in POSITIVE:
            with self.subTest(source=source, target=target):
                tree = ast.parse((ROOT / source).read_bytes(), filename=source)
                self.assertIn(
                    _module(target),
                    {node.module for node in ast.walk(tree)
                     if isinstance(node, ast.ImportFrom) and node.level == 0},
                )

        pairs = (*POSITIVE, *REVERSE)
        paths = {path for pair in pairs for path in pair}
        hashes = {
            path: sha256((ROOT / path).read_bytes()).hexdigest()
            for path in sorted(paths)
        }
        checkout = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
        ).strip()
        report = capture_unittest_call_pairs(
            unittest.TestSuite([
                PinnedCases("test_field_projection"),
                PinnedCases("test_rule_inventory"),
            ]),
            snapshot_sha=checkout,
            repository_root=ROOT,
            source_sha256=hashes,
            pairs=pairs,
        )
        self.assertEqual(report["tests_run"], 2)
        self.assertTrue(report["suite_was_successful"], report["executed_tests"])
        self.assertEqual(
            [row["outcome"] for row in report["executed_tests"]],
            ["PASSED", "PASSED"],
        )
        observed = {
            (row["source_path"], row["target_path"]): row
            for row in report["observed_pairs"]
        }
        for pair in POSITIVE:
            with self.subTest(pair=pair):
                row = observed[pair]
                self.assertGreater(row["observed_direct_python_calls"], 0)
                self.assertTrue(row["call_witnesses"])
                expected_test = (
                    "test_field_projection" if pair[0] == FIELD
                    else "test_rule_inventory"
                )
                self.assertTrue(all(
                    witness["test_id"].endswith(".PinnedCases." + expected_test)
                    and witness["caller_line"] > 0
                    and witness["callee_first_line"] > 0
                    for witness in row["call_witnesses"]
                ))
        for pair in REVERSE:
            self.assertEqual(observed[pair]["observed_direct_python_calls"], 0)
        self.assertEqual(report["source_identity"]["source_sha256"], hashes)
        for claim in (
            "static_import_edge_traversal", "semantic_ownership",
            "public_api_compatibility", "decision",
        ):
            self.assertEqual(report[claim], "NOT_EVALUATED")
        print(
            "ARCHITECTURE_NAMING_ROLE_CALLS "
            "direct_source_pairs=6 reverse_controls=2 "
            "test_cases=2 semantic_ownership=NOT_EVALUATED "
            "external_consumers=NOT_EVALUATED"
        )


if __name__ == "__main__":
    unittest.main()
