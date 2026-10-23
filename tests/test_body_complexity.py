"""#49: typed Python declaration exclusion is not loss of measurable body AST."""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator

from codeqa.adapters.python import adapt_parsed_python
from codeqa.adapters.python_snapshot import parse_python_snapshot
from codeqa.adapters.python_complexity import (
    extract_python_complexity, extract_python_body_complexity,
)
from codeqa.evaluation.body_complexity import evaluate_body_complexity
from codeqa.evaluation.complexity import ComplexityProfile, ComplexityProfileError, evaluate_complexity
from codeqa.infrastructure.resources import ResourceRegistry


ROOT=Path(__file__).resolve().parents[1]


class BodyComplexityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reg=ResourceRegistry(ROOT)
        cls.graph_schema=reg.load_json("ccg_schema")
        cls.profile=ComplexityProfile.from_mapping(reg.load_json("complexity_profile"))
        cls.report_schema=reg.load_json("body_complexity_v02_schema")
        Draft202012Validator.check_schema(cls.report_schema)

    def check(self, sources):
        parsed=parse_python_snapshot(sources)
        graph=adapt_parsed_python(parsed,snapshot_id="pinned-git-revision",schema=self.graph_schema)
        old=evaluate_complexity(graph,extract_python_complexity(parsed),self.profile)
        facts=extract_python_body_complexity(parsed)
        report=evaluate_body_complexity(graph,facts,self.profile)
        Draft202012Validator(self.report_schema).validate(report.to_document())
        return old,facts,report,graph

    def test_annotated_function_body_is_measured_without_executing_annotations(self):
        source=(
            "def f(x: expensive(), y: 'Future') -> 'Outcome':\n"
            "    if x:\n        return 1\n"
            "    return 0\n"
        )
        old,evidence,new,_=self.check({"a.py":source})
        self.assertEqual(old.reviews[0].status,"NOT_EVALUATED")
        self.assertEqual(new.reviews[0].status,"PASS")
        self.assertEqual((new.reviews[0].cyclomatic_proxy,
                          new.reviews[0].branch_nesting_max),(2,1))
        self.assertEqual(new.reviews[0].excluded_declaration_scope,
                         ("signature_expressions_excluded_from_body_scope",))
        self.assertEqual(new.status,"PASS")

    def test_ignored_decorators_and_defaults_are_not_called_or_traversed(self):
        source=(
            "@decorator_factory(lambda q: q if q else 0)\n"
            "def f(a: 'Awaited'=potential_side_effect()) -> int:\n"
            "    return 1\n"
        )
        old,facts,new,_=self.check({"a.py":source})
        self.assertEqual(old.reviews[0].status,"NOT_EVALUATED")
        self.assertEqual(new.reviews[0].cyclomatic_proxy,1)
        self.assertEqual(new.reviews[0].branch_nesting_max,0)
        self.assertEqual(set(new.reviews[0].excluded_declaration_scope),{
            "decorators_excluded_from_body_scope",
            "signature_expressions_excluded_from_body_scope",
        })
        self.assertEqual(facts.observations[0].status,"MEASURED")

    def test_body_lambda_remains_not_evaluated(self):
        _,facts,report,_=self.check({"a.py":(
            "def f(x: int) -> int:\n"
            "    y = lambda q: q if q else 1\n"
            "    return y(x)\n"
        )})
        self.assertEqual(facts.observations[0].status,"NOT_EVALUATED")
        self.assertEqual(report.reviews[0].status,"NOT_EVALUATED")
        self.assertIsNone(report.reviews[0].cyclomatic_proxy)
        self.assertEqual(report.reviews[0].limitations,("lambda_body_not_evaluated",))
        self.assertEqual(report.status,"NOT_EVALUATED")

    def test_match_try_nested_and_async_body_are_separate(self):
        source=(
            "async def outside(x: int) -> int:\n"
            "    try:\n"
            "        match x:\n"
            "            case 0: return 1\n"
            "            case _: return 2\n"
            "    except ValueError:\n"
            "        return 0\n"
            "    async def nested(y: int):\n"
            "        if y: return 1\n"
            "    return 0\n"
        )
        _,facts,report,_=self.check({"a.py":source})
        self.assertEqual(len(facts.observations),2)
        byname={x.node_id.split("::")[-1].split("@")[0]:x for x in report.reviews}
        self.assertEqual(byname["outside"].cyclomatic_proxy,3)
        self.assertEqual(byname["outside.nested"].cyclomatic_proxy,2)
        self.assertTrue(all(x.status=="PASS" for x in report.reviews))

    def test_partial_coverage_cannot_claim_complete_scope(self):
        _,facts,report,_=self.check({
            "a.py":"def f(x:int):\n    if x:return 1\n",
            "bad.py":"def (",
            "foreign.rs":"fn main() {}",
        })
        self.assertEqual(report.coverage_status,"partial")
        self.assertEqual(report.status,"NOT_EVALUATED")
        self.assertEqual(report.unprocessed_paths,("bad.py","foreign.rs"))
        self.assertEqual(len(report.reviews),1)

    def test_pinned_real_moose_production_samples_gain_body_evidence(self):
        for label in ("base","blind","guided"):
            with self.subTest(label=label):
                src=(ROOT/f"fixtures/moose-p3-refactor/{label}.py.txt").read_text()
                old,facts,new,_=self.check({"physics_harness/analysis/field_comparison.py":src})
                old_by={x.node_id.split("::")[-1].split("@")[0]:x for x in old.reviews}
                new_by={x.node_id.split("::")[-1].split("@")[0]:x for x in new.reviews}
                self.assertEqual(old_by["compare_named_scalars"].status,"NOT_EVALUATED")
                self.assertIn(new_by["compare_named_scalars"].status,("PASS","REVIEW_REQUIRED"))
                self.assertIsNotNone(new_by["compare_named_scalars"].cyclomatic_proxy)
                self.assertEqual(new_by["compare_named_scalars"].producer,
                                 "python-ast-body-complexity-v0.2")
                self.assertIn("signature_expressions_excluded_from_body_scope",
                              new_by["compare_named_scalars"].excluded_declaration_scope)
                self.assertTrue(all(x.method=="bounded_body_ast_syntax_no_annotation_execution"
                                    for x in facts.observations))

    def test_old_v01_contract_and_adapter_remain_identical(self):
        source="def f(x: int) -> int:\n    if x: return 1\n"
        parsed=parse_python_snapshot({"a.py":source})
        old=extract_python_complexity(parsed)
        self.assertEqual(old[0].status,"NOT_EVALUATED")
        self.assertEqual(old[0].producer,"python-ast-complexity-v0.1")
        self.assertEqual(old[0].method,"bounded_python_ast_syntax")
        facts=extract_python_body_complexity(parsed)
        self.assertEqual(facts.observations[0].producer,"python-ast-body-complexity-v0.2")
        self.assertNotEqual(facts.observations[0].status,old[0].status)

    def test_evidence_corruption_is_rejected(self):
        _,facts,_,graph=self.check({"a.py":"def f(x:int):\n    return x\n"})
        for mutated in (
            replace(facts,producer="pretend-v0.1"),
            replace(facts,observations=(replace(facts.observations[0],producer="incorrect"),)),
            replace(facts,observations=(replace(facts.observations[0],path="other.py"),)),
            replace(facts,ignored_declarations=(("invented",("decorators_excluded_from_body_scope",)),)),
            replace(facts,observations=(replace(
                facts.observations[0],cyclomatic_proxy=99),)),
            replace(facts,observations=(replace(
                facts.observations[0],status="NOT_EVALUATED"),)),
        ):
            with self.subTest(mutated=mutated),self.assertRaises(ComplexityProfileError):
                evaluate_body_complexity(graph,mutated,self.profile)

    def test_deterministic_permutation(self):
        src={"b.py":"def b(z: int):\n    return z\n",
             "a.py":"def a(z: int):\n    if z: return z\n"}
        a=self.check(src)[2].to_document()
        b=self.check(dict(reversed(list(src.items()))))[2].to_document()
        self.assertEqual(a,b)


if __name__=="__main__":
    unittest.main()
