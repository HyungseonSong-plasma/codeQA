"""AnalysisRequest defaults are exactly the old Python Mechanical path (#123)."""
from __future__ import annotations

from pathlib import Path
import unittest

from codeqa.infrastructure.resources import ResourceRegistry
from codeqa.pipeline.analysis_request import (
    AnalysisOptions, AnalysisRequest, AnalysisRequestError, analyze_python_request,
)
from codeqa.pipeline.python import analyze_python


ROOT = Path(__file__).resolve().parents[1]


class AnalysisRequestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        resources = ResourceRegistry(ROOT)
        cls.ccg = resources.load_json("ccg_schema")
        cls.profile = resources.load_json("mechanical_profile")

    def request(self, options=None):
        return AnalysisRequest(
            sources={
                "a.py": "def alpha():\n    return 1\n",
                "b.py": "import a\n\ndef beta():\n    return a.alpha()\n",
            },
            snapshot_id="git:fixture",
            ccg_schema=self.ccg,
            mechanical_profile=self.profile,
            options=AnalysisOptions() if options is None else options,
        )

    def test_default_exact_graph_and_mechanical_equality(self):
        req = self.request()
        old = analyze_python(
            req.sources, snapshot_id=req.snapshot_id,
            ccg_schema=req.ccg_schema, mechanical_profile=req.mechanical_profile,
        )
        new = analyze_python_request(req)
        self.assertEqual(new.analysis.graph.to_document(), old.graph.to_document())
        self.assertEqual(new.analysis.quality.to_document(), old.quality.to_document())
        self.assertEqual(new.analysis.summary_document(), old.summary_document())
        self.assertEqual(new.companion_states["naming"], "NOT_REQUESTED")
        self.assertEqual(new.companion_states["formal"], "NOT_REQUESTED")
        self.assertEqual(new.companion_states["external_gate"], "NOT_REQUESTED")

    def test_explicit_impact_only_does_not_change_mechanical(self):
        req = self.request(AnalysisOptions.from_mapping({"changed_paths": ["a.py"]}))
        result = analyze_python_request(req)
        self.assertEqual(result.companion_states["impact"], "EXECUTED")
        self.assertEqual(result.companion_states["naming"], "NOT_REQUESTED")
        self.assertEqual(result.analysis.quality.to_document(), analyze_python(
            req.sources, snapshot_id=req.snapshot_id,
            ccg_schema=req.ccg_schema, mechanical_profile=req.mechanical_profile,
        ).quality.to_document())

    def test_unknown_option_fails_closed(self):
        with self.assertRaises(AnalysisRequestError):
            AnalysisOptions.from_mapping({"autonomous_full_qa_pass": True})

    def test_unsupported_naming_formal_gate_not_silently_activated(self):
        for name in ("naming", "formal", "external_gate"):
            with self.subTest(name=name), self.assertRaises(AnalysisRequestError):
                AnalysisOptions.from_mapping({name: True})

    def test_falsy_non_boolean_authority_values_are_rejected(self):
        # False is the only disabled Boolean; 0, None, empty containers
        # and empty strings must never masquerade as an explicit opt-out.
        for name in ("naming", "formal", "external_gate"):
            for value in (0, 1, None, "", [], {}):
                with self.subTest(name=name, value=value), self.assertRaisesRegex(
                    AnalysisRequestError, "explicit Boolean"
                ):
                    AnalysisOptions.from_mapping({name: value})
            self.assertEqual(
                getattr(AnalysisOptions.from_mapping({name: False}), name), False
            )
        with self.assertRaisesRegex(AnalysisRequestError, "explicit Boolean"):
            AnalysisOptions(naming=0).validate()

    def test_direct_unhashable_changed_path_fails_with_typed_error(self):
        with self.assertRaisesRegex(AnalysisRequestError, "invalid changed paths"):
            AnalysisOptions(changed_paths=(["nested"],)).validate()

    def test_control_character_changed_paths_rejected(self):
        for path in ("a\\nb.py", "a\\tb.py", "a\\rb.py", "a\\x7fb.py"):
            with self.subTest(path=path), self.assertRaises(AnalysisRequestError):
                AnalysisOptions.from_mapping({"changed_paths": [path]})

    def test_unsafe_duplicate_changed_paths_rejected(self):
        for paths in (["../outside.py"], ["a.py", "a.py"], ["/tmp/file.py"]):
            with self.subTest(paths=paths), self.assertRaises(AnalysisRequestError):
                AnalysisOptions.from_mapping({"changed_paths": paths})

    def test_unknown_version_rejected(self):
        with self.assertRaises(AnalysisRequestError):
            AnalysisOptions.from_mapping({"version": "2.0"})

    def test_non_json_policy_rejected(self):
        with self.assertRaises(AnalysisRequestError):
            AnalysisOptions.from_mapping({"semantic_policy": {"unsafe": object()}})

    def test_missing_snapshot_rejected(self):
        req = self.request()
        from dataclasses import replace
        with self.assertRaises(AnalysisRequestError):
            analyze_python_request(replace(req, snapshot_id=""))


if __name__ == "__main__":
    unittest.main()
