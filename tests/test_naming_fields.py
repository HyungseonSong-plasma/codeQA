"""#64 Directional DTO field contracts: lexical mapping != runtime output."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator

from codeqa.adapters.python_snapshot import parse_python_snapshot
from codeqa.adapters.python_naming import extract_python_naming
from codeqa.adapters.python_naming_fields import extract_python_directional_fields
from codeqa.core.naming_fields import FieldMappingError, FieldMappingProfile
from codeqa.evaluation.naming_fields import evaluate_directional_fields
from codeqa.infrastructure.resources import ResourceRegistry


ROOT=Path(__file__).resolve().parents[1]
PATH="src/models.py"

BASE=("from pydantic import BaseModel, Field\n"
      "from sqlalchemy.orm import mapped_column\n"
      "class UserDTO(BaseModel):\n"
      "    user_id: str = Field(validation_alias='UserID', serialization_alias='userId')\n"
      "class LegacyRow:\n"
      "    user_id: str = mapped_column('USER_ID')\n")


class DirectionalMappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        resources=ResourceRegistry(ROOT)
        cls.profile=FieldMappingProfile.from_mapping(
            resources.load_json("python_directional_fields_profile"))
        cls.schema=resources.load_json("directional_fields_report_schema")
        cls.external=(ROOT/cls.profile.schema_path).read_text()
        Draft202012Validator.check_schema(cls.schema)

    def analyze(self, source=BASE, *, contract=None, profile=None):
        p=profile or self.profile
        text=self.external if contract is None else contract
        selected={PATH:source}
        parsed=parse_python_snapshot(selected)
        naming=extract_python_naming(
            parsed,selected,snapshot_id="git:owner/repo@"+"a"*40)
        witness=extract_python_directional_fields(
            parsed,selected,text,snapshot_id=naming.snapshot_id,profile=p)
        report=evaluate_directional_fields(naming,witness,p)
        Draft202012Validator(self.schema).validate(report.to_document())
        return naming,witness,report

    def test_pydantic_directional_and_sqlalchemy_physical_name(self):
        _,_,report=self.analyze()
        rows={(x.owner,x.direction):x for x in report.findings}
        self.assertEqual(len(rows),3)
        self.assertEqual(report.status,"DECLARED_MAPPING_OBSERVED")
        self.assertEqual(rows[("UserDTO","input")].expected_external_name,"UserID")
        self.assertEqual(rows[("UserDTO","output")].expected_external_name,"userId")
        self.assertEqual(rows[("LegacyRow","database")].expected_external_name,"USER_ID")
        self.assertTrue(all(x.status=="DECLARED_MATCH_NOT_RUNTIME_VERIFIED"
                            for x in report.findings))
        self.assertTrue(all(x.internal_name=="user_id" for x in report.findings))
        self.assertIn("NOT_EFFECTIVE_RUNTIME",report.interpretation)

    def test_alias_declared_wrong_direction_is_review(self):
        bad=BASE.replace("validation_alias='UserID'","validation_alias='WrongID'")
        _,_,report=self.analyze(bad)
        rows={(x.owner,x.direction):x for x in report.findings}
        self.assertEqual(rows[("UserDTO","input")].status,"DECLARED_MISMATCH")
        self.assertEqual(rows[("UserDTO","output")].status,
                         "DECLARED_MATCH_NOT_RUNTIME_VERIFIED")
        self.assertEqual(report.status,"REVIEW_REQUIRED")

    def test_inbound_unknown_does_not_impute_from_internal_field(self):
        dynamic=BASE.replace("validation_alias='UserID'","validation_alias=generate_alias()")
        _,w,r=self.analyze(dynamic)
        self.assertEqual([x.status for x in r.findings if x.owner=="UserDTO"],
                         ["NOT_EVALUATED","DECLARED_MATCH_NOT_RUNTIME_VERIFIED"])
        self.assertEqual(r.status,"NOT_EVALUATED")
        self.assertIsNone([x for x in r.findings
                           if x.owner=="UserDTO" and x.direction=="input"][0].declared_external_name)

    def test_missing_field_not_treated_as_conformance(self):
        edited=BASE.replace("    user_id: str = mapped_column('USER_ID')\n",
                            "    unrelated: str = mapped_column('USER_ID')\n")
        _,w,r=self.analyze(edited)
        self.assertEqual(w.skipped_contracts,((PATH,"LegacyRow","user_id"),))
        self.assertEqual(r.status,"NOT_EVALUATED")

    def test_aliased_qualified_imports_support_exact_syntax(self):
        content=("import pydantic as p\n"
                 "from sqlalchemy.orm import mapped_column as column\n"
                 "class UserDTO(p.BaseModel):\n"
                 "    user_id: str = p.Field(validation_alias='UserID',serialization_alias='userId')\n"
                 "class LegacyRow:\n"
                 "    user_id: str = column('USER_ID')\n")
        _,_,r=self.analyze(content)
        self.assertEqual(r.status,"DECLARED_MAPPING_OBSERVED")

    def test_shadowed_field_constructor_is_not_trusted(self):
        content=BASE.replace("from pydantic import BaseModel, Field\n",
                             "from pydantic import BaseModel, Field\n"
                             "def Field(**kwargs): return object()\n")
        # Until shadow analysis is supported by this adapter, cannot treat
        # the local constructor as genuine Pydantic. This test intentionally
        # expects no clean declaration match.
        _,_,r=self.analyze(content)
        self.assertEqual(r.status,"NOT_EVALUATED")

    def test_mismatched_schema_bytes_and_version_fail_closed(self):
        with self.assertRaises(FieldMappingError):
            self.analyze(contract=self.external.replace("userId","newKey"))
        changed=replace(self.profile,revision="other")
        with self.assertRaises(FieldMappingError):
            self.analyze(profile=changed)

    def test_forged_source_evidence_fails(self):
        naming,witness,_=self.analyze()
        first=witness.witnesses[0]
        for changed in (
            replace(first,line=300),
            replace(first,name="forged_field"),
            replace(first,producer="pretend-mapper"),
        ):
            with self.subTest(changed=changed),self.assertRaises(FieldMappingError):
                evaluate_directional_fields(naming,replace(
                    witness,witnesses=(changed,*witness.witnesses[1:])),self.profile)
        with self.assertRaises(FieldMappingError):
            evaluate_directional_fields(naming,replace(
                witness,witnesses=(first,first,*witness.witnesses[1:])),self.profile)

    def test_duplicate_contract_and_stale_digest_rejected(self):
        document=dict(schema_version="0.1",
                      profile_id="codeqa.naming.directional-fields.v0.1",
                      schema_path=self.profile.schema_path,
                      schema_sha256=self.profile.schema_sha256,
                      provider=self.profile.provider,
                      revision=self.profile.revision,
                      bindings=[
                          dict(path=b.path,owner=b.owner,field=b.field,
                               schema_model=b.schema_model)
                          for b in self.profile.bindings
                      ])
        document["bindings"].append(document["bindings"][0])
        with self.assertRaises(FieldMappingError):
            FieldMappingProfile.from_mapping(document)
        _,w,_=self.analyze()
        with self.assertRaises(FieldMappingError):
            evaluate_directional_fields(
                self.analyze()[0],replace(w,schema_sha256="0"*64),self.profile)

    def test_determinism(self):
        self.assertEqual(self.analyze()[2].to_document(),
                         self.analyze()[2].to_document())


if __name__=="__main__":
    unittest.main()
