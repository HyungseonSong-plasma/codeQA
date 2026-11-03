"""#184: bounded opt-in Naming composition witnesses across three target roles.

Exercises real opt-in Naming behavior against the registered safe profile.
Frame calls and import syntax support a composition hypothesis only; neither
semantic ownership nor external/public compatibility is established.
"""
from __future__ import annotations

import ast
from hashlib import sha256
from pathlib import Path
import subprocess
import unittest

from codeqa.evaluation.architecture.runtime_call_pairs import capture_unittest_call_pairs
from codeqa.infrastructure.resources import ResourceRegistry
from codeqa.pipeline.naming_product import analyze_python_naming_opt_in


ROOT = Path(__file__).resolve().parents[1]
NAMING = "src/codeqa/pipeline/naming_product.py"
CORE = "src/codeqa/core/naming.py"
SNAPSHOT = "src/codeqa/adapters/python_snapshot.py"
ADAPTER = "src/codeqa/adapters/python_naming.py"
EVALUATION = "src/codeqa/evaluation/naming.py"
MECHANICAL = "src/codeqa/pipeline/python.py"

# These four source/target relationships are declared by Naming's source
# imports. Reverse/non-opt-in pairs are bounded negative runtime controls.
POSITIVE = (
    (NAMING, CORE),
    (NAMING, SNAPSHOT),
    (NAMING, ADAPTER),
    (NAMING, EVALUATION),
)
NEGATIVE = (
    (CORE, NAMING),
    (EVALUATION, NAMING),
    (NAMING, MECHANICAL),
)


def _module(path: str) -> str:
    return path.removeprefix("src/").removesuffix(".py").replace("/", ".")


class NamingOptInCompositionTests(unittest.TestCase):
    def test_real_opt_in_pipeline_calls_three_roles_without_mechanical_pipeline(self):
        profile = ResourceRegistry(ROOT).load_json("python_naming_safe_profile")

        class NamingCases(unittest.TestCase):
            def test_local_style_finding(self):
                report = analyze_python_naming_opt_in(
                    {"src/demo.py": (
                        "class Example:\n"
                        "    def BadMethod(self):\n"
                        "        return 1\n"
                    )},
                    snapshot_id="git:naming-role-composition-v01",
                    naming_profile=profile,
                )
                self.assertEqual(report.status, "REVIEW_REQUIRED")
                self.assertTrue(any(f.name == "BadMethod" for f in report.findings))

            def test_unknown_external_contract(self):
                report = analyze_python_naming_opt_in(
                    {"src/demo.py": (
                        "from vendor_sdk import ExternalBase\n"
                        "class Child(ExternalBase):\n"
                        "    def ExternalHook(self): pass\n"
                    )},
                    snapshot_id="git:naming-role-composition-external-v01",
                    naming_profile=profile,
                )
                self.assertEqual(report.status, "NOT_EVALUATED")
                self.assertTrue(any(
                    f.status == "NOT_EVALUATED" for f in report.findings
                ))

        # Source-grounded relationship precondition: a direct frame call
        # alone must not be mistaken for a measured static import edge.
        tree = ast.parse((ROOT / NAMING).read_bytes(), filename=NAMING)
        declared = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.level == 0
        }
        for _, target in POSITIVE:
            with self.subTest(static_target=target):
                self.assertIn(_module(target), declared)
        self.assertNotIn(_module(MECHANICAL), declared)

        pairs = (*POSITIVE, *NEGATIVE)
        paths = sorted({path for pair in pairs for path in pair})
        source_hashes = {
            path: sha256((ROOT / path).read_bytes()).hexdigest()
            for path in paths
        }
        # Git HEAD is the checkout's claim, not independent attestation of
        # the Python code objects that the interpreter actually executed.
        checkout = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
        ).strip()
        receipt = capture_unittest_call_pairs(
            unittest.TestSuite([
                NamingCases("test_local_style_finding"),
                NamingCases("test_unknown_external_contract"),
            ]),
            snapshot_sha=checkout,
            repository_root=ROOT,
            source_sha256=source_hashes,
            pairs=pairs,
        )

        self.assertEqual(receipt["tests_run"], 2)
        self.assertTrue(receipt["suite_was_successful"], receipt["executed_tests"])
        self.assertEqual(
            [item["outcome"] for item in receipt["executed_tests"]],
            ["PASSED", "PASSED"],
        )
        observed = {
            (row["source_path"], row["target_path"]): row
            for row in receipt["observed_pairs"]
        }
        self.assertEqual(len(observed), len(pairs))
        for pair in POSITIVE:
            with self.subTest(observed_pair=pair):
                row = observed[pair]
                self.assertGreater(row["observed_direct_python_calls"], 0)
                self.assertTrue(row["call_witnesses"])
                self.assertTrue(all(
                    witness["test_id"].endswith(
                        (".NamingCases.test_local_style_finding",
                         ".NamingCases.test_unknown_external_contract")
                    )
                    and witness["caller_line"] > 0
                    and witness["callee_first_line"] > 0
                    for witness in row["call_witnesses"]
                ))
        for pair in NEGATIVE:
            with self.subTest(negative_pair=pair):
                self.assertEqual(observed[pair]["observed_direct_python_calls"], 0)

        self.assertEqual(receipt["source_identity"]["source_sha256"], source_hashes)
        self.assertEqual(receipt["evidence_class"], "LOCAL_PYTHON_FRAME_CALL_UNATTESTED")
        for key in (
            "static_import_edge_traversal", "semantic_ownership",
            "public_api_compatibility", "decision",
        ):
            self.assertEqual(receipt[key], "NOT_EVALUATED")
        print(
            "ARCHITECTURE_NAMING_OPTIN_ROLE_CALLS "
            "direct_source_pairs=4 reverse_or_nonoptin_controls=3 "
            "test_cases=2 semantic_ownership=NOT_EVALUATED "
            "external_consumers=NOT_EVALUATED"
        )


if __name__ == "__main__":
    unittest.main()
