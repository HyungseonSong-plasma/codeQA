"""Issue #48: P3 threshold redistribution must not imply less coupling.

Three exact production MOOSE files are checked byte-for-byte by separate CI.
This test uses source-only CCG and frozen Mechanical reports; no target code
is imported or executed.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from hashlib import sha1
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator

from codeqa.adapters import adapt_python_sources
from codeqa.adapters.python_p3_witness import extract_python_p3_call_evidence
from codeqa.core import Graph, parse_graph, GraphValidationError
from codeqa.evaluation.extraction_aware_p3 import (
    ExtractionP3Error, ExtractionP3Profile, ExtractionSpec, compare_extraction_aware_p3,
)
from codeqa.evaluation.mechanical import MechanicalProfile, evaluate_mechanical
from codeqa.infrastructure.resources import ResourceRegistry


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = "physics_harness/analysis/field_comparison.py"
SRC_REPO = "HyungseonSong-plasma/moose-test-repo"


class ExtractionAwareP3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reg = ResourceRegistry(ROOT)
        cls.ccg_schema = reg.load_json("ccg_schema")
        cls.mechanical_profile = MechanicalProfile.from_mapping(
            reg.load_json("mechanical_profile"))
        cls.profile = ExtractionP3Profile.from_mapping(
            reg.load_json("extraction_p3_profile"))
        cls.report_schema = reg.load_json("extraction_p3_report_schema")
        Draft202012Validator.check_schema(cls.report_schema)
        manifest = json.loads(
            (ROOT / "fixtures/moose-p3-refactor/provenance.json").read_text()
        )
        cls.manifest = manifest
        cls.arms = {}
        for item in manifest["sources"]:
            binary = (ROOT / item["fixture"]).read_bytes()
            actual = sha1(f"blob {len(binary)}\0".encode("ascii") + binary).hexdigest()
            if actual != item["git_blob_sha"]:
                raise AssertionError("independent pinned source Git blob mismatch")
            text = binary.decode("utf-8")
            cls.arms[item["arm"]] = cls.make_arm(
                {SOURCE_PATH: text}, SRC_REPO, item["commit_sha"],
                cls.ccg_schema, cls.mechanical_profile,
            )

    @staticmethod
    def make_arm(sources, repo, sha, schema, mechanical_profile):
        snapshot = f"git:{repo}@{sha}"
        graph = adapt_python_sources(sources, snapshot_id=snapshot, schema=schema)
        report = evaluate_mechanical(graph, mechanical_profile)
        return graph, report, sources

    def compare(self, baseline, candidate, spec=None, profile=None, mechanical=None):
        a, am, ax = baseline
        b, bm, bx = candidate
        result = compare_extraction_aware_p3(
            a, am, ax, extract_python_p3_call_evidence(ax),
            b, bm, bx, extract_python_p3_call_evidence(bx),
            spec=spec or ExtractionSpec(
                SOURCE_PATH, "compare_named_scalars", "compare_named_scalars",
                after_helpers=("_compare_scalar_row",),
            ),
            profile=profile or self.profile,
            mechanical_profile=mechanical or self.mechanical_profile,
        )
        Draft202012Validator(self.report_schema).validate(result.to_document())
        return result

    def test_source_identity_and_pre_analysis_blind_provenance(self):
        self.assertEqual(self.manifest["source_repository"], SRC_REPO)
        self.assertEqual(len(self.arms), 3)
        expected = {
            "base": "69be07aab3e5815a1670f7308deb6caf6b49bc79",
            "blind": "9343dfd8a62f51886b1bf80e73f9887076fcd8d9",
            "guided": "d8e8d5e2d5154d907953699644263b1dba681be6",
        }
        for label, arm in self.arms.items():
            self.assertEqual(arm[0].snapshot.id, f"git:{SRC_REPO}@{expected[label]}")
        self.assertEqual(self.profile.max_call_sites, self.mechanical_profile.max_call_sites)
        self.assertEqual(self.manifest["observed_p3"]["trigger_threshold_exclusive"], 12)

    def test_real_guided_refactor_is_not_proven_lower_coupling(self):
        data = self.compare(self.arms["base"], self.arms["guided"])
        self.assertEqual(data.status, "REVIEW_TRIGGER_REDISTRIBUTION")
        self.assertEqual((data.before.parent_calls, data.after.parent_calls), (19, 12))
        self.assertEqual(data.after.helpers, (("_compare_scalar_row", 8),))
        self.assertEqual((data.before.cohort_calls, data.after.cohort_calls), (19, 20))
        self.assertEqual(data.cohort_call_delta, 1)
        self.assertEqual(data.parent_call_delta, -7)
        self.assertEqual(data.selected_scope_call_delta, 1)
        self.assertTrue(data.before.parent_review)
        self.assertFalse(data.after.parent_review)
        self.assertEqual(data.selected_scope_review_delta, -1)
        self.assertGreater(data.after.selected_scope_unresolved_calls, 0)
        self.assertIn("unresolved_call_targets_are_not_proven_dependencies", data.limitations)
        self.assertIn("NOT_PROVEN_DEPENDENCY_IMPROVEMENT", data.interpretation)
        self.assertGreaterEqual(len(data.relocated_exact_syntax), 1)
        self.assertTrue(all(item.before_parent == "compare_named_scalars"
                            and item.after_helper == "_compare_scalar_row"
                            for item in data.relocated_exact_syntax))

    def test_real_blind_refactor_did_not_clear_p3_review(self):
        data = self.compare(
            self.arms["base"], self.arms["blind"],
            ExtractionSpec(
                SOURCE_PATH, "compare_named_scalars", "compare_named_scalars",
                after_helpers=("_require_finite_nonnegative_tolerance",),
            ),
        )
        self.assertEqual(data.status, "NO_THRESHOLD_REDISTRIBUTION")
        self.assertEqual((data.before.parent_calls, data.after.parent_calls), (19, 17))
        self.assertEqual(data.after.helpers[0][1], 2)
        self.assertEqual((data.before.cohort_calls, data.after.cohort_calls), (19, 19))
        self.assertEqual(data.selected_scope_call_delta, 0)
        self.assertEqual(data.selected_scope_review_delta, 0)
        self.assertTrue(data.after.parent_review)

    def test_blind_to_guided_explicitly_declared_helper_mapping(self):
        data = self.compare(
            self.arms["blind"], self.arms["guided"],
            ExtractionSpec(SOURCE_PATH, "compare_named_scalars", "compare_named_scalars",
                           before_helpers=("_require_finite_nonnegative_tolerance",),
                           after_helpers=("_compare_scalar_row",)),
        )
        self.assertEqual(data.status, "REVIEW_TRIGGER_REDISTRIBUTION")
        self.assertEqual(data.cohort_call_delta, 1)

    def synthetic(self, before, after, *, path="a.py", max_calls=2,
                  before_other=None, after_other=None):
        profile = MechanicalProfile("codeqa.mechanical.v0.1", 80, max_calls)
        extra_before = {} if before_other is None else before_other
        extra_after = {} if after_other is None else after_other
        a = self.make_arm({path: before, **extra_before}, "owner/repo", "a"*40,
                          self.ccg_schema, profile)
        b = self.make_arm({path: after, **extra_after}, "owner/repo", "b"*40,
                          self.ccg_schema, profile)
        return a, b, profile, ExtractionP3Profile(
            "0.1", "codeqa.p3.extraction.v0.1", "codeqa.mechanical.v0.1", max_calls
        )

    def test_move_same_exact_call_syntax_is_witnessed_not_guessed(self):
        a,b,mp,ep = self.synthetic(
            "def main():\n    alpha()\n    beta()\n    gamma()\n",
            "def main():\n    beta()\n    return helper()\n"
            "def helper():\n    alpha()\n    gamma()\n",
        )
        r = self.compare(a,b,ExtractionSpec("a.py","main","main",after_helpers=("helper",)),ep,mp)
        self.assertEqual(r.status, "REVIEW_TRIGGER_REDISTRIBUTION")
        self.assertEqual(r.parent_call_delta, -1)
        self.assertEqual(r.cohort_call_delta, 1)
        self.assertEqual({w.expression for w in r.relocated_exact_syntax},
                         {"alpha()", "gamma()"})
        self.assertEqual({w.before_line for w in r.relocated_exact_syntax}, {2,4})
        self.assertEqual({w.after_line for w in r.relocated_exact_syntax}, {5,6})

    def test_nested_async_calls_are_attributed_to_actual_owners(self):
        original = ("async def main():\n"
                    "    alpha()\n    beta()\n    gamma()\n"
                    "    async def inside():\n        nested()\n")
        edited = ("async def main():\n"
                  "    alpha()\n    return helper()\n"
                  "async def helper():\n    beta()\n    gamma()\n"
                  "    async def inside():\n        nested()\n")
        a,b,mp,ep = self.synthetic(original,edited)
        r=self.compare(a,b,ExtractionSpec("a.py","main","main",after_helpers=("helper",)),ep,mp)
        self.assertEqual((r.before.cohort_calls,r.after.cohort_calls),(3,4))
        self.assertEqual(r.status,"REVIEW_TRIGGER_REDISTRIBUTION")
        self.assertEqual(r.after.selected_scope_calls,5) # nested() owned by helper.inside

    def test_function_renames_require_explicit_owner_not_inferred(self):
        a,b,mp,ep=self.synthetic(
            "def old():\n    alpha()\n    beta()\n    gamma()\n",
            "def renamed():\n    alpha()\n    beta()\n    gamma()\n")
        with self.assertRaises(ExtractionP3Error):
            self.compare(a,b,ExtractionSpec("a.py","old","old"),ep,mp)
        r=self.compare(a,b,ExtractionSpec("a.py","old","renamed"),ep,mp)
        self.assertEqual(r.status,"NO_THRESHOLD_REDISTRIBUTION")
        self.assertEqual(r.selected_scope_call_delta,0)

    def test_unchanged_source_different_commit_does_not_claim_improvement(self):
        source="def main():\n    one()\n    two()\n    three()\n"
        a,b,mp,ep=self.synthetic(source,source)
        r=self.compare(a,b,ExtractionSpec("a.py","main","main"),ep,mp)
        self.assertEqual(r.status,"UNCHANGED_SOURCE")
        self.assertEqual(r.parent_call_delta,0)

    def test_parse_errors_block_a_winning_signal(self):
        original=("def main():\n    a()\n    b()\n    c()\n")
        edited=("def main():\n    return helper()\n"
                "def helper():\n    a()\n    b()\n    c()\n")
        a,b,mp,ep=self.synthetic(original,edited,before_other={"bad.py":"def ("},
                                   after_other={"bad.py":"def ("})
        r=self.compare(a,b,ExtractionSpec("a.py","main","main",after_helpers=("helper",)),ep,mp)
        self.assertEqual(r.status,"INSUFFICIENT_COVERAGE")
        self.assertIn("incomplete_selected_source_coverage",r.limitations)
        self.assertEqual(r.before.coverage_status,"partial")

    def test_outside_scope_imports_and_unknown_calls_remain_uncertain(self):
        a,b,mp,ep=self.synthetic(
            "import foreign_package\n"
            "def main():\n    foreign_package.f()\n    foreign_package.f()\n    foreign_package.f()\n",
            "import foreign_package\n"
            "def main():\n    return helper()\n"
            "def helper():\n    foreign_package.f()\n    foreign_package.f()\n    foreign_package.f()\n",
        )
        r=self.compare(a,b,ExtractionSpec("a.py","main","main",after_helpers=("helper",)),ep,mp)
        self.assertEqual(r.status,"REVIEW_TRIGGER_REDISTRIBUTION")
        self.assertGreater(r.before.selected_scope_unresolved_calls,0)
        self.assertIn("unresolved_call_targets_are_not_proven_dependencies",r.limitations)

    def test_changed_selected_paths_and_unscoped_edits_are_rejected(self):
        a,b,mp,ep=self.synthetic(
            "def main():\n    alpha()\n    beta()\n    gamma()\n",
            "def main():\n    return helper()\n"
            "def helper():\n    alpha()\n    beta()\n    gamma()\n",
            before_other={"other.py":"def g(): pass\n"},
            after_other={"other.py":"def g(): return 1\n"},
        )
        with self.assertRaises(ExtractionP3Error):
            self.compare(a,b,ExtractionSpec("a.py","main","main",after_helpers=("helper",)),ep,mp)
        other=(b[0],b[1],{"a.py":b[2]["a.py"]})
        with self.assertRaises(ExtractionP3Error):
            self.compare(a,other,ExtractionSpec("a.py","main","main",after_helpers=("helper",)),ep,mp)

    def test_threshold_and_engine_profile_drift_fail_closed(self):
        a,b,mp,ep=self.synthetic(
            "def main():\n    alpha()\n    beta()\n    gamma()\n",
            "def main():\n    return helper()\n"
            "def helper():\n    alpha()\n    beta()\n    gamma()\n")
        spec=ExtractionSpec("a.py","main","main",after_helpers=("helper",))
        bad = ExtractionP3Profile("0.1",ep.profile_id,ep.mechanical_profile_id,3)
        with self.assertRaises(ExtractionP3Error):
            self.compare(a,b,spec,bad,mp)
        wrong = replace(b[1], profile_id="incorrect-profile")
        with self.assertRaises(ExtractionP3Error):
            self.compare(a,(b[0],wrong,b[2]),spec,ep,mp)
        for patch in ({"max_call_sites":True},{"schema_version":"0.2"},
                      {"profile_id":"unexpected"},{"added":1}):
            with self.subTest(patch=patch), self.assertRaises(ExtractionP3Error):
                ExtractionP3Profile.from_mapping({
                    "schema_version":"0.1","profile_id":ep.profile_id,
                    "mechanical_profile_id":ep.mechanical_profile_id,
                    "max_call_sites":2,**patch,
                })

    def test_ungrounded_edge_source_or_fabricated_call_target_rejected(self):
        a,b,mp,ep=self.synthetic(
            "def main():\n    alpha()\n    beta()\n    gamma()\n",
            "def main():\n    return helper()\n"
            "def helper():\n    alpha()\n    beta()\n    gamma()\n")
        spec=ExtractionSpec("a.py","main","main",after_helpers=("helper",))
        doc=deepcopy(b[0].to_document())
        call=next(e for e in doc["edges"] if e["kind"]=="calls")
        call["location"]["start_line"]=99
        graph=Graph.from_document(doc)
        with self.assertRaises(ExtractionP3Error):
            self.compare(a,(graph,b[1],b[2]),spec,ep,mp)
        doc=deepcopy(b[0].to_document())
        call=next(e for e in doc["edges"] if e["kind"]=="calls")
        call.pop("target_hint",None)
        call["resolution"]="resolved"
        call["target"]="invented:external_target"
        with self.assertRaises(GraphValidationError):
            parse_graph(doc,self.ccg_schema)

    def test_modified_source_cannot_reuse_old_pinned_call_evidence(self):
        a,b,mp,ep=self.synthetic(
            "def main():\n    a()\n    b()\n    c()\n",
            "def main():\n    return helper()\n"
            "def helper():\n    a()\n    b()\n    c()\n")
        original_evidence = extract_python_p3_call_evidence(b[2])
        altered = {"a.py": b[2]["a.py"].replace("    b()", "    x()")}
        with self.assertRaises(ExtractionP3Error):
            compare_extraction_aware_p3(
                a[0], a[1], a[2], extract_python_p3_call_evidence(a[2]),
                b[0], b[1], altered, original_evidence,
                spec=ExtractionSpec("a.py", "main", "main", after_helpers=("helper",)),
                profile=ep, mechanical_profile=mp,
            )

    def test_source_bytes_tampering_is_detected_against_ast_call_locations(self):
        a,b,mp,ep=self.synthetic(
            "def main():\n    a()\n    b()\n    c()\n",
            "def main():\n    return helper()\n"
            "def helper():\n    a()\n    b()\n    c()\n")
        edited=replace(b[1],call_metrics=tuple(replace(x,call_sites=1) for x in b[1].call_metrics))
        with self.assertRaises(ExtractionP3Error):
            self.compare(a,(b[0],edited,b[2]),
                         ExtractionSpec("a.py","main","main",after_helpers=("helper",)),ep,mp)


if __name__=="__main__":
    unittest.main()
