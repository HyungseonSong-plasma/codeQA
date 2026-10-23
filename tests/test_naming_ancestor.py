"""#63 Pinned external ancestor declarations; spelling never proves dispatch."""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator

from codeqa.adapters.python_snapshot import parse_python_snapshot
from codeqa.adapters.python_naming import extract_python_naming
from codeqa.adapters.python_naming_ancestor import extract_python_pinned_ancestor_evidence
from codeqa.core.naming_ancestor import ExternalAncestorError, ExternalAncestorProfile
from codeqa.evaluation.naming_ancestor import evaluate_pinned_ancestor_names
from codeqa.infrastructure.resources import ResourceRegistry


ROOT=Path(__file__).resolve().parents[1]


class PinnedAncestorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        registry=ResourceRegistry(ROOT)
        cls.profile=ExternalAncestorProfile.from_mapping(
            registry.load_json("python_pinned_ancestor_profile"))
        cls.schema=registry.load_json("pinned_ancestor_report_schema")
        Draft202012Validator.check_schema(cls.schema)
        cls.stub_path=cls.profile.providers[0].source_path
        cls.stub=(ROOT/cls.stub_path).read_text()
        cls.externals={cls.stub_path:cls.stub}

    def analyze(self, source, *, external=None, profile=None):
        src={"main.py":source}
        parsed=parse_python_snapshot(src)
        naming=extract_python_naming(
            parsed,src,snapshot_id="git:owner/repo@"+"a"*40)
        policy=profile or self.profile
        witnesses=extract_python_pinned_ancestor_evidence(
            parsed,src,self.externals if external is None else external,
            snapshot_id=naming.snapshot_id,profile=policy)
        report=evaluate_pinned_ancestor_names(naming,witnesses,policy)
        Draft202012Validator(self.schema).validate(report.to_document())
        return naming,witnesses,report

    def test_exact_external_alias_and_inherited_name(self):
        source=("from vendor_sdk import ExternalBase as Parent\n"
                "class Child(Parent):\n"
                "    def do_something_Special(self, value):\n"
                "        return value\n"
                "    def new_helper(self):\n"
                "        return True\n")
        naming,evidence,report=self.analyze(source)
        self.assertEqual([(x.name,x.state) for x in evidence.witnesses],[
            ("do_something_Special","PINNED_MEMBER_DECLARED"),
            ("new_helper","PINNED_MEMBER_NOT_DECLARED")
        ])
        self.assertEqual(report.status,"PARTIAL")
        self.assertEqual(report.matched_direct_declarations,1)
        self.assertEqual(report.absent_in_pinned_declarations,1)
        self.assertEqual(report.findings[0].verdict,"EXEMPT_BY_PINNED_DECLARATION")
        self.assertEqual(report.findings[1].verdict,"NOT_EVALUATED")
        self.assertEqual(report.findings[0].ancestor,"vendor_sdk.ExternalBase")
        self.assertIn("does_not_verify_installed_runtime",report.findings[0].limitation)
        self.assertEqual(naming.source_sha256,evidence.source_sha256)

    def test_module_qualified_alias_is_supported(self):
        source=("import vendor_sdk as sdk\n"
                "class Child(sdk.ExternalBase):\n"
                "    async def another_API(self): return None\n")
        _,_,r=self.analyze(source)
        self.assertEqual(len(r.findings),1)
        self.assertEqual(r.findings[0].name,"another_API")
        self.assertEqual(r.findings[0].verdict,"EXEMPT_BY_PINNED_DECLARATION")

    def test_override_decorator_intent_alone_is_not_proof(self):
        source=("from typing import override\n"
                "from vendor_sdk import ExternalBase\n"
                "class Child(ExternalBase):\n"
                "    @override\n"
                "    def MissingInStub(self): pass\n")
        _,_,r=self.analyze(source)
        self.assertEqual(r.findings[0].verdict,"NOT_EVALUATED")
        self.assertEqual(r.absent_in_pinned_declarations,1)

    def test_ambiguous_source_binding_does_not_exempt(self):
        sources=[
            ("from vendor_sdk import ExternalBase\n"
             "ExternalBase = dynamic_base\n"
             "class Child(ExternalBase):\n"
             "    def do_something_Special(self): pass\n"),
            ("from vendor_sdk import ExternalBase\n"
             "class ExternalBase: pass\n"
             "class Child(ExternalBase):\n"
             "    def do_something_Special(self): pass\n"),
            ("from vendor_sdk import ExternalBase\n"
             "class Child(ExternalBase, object):\n"
             "    def do_something_Special(self): pass\n"),
            ("from vendor_sdk import ExternalBase\n"
             "class Child(ExternalBase, metaclass=Meta):\n"
             "    def do_something_Special(self): pass\n"),
            ("from vendor_sdk import ExternalBase\n"
             "@class_factory\n"
             "class Child(ExternalBase):\n"
             "    def do_something_Special(self): pass\n"),
            ("from vendor_sdk import ExternalBase\n"
             "class Child(dynamic_factory(ExternalBase)):\n"
             "    def do_something_Special(self): pass\n"),
        ]
        for source in sources:
            with self.subTest(source=source):
                _,_,r=self.analyze(source)
                self.assertFalse(r.findings)
                self.assertEqual(r.status,"NOT_EVALUATED")

    def test_provider_bytes_hash_and_version_fail_closed(self):
        source=("from vendor_sdk import ExternalBase\n"
                "class Child(ExternalBase):\n"
                "    def do_something_Special(self): pass\n")
        bad_external={self.stub_path:self.stub.replace("another_API","other_API")}
        with self.assertRaises(ExternalAncestorError):
            self.analyze(source,external=bad_external)
        wrong = replace(self.profile.providers[0],revision="other")
        other_policy = replace(self.profile,providers=(wrong,))
        naming,evidence,_=self.analyze(source)
        with self.assertRaises(ExternalAncestorError):
            evaluate_pinned_ancestor_names(naming,evidence,other_policy)

    def test_forged_member_line_method_and_duplicate_rejected(self):
        source=("from vendor_sdk import ExternalBase\n"
                "class Child(ExternalBase):\n"
                "    def do_something_Special(self): pass\n")
        naming,evidence,_=self.analyze(source)
        original=evidence.witnesses[0]
        for value in (
            replace(original,line=999),
            replace(original,name="Imaginary"),
            replace(original,external_source_sha256="0"*64),
            replace(original,external_declaration_line=None),
        ):
            with self.subTest(value=value), self.assertRaises(ExternalAncestorError):
                evaluate_pinned_ancestor_names(
                    naming,replace(evidence,witnesses=(value,)),self.profile)
        with self.assertRaises(ExternalAncestorError):
            evaluate_pinned_ancestor_names(
                naming,replace(evidence,witnesses=(original,original)),self.profile)

    def test_dynamic_stub_inheritance_is_unknown_not_verified(self):
        source=("from vendor_sdk import ExternalBase\n"
                "class Child(ExternalBase):\n"
                "    def do_something_Special(self): pass\n")
        stub=self.stub.replace("class ExternalBase:", "class ExternalBase(UnknownParent):")
        updated=replace(self.profile.providers[0],source_sha256=sha256(stub.encode()).hexdigest())
        policy=replace(self.profile,providers=(updated,))
        with self.assertRaises(ExternalAncestorError):
            self.analyze(source,external={self.stub_path:stub},profile=policy)

    def test_empty_and_deterministic_reports(self):
        source="def standalone(): return 1\n"
        a=self.analyze(source)[2].to_document()
        b=self.analyze(source)[2].to_document()
        self.assertEqual(a,b)
        self.assertEqual(a["status"],"NOT_EVALUATED")
        self.assertEqual(a["matched_direct_declarations"],0)


if __name__=="__main__":
    unittest.main()
