"""#53: repeated direct function-body statements with source-only witnesses."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator

from codeqa.adapters.python_snapshot import parse_python_snapshot
from codeqa.adapters.python_statement_similarity import extract_python_statement_patterns
from codeqa.core.statement_similarity import StatementPatternProfile,StatementSimilarityError
from codeqa.evaluation.statement_similarity import evaluate_statement_similarity
from codeqa.infrastructure.resources import ResourceRegistry


ROOT=Path(__file__).resolve().parents[1]
TARGET="physics_harness/analysis/field_comparison.py"


class StatementSimilarityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        registry=ResourceRegistry(ROOT)
        cls.profile_json=registry.load_json("statement_similarity_profile")
        cls.schema=registry.load_json("statement_similarity_report_schema")
        Draft202012Validator.check_schema(cls.schema)
        cls.old_profile=registry.load_json("duplication_profile")
        cls.old_schema=registry.load_json("duplication_report_schema")

    def analyze(self,sources,profile=None):
        settings=deepcopy(profile if profile is not None else self.profile_json)
        parsed=parse_python_snapshot(sources)
        observations=extract_python_statement_patterns(
            parsed,sources,snapshot_id="pinned-git-source",profile=settings,
        )
        result=evaluate_statement_similarity(
            observations,StatementPatternProfile.from_mapping(settings),
        )
        Draft202012Validator(self.schema).validate(result.to_document())
        return observations,result

    def source(self,label):
        return {TARGET:(ROOT/f"fixtures/moose-p3-refactor/{label}.py.txt").read_text()}

    def test_pinned_moose_baseline_tolerance_guards_are_detected(self):
        observed,result=self.analyze(self.source("base"))
        self.assertEqual(result.status,"REPEATED_PATTERNS_OBSERVED")
        self.assertEqual(result.coverage_status,"complete")
        groups=[g for g in result.groups
                if "compare_named_scalars" in g.owner_id and g.statement_kind=="if"]
        self.assertTrue(groups)
        guard=next(g for g in groups if len(g.witnesses)==2)
        self.assertEqual(guard.witnesses[0].line,20)
        self.assertEqual(guard.witnesses[1].line,22)
        self.assertTrue(all(w.source_sha256==observed.source_hashes[0][1]
                            for w in guard.witnesses))
        self.assertEqual(guard.witnesses[0].normalized_syntax_sha256,
                         guard.witnesses[1].normalized_syntax_sha256)
        self.assertNotIn("behavioral_clone",result.interpretation)

    def test_blind_consolidation_reduces_exact_guard_pattern_not_full_quality(self):
        _,baseline=self.analyze(self.source("base"))
        _,blind=self.analyze(self.source("blind"))
        _,guided=self.analyze(self.source("guided"))
        self.assertGreaterEqual(baseline.repeated_statement_occurrences,2)
        self.assertEqual(blind.status,"NO_REPEATS_OBSERVED")
        self.assertEqual(blind.repeated_statement_occurrences,0)
        self.assertEqual(guided.status,"REPEATED_PATTERNS_OBSERVED")
        self.assertGreaterEqual(guided.repeated_statement_occurrences,2)

    def test_profile_owns_normalization_and_minimum(self):
        base=self.source("base")
        no_ids={**self.profile_json,"normalize_identifiers":False}
        no_literals={**self.profile_json,"normalize_literals":False}
        for cfg in (no_ids,no_literals):
            with self.subTest(cfg=cfg):
                _,r=self.analyze(base,cfg)
                self.assertEqual(r.repeated_statement_occurrences,0)
        _,r=self.analyze(base,{**self.profile_json,"min_statement_tokens":1000})
        self.assertEqual(r.status,"NOT_EVALUATED")
        self.assertIn("no_eligible_direct_function_statements",r.not_evaluated)

    def test_different_comparison_operators_not_same_pattern(self):
        s=("def f(a,b):\n"
           "    if a < 0 or a == 0:\n        raise ValueError('a')\n"
           "    if b > 0 or b == 0:\n        raise ValueError('b')\n")
        _,r=self.analyze({"a.py":s},{**self.profile_json,"min_statement_tokens":12})
        self.assertEqual(r.status,"NO_REPEATS_OBSERVED")

    def test_comments_whitespace_do_not_change_ast_pattern(self):
        s=("def f(a,b):\n"
           "    if a < 0 or a == 0:\n"
           "        # doc\n        raise ValueError('a')\n"
           "\n"
           "    if b < 0 or b == 0: # same operation\n"
           "        raise ValueError('b')\n")
        _,r=self.analyze({"a.py":s},{**self.profile_json,"min_statement_tokens":12})
        self.assertEqual(len(r.groups),1)
        self.assertEqual({w.line for w in r.groups[0].witnesses},{2,6})

    def test_nested_scopes_are_not_grouped_with_outer_function(self):
        source=(
            "def outer(x):\n"
            "    if x < 0 or x == 0: raise ValueError('x')\n"
            "    def inner(y,z):\n"
            "        if y < 0 or y == 0: raise ValueError('y')\n"
            "        if z < 0 or z == 0: raise ValueError('z')\n"
        )
        _,r=self.analyze({"a.py":source},{**self.profile_json,"min_statement_tokens":12})
        self.assertEqual(len(r.groups),1)
        self.assertIn("outer.inner@",r.groups[0].owner_id)
        self.assertEqual(r.repeated_statement_occurrences,2)

    def test_unprocessed_and_generated_sources_preserve_evidence_limitations(self):
        source={
            "src/main.py":"def f(a,b):\n    if a < 0 or a == 0: raise ValueError('a')\n"
                          "    if b < 0 or b == 0: raise ValueError('b')\n",
            "vendor/lib.py":"def copied(a,b):\n    if a < 0 or a == 0: raise ValueError('a')\n"
                          "    if b < 0 or b == 0: raise ValueError('b')\n",
            "broken.py":"def (",
            "foreign.rs":"fn main() {}",
        }
        witness,report=self.analyze(source,{**self.profile_json,"min_statement_tokens":12})
        self.assertEqual(report.coverage_status,"partial")
        self.assertIn("unprocessed_selected_files",report.not_evaluated)
        self.assertIn(("vendor/lib.py","profile_excluded_path"),witness.skipped)
        self.assertEqual(len(report.groups),1)
        self.assertEqual(report.groups[0].witnesses[0].path,"src/main.py")

    def test_profile_or_source_evidence_corruption_fail_closed(self):
        evidence,_=self.analyze(self.source("base"))
        other=StatementPatternProfile.from_mapping({
            **self.profile_json,"normalize_literals":False,
        })
        with self.assertRaises(StatementSimilarityError):
            evaluate_statement_similarity(evidence,other)
        one=evidence.witnesses[0]
        for tampered in (
            replace(one,path="outside.py"),
            replace(one,source_sha256="0"*64),
            replace(one,token_count=1),
            replace(one,normalized_syntax_sha256="not-a-hash"),
        ):
            with self.subTest(tampered=tampered),self.assertRaises(StatementSimilarityError):
                evaluate_statement_similarity(
                    replace(evidence,witnesses=(tampered,*evidence.witnesses[1:])),
                    StatementPatternProfile.from_mapping(self.profile_json),
                )
        with self.assertRaises(StatementSimilarityError):
            evaluate_statement_similarity(
                replace(evidence,witnesses=(one,*evidence.witnesses)),
                StatementPatternProfile.from_mapping(self.profile_json),
            )

    def test_source_content_must_match_cached_ast(self):
        s={"a.py":"def f(a):\n    if a<0: raise ValueError('a')\n"}
        p=parse_python_snapshot(s)
        with self.assertRaises(ValueError):
            extract_python_statement_patterns(
                p,{"a.py":s["a.py"].replace("a<0","a>0")},
                snapshot_id="git:changed",profile=self.profile_json,
            )

    def test_legacy_whole_function_duplication_contract_unchanged(self):
        self.assertEqual(self.old_schema["$id"],"urn:codeqa:qa:duplication:v0.1")
        self.assertEqual(self.old_profile["schema_version"],"0.1")
        r1=self.analyze(self.source("base"))[1].to_document()
        r2=self.analyze(self.source("base"))[1].to_document()
        self.assertEqual(r1,r2)
        self.assertEqual(r1["schema_version"],"0.2")


if __name__=="__main__":
    unittest.main()
