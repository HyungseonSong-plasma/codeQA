"""#166/#184: every measured boundary pair gets one conservative review row."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import unittest

from codeqa.evaluation.architecture.bounded_disposition import assess_bounded_disposition
from codeqa.evaluation.architecture.edge_review_worklist import (
    EdgeReviewWorklistError, build_edge_review_worklist,
    render_edge_review_worklist_markdown,
)
from codeqa.evaluation.architecture.test_behavior_candidates import census_test_behavior_candidates
from test_architecture_bounded_disposition_v01 import fixture


def seal(report, key):
    report[key] = sha256(json.dumps(
        {k: v for k, v in report.items() if k != key},
        sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()


def inputs(*, edges=None, collision=False):
    inv, triage, responsibility, assessment = fixture(edges=edges, collision=collision)
    tests = census_test_behavior_candidates(inv, responsibility, {})
    head = inv["source_identity"]["repository_commit_sha"]
    context = {
        "schema_version": "0.1",
        "source_identity": {
            "snapshot_sha": head,
            "inventory_id": inv["inventory_id"],
            "responsibility_id": responsibility["responsibility_id"],
        },
        "static_pairs": len(responsibility["edges"]),
        "direct_call_observed_pairs": 0,
        "direct_python_calls": 0,
        "sampled_call_witnesses": 0,
        "edges": [{
            "source_path": e["source_path"],
            "target_path": e["target_path"],
            "source_sha256": e["import_witnesses"][0]["source_sha256"],
            "source_role": e["source_role"],
            "target_role": e["target_role"],
            "declared_policy_direction": e["declared_policy_direction"],
            "direct_python_calls": 0,
            "sampled_call_witnesses": [],
            "witnesses_truncated": False,
            "semantic_ownership": "NOT_EVALUATED",
        } for e in responsibility["edges"]],
        "semantic_ownership": "NOT_EVALUATED",
        "intentional_orchestration": "NOT_EVALUATED",
        "decision": "NOT_EVALUATED",
    }
    seal(context, "context_id")
    disposition = assess_bounded_disposition(inv, triage, responsibility, assessment)
    return responsibility, tests, context, disposition


class EdgeReviewWorklistTests(unittest.TestCase):
    def test_all_measured_pairs_are_present_without_semantic_keep(self):
        reports = inputs()
        result = build_edge_review_worklist(*reports)
        self.assertEqual(result["observed_cross_role_pairs"], 3)
        self.assertEqual(len(result["edges"]), 3)
        self.assertEqual(result["review_focus_counts"], {"UNOBSERVED_IN_BOUNDED_SAMPLE": 3})
        self.assertEqual(result["decision"], "NOT_EVALUATED")
        self.assertEqual(result["recommended_action"], "NO_AUTOMATIC_MOVE")
        self.assertTrue(all(row["import_witnesses"] and
                            row["semantic_ownership"] == "NOT_EVALUATED" and
                            row["behavioral_edge_coverage"] == "NOT_EVALUATED"
                            for row in result["edges"]))
        self.assertEqual(result, build_edge_review_worklist(*reports))
        text = render_edge_review_worklist_markdown(result)
        self.assertIn("src/orchard/sky/view.py", text)
        self.assertIn("NOT_EVALUATED", text)

    def test_observed_call_and_alias_warning_prioritize_review_not_proof(self):
        r, t, ctx, d = inputs()
        witness = {
            "test_id": "suite.test", "caller_line": 4,
            "function_qualname": "Runner.execute",
            "enclosing_statement_kind": "Return",
            "target_import_alias_call_candidates": [{"callee_expression": "work.run"}],
            "target_import_alias_parameter_shadowing_warnings": ["work"],
            "target_import_alias_local_binding_warnings": [],
            "unmatched_indirect_receiver_call_candidates": [],
        }
        ctx["edges"][0]["direct_python_calls"] = 1
        ctx["edges"][0]["sampled_call_witnesses"] = [witness]
        ctx["direct_python_calls"] = 1
        ctx["direct_call_observed_pairs"] = 1
        ctx["sampled_call_witnesses"] = 1
        seal(ctx, "context_id")
        result = build_edge_review_worklist(r, t, ctx, d)
        row = next(row for row in result["edges"]
                   if row["source_path"] == ctx["edges"][0]["source_path"]
                   and row["target_path"] == ctx["edges"][0]["target_path"])
        self.assertEqual(row["review_focus"], "ALIAS_BINDING_REVIEW")
        self.assertEqual(row["sampled_shadowing_warnings"], 1)
        self.assertEqual(row["direct_python_calls"], 1)
        self.assertEqual(row["semantic_ownership"], "NOT_EVALUATED")

    def test_test_assertion_candidate_is_not_behavioral_coverage(self):
        r, t, ctx, d = inputs()
        t["edges"][0]["candidate_test_paths"] = [{
            "test_path": "tests/test_view.py", "parse_status": "PARSED",
            "candidate_tests": [{
                "test_function": "test_view",
                "assertion_operand_pairs": [{"call_line": 4, "assertion_line": 4}],
            }],
        }]
        t["candidate_test_functions_across_edges"] = 1
        t["assertion_operand_candidate_pairs_across_edges"] = 1
        seal(t, "candidate_id")
        result = build_edge_review_worklist(r, t, ctx, d)
        self.assertEqual(result["edges"][0]["candidate_test_functions"], 1)
        self.assertEqual(result["edges"][0]["assertion_operand_candidates"], 1)
        self.assertEqual(result["edges"][0]["behavioral_edge_coverage"], "NOT_EVALUATED")

    def test_collision_is_not_a_global_keep(self):
        report = build_edge_review_worklist(*inputs(collision=True))
        self.assertTrue(report["edges"])
        self.assertTrue(all(row["signal_disposition"] == "INSUFFICIENT_EVIDENCE"
                            for row in report["edges"]))
        self.assertEqual(report["decision"], "NOT_EVALUATED")

    def test_zero_signal_has_no_forced_review_rows(self):
        report = build_edge_review_worklist(*inputs(edges=()))
        self.assertEqual(report["edges"], [])
        self.assertEqual(report["review_focus_counts"], {})
        self.assertEqual(report["observed_cross_role_pairs"], 0)

    def test_reject_resealed_stale_source_and_missing_pair(self):
        r, t, ctx, d = inputs()
        stale = deepcopy(ctx)
        stale["source_identity"]["snapshot_sha"] = "f" * 40
        seal(stale, "context_id")
        with self.assertRaises(EdgeReviewWorklistError):
            build_edge_review_worklist(r, t, stale, d)
        missing = deepcopy(ctx)
        missing["edges"].pop()
        missing["static_pairs"] -= 1
        seal(missing, "context_id")
        with self.assertRaises(EdgeReviewWorklistError):
            build_edge_review_worklist(r, t, missing, d)

    def test_reject_resealed_forged_witness_or_denominator(self):
        r, t, ctx, d = inputs()
        changed = deepcopy(r)
        changed["edges"][0]["import_witnesses"][0]["line"] = 0
        seal(changed, "responsibility_id")
        with self.assertRaises(EdgeReviewWorklistError):
            build_edge_review_worklist(changed, t, ctx, d)
        changed = deepcopy(ctx)
        changed["direct_python_calls"] = 1
        seal(changed, "context_id")
        with self.assertRaises(EdgeReviewWorklistError):
            build_edge_review_worklist(r, t, changed, d)

    def test_renderer_rejects_tampering(self):
        report = build_edge_review_worklist(*inputs())
        report["edges"][0]["semantic_ownership"] = "PASS"
        with self.assertRaises(EdgeReviewWorklistError):
            render_edge_review_worklist_markdown(report)


if __name__ == "__main__":
    unittest.main()
