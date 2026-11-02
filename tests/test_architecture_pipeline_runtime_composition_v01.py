"""#184: bounded real Pipeline composition calls, not import-edge certification.

This exercises codeQA's existing Python pipeline on a small real analysis
request and observes direct Python frame calls from Pipeline into its Adapter
and Evaluation collaborators, including the optional change-impact path. The negative reverse direction is only an
observation for this execution, never proof that an import edge is absent.
No external consumers, semantic ownership, or migration safety are attested.
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
ADAPTER = "src/codeqa/adapters/python.py"
DEPENDENCIES = "src/codeqa/adapters/python_dependencies.py"
SNAPSHOT = "src/codeqa/adapters/python_snapshot.py"
EVIDENCE = "src/codeqa/adapters/python_evidence.py"
FUNCTION_CONTEXT = "src/codeqa/adapters/python_context.py"
SYMBOLS = "src/codeqa/adapters/python_symbols.py"
EVALUATION = "src/codeqa/evaluation/mechanical.py"
CONTEXTUAL = "src/codeqa/evaluation/contextual.py"
IMPACT = "src/codeqa/evaluation/impact.py"


class PipelineRuntimeCompositionTests(unittest.TestCase):
    def test_real_analysis_observes_bounded_pipeline_collaborator_calls(self):
        registry = ResourceRegistry(ROOT)
        ccg_schema = registry.load_json("ccg_schema")
        mechanical_profile = registry.load_json("mechanical_profile")
        sources = {
            "src/pkg/a.py": "def helper():\n    return 1\n",
            "src/pkg/b.py": (
                "from pkg.a import helper\n\ndef run():\n"
                "    return helper()\n"
            ),
        }

        class AnalyzeCase(unittest.TestCase):
            def test_analyze(self):
                analysis = analyze_python(
                    sources, snapshot_id="git:composition-observation-v01",
                    ccg_schema=ccg_schema, mechanical_profile=mechanical_profile,
                    changed_paths=("src/pkg/a.py",),
                )
                self.assertEqual(analysis.graph.coverage.status, "complete")
                self.assertGreater(len(analysis.graph.nodes), 0)
                self.assertIsNotNone(analysis.impact)
                self.assertIn("src/pkg/a.py", analysis.impact.changed_paths)

        pairs = [
            (PIPELINE, ADAPTER),
            (PIPELINE, DEPENDENCIES),
            (PIPELINE, SNAPSHOT),
            (PIPELINE, EVIDENCE),
            (PIPELINE, FUNCTION_CONTEXT),
            (PIPELINE, SYMBOLS),
            (PIPELINE, EVALUATION),
            (PIPELINE, CONTEXTUAL),
            (PIPELINE, IMPACT),  # optional changed-path analysis is executed
            (ADAPTER, PIPELINE),  # negative control: not a static edge
            (IMPACT, PIPELINE),  # negative control: no reverse call
        ]
        paths = {path for pair in pairs for path in pair}
        source_hashes = {
            path: sha256((ROOT / path).read_bytes()).hexdigest()
            for path in sorted(paths)
        }
        # This is the checked-out Git revision, possibly GitHub's synthetic
        # PR merge commit; it is not an independent provenance attestation.
        checkout_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
        ).strip()
        report = capture_unittest_call_pairs(
            unittest.TestSuite([AnalyzeCase("test_analyze")]),
            snapshot_sha=checkout_sha, repository_root=ROOT,
            source_sha256=source_hashes, pairs=pairs,
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
        for target in (
            ADAPTER, DEPENDENCIES, SNAPSHOT, EVIDENCE, FUNCTION_CONTEXT,
            SYMBOLS, EVALUATION, CONTEXTUAL, IMPACT,
        ):
            with self.subTest(target=target):
                edge = observed[(PIPELINE, target)]
                self.assertGreater(edge["observed_direct_python_calls"], 0)
                self.assertTrue(edge["call_witnesses"])
                self.assertTrue(all(
                    witness["test_id"].endswith(".AnalyzeCase.test_analyze")
                    for witness in edge["call_witnesses"]
                ))
        for source in (ADAPTER, IMPACT):
            self.assertEqual(
                observed[(source, PIPELINE)]["observed_direct_python_calls"], 0,
            )
        self.assertEqual(
            report["source_identity"]["source_sha256"], source_hashes,
        )
        self.assertEqual(report["static_import_edge_traversal"], "NOT_EVALUATED")
        self.assertEqual(report["semantic_ownership"], "NOT_EVALUATED")
        self.assertEqual(report["public_api_compatibility"], "NOT_EVALUATED")
        self.assertEqual(report["decision"], "NOT_EVALUATED")


if __name__ == "__main__":
    unittest.main()
