"""Naming #69 opt-in v0.2: bounded additional declaration coverage, no v0.1 drift."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import json
import unittest

from jsonschema import Draft202012Validator

from codeqa.adapters.python_snapshot import parse_python_snapshot
from codeqa.adapters.python_naming import extract_python_naming
from codeqa.adapters.python_naming_coverage_v02 import extract_python_extended_naming
from codeqa.core.naming import NamingProfile
from codeqa.core.naming_coverage_v02 import NamingCoverageError, NamingCoveragePolicy
from codeqa.evaluation.naming import evaluate_naming
from codeqa.evaluation.naming_coverage_v02 import evaluate_extended_naming
from codeqa.infrastructure.resources import ResourceRegistry


ROOT=Path(__file__).resolve().parents[1]
SAMPLE=(
    "from typing import Final as Immutable\n"
    "MAX_RETRIES: Immutable[int] = 5\n"
    "class Handler:\n"
    "    TIMEOUT: Immutable[int] = 30\n"
    "    def __init__(self):\n"
    "        self.session_id = 'x'\n"
    "        self.BadField = 2\n"
)


class ExtendedCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        r=ResourceRegistry(ROOT)
        cls.base=NamingProfile.from_mapping(r.load_json("python_naming_safe_profile"))
        cls.raw=r.load_json("python_naming_coverage_v02_profile")
        cls.schema=r.load_json("naming_coverage_v02_report_schema")
        Draft202012Validator.check_schema(cls.schema)
        cls.original_contract=r.load_json("naming_report_schema")

    def inspect(self, sources=None, policy=None):
        source={"src/module.py":SAMPLE} if sources is None else sources
        cfg=NamingCoveragePolicy.from_mapping(policy or self.raw)
        parsed=parse_python_snapshot(source)
        baseline=extract_python_naming(parsed,source,snapshot_id="git:owner/repo@"+"a"*40)
        ext=extract_python_extended_naming(parsed,source,snapshot_id=baseline.snapshot_id)
        report=evaluate_extended_naming(baseline,ext,source,baseline_profile=self.base,policy=cfg)
        Draft202012Validator(self.schema).validate(report.to_document())
        return baseline,ext,report

    def find(self,report,name):
        records=[f for f in report.findings if f.name==name]
        self.assertEqual(len(records),1,name)
        return records[0]

    def test_final_and_instance_attribute_evidence(self):
        _,_,report=self.inspect()
        self.assertEqual(report.status,"REVIEW_REQUIRED")
        self.assertEqual(report.counts_by_kind,(
            ("class_constant",1),("instance_attribute",2),("module_constant",1)))
        self.assertEqual(self.find(report,"MAX_RETRIES").status,"CONFORMANT_WITH_APPLIED_RULE")
        self.assertEqual(self.find(report,"TIMEOUT").status,"CONFORMANT_WITH_APPLIED_RULE")
        self.assertEqual(self.find(report,"session_id").status,"CONFORMANT_WITH_APPLIED_RULE")
        bad=self.find(report,"BadField")
        self.assertEqual(bad.status,"REVIEW_REQUIRED")
        self.assertEqual(bad.owner,"Handler.__init__")
        self.assertEqual(bad.expected_style,"snake_case")
        self.assertEqual(report.evaluated,4)

    def test_nonfinal_uppercase_is_coverage_unknown_not_const_proof(self):
        _,ext,report=self.inspect({"src/module.py":"MAX_VALUE=4\n"
                                  "class C:\n    PERMANENT = 2\n"})
        self.assertFalse(report.findings)
        self.assertEqual(report.status,"NOT_EVALUATED")
        self.assertTrue(any(u.category=="constant_intent" for u in ext.uncertainty))
        self.assertGreaterEqual(report.uncertain,2)

    def test_dynamic_attribute_writes_and_nested_lexical_roles(self):
        text=("class C:\n"
              "    @decorate\n"
              "    def __init__(self):\n"
              "        self.good_field=1\n"
              "        if predicate():\n"
              "            setattr(self,'BadField',2)\n"
              "        def nested_func(): pass\n")
        _,ext,report=self.inspect({"src/module.py":text})
        self.assertEqual(self.find(report,"good_field").status,
                         "CONFORMANT_WITH_APPLIED_RULE")
        unknown={u.category for u in ext.uncertainty}
        self.assertIn("dynamic_binding",unknown)
        self.assertIn("decorator_binding",unknown)
        self.assertIn("nested_declaration",unknown)
        self.assertEqual(report.status,"NOT_EVALUATED")

    def test_inherited_instance_attribute_abstains(self):
        text=("from vendor import Parent\n"
              "class Child(Parent):\n"
              "    def __init__(self):\n"
              "        self.BadField=1\n")
        _,_,report=self.inspect({"src/module.py":text})
        self.assertEqual(self.find(report,"BadField").status,"NOT_EVALUATED")
        self.assertEqual(report.uncertain,1)

    def test_path_override_longest_match_and_exact_exception(self):
        overrides=[
            {"prefix":"src/","kind":"instance_attribute","style":"UPPER_SNAKE_CASE"},
            {"prefix":"src/app/","kind":"instance_attribute","style":"snake_case"},
        ]
        policy={**self.raw,"path_overrides":overrides}
        src={"src/app/models.py":"class C:\n    def __init__(self):\n"
                                   "        self.BadField=1\n"}
        _,_,r=self.inspect(src,policy)
        self.assertEqual(self.find(r,"BadField").applied_rule,
                         "path:src/app/:instance_attribute")
        self.assertEqual(self.find(r,"BadField").status,"REVIEW_REQUIRED")
        exact=dict(path="src/app/models.py",owner="C.__init__",
                   name="BadField",kind="instance_attribute",
                   provider="vendor",revision="v1",reason="exact versioned callback field")
        _,_,r=self.inspect(src,{**policy,"exact_exceptions":[exact]})
        self.assertEqual(self.find(r,"BadField").status,"EXEMPT_BY_DECLARED_CONTRACT")
        self.assertIn("vendor@v1",self.find(r,"BadField").exception_origin)

    def test_equal_precedence_conflicts_and_unsafe_policy_rejected(self):
        cases=[
            {**self.raw,"path_overrides":[
                {"prefix":"src/","kind":"instance_attribute","style":"snake_case"},
                {"prefix":"src/","kind":"instance_attribute","style":"UPPER_SNAKE_CASE"}]},
            {**self.raw,"excluded_prefixes":["../outside/"]},
            {**self.raw,"styles":{**self.raw["styles"],"module_constant":"PascalCase"}},
            {**self.raw,"schema_version":"0.1"},
        ]
        for case in cases:
            with self.subTest(case=case),self.assertRaises(NamingCoverageError):
                NamingCoveragePolicy.from_mapping(case)

    def test_unicode_identifier_does_not_auto_normalize_or_claim_conformance(self):
        src={"src/unicode.py":"from typing import Final\nK: Final[str] = 'kelvin'\n"}
        _,_,report=self.inspect(src)
        self.assertEqual(report.status,"NOT_EVALUATED")
        self.assertFalse(report.findings)
        self.assertTrue(any(u.category=="unicode_identifier" for u in report.uncertainty))

    def test_legacy_v01_report_unchanged_for_same_source(self):
        source={"src/module.py":SAMPLE}
        baseline,_,extended=self.inspect(source)
        old=evaluate_naming(baseline,source,self.base)
        Draft202012Validator(self.original_contract).validate(old.to_document())
        self.assertEqual(old.schema_version,"0.1")
        self.assertEqual(extended.schema_version,"0.2")
        self.assertTrue(any(f.name=="TIMEOUT" and f.status=="REVIEW_REQUIRED"
                            for f in old.findings))
        self.assertEqual(self.find(extended,"TIMEOUT").status,
                         "CONFORMANT_WITH_APPLIED_RULE")

    def test_source_hash_and_forged_columns_rejected(self):
        source={"src/module.py":SAMPLE}
        base,ext,_=self.inspect(source)
        p=NamingCoveragePolicy.from_mapping(self.raw)
        altered=dict(source,**{"src/module.py":SAMPLE.replace("BadField","good_field")})
        with self.assertRaises(Exception):
            evaluate_extended_naming(base,ext,altered,baseline_profile=self.base,policy=p)
        tampered=replace(ext.declarations[0],line=1000)
        with self.assertRaises(NamingCoverageError):
            evaluate_extended_naming(base,replace(
                ext,declarations=(tampered,*ext.declarations[1:])),
                source,baseline_profile=self.base,policy=p)
        with self.assertRaises(NamingCoverageError):
            evaluate_extended_naming(base,replace(ext,source_sha256=(("src/module.py","0"*64),)),
                                     source,baseline_profile=self.base,policy=p)

    def test_excluded_partial_and_unused_exceptions_never_clean_pass(self):
        src={"vendor/ignore.py":SAMPLE,
             "src/valid.py":"from typing import Final\nVALUE: Final[int]=5\n",
             "broken.py":"def ("}
        _,_,r=self.inspect(src)
        self.assertEqual(r.coverage,"partial")
        self.assertGreater(r.excluded,0)
        self.assertEqual(r.status,"NOT_EVALUATED")
        unused=dict(path="src/valid.py",owner="",kind="module_constant",
                    name="MISSING",provider="external",revision="v1",reason="attested")
        _,_,r=self.inspect(src,{**self.raw,"exact_exceptions":[unused]})
        self.assertTrue(any(u.category=="unused_exact_exception" for u in r.uncertainty))

    def test_pinned_codeqa_source_inventory_explicitly_limited(self):
        manifest=json.loads((ROOT/"fixtures/naming-codeqa/provenance.json").read_text())
        source=(ROOT/manifest["path"]).read_text(encoding="utf-8")
        _,_,r=self.inspect({manifest["original_path"]:source})
        self.assertEqual(r.coverage,"complete")
        self.assertEqual(r.profile_fingerprint,
                         NamingCoveragePolicy.from_mapping(self.raw).fingerprint())
        # The pinned real source has no explicitly annotated module constant
        # in the inspected direct-syntax inventory. This is NOT a
        # human-reviewed full naming compliance attestation.
        self.assertGreater(r.evaluated,0)
        self.assertTrue(any(x.kind=="instance_attribute" for x in r.findings))
        self.assertIn("NOT_COMPLETE_PYTHON",r.interpretation)
        self.assertEqual(r.to_document(),self.inspect(
            {manifest["original_path"]:source})[2].to_document())


if __name__=="__main__":
    unittest.main()
