"""#184: observe opt-in Pipeline role analysis, without certifying ownership.

This bounded runtime test exercises the real semantic/behavior branches of
analyze_python on source strings. Direct frame calls support a composition
hypothesis; they do not prove import-edge traversal, external consumers,
correct semantic ownership, or the safety of a package move.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import subprocess
import unittest

from codeqa.evaluation.architecture.runtime_call_pairs import (
    capture_unittest_call_pairs,
)
from codeqa.infrastructure.resources import ResourceRegistry
from codeqa.pipeline.python import analyze_python


ROOT = Path(__file__).resolve().parents[1]
PIPELINE = "src/codeqa/pipeline/python.py"
BEHAVIOR_ADAPTER = "src/codeqa/adapters/python_behavior.py"
BEHAVIOR_EVALUATION = "src/codeqa/evaluation/responsibility_behavior.py"
SEMANTIC_EVALUATION = "src/codeqa/evaluation/semantic_architecture.py"


def _role_policy():
    return {
        "policy_id": "fixture.pipeline.optional-roles",
        "schema_version": 1,
        "scope": "src/pkg",
        "roles": {
            "adapters": {
                "responsibility": "source interpretation",
                "forbidden_imports": [],
            },
            "evaluation": {
                "responsibility": "pure evidence evaluation",
                "forbidden_imports": [],
            },
            "core": {
                "responsibility": "language-neutral data",
                "forbidden_imports": [],
            },
        },
        "exceptions": [],
    }


def _behavior_policy():
    kinds = (
        "AST_SOURCE_INTERPRETATION_SYNTAX",
        "PROCESS_INVOCATION_SYNTAX",
    )
    return {
        "policy_id": "fixture.pipeline.optional-behavior",
        "schema_version": "0.1",
        "scope": "src/pkg",
        "catalog": [
            {"module": "ast", "symbol": "parse", "kind": kinds[0]},
            {"module": "subprocess", "symbol": "run", "kind": kinds[1]},
        ],
        "roles": {
            "adapters": {"forbidden": [kinds[1]]},
            "evaluation": {"forbidden": list(kinds)},
            "core": {"forbidden": list(kinds)},
        },
    }


class PipelineOptionalRoleCompositionTests(unittest.TestCase):
    def test_real_opt_in_analysis_observes_three_role_collaborators(self):
        registry = ResourceRegistry(ROOT)
        ccg_schema = registry.load_json("ccg_schema")
        mechanical_profile = registry.load_json("mechanical_profile")
        sources = {
            "src/pkg/adapters/parser.py": (
                "import ast\n\ndef parse(text):\n    return ast.parse(text)\n"
            ),
            "src/pkg/evaluation/runner.py": (
                "import subprocess\n\ndef run():\n"
                "    return subprocess.run(['true'])\n"
            ),
            "src/pkg/core/model.py": "VALUE = 1\n",
        }

        class AnalyzeCase(unittest.TestCase):
            def test_analyze(self):
                analysis = analyze_python(
                    sources,
                    snapshot_id="git:optional-roles-observation-v01",
                    ccg_schema=ccg_schema,
                    mechanical_profile=mechanical_profile,
                    semantic_policy=_role_policy(),
                    behavior_policy=_behavior_policy(),
                )
                self.assertEqual(analysis.graph.coverage.status, "complete")
                self.assertIsNotNone(analysis.semantic_architecture)
                self.assertIsNotNone(analysis.responsibility_behavior)
                self.assertEqual(
                    analysis.responsibility_behavior.status, "REVIEW_REQUIRED",
                )
                self.assertEqual(len(analysis.responsibility_behavior.observations), 2)

        pairs = [
            (PIPELINE, BEHAVIOR_ADAPTER),
            (PIPELINE, BEHAVIOR_EVALUATION),
            (PIPELINE, SEMANTIC_EVALUATION),
            (BEHAVIOR_ADAPTER, PIPELINE),  # reverse-direction negative control
            (SEMANTIC_EVALUATION, PIPELINE),
        ]
        paths = {path for pair in pairs for path in pair}
        source_hashes = {
            path: sha256((ROOT / path).read_bytes()).hexdigest()
            for path in sorted(paths)
        }
        # Checkout identity is a claim, not an independent source attestation.
        checkout_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
        ).strip()
        report = capture_unittest_call_pairs(
            unittest.TestSuite([AnalyzeCase("test_analyze")]),
            snapshot_sha=checkout_sha,
            repository_root=ROOT,
            source_sha256=source_hashes,
            pairs=pairs,
        )

        observed = {
            (edge["source_path"], edge["target_path"]): edge
            for edge in report["observed_pairs"]
        }
        self.assertEqual(report["tests_run"], 1)
        self.assertTrue(report["suite_was_successful"])
        self.assertEqual(
            [row["outcome"] for row in report["executed_tests"]], ["PASSED"],
        )
        for target in (BEHAVIOR_ADAPTER, BEHAVIOR_EVALUATION, SEMANTIC_EVALUATION):
            with self.subTest(target=target):
                edge = observed[(PIPELINE, target)]
                self.assertGreater(edge["observed_direct_python_calls"], 0)
                self.assertTrue(edge["call_witnesses"])
                self.assertTrue(all(
                    witness["test_id"].endswith(".AnalyzeCase.test_analyze")
                    for witness in edge["call_witnesses"]
                ))
        for source in (BEHAVIOR_ADAPTER, SEMANTIC_EVALUATION):
            self.assertEqual(
                observed[(source, PIPELINE)]["observed_direct_python_calls"], 0,
            )
        self.assertEqual(
            report["source_identity"]["source_sha256"], source_hashes,
        )
        for claim in (
            "static_import_edge_traversal", "semantic_ownership",
            "public_api_compatibility", "decision",
        ):
            self.assertEqual(report[claim], "NOT_EVALUATED")


if __name__ == "__main__":
    unittest.main()
