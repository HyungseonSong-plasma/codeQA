"""Syntactic context for Mechanical P3 without suppressing findings."""
from __future__ import annotations

from pathlib import Path
import unittest

from codeqa.infrastructure.resources import ResourceRegistry
from codeqa.pipeline.python import analyze_python


ROOT = Path(__file__).resolve().parents[1]


class ContextualCallReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reg = ResourceRegistry(ROOT)
        cls.schema = reg.load_json("ccg_schema")
        cls.profile = reg.load_json("mechanical_profile")

    def analyze(self, source: str):
        return analyze_python(
            {"src/pkg/demo.py": source},
            snapshot_id="pinned-syntax-context",
            ccg_schema=self.schema,
            mechanical_profile=self.profile,
        )

    def test_fluent_polars_shaped_expressions_keep_original_call_warning(self):
        body = "def compute():\n"
        body += "".join(
            f'    result_{i} = pl.col("x").sum().alias("total")\n'
            for i in range(7)
        )
        report = self.analyze(body)
        warnings = [f for f in report.quality.findings
                    if f.rule_id == "outgoing_call_sites_review"]
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0].observed, 21)
        ctx = report.contextual_review
        self.assertEqual((ctx.call_site_findings, ctx.context_available,
                          ctx.context_unavailable), (1, 1, 0))
        item = ctx.reviews[0]
        self.assertEqual(item.call_sites, 21)
        self.assertEqual((item.name_calls, item.attribute_calls,
                          item.chained_attribute_calls, item.other_calls), (0, 7, 14, 0))
        self.assertEqual(item.distinct_callee_syntax, 3)
        self.assertEqual(item.unresolved_call_sites, 21)
        self.assertIn("ATTRIBUTE_SYNTAX_DOMINANT", item.context_flags)
        self.assertIn("CHAINED_ATTRIBUTE_SYNTAX", item.context_flags)
        self.assertIn("REPEATED_CALLEE_SYNTAX", item.context_flags)
        self.assertEqual(report.quality.status, "REVIEW_REQUIRED")
        self.assertEqual(report.contextual_review.interpretation, "NON_SCORING_CONTEXT_ONLY")
        self.assertIsNone(report.quality.call_metrics[0].external_dependencies)

    def test_declared_namespace_evidence_is_not_runtime_identity(self):
        source = "import polars as pl\n\ndef compute():\n"
        source += "".join('    value = pl.col("x").sum().alias("x")\n' for _ in range(7))
        result = self.analyze(source)
        item = result.contextual_review.reviews[0]
        self.assertEqual(item.declared_import_namespace_hints, (("pl", "polars", 21),))
        self.assertIn("DECLARED_IMPORT_NAMESPACE_SYNTAX", item.context_flags)
        self.assertEqual(item.interpretation, "SYNTACTIC_TRIAGE_NOT_COUPLING_VERDICT")
        self.assertEqual(result.quality.status, "REVIEW_REQUIRED")

    def test_namespace_rebinding_prevents_unjustified_alias_claim(self):
        source = "import polars as pl\npl = object()\n\ndef compute():\n"
        source += "".join('    value = pl.col("x").sum().alias("x")\n' for _ in range(7))
        item = self.analyze(source).contextual_review.reviews[0]
        self.assertEqual(item.declared_import_namespace_hints, ())
        self.assertNotIn("DECLARED_IMPORT_NAMESPACE_SYNTAX", item.context_flags)

    def test_direct_calls_with_branching_have_distinct_shape(self):
        source = "def helper(): pass\n"
        source += "def compute():\n    if True:\n"
        source += "        " + "; ".join("helper()" for _ in range(14)) + "\n"
        report = self.analyze(source)
        ctx = report.contextual_review.reviews[0]
        self.assertEqual(ctx.name_calls, 14)
        self.assertEqual(ctx.chained_attribute_calls, 0)
        self.assertEqual(ctx.distinct_resolved_targets, 1)
        self.assertIn("CONTROL_FLOW_PRESENT", ctx.context_flags)
        self.assertNotIn("ATTRIBUTE_SYNTAX_DOMINANT", ctx.context_flags)
        self.assertEqual(ctx.branch_constructs, 1)
        self.assertEqual(ctx.unresolved_call_sites, 0)

    def test_independent_syntactic_context_does_not_claim_actual_dsl(self):
        code = "def f():\n"
        code += "".join("    obj.step().finish()\n" for _ in range(7))
        report = self.analyze(code)
        item = report.contextual_review.reviews[0]
        self.assertEqual(item.chained_attribute_calls, 7)
        self.assertEqual(item.interpretation, "SYNTACTIC_TRIAGE_NOT_COUPLING_VERDICT")
        self.assertEqual(item.unresolved_call_sites, 14)
        self.assertEqual(report.quality.status, "REVIEW_REQUIRED")

    def test_nested_functions_and_methods_get_separate_context_ids(self):
        source = (
            "class T:\n"
            "    def method(self):\n"
            "        def nested():\n"
            "            self.work()\n"
            "        return nested()\n"
        )
        analysis = self.analyze(source)
        contexts = {c.node_id: c for c in analysis.function_context}
        method = next(v for k,v in contexts.items() if "::T.method@" in k)
        nested = next(v for k,v in contexts.items() if "::T.method.nested@" in k)
        self.assertEqual(method.call_sites, 1)
        self.assertEqual(nested.call_sites, 1)

    def test_lambda_calls_are_not_attributed_to_enclosing_function(self):
        src = "def work():\n    fn = lambda: remote.call()\n    return local()\n"
        report = self.analyze(src)
        function = next(c for c in report.function_context if "::work@" in c.node_id)
        self.assertEqual(function.call_sites, 1)
        self.assertEqual(function.attribute_calls, 0)
        self.assertEqual(function.name_calls, 1)

    def test_no_function_call_warning_does_not_invent_contextual_finding(self):
        report = self.analyze("def short():\n    return abs(1)\n")
        self.assertEqual(report.contextual_review.call_site_findings, 0)
        self.assertEqual(report.contextual_review.reviews, ())
        self.assertEqual(report.quality.status, "PASS")

    def test_context_and_mechanical_report_remain_independent(self):
        src = "def long():\n" + "".join("    x = 1\n" for _ in range(81))
        result = self.analyze(src)
        self.assertTrue(any(f.rule_id == "function_span_review"
                            for f in result.quality.findings))
        self.assertEqual(result.contextual_review.call_site_findings, 0)
        self.assertEqual(result.contextual_review.context_available, 0)

    def test_summary_and_details_explain_non_scoring_scope(self):
        src = "def compute():\n" + "    external.call()\n" * 14
        result = self.analyze(src)
        data = result.to_document()
        self.assertEqual(data["summary"]["contextual_review"]["call_site_findings"], 1)
        self.assertEqual(data["summary"]["contextual_review"]["context_available"], 1)
        self.assertEqual(
            data["summary"]["contextual_review"]["meaning"],
            "NON_SCORING_AST_OBSERVATIONS",
        )
        self.assertEqual(len(data["contextual_review"]["reviews"]), 1)
        self.assertTrue(all(x["interpretation"] == "SYNTAX_ONLY"
                            for x in data["function_context"]))


if __name__ == "__main__":
    unittest.main()
