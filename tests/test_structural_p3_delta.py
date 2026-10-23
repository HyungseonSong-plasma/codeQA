"""#54: source-scope P3 deltas survive helper extraction without P8 overclaims."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator

from codeqa.adapters import adapt_python_sources
from codeqa.adapters.python_p3_witness import extract_python_p3_call_evidence
from codeqa.evaluation.mechanical import MechanicalProfile, evaluate_mechanical
from codeqa.evaluation.extraction_aware_p3 import (
    ExtractionSpec, ExtractionP3Profile, compare_extraction_aware_p3,
)
from codeqa.evaluation.structural_p3_delta import (
    StructuralP3DeltaError, structural_p3_delta,
)
from codeqa.infrastructure.resources import ResourceRegistry


ROOT=Path(__file__).resolve().parents[1]
TARGET="physics_harness/analysis/field_comparison.py"
REPO="HyungseonSong-plasma/moose-test-repo"
SHAS={
    "base":"69be07aab3e5815a1670f7308deb6caf6b49bc79",
    "blind":"9343dfd8a62f51886b1bf80e73f9887076fcd8d9",
    "guided":"d8e8d5e2d5154d907953699644263b1dba681be6",
}


class StructuralDeltaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        resources=ResourceRegistry(ROOT)
        cls.schema=resources.load_json("structural_p3_delta_schema")
        cls.ccg=resources.load_json("ccg_schema")
        cls.mp=MechanicalProfile.from_mapping(resources.load_json("mechanical_profile"))
        cls.ep=ExtractionP3Profile.from_mapping(resources.load_json("extraction_p3_profile"))
        Draft202012Validator.check_schema(cls.schema)

    def arm(self,label,extra=None):
        sources={TARGET:(ROOT/f"fixtures/moose-p3-refactor/{label}.py.txt").read_text()}
        if extra:
            sources.update(extra)
        graph=adapt_python_sources(sources,snapshot_id=f"git:{REPO}@{SHAS[label]}",schema=self.ccg)
        mechanical=evaluate_mechanical(graph,self.mp)
        return graph,mechanical,sources,extract_python_p3_call_evidence(sources)

    def compare(self,before,after,*,spec):
        a,am,src_a,w_a=before
        b,bm,src_b,w_b=after
        return compare_extraction_aware_p3(
            a,am,src_a,w_a,b,bm,src_b,w_b,
            spec=spec,profile=self.ep,mechanical_profile=self.mp,
        )

    def test_real_base_guided_static_counts_not_quality_verdict(self):
        comparison=self.compare(self.arm("base"),self.arm("guided"),spec=ExtractionSpec(
            TARGET,"compare_named_scalars","compare_named_scalars",
            after_helpers=("_compare_scalar_row",),
        ))
        self.assertEqual(comparison.status,"REVIEW_TRIGGER_REDISTRIBUTION")
        report=structural_p3_delta(comparison,schema=self.schema)
        self.assertEqual(report.status,"COMPARABLE_STATIC_COUNTS")
        self.assertEqual(report.function_counts[1]-report.function_counts[0],1)
        values={m.metric:(m.baseline,m.candidate,m.delta) for m in report.counts}
        self.assertEqual(values["declared_parent_helper_ast_calls"],(19,20,1))
        self.assertEqual(values["selected_p3_review_trigger_count"],(1,0,-1))
        self.assertEqual(values["selected_ast_call_sites"][2],1)
        self.assertIn("unresolved_static_call_targets",report.analysis_limitations)
        self.assertIn("NOT_PROVEN",report.interpretation)

    def test_real_blind_static_counts_and_review_signal(self):
        evidence=self.compare(self.arm("base"),self.arm("blind"),spec=ExtractionSpec(
            TARGET,"compare_named_scalars","compare_named_scalars",
            after_helpers=("_require_finite_nonnegative_tolerance",),
        ))
        report=structural_p3_delta(evidence,schema=self.schema)
        metrics={x.metric:x.delta for x in report.counts}
        self.assertEqual(metrics["declared_parent_helper_ast_calls"],0)
        self.assertEqual(metrics["selected_ast_call_sites"],0)
        self.assertEqual(metrics["selected_p3_review_trigger_count"],0)

    def test_partial_source_coverage_cannot_claim_comparable(self):
        a=self.arm("base",{"broken.py":"def ("})
        b=self.arm("guided",{"broken.py":"def ("})
        evidence=self.compare(a,b,spec=ExtractionSpec(
            TARGET,"compare_named_scalars","compare_named_scalars",
            after_helpers=("_compare_scalar_row",),
        ))
        result=structural_p3_delta(evidence,schema=self.schema)
        self.assertEqual(result.status,"NOT_COMPARABLE")
        self.assertEqual(result.counts,())
        self.assertIn("incomplete_selected_source_coverage",result.analysis_limitations)

    def test_unchanged_source_counts_do_not_claim_improvement(self):
        source="def main():\n    one()\n    two()\n"
        a={"a.py":source}
        base=adapt_python_sources(a,snapshot_id="git:owner/repo@"+"a"*40,schema=self.ccg)
        b=adapt_python_sources(a,snapshot_id="git:owner/repo@"+"b"*40,schema=self.ccg)
        cmp=compare_extraction_aware_p3(
            base,evaluate_mechanical(base,self.mp),a,extract_python_p3_call_evidence(a),
            b,evaluate_mechanical(b,self.mp),a,extract_python_p3_call_evidence(a),
            spec=ExtractionSpec("a.py","main","main"),
            profile=self.ep,mechanical_profile=self.mp,
        )
        result=structural_p3_delta(cmp,schema=self.schema)
        self.assertEqual(result.status,"NOT_COMPARABLE")
        self.assertIn("unchanged_selected_source_bytes",result.analysis_limitations)

    def test_mutated_evidence_and_cross_repo_rejected(self):
        cmp=self.compare(self.arm("base"),self.arm("guided"),spec=ExtractionSpec(
            TARGET,"compare_named_scalars","compare_named_scalars",
            after_helpers=("_compare_scalar_row",),
        ))
        bad=[
            replace(cmp,selected_scope_call_delta=0),
            replace(cmp,cohort_call_delta=0),
            replace(cmp,after=replace(cmp.after,parent_review=True)),
            replace(cmp,after=replace(cmp.after,selected_scope_calls=1)),
            replace(cmp,after=replace(cmp.after,snapshot_id="git:other/repo@"+"b"*40)),
            replace(cmp,before=replace(cmp.before,function_count=0)),
            replace(cmp,profile_id="invented"),
        ]
        for evidence in bad:
            with self.subTest(evidence=evidence),self.assertRaises(StructuralP3DeltaError):
                structural_p3_delta(evidence,schema=self.schema)

    def test_unchanged_v02_quality_delta_contract_and_deterministic_report(self):
        r=ResourceRegistry(ROOT)
        self.assertEqual(r.load_json("qa_delta_v02_schema")["$id"],
                         "urn:codeqa:qa:delta:v0.2")
        cmp=self.compare(self.arm("base"),self.arm("guided"),spec=ExtractionSpec(
            TARGET,"compare_named_scalars","compare_named_scalars",
            after_helpers=("_compare_scalar_row",),
        ))
        self.assertEqual(structural_p3_delta(cmp,schema=self.schema).to_document(),
                         structural_p3_delta(cmp,schema=self.schema).to_document())


if __name__=="__main__":
    unittest.main()
