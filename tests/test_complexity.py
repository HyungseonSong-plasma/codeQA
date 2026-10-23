"""#37: versioned Python AST P6 complexity proxy and adversarial controls."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator

from codeqa.adapters.python import adapt_parsed_python
from codeqa.adapters.python_complexity import extract_python_complexity
from codeqa.adapters.python_snapshot import parse_python_snapshot
from codeqa.evaluation.complexity import (
    ComplexityProfile, ComplexityProfileError, evaluate_complexity,
)
from codeqa.infrastructure.resources import ResourceRegistry
from codeqa.pipeline.python import analyze_python


ROOT = Path(__file__).resolve().parents[1]


class ComplexityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reg = ResourceRegistry(ROOT)
        cls.ccg_schema = reg.load_json("ccg_schema")
        cls.mechanical_profile = reg.load_json("mechanical_profile")
        cls.profile = ComplexityProfile.from_mapping(reg.load_json("complexity_profile"))
        cls.report_schema = reg.load_json("complexity_report_schema")
        Draft202012Validator.check_schema(cls.report_schema)

    def audit(self, sources, profile=None):
        parsed = parse_python_snapshot(sources)
        graph = adapt_parsed_python(parsed, snapshot_id="pinned-A", schema=self.ccg_schema)
        evidence = extract_python_complexity(parsed)
        report = evaluate_complexity(graph, evidence, profile or self.profile)
        Draft202012Validator(self.report_schema).validate(report.to_document())
        return graph, evidence, report

    def test_simple_branch_and_boolean_decisions_and_scope(self):
        source = ("def outer(a, b, c):\n"
                  "    if a and b or c:\n"
                  "        return 1\n"
                  "    else:\n"
                  "        return 0\n"
                  "\n"
                  "async def task(x):\n"
                  "    if x:\n"
                  "        return 1\n")
        _, evidence, report = self.audit({"a.py": source})
        outer = next(item for item in evidence if "outer@" in item.node_id)
        self.assertEqual(outer.decision_count, 3)  # if + and + or
        self.assertEqual(outer.cyclomatic_proxy, 4)
        self.assertEqual(outer.branch_nesting_max, 1)
        task = next(item for item in evidence if "task@" in item.node_id)
        self.assertEqual((task.cyclomatic_proxy, task.branch_nesting_max), (2, 1))
        self.assertEqual(report.status, "PASS")

    def test_nested_declarations_are_independent_not_double_counted(self):
        source = ("class Engine:\n"
                  "    def method(self, x):\n"
                  "        if x:\n"
                  "            def nested():\n"
                  "                while True:\n"
                  "                    break\n"
                  "            return nested()\n")
        _, evidence, _ = self.audit({"a.py": source})
        self.assertEqual(len(evidence), 2)
        by_name = {item.node_id.split("::")[-1].split("@")[0]: item for item in evidence}
        self.assertEqual(by_name["Engine.method"].cyclomatic_proxy, 2)
        self.assertEqual(by_name["Engine.method.nested"].cyclomatic_proxy, 2)
        self.assertEqual(by_name["Engine.method"].branch_nesting_max, 1)

    def test_advanced_control_constructs_have_documented_counts(self):
        source = (
            "def heavy(seq):\n"
            "    for item in seq:\n"
            "        if item:\n"
            "            x = [a for a in seq if a]\n"
            "    try:\n"
            "        match seq:\n"
            "            case []:\n"
            "                return 0\n"
            "            case _:\n"
            "                return 1\n"
            "    except ValueError:\n"
            "        return 2\n"
        )
        _, evidence, _ = self.audit({"a.py": source})
        x = evidence[0]
        self.assertEqual(x.decision_count, 6)  # for + if + comp-for + comp-if + match + except
        self.assertGreaterEqual(x.branch_nesting_max, 2)

    def test_decorator_signature_and_lambda_fail_closed(self):
        src = ("@wrap\n"
               "def decorated(x): return 1\n"
               "def defaults(x=make_default()): return x\n"
               "def closure():\n"
               "    fn = lambda k: k if k else 0\n"
               "    return fn(1)\n")
        _, observations, report = self.audit({"a.py": src})
        self.assertEqual(report.status, "NOT_EVALUATED")
        self.assertTrue(all(item.status == "NOT_EVALUATED" for item in observations))
        reasons = {r for item in observations for r in item.limitations}
        self.assertEqual(reasons, {
            "decorators_not_evaluated", "signature_expressions_not_evaluated",
            "lambda_body_not_evaluated",
        })
        for item in report.reviews:
            self.assertIsNone(item.cyclomatic_proxy)
            self.assertIsNone(item.branch_nesting_max)
            self.assertTrue(item.limitations)

    def test_thresholds_review_syntax_not_prove_p6_violation(self):
        profile = ComplexityProfile("custom", "0.1", 1, 0)
        _, _, report = self.audit({"a.py": "def f(x):\n    if x: return 1\n"}, profile)
        self.assertEqual(report.status, "REVIEW_REQUIRED")
        self.assertEqual(report.reviews[0].cyclomatic_proxy, 2)
        self.assertEqual(report.interpretation, "HEURISTIC_SYNTAX_PROXY_NOT_P6_VERDICT")

    def test_parse_failure_preserves_partial_coverage(self):
        _, observations, report = self.audit({
            "good.py": "def f(): pass\n", "broken.py": "def (",
            "foreign.rs": "fn main() {}",
        })
        self.assertEqual(len(observations), 1)
        self.assertEqual(report.coverage_status, "partial")
        self.assertEqual(report.unprocessed_paths, ("broken.py", "foreign.rs"))
        self.assertEqual(report.status, "NOT_EVALUATED")
        _, _, none_report = self.audit({"bad.py": "def ("})
        self.assertEqual(none_report.status, "NOT_EVALUATED")

    def test_stable_order_and_no_legacy_report_changes(self):
        src = {"b.py": "def b(): pass\n", "a.py": "def a():\n    if True: pass\n"}
        a = self.audit(src)[2].to_document()
        b = self.audit(dict(reversed(list(src.items()))))[2].to_document()
        self.assertEqual(a, b)
        existing = analyze_python(
            src, snapshot_id="pinned-A", ccg_schema=self.ccg_schema,
            mechanical_profile=self.mechanical_profile,
        )
        self.assertEqual(existing.quality.status, "PASS")
        self.assertNotIn("complexity", existing.to_document())

    def test_profile_and_evidence_corruption_fail_closed(self):
        for bad in (
            {"schema_version": "1.0"},
            {"max_cyclomatic_proxy_review": -1},
            {"max_branch_nesting_review": False},
        ):
            with self.subTest(bad=bad), self.assertRaises(ComplexityProfileError):
                ComplexityProfile.from_mapping({
                    "profile_id": "bad", "schema_version": "0.1",
                    "max_cyclomatic_proxy_review": 5,
                    "max_branch_nesting_review": 3, **bad,
                })
        from dataclasses import replace
        graph, items, _ = self.audit({"a.py": "def a(): pass\n"})
        for changed in (
            (replace(items[0], node_id="invented"),),
            (replace(items[0], path="../other.py"),),
            (replace(items[0], cyclomatic_proxy=5),),
            (replace(items[0], status="NOT_EVALUATED"),),
        ):
            with self.subTest(changed=changed), self.assertRaises(ComplexityProfileError):
                evaluate_complexity(graph, changed, self.profile)


if __name__ == "__main__":
    unittest.main()
