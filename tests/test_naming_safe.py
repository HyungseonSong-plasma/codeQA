"""Issue #61 Phase 1: source-grounded naming and external-contract safeguards."""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha1
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator

from codeqa.adapters.python_naming import extract_python_naming
from codeqa.adapters.python_snapshot import parse_python_snapshot
from codeqa.core.naming import NamingContractError, NamingProfile
from codeqa.evaluation.naming import evaluate_naming
from codeqa.infrastructure.resources import ResourceRegistry


ROOT = Path(__file__).resolve().parents[1]


class NamingSafeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        resources = ResourceRegistry(ROOT)
        cls.profile_document = resources.load_json("python_naming_safe_profile")
        cls.schema = resources.load_json("naming_report_schema")
        Draft202012Validator.check_schema(cls.schema)

    def observe(self, sources: dict[str, str], profile=None):
        cfg = self.profile_document if profile is None else profile
        parsed = parse_python_snapshot(sources)
        evidence = extract_python_naming(
            parsed, sources, snapshot_id="git:owner/repo@" + "a"*40
        )
        report = evaluate_naming(evidence, sources, NamingProfile.from_mapping(cfg))
        Draft202012Validator(self.schema).validate(report.to_document())
        return evidence, report

    def find(self, report, name, kind=None, owner=None):
        matched = [x for x in report.findings if x.name == name
                   and (kind is None or x.kind == kind)
                   and (owner is None or x.owner == owner)]
        self.assertEqual(len(matched), 1, (name, kind, owner, matched))
        return matched[0]

    def test_style_and_private_names_and_language_dunders(self):
        _, report = self.observe({"good_name.py": (
            "class GoodClass:\n"
            "    def __init__(self, sample_value: int):\n"
            "        pass\n"
            "    def _private_method(self): pass\n"
            "    def BadMethod(self, BadParam: int): pass\n"
            "def correct_function(good_argument): pass\n"
        )})
        self.assertEqual(report.status, "REVIEW_REQUIRED")
        self.assertEqual(self.find(report,"GoodClass").status,"CONFORMANT_WITH_APPLIED_RULE")
        self.assertEqual(self.find(report,"__init__").status,"EXEMPT_BY_POLICY")
        self.assertEqual(self.find(report,"_private_method").status,"CONFORMANT_WITH_APPLIED_RULE")
        self.assertEqual(self.find(report,"BadMethod").status,"REVIEW_REQUIRED")
        self.assertEqual(self.find(report,"BadParam").status,"REVIEW_REQUIRED")

    def test_local_ancestor_member_exact_name_protected_but_sibling_linted(self):
        source = (
            "from typing import override as must_override\n"
            "class Parent:\n"
            "    def do_something_Special(self): pass\n"
            "class Child(Parent):\n"
            "    @must_override\n"
            "    def do_something_Special(self): pass\n"
            "    def WrongLocalName(self): pass\n"
            "    @must_override\n"
            "    def nonexistentParentMember(self): pass\n"
        )
        _, report = self.observe({"a.py": source})
        self.assertEqual(self.find(report,"do_something_Special",owner="Child").status,
                         "EXEMPT_BY_INTERFACE_CONTRACT")
        self.assertEqual(self.find(report,"do_something_Special",owner="Parent").status,
                         "REVIEW_REQUIRED")
        self.assertEqual(self.find(report,"WrongLocalName").status,"REVIEW_REQUIRED")
        missing=self.find(report,"nonexistentParentMember")
        self.assertEqual(missing.status,"REVIEW_REQUIRED")
        self.assertIn("ancestor_member_missing",missing.reason)

    def test_undecorated_ancestor_member_protected(self):
        _,report=self.observe({"a.py":(
            "class Parent:\n    def MixedVendorAPI(self): pass\n"
            "class Child(Parent):\n    def MixedVendorAPI(self): pass\n"
        )})
        self.assertEqual(self.find(report,"MixedVendorAPI",owner="Child").status,
                         "EXEMPT_BY_INTERFACE_CONTRACT")

    def test_unresolved_external_ancestor_is_not_proven_override(self):
        _,report=self.observe({"a.py":(
            "from vendor_sdk import ExternalBase\n"
            "from typing_extensions import override\n"
            "class Child(ExternalBase):\n"
            "    @override\n"
            "    def do_something_Special(self): pass\n"
            "    def MyPossibleHook(self): pass\n"
        )})
        self.assertEqual(self.find(report,"do_something_Special").status,"NOT_EVALUATED")
        self.assertEqual(self.find(report,"MyPossibleHook").status,"NOT_EVALUATED")
        self.assertIn("unresolved_contract_or_unsupported_naming_evidence",report.limitations)
        self.assertGreaterEqual(report.unresolved_declarations,2)

    def test_pinned_external_interface_contract_is_attestation_not_proof(self):
        source=("from vendor_sdk import ExternalBase\n"
                "class Child(ExternalBase):\n"
                "    def do_something_Special(self): pass\n"
                "    def new_helper_method(self): pass\n")
        contract=dict(kind="interface",path="a.py",owner="Child",
                      name="do_something_Special",provider="vendor_sdk.ExternalBase",
                      revision="sdk-v2.1-sha256-abc",reason="exact external override API")
        profile={**self.profile_document,"external_contracts":[contract]}
        _,report=self.observe({"a.py":source},profile)
        target=self.find(report,"do_something_Special")
        self.assertEqual(target.status,"EXEMPT_BY_DECLARED_CONTRACT")
        self.assertIn("attested_not_runtime_verified",target.reason)
        self.assertEqual(self.find(report,"new_helper_method").status,"NOT_EVALUATED")
        wrong=dict(contract,name="new_helper_method")
        with self.assertRaises(NamingContractError):
            # Same project profile, but contract without method ancestral proof?
            self.observe({"a.py":source},{**profile,"external_contracts":[contract,wrong,wrong]})

    def test_aliased_external_import_spelling_never_rewritten(self):
        _,report=self.observe({"a.py":(
            "from sdk import BadExternalName, AnotherName as good_alias\n"
            "from sdk import ThirdName as BadAlias\n"
            "import vendor.BadModule\n"
        )})
        self.assertEqual(self.find(report,"BadExternalName").status,"EXEMPT_BY_POLICY")
        self.assertEqual(self.find(report,"good_alias").status,"CONFORMANT_WITH_APPLIED_RULE")
        self.assertEqual(self.find(report,"BadAlias").status,"REVIEW_REQUIRED")
        self.assertEqual(self.find(report,"vendor").status,"EXEMPT_BY_POLICY")

    def test_dto_directional_alias_and_db_column_are_separate(self):
        src=(
            "from pydantic import BaseModel, Field\n"
            "from sqlalchemy.orm import mapped_column\n"
            "class UserDTO(BaseModel):\n"
            "    user_id: str = Field(validation_alias='UserID', serialization_alias='userId')\n"
            "    BadInternal: str = Field(alias='EXT_FIELD')\n"
            "    USER_ID: str\n"
            "class LegacyRow:\n"
            "    user_id: str = mapped_column('USER_ID')\n"
        )
        _,report=self.observe({"a.py":src})
        internal=self.find(report,"user_id",owner="UserDTO")
        self.assertEqual(internal.status,"CONFORMANT_WITH_APPLIED_RULE")
        self.assertIn("DTO_FIELD_ALIAS_DECLARED",internal.evidence_relation)
        self.assertEqual(self.find(report,"BadInternal").status,"REVIEW_REQUIRED")
        self.assertEqual(self.find(report,"USER_ID").status,"NOT_EVALUATED")
        self.assertEqual(self.find(report,"user_id",owner="LegacyRow").status,
                         "CONFORMANT_WITH_APPLIED_RULE")
        self.assertFalse(any(x.name in ("UserID","userId","EXT_FIELD") for x in report.findings))

    def test_direct_dto_field_exact_contract_only(self):
        source=("from pydantic import BaseModel\n"
                "class Payload(BaseModel):\n"
                "    USER_ID: str\n"
                "    OddName: int\n")
        contract=dict(kind="field",path="a.py",owner="Payload",name="USER_ID",
                      provider="api.example/users",revision="openapi-2026-01",
                      reason="serialized external field unchanged")
        _, report=self.observe({"a.py":source},
                              {**self.profile_document,"external_contracts":[contract]})
        self.assertEqual(self.find(report,"USER_ID").status,"EXEMPT_BY_DECLARED_CONTRACT")
        self.assertEqual(self.find(report,"OddName").status,"NOT_EVALUATED")

    def test_dynamic_alias_and_unrecognized_fields_fail_closed(self):
        source=("from pydantic import BaseModel, Field\n"
                "class Payload(BaseModel):\n"
                "    WildField: str = Field(alias=make_alias())\n")
        _,r=self.observe({"a.py":source})
        self.assertEqual(self.find(r,"WildField").status,"NOT_EVALUATED")

    def test_non_external_decorator_is_not_blanket_exemption(self):
        source=("class Plain:\n"
                "    @property\n"
                "    def BadProperty(self): return 1\n")
        _,r=self.observe({"a.py":source})
        self.assertEqual(self.find(r,"BadProperty").status,"REVIEW_REQUIRED")

    def test_ambiguous_multiple_inheritance_not_resolved(self):
        s=("class A:\n    def MixedAPI(self): pass\n"
           "class B:\n    def MixedAPI(self): pass\n"
           "class C(A, B):\n    def MixedAPI(self): pass\n")
        _,r=self.observe({"a.py":s})
        self.assertEqual(self.find(r,"MixedAPI",owner="C").status,"NOT_EVALUATED")

    def test_partial_parse_profile_exclusions_and_stale_cache(self):
        sources={"src/ok.py":"def fine_name():pass\n","broken.py":"def (",
                 "unknown.rs":"fn main() {}",
                 "vendor/copy.py":"def BadFunction():pass\n"}
        evidence,report=self.observe(sources)
        self.assertEqual(report.coverage_status,"partial")
        self.assertEqual(report.excluded_declarations,2) # module + function
        self.assertIn("unprocessed_or_unsupported_sources",report.limitations)
        changed={**sources,"src/ok.py":"def changed_name():pass\n"}
        with self.assertRaises(NamingContractError):
            evaluate_naming(evidence,changed,
                            NamingProfile.from_mapping(self.profile_document))
        with self.assertRaises(ValueError):
            extract_python_naming(parse_python_snapshot(sources),changed,
                                  snapshot_id="git:revision")

    def test_policy_conflicts_and_bad_contract_are_errors(self):
        contract=dict(kind="interface",path="a.py",owner="Child",name="Special",
                      provider="vendor",revision="1.0",reason="API")
        bads=(
            {**self.profile_document,"schema_version":"0.2"},
            {**self.profile_document,"rules":{"method":"snake_case"}},
            {**self.profile_document,"rules":{**self.profile_document["rules"],
                                             "method":"inferred_style"}},
            {**self.profile_document,"external_contracts":[contract,contract]},
            {**self.profile_document,"external_contracts":[dict(contract,revision="")]},
        )
        for p in bads:
            with self.subTest(profile=p),self.assertRaises(NamingContractError):
                NamingProfile.from_mapping(p)

    def test_unicode_identifier_requires_explicit_policy(self):
        _,r=self.observe({"a.py":"def café(): pass\n"})
        self.assertEqual(self.find(r,"café").status,"NOT_EVALUATED")

    def test_frozen_codeqa_python_adapter_source(self):
        import json
        manifest=json.loads((ROOT/"fixtures/naming-codeqa/provenance.json").read_text())
        data=(ROOT/manifest["path"]).read_bytes()
        observed=sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
        self.assertEqual(observed,manifest["git_blob_sha"])
        self.assertEqual(manifest["source_commit"],
                         "ef6359131f0cd952ed43674274ffe0453c6bf2a9")
        _,r=self.observe({manifest["original_path"]:data.decode("utf-8")})
        self.assertTrue(r.findings)
        self.assertEqual(r.coverage_status,"complete")
        self.assertEqual(r.profile_fingerprint,
                         NamingProfile.from_mapping(self.profile_document).fingerprint())


if __name__=="__main__":
    unittest.main()
