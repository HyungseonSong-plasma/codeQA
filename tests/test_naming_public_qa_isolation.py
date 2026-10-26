"""Naming opt-in cannot mutate frozen Public QA Result v0.1 bytes."""
from pathlib import Path
import unittest

from codeqa.evaluation.mechanical import MechanicalProfile
from codeqa.evaluation.qa_result import mechanical_to_qa_result, canonical_qa_json
from codeqa.infrastructure.resources import ResourceRegistry
from codeqa.pipeline.python import analyze_python
from codeqa.pipeline.naming_product import analyze_python_naming_opt_in

ROOT = Path(__file__).resolve().parents[1]


class NamingPublicQaIsolationTests(unittest.TestCase):
    def test_public_qa_schema_bytes_are_stable_across_explicit_naming(self):
        resources = ResourceRegistry(ROOT)
        mechanical = resources.load_json("mechanical_profile")
        qa_schema = resources.load_json("qa_result_schema")
        ccg_schema = resources.load_json("ccg_schema")
        naming = resources.load_json("python_naming_safe_profile")
        sources = {
            "src/thing.py": "class Thing:\n    def BadMethod(self):\n        return 1\n"
        }
        def public_qa():
            analysis = analyze_python(
                sources, snapshot_id="git:fixture", ccg_schema=ccg_schema,
                mechanical_profile=mechanical,
            )
            document = mechanical_to_qa_result(
                analysis.graph, analysis.quality,
                MechanicalProfile.from_mapping(mechanical), schema=qa_schema,
            )
            return canonical_qa_json(document)

        before = public_qa()
        observed = analyze_python_naming_opt_in(
            sources, snapshot_id="git:fixture", naming_profile=naming,
        )
        self.assertEqual(observed.status, "REVIEW_REQUIRED")
        after = public_qa()
        self.assertEqual(before, after)
        self.assertNotIn('"naming"', after)
        self.assertIn('"unsupported_rules"', after)
