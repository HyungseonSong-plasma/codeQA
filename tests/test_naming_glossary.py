"""#65: project-declared terminology, no synonym inference or automatic rename."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator

from codeqa.adapters.python_naming import extract_python_naming
from codeqa.adapters.python_snapshot import parse_python_snapshot
from codeqa.core.naming import NamingContractError, NamingProfile
from codeqa.core.naming_glossary import NamingGlossaryError,NamingGlossaryProfile
from codeqa.evaluation.naming_glossary import evaluate_naming_glossary
from codeqa.infrastructure.resources import ResourceRegistry


ROOT=Path(__file__).resolve().parents[1]


class NamingGlossaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        registry=ResourceRegistry(ROOT)
        cls.profile=NamingGlossaryProfile.from_mapping(
            registry.load_json("python_naming_glossary_profile"))
        cls.naming=NamingProfile.from_mapping(
            registry.load_json("python_naming_safe_profile"))
        cls.schema=registry.load_json("naming_glossary_report_schema")
        Draft202012Validator.check_schema(cls.schema)

    def report(self, sources, profile=None, source_override=None):
        parsed=parse_python_snapshot(sources)
        evidence=extract_python_naming(
            parsed,sources,snapshot_id="git:owner/repo@"+"a"*40)
        result=evaluate_naming_glossary(
            evidence, source_override if source_override is not None else sources,
            naming_profile=self.naming,glossary=profile or self.profile)
        Draft202012Validator(self.schema).validate(result.to_document())
        return result

    def test_explicit_timestep_alias_not_generic_similarity(self):
        src={"src/solver.py":(
            "def compute_time_step(time_step): pass\n"
            "def compute_timestep(timestep): pass\n"
            "def calculate_timestamp(timestamp): pass\n"
        )}
        report=self.report(src)
        self.assertEqual(report.status,"REVIEW_TERMINOLOGY")
        alias=[x for x in report.findings if x.status=="NON_CANONICAL_TERM_REVIEW"]
        canonical=[x for x in report.findings if x.status=="CANONICAL_TERM_OBSERVED"]
        self.assertEqual(len(alias),2)
        self.assertEqual(len(canonical),2)
        self.assertTrue(all(x.canonical_term=="time_step" for x in alias))
        self.assertFalse(any("timestamp" in x.name for x in report.findings))
        self.assertTrue(all(x.reason=="exact_project_declared_alias_not_semantic_proof"
                            for x in alias))

    def test_explicit_nodeid_and_camel_case_name(self):
        result=self.report({"src/model.py":(
            "class Model:\n"
            "    def load_node_id(self, nodeid): pass\n"
            "    def readNodeID(self): pass\n"
        )})
        aliased=[x for x in result.findings if x.canonical_term=="node_id"
                 and x.status=="NON_CANONICAL_TERM_REVIEW"]
        self.assertEqual(len(aliased),1)
        self.assertEqual(aliased[0].name,"nodeid")
        self.assertTrue(any(x.name=="readNodeID" and
                            x.status=="CANONICAL_TERM_OBSERVED"
                            for x in result.findings))

    def test_unresolved_external_method_not_misclassified(self):
        result=self.report({"src/adapter.py":(
            "from vendor import Base\n"
            "class Adapter(Base):\n"
            "    def get_timestep(self): pass\n"
        )})
        self.assertFalse(result.findings)
        self.assertEqual(result.status,"NOT_EVALUATED")
        self.assertGreater(result.suppressed_external_or_unknown,0)

    def test_no_terms_is_not_naming_quality_pass(self):
        report=self.report({"src/lib.py":"def do_work(): return 3\n"})
        self.assertEqual(report.status,"NOT_EVALUATED")
        self.assertIn("no_explicit_glossary_terms_observed",report.limitations)

    def test_outside_scope_not_compared(self):
        report=self.report({"vendor/lib.py":"def compute_timestep(): pass\n"})
        self.assertEqual(report.status,"NOT_EVALUATED")
        self.assertFalse(report.findings)

    def test_partial_parse_and_unknowns_remain_visible(self):
        result=self.report({
            "src/ok.py":"def get_timestep(): pass\n",
            "src/broken.py":"def ("
        })
        self.assertEqual(result.status,"REVIEW_TERMINOLOGY")
        self.assertIn("naming_source_coverage_or_contracts_incomplete",result.limitations)

    def test_reject_policy_collision_and_invalid_canonical(self):
        p={"schema_version":"0.1","profile_id":"codeqa.naming.glossary.v0.1",
           "include_prefixes":["src/"],"terms":[
            {"canonical":"time_step","aliases":["timestep"],"kinds":["function"]},
            {"canonical":"other","aliases":["timestep"],"kinds":["function"]},
        ]}
        with self.assertRaises(NamingGlossaryError):
            NamingGlossaryProfile.from_mapping(p)
        wrong=deepcopy(p)
        wrong["terms"][1]["aliases"]=["different"]
        wrong["terms"][0]["canonical"]="TimeStep"
        with self.assertRaises(NamingGlossaryError):
            NamingGlossaryProfile.from_mapping(wrong)

    def test_stale_source_digest_cannot_be_reused(self):
        content={"src/test.py":"def get_timestep(): pass\n"}
        with self.assertRaises(NamingContractError):
            self.report(content,source_override={"src/test.py":"def get_time_step(): pass\n"})

    def test_same_source_and_profile_yield_stable_report(self):
        src={"src/helper.py":"def nodeid_to_time_step(nodeid, time_step): pass\n"}
        self.assertEqual(self.report(src).to_document(),
                         self.report(src).to_document())
        self.assertEqual(self.profile.fingerprint(),self.profile.fingerprint())


if __name__=="__main__":
    unittest.main()
