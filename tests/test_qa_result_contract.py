"""#28: Public QA Result v0.1 and conservative quality delta conformance."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator

from codeqa.core import parse_graph
from codeqa.evaluation.mechanical import (
    MechanicalProfile, evaluate_mechanical,
)
from codeqa.evaluation.qa_result import (
    QaResultContractError, canonical_qa_json, compare_quality_delta,
    mechanical_to_qa_result, validate_qa_result,
)
from codeqa.infrastructure.resources import ResourceRegistry
from codeqa.pipeline.python import analyze_python


ROOT = Path(__file__).resolve().parents[1]


class QaResultContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        registry = ResourceRegistry(ROOT)
        cls.ccg = registry.load_json("ccg_schema")
        cls.profile = registry.load_json("mechanical_profile")
        cls.result_schema = registry.load_json("qa_result_schema")
        cls.delta_schema = registry.load_json("qa_delta_schema")
        Draft202012Validator.check_schema(cls.result_schema)
        Draft202012Validator.check_schema(cls.delta_schema)

    def convert(self, sources, *, snapshot="snapshot-a", profile=None):
        profile = profile or self.profile
        analysis = analyze_python(
            sources, snapshot_id=snapshot, ccg_schema=self.ccg,
            mechanical_profile=profile,
        )
        document = mechanical_to_qa_result(
            analysis.graph, analysis.quality,
            MechanicalProfile.from_mapping(profile), schema=self.result_schema,
        )
        return analysis, document

    def test_schema_versions_are_public_and_non_ccg(self):
        self.assertEqual(self.result_schema["$id"], "urn:codeqa:qa:result:v0.1")
        self.assertEqual(self.delta_schema["$id"], "urn:codeqa:qa:delta:v0.1")
        self.assertEqual(self.result_schema["properties"]["schema_version"]["const"], "0.1")
        self.assertNotIn("quality", self.ccg["properties"])

    def test_supported_rules_and_absent_principles_are_explicit(self):
        _, doc = self.convert({"clean.py": "def f():\n    return 1\n"})
        self.assertEqual(doc["verdict"]["status"], "PASS")
        self.assertEqual(doc["verdict"]["scope"], "evaluated_rules_only")
        self.assertEqual(doc["scope"]["meaning"], "analyzed_paths_only")
        self.assertEqual(doc["analysis"]["status"], "COMPLETE")
        self.assertEqual([r["id"] for r in doc["rules"]],
                         ["function_span_review", "outgoing_call_sites_review"])
        self.assertEqual({x["id"] for x in doc["unsupported_rules"]},
                         {"P2", "P4", "P5", "P6", "P7", "P8"})
        self.assertEqual(len(doc["evidence"]), 2)
        for item in doc["evidence"]:
            self.assertEqual(item["location"]["path"], "clean.py")
            self.assertEqual(item["provenance"]["producer"], "codeqa.mechanical")
        self.assertEqual(validate_qa_result(doc, self.result_schema), doc)

    def test_measured_review_is_not_a_proven_design_failure(self):
        custom = {**self.profile, "max_function_lines": 2}
        result, doc = self.convert({"long.py": "def f():\n    n = 1\n    return n\n"}, profile=custom)
        self.assertEqual(result.quality.status, "REVIEW_REQUIRED")
        self.assertEqual(doc["verdict"]["status"], "REVIEW_REQUIRED")
        observations = [e for e in doc["evidence"] if e["status"] == "REVIEW_REQUIRED"]
        self.assertEqual(len(observations), 1)
        self.assertEqual(observations[0]["metric"],
                         {"name": "function_span_lines", "value": 3, "unit": "line"})
        self.assertEqual(observations[0]["threshold"], {"operator": ">", "value": 2})

    def test_partial_parse_preserves_scoped_pass_and_limitations(self):
        old, doc = self.convert({"ok.py": "def f(): pass\n", "bad.py": "def ("})
        self.assertEqual(old.quality.status, "PASS")
        self.assertEqual(doc["verdict"]["status"], "PASS")
        self.assertEqual(doc["coverage"]["status"], "partial")
        self.assertEqual(doc["analysis"]["status"], "LIMITED")
        self.assertIn("incomplete_source_coverage", doc["analysis"]["limitations"])
        self.assertEqual(doc["coverage"]["unprocessed"],
                         [{"path": "bad.py", "reason": "syntax_error"}])

    def test_unsupported_input_and_zero_functions_are_not_evaluated(self):
        for sources in ({}, {"bad.py": "def ("}, {"x.py": "answer = 2\n"}):
            with self.subTest(sources=sources):
                _, doc = self.convert(sources)
                self.assertEqual(doc["verdict"]["status"], "NOT_EVALUATED")
                self.assertTrue(all(r["verdict"] == "NOT_EVALUATED" for r in doc["rules"]))
                self.assertFalse(doc["evidence"])

    def test_validation_rejects_missing_provenance_or_orphan_evidence(self):
        _, original = self.convert({"x.py": "def x(): pass\n"})
        for change in ("provenance", "broken_reference", "foreign_rule", "orphan"):
            with self.subTest(change=change):
                doc = deepcopy(original)
                if change == "provenance":
                    del doc["evidence"][0]["provenance"]
                elif change == "broken_reference":
                    doc["rules"][0]["evidence_ids"][0] = "missing"
                elif change == "foreign_rule":
                    doc["evidence"][0]["rule_id"] = "unknown_rule"
                else:
                    doc["evidence"].append(dict(doc["evidence"][0], id="extra"))
                with self.assertRaises(QaResultContractError):
                    validate_qa_result(doc, self.result_schema)

    def test_rejects_fake_quality_or_unit_conflicts(self):
        _, original = self.convert({"x.py": "def x(): pass\n"})
        for change in ("fake_review", "invented_fail", "not_evaluated_as_pass",
                       "unit", "unsupported", "extra_principle", "nonfinite"):
            with self.subTest(change=change):
                doc = deepcopy(original)
                if change == "fake_review":
                    doc["verdict"]["status"] = "REVIEW_REQUIRED"
                elif change == "invented_fail":
                    doc["rules"][0]["verdict"] = "FAIL"
                    doc["verdict"]["status"] = "FAIL"
                elif change == "not_evaluated_as_pass":
                    doc["rules"][0]["verdict"] = "NOT_EVALUATED"
                elif change == "unit":
                    doc["evidence"][0]["metric"]["unit"] = "millisecond"
                elif change == "unsupported":
                    doc["unsupported_rules"].pop()
                elif change == "extra_principle":
                    doc["rules"][0]["principle"] = "P9"
                else:
                    doc["evidence"][0]["metric"]["value"] = float("nan")
                with self.assertRaises(QaResultContractError):
                    validate_qa_result(doc, self.result_schema)

    def test_invalid_source_location_and_coverage_fail_closed(self):
        _, original = self.convert({"x.py": "def x(): pass\n"})
        for change in ("path", "line", "overlap", "coverage_status", "completeness"):
            with self.subTest(change=change):
                doc = deepcopy(original)
                if change == "path":
                    doc["evidence"][0]["location"]["path"] = "../escape.py"
                elif change == "line":
                    doc["evidence"][0]["location"]["end_line"] = 0
                elif change == "overlap":
                    doc["coverage"]["unprocessed"].append(
                        {"path": "x.py", "reason": "synthetic"}
                    )
                elif change == "coverage_status":
                    doc["coverage"]["status"] = "none"
                else:
                    doc["analysis"]["status"] = "NONE"
                with self.assertRaises(QaResultContractError):
                    validate_qa_result(doc, self.result_schema)

    def test_profile_fingerprint_changes_with_threshold(self):
        _, baseline = self.convert({"x.py": "def f(): pass\n"})
        _, changed = self.convert({"x.py": "def f(): pass\n"},
                                  profile={**self.profile, "max_call_sites": 2})
        self.assertEqual(baseline["profile"]["id"], changed["profile"]["id"])
        self.assertNotEqual(baseline["profile"]["fingerprint"],
                            changed["profile"]["fingerprint"])

    def test_opt_in_converter_leaves_old_report_intact(self):
        analysis, qa = self.convert({"x.py": "def f(): pass\n"})
        old = analysis.to_document()
        self.assertIn("quality", old)
        self.assertIn("graph", old)
        self.assertNotIn("schema_version", old)
        self.assertEqual(old["quality"]["status"], qa["verdict"]["status"])
        self.assertEqual(old, analysis.to_document())

    def test_identical_sources_and_mapping_order_produce_stable_qa(self):
        a = {"z.py": "def z(): pass\n", "a.py": "def a(): pass\n"}
        b = dict(reversed(list(a.items())))
        _, first = self.convert(a)
        _, second = self.convert(b)
        self.assertEqual(canonical_qa_json(first), canonical_qa_json(second))

    def _delta(self, baseline, candidate):
        return compare_quality_delta(
            baseline, candidate,
            result_schema=self.result_schema, delta_schema=self.delta_schema,
        )

    def test_quality_delta_reports_descriptive_review_count_only(self):
        profile = {**self.profile, "max_function_lines": 2}
        _, base = self.convert({"x.py": "def f(): pass\n"},
                               snapshot="old", profile=profile)
        _, candidate = self.convert({"x.py": "def f():\n    a = 1\n    return a\n"},
                                   snapshot="new", profile=profile)
        delta = self._delta(base, candidate)
        self.assertEqual(delta["interpretation"], "descriptive_review_counts_only")
        self.assertEqual(delta["baseline_snapshot_id"], "old")
        self.assertEqual(delta["candidate_snapshot_id"], "new")
        changes = {x["rule_id"]: x["review_count_delta"] for x in delta["rule_deltas"]}
        self.assertEqual(changes, {
            "function_span_review": 1,
            "outgoing_call_sites_review": 0,
        })
        self.assertEqual(canonical_qa_json(delta), canonical_qa_json(self._delta(base, candidate)))

    def test_quality_delta_rejects_incomparable_snapshots(self):
        _, base = self.convert({"x.py": "def f(): pass\n"}, snapshot="old")
        _, other = self.convert({"x.py": "def f(): pass\n"}, snapshot="new")
        alterations = ("same_snapshot", "engine", "profile", "metric", "unit",
                       "rule_version", "paths", "partial", "limited", "not_evaluated")
        for alteration in alterations:
            with self.subTest(alteration=alteration):
                doc = deepcopy(other)
                if alteration == "same_snapshot":
                    doc["snapshot"]["id"] = "old"
                elif alteration == "engine":
                    doc["engine"]["version"] = "0.2"
                elif alteration == "profile":
                    doc["profile"]["fingerprint"] = "b" * 64
                elif alteration == "metric":
                    doc["rules"][0]["metric"]["name"] = "another_metric"
                    doc["evidence"][0]["metric"]["name"] = "another_metric"
                elif alteration == "unit":
                    doc["rules"][0]["metric"]["unit"] = "other_unit"
                    doc["evidence"][0]["metric"]["unit"] = "other_unit"
                elif alteration == "rule_version":
                    doc["rules"][0]["version"] = "0.2"
                elif alteration == "paths":
                    doc["coverage"]["analyzed_paths"].append("another.py")
                elif alteration == "partial":
                    doc["coverage"]["status"] = "partial"
                    doc["coverage"]["unprocessed"].append({"path": "broken.py", "reason": "syntax_error"})
                    doc["analysis"]["status"] = "LIMITED"
                    doc["analysis"]["limitations"] = ["incomplete_source_coverage"]
                elif alteration == "limited":
                    doc["analysis"]["status"] = "LIMITED"
                    doc["analysis"]["limitations"] = ["unresolved_relationships"]
                else:
                    doc["rules"][0]["verdict"] = "NOT_EVALUATED"
                    doc["rules"][0]["limitations"] = ["unavailable_feature"]
                    doc["verdict"]["status"] = "NOT_EVALUATED"
                with self.assertRaises(QaResultContractError):
                    self._delta(base, doc)

    def test_converter_fails_closed_on_stale_profile_or_ungrounded_finding(self):
        analysis, _ = self.convert({"x.py": "def f(): pass\n"})
        with self.assertRaises(QaResultContractError):
            mechanical_to_qa_result(
                analysis.graph, analysis.quality,
                MechanicalProfile(profile_id="wrong", max_function_lines=80, max_call_sites=12),
                schema=self.result_schema,
            )
        graph = analysis.graph.to_document()
        next(node for node in graph["nodes"] if node["kind"] == "function").pop("location")
        incomplete = parse_graph(graph, self.ccg)
        # A report from a different graph cannot silently certify that location.
        with self.assertRaises(QaResultContractError):
            mechanical_to_qa_result(
                incomplete, analysis.quality,
                MechanicalProfile.from_mapping(self.profile),
                schema=self.result_schema,
            )


if __name__ == "__main__":
    unittest.main()
