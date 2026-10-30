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


def lexical_census(responsibility):
    edges = responsibility["edges"]
    records = []
    for edge in edges:
        witnesses = edge["import_witnesses"]
        records.append({
            "source_path": edge["source_path"],
            "target_path": edge["target_path"],
            "source_sha256": witnesses[0]["source_sha256"],
            "import_lines": sorted({w["line"] for w in witnesses}),
            "candidate_bindings": [{
                "line": witnesses[0]["line"], "name": "imported_name",
                "lexical_load_count": 2, "load_witnesses": [],
                "status": "NAME_LOAD_CANDIDATE",
            }],
            "has_name_load_candidate": True,
            "binding_target_attribution": "LINE_COLOCATED_UNVERIFIED",
            "import_execution": "NOT_EVALUATED",
            "semantic_ownership": "NOT_EVALUATED",
        })
    report = {
        "schema_version": "0.1",
        "source_identity": {
            "snapshot_sha": responsibility["source_identity"]["snapshot_sha"],
            "inventory_id": responsibility["source_identity"]["inventory_id"],
            "responsibility_id": responsibility["responsibility_id"],
        },
        "responsibility_id": responsibility["responsibility_id"],
        "static_pairs": len(edges),
        "pairs_with_name_load_candidates": len(edges),
        "pairs_without_name_load_candidates": 0,
        "records": records,
        "import_execution": "NOT_EVALUATED",
        "semantic_ownership": "NOT_EVALUATED",
        "decision": "NOT_EVALUATED",
    }
    seal(report, "usage_id")
    return report


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

    def test_lexical_census_join_preserves_unknowns_and_denominator(self):
        r, t, ctx, d = inputs()
        lexical = lexical_census(r)
        result = build_edge_review_worklist(
            r, t, ctx, d, lexical_usage=lexical,
        )
        self.assertEqual(result["source_identity"]["usage_id"], lexical["usage_id"])
        self.assertEqual(result["pairs_with_lexical_name_load_candidates"], 3)
        self.assertEqual(result["pairs_without_lexical_name_load_candidates"], 0)
        self.assertEqual(sum(x["lexical_name_load_candidates"] for x in result["edges"]), 6)
        self.assertTrue(all(x["lexical_binding_target_attribution"]
                            == "LINE_COLOCATED_UNVERIFIED" and
                            x["lexical_import_execution"] == "NOT_EVALUATED"
                            for x in result["edges"]))
        self.assertIn("lexical-name-loads=2",
                      render_edge_review_worklist_markdown(result))
        self.assertEqual(result["decision"], "NOT_EVALUATED")

    def test_lexical_census_rejects_stale_or_missing_pairs(self):
        r, t, ctx, d = inputs()
        stale = lexical_census(r)
        stale["source_identity"]["snapshot_sha"] = "f" * 40
        seal(stale, "usage_id")
        with self.assertRaises(EdgeReviewWorklistError):
            build_edge_review_worklist(r, t, ctx, d, lexical_usage=stale)
        missing = lexical_census(r)
        missing["records"].pop()
        seal(missing, "usage_id")
        with self.assertRaises(EdgeReviewWorklistError):
            build_edge_review_worklist(r, t, ctx, d, lexical_usage=missing)

    def test_lexical_census_rejects_forged_witness_or_denominator(self):
        r, t, ctx, d = inputs()
        forged = lexical_census(r)
        forged["records"][0]["source_sha256"] = "0" * 64
        seal(forged, "usage_id")
        with self.assertRaises(EdgeReviewWorklistError):
            build_edge_review_worklist(r, t, ctx, d, lexical_usage=forged)
        forged = lexical_census(r)
        forged["pairs_with_name_load_candidates"] -= 1
        seal(forged, "usage_id")
        with self.assertRaises(EdgeReviewWorklistError):
            build_edge_review_worklist(r, t, ctx, d, lexical_usage=forged)

    def test_empty_import_witness_is_domain_error_not_index_error(self):
        r, t, ctx, d = inputs()
        broken = deepcopy(r)
        broken["edges"][0]["import_witnesses"] = []
        seal(broken, "responsibility_id")
        with self.assertRaises(EdgeReviewWorklistError):
            build_edge_review_worklist(broken, t, ctx, d)

    def test_zero_pair_lexical_join_remains_healthy(self):
        r, t, ctx, d = inputs(edges=())
        result = build_edge_review_worklist(
            r, t, ctx, d, lexical_usage=lexical_census(r),
        )
        self.assertEqual(result["edges"], [])
        self.assertEqual(result["pairs_with_lexical_name_load_candidates"], 0)
        self.assertEqual(result["decision"], "NOT_EVALUATED")

    def test_syntax_context_join_remains_non_semantic(self):
        r, t, ctx, d = inputs()
        lexical = lexical_census(r)
        counts = {
            "ANNOTATION_SYNTAX": 1,
            "CALL_TARGET_SYNTAX": 1,
            "ATTRIBUTE_ACCESS_SYNTAX": 0,
            "OTHER_LOAD_SYNTAX": 0,
        }
        for row in lexical["records"]:
            row["candidate_bindings"][0]["syntax_context_counts"] = counts.copy()
            row["candidate_bindings"][0]["conditional_load_candidates"] = 1
            row["syntax_context_counts"] = counts.copy()
            row["conditional_load_candidates"] = 1
        lexical["syntax_context_counts"] = {
            k: v * len(lexical["records"]) for k, v in counts.items()
        }
        lexical["conditional_load_candidates"] = len(lexical["records"])
        seal(lexical, "usage_id")
        result = build_edge_review_worklist(r, t, ctx, d, lexical_usage=lexical)
        self.assertEqual(result["lexical_syntax_context_counts"]["ANNOTATION_SYNTAX"], 3)
        self.assertEqual(result["lexical_conditional_load_candidates"], 3)
        self.assertIn("syntax=1/1/0/0; conditional=1",
                      render_edge_review_worklist_markdown(result))
        self.assertEqual(result["semantic_ownership"], "NOT_EVALUATED")
        self.assertEqual(result["recommended_action"], "NO_AUTOMATIC_MOVE")

        lexical["records"][0]["syntax_context_counts"]["CALL_TARGET_SYNTAX"] = 0
        seal(lexical, "usage_id")
        with self.assertRaises(EdgeReviewWorklistError):
            build_edge_review_worklist(r, t, ctx, d, lexical_usage=lexical)

    def test_syntax_modes_prioritize_source_review_without_semantic_keep(self):
        r, t, ctx, d = inputs()
        lexical = lexical_census(r)
        modes = ("ANNOTATION_SYNTAX", "CALL_TARGET_SYNTAX", None)
        kinds = ("ANNOTATION_SYNTAX", "CALL_TARGET_SYNTAX",
                 "ATTRIBUTE_ACCESS_SYNTAX", "OTHER_LOAD_SYNTAX")
        for row, kind in zip(lexical["records"], modes):
            binding = row["candidate_bindings"][0]
            binding["lexical_load_count"] = 2 if kind else 0
            binding["status"] = ("NAME_LOAD_CANDIDATE" if kind
                                 else "NO_NAME_LOAD_IN_SOURCE")
            binding["syntax_context_counts"] = {
                k: (2 if k == kind else 0) for k in kinds
            }
            binding["conditional_load_candidates"] = 0
            row["syntax_context_counts"] = binding["syntax_context_counts"].copy()
            row["conditional_load_candidates"] = 0
            row["has_name_load_candidate"] = bool(kind)
        lexical["syntax_context_counts"] = {
            k: sum(row["syntax_context_counts"][k] for row in lexical["records"])
            for k in kinds
        }
        lexical["conditional_load_candidates"] = 0
        lexical["pairs_with_name_load_candidates"] = 2
        lexical["pairs_without_name_load_candidates"] = 1
        seal(lexical, "usage_id")
        report = build_edge_review_worklist(r, t, ctx, d, lexical_usage=lexical)
        self.assertEqual(report["lexical_use_mode_counts"], {
            "ANNOTATION_ONLY_SYNTAX": 1,
            "CALL_TARGET_SYNTAX_PRESENT": 1,
            "NO_NAME_LOAD_CANDIDATE": 1,
        })
        self.assertTrue(all(row["semantic_ownership"] == "NOT_EVALUATED"
                            and row["review_focus"] == "UNOBSERVED_IN_BOUNDED_SAMPLE"
                            for row in report["edges"]))
        self.assertIn("use-mode=ANNOTATION_ONLY_SYNTAX",
                      render_edge_review_worklist_markdown(report))
        report["edges"][0]["lexical_use_mode"] = "SEMANTIC_KEEP"
        seal(report, "worklist_id")
        with self.assertRaises(EdgeReviewWorklistError):
            render_edge_review_worklist_markdown(report)

    def test_reject_resealed_lexical_binding_line_and_status_forgeries(self):
        r, t, ctx, d = inputs()
        lexical = lexical_census(r)
        lexical["records"][0]["candidate_bindings"][0]["line"] = 999
        seal(lexical, "usage_id")
        with self.assertRaises(EdgeReviewWorklistError):
            build_edge_review_worklist(r, t, ctx, d, lexical_usage=lexical)
        lexical = lexical_census(r)
        lexical["records"][0]["candidate_bindings"][0]["status"] = "RUNTIME_VERIFIED"
        seal(lexical, "usage_id")
        with self.assertRaises(EdgeReviewWorklistError):
            build_edge_review_worklist(r, t, ctx, d, lexical_usage=lexical)

    def test_reject_resealed_negative_per_binding_syntax_with_valid_totals(self):
        r, t, ctx, d = inputs()
        lexical = lexical_census(r)
        kinds = ("ANNOTATION_SYNTAX", "CALL_TARGET_SYNTAX",
                 "ATTRIBUTE_ACCESS_SYNTAX", "OTHER_LOAD_SYNTAX")
        for row in lexical["records"]:
            binding = row["candidate_bindings"][0]
            binding["syntax_context_counts"] = {
                k: (2 if k == "CALL_TARGET_SYNTAX" else 0) for k in kinds
            }
            binding["conditional_load_candidates"] = 0
            row["syntax_context_counts"] = binding["syntax_context_counts"].copy()
            row["conditional_load_candidates"] = 0
        first = lexical["records"][0]
        first["candidate_bindings"] = [
            {**first["candidate_bindings"][0], "lexical_load_count": 1,
             "syntax_context_counts": {
                 "ANNOTATION_SYNTAX": -1, "CALL_TARGET_SYNTAX": 2,
                 "ATTRIBUTE_ACCESS_SYNTAX": 0, "OTHER_LOAD_SYNTAX": 0,
             }},
            {**first["candidate_bindings"][0], "lexical_load_count": 1,
             "syntax_context_counts": {
                 "ANNOTATION_SYNTAX": 1, "CALL_TARGET_SYNTAX": 0,
                 "ATTRIBUTE_ACCESS_SYNTAX": 0, "OTHER_LOAD_SYNTAX": 0,
             }},
        ]
        lexical["syntax_context_counts"] = {
            k: sum(row["syntax_context_counts"][k] for row in lexical["records"])
            for k in kinds
        }
        lexical["conditional_load_candidates"] = 0
        seal(lexical, "usage_id")
        with self.assertRaises(EdgeReviewWorklistError):
            build_edge_review_worklist(r, t, ctx, d, lexical_usage=lexical)

    def test_renderer_rejects_tampering(self):
        report = build_edge_review_worklist(*inputs())
        report["edges"][0]["semantic_ownership"] = "PASS"
        with self.assertRaises(EdgeReviewWorklistError):
            render_edge_review_worklist_markdown(report)


if __name__ == "__main__":
    unittest.main()
