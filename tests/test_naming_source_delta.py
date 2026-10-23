"""#75 bounded naming delta; no automatic rename or score inference."""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator

from codeqa.adapters.python_snapshot import parse_python_snapshot
from codeqa.adapters.python_naming import extract_python_naming
from codeqa.core.naming import NamingProfile
from codeqa.evaluation.naming_source_delta import (
    NamingDeltaError,NamingDeltaManifest,compare_naming_snapshots,
)
from codeqa.infrastructure.resources import ResourceRegistry


ROOT=Path(__file__).resolve().parents[1]
PREFIX="git:owner/repo@"
FIRST=PREFIX+"a"*40
SECOND=PREFIX+"b"*40
MOOSE="git:HyungseonSong-plasma/moose-test-repo@"
MOOSE_BASE=MOOSE+"69be07aab3e5815a1670f7308deb6caf6b49bc79"
MOOSE_GUIDED=MOOSE+"d8e8d5e2d5154d907953699644263b1dba681be6"


class NamingSourceDeltaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        registry=ResourceRegistry(ROOT)
        cls.profile=NamingProfile.from_mapping(
            registry.load_json("python_naming_safe_profile"))
        cls.schema=registry.load_json("naming_source_delta_schema")
        Draft202012Validator.check_schema(cls.schema)

    def observe(self,sources,snapshot):
        parsed=parse_python_snapshot(sources)
        return extract_python_naming(parsed,sources,snapshot_id=snapshot)

    def manifest(self,**changes):
        data=dict(schema_version="0.1",baseline_snapshot_id=FIRST,
                  candidate_snapshot_id=SECOND,
                  profile_fingerprint=self.profile.fingerprint(),
                  path_renames=[],symbol_renames=[])
        data.update(changes)
        return NamingDeltaManifest.from_mapping(data)

    def compare(self,a,b,*,manifest=None,snap_before=FIRST,snap_after=SECOND):
        base=self.observe(a,snap_before)
        cand=self.observe(b,snap_after)
        policy=manifest or self.manifest(
            baseline_snapshot_id=snap_before,candidate_snapshot_id=snap_after)
        result=compare_naming_snapshots(
            base,cand,a,b,profile=self.profile,manifest=policy)
        Draft202012Validator(self.schema).validate(result.to_document())
        return result

    def test_explicit_rename_resolves_one_review_but_not_global_quality(self):
        a={"src/model.py":"def BadName(param_value): return param_value\n"}
        b={"src/model.py":"def good_name(param_value): return param_value\n"}
        renamed=dict(before_path="src/model.py",before_owner="",before_name="BadName",
                     after_path="src/model.py",after_owner="",after_name="good_name",
                     kind="function")
        result=self.compare(a,b,manifest=self.manifest(symbol_renames=[renamed]))
        self.assertEqual(result.status,"COMPARABLE_STATIC_DECLARATIONS")
        self.assertEqual(result.baseline_reviews,1)
        self.assertEqual(result.candidate_reviews,0)
        match=[x for x in result.observations if x.relationship=="RENAMED_DECLARED"]
        self.assertEqual(len(match),1)
        self.assertEqual(match[0].review_status_change,"RESOLVED_REVIEW")
        self.assertIn("NOT_PROVEN",result.interpretation)
        self.assertEqual(self.compare(a,b).status,"COMPARABLE_STATIC_DECLARATIONS")
        self.assertFalse(any(x.relationship=="RENAMED_DECLARED"
                             for x in self.compare(a,b).observations))

    def test_added_extracted_helper_is_not_hidden_as_semantic_rename(self):
        a={"src/app.py":"def parent(value): return value\n"}
        b={"src/app.py":"def parent(value): return helper_new(value)\n"
                        "def helper_new(value): return value\n"}
        result=self.compare(a,b)
        self.assertEqual(result.status,"COMPARABLE_STATIC_DECLARATIONS")
        self.assertGreater(result.candidate_symbol_count,result.baseline_symbol_count)
        self.assertTrue(any(x.relationship=="ADDED" and x.after_name=="helper_new"
                            for x in result.observations))
        self.assertEqual(result.baseline_reviews,0)
        self.assertEqual(result.candidate_reviews,0)

    def test_exact_source_backed_path_rename_and_module_name_change(self):
        source="def helper(value): return value\n"
        a={"old_pkg/old_model.py":source}
        b={"new_pkg/new_model.py":source}
        digest=sha256(source.encode()).hexdigest()
        path=dict(before="old_pkg/old_model.py",after="new_pkg/new_model.py",
                  before_sha256=digest,after_sha256=digest)
        renamed=dict(before_path=path["before"],before_owner="",
                     before_name="old_model",after_path=path["after"],
                     after_owner="",after_name="new_model",kind="module")
        report=self.compare(a,b,manifest=self.manifest(
            path_renames=[path],symbol_renames=[renamed]))
        self.assertEqual(report.status,"COMPARABLE_STATIC_DECLARATIONS")
        self.assertTrue(any(x.relationship=="RENAMED_DECLARED" and x.kind=="module"
                            for x in report.observations))
        self.assertEqual(report.baseline_symbol_count,report.candidate_symbol_count)
        self.assertEqual(self.compare(a,b).status,"NOT_COMPARABLE")
        with self.assertRaises(NamingDeltaError):
            self.compare(a,b,manifest=self.manifest(
                path_renames=[dict(path,before_sha256="0"*64)]))

    def test_incomplete_parsing_and_unresolved_imports_are_not_comparable(self):
        parsed=self.compare({"src/a.py":"def ("},
                            {"src/a.py":"def helper(): pass\n"})
        self.assertEqual(parsed.status,"NOT_COMPARABLE")
        self.assertIn("incomplete_selected_source_parsing",parsed.reasons)
        self.assertEqual(parsed.observations,())
        base={"src/a.py":"from sdk import Base\nclass Child(Base):\n"
                         "    def WeirdHook(self): pass\n"}
        cand={"src/a.py":base["src/a.py"]+"\ndef new_helper(): pass\n"}
        report=self.compare(base,cand)
        self.assertEqual(report.status,"NOT_COMPARABLE")
        self.assertIn("unresolved_external_interface_or_symbol_bindings",report.reasons)
        self.assertEqual(report.observations,())

    def test_same_source_other_git_revision_does_not_imply_change(self):
        a={"src/model.py":"def valid_name(): pass\n"}
        report=self.compare(a,a)
        self.assertEqual(report.status,"NOT_COMPARABLE")
        self.assertIn("unchanged_selected_source_bytes",report.reasons)
        self.assertEqual(report.observations,())

    def test_wrong_revision_repo_profile_and_forged_mapping_are_rejected(self):
        a={"src/a.py":"def before(): pass\n"}
        b={"src/a.py":"def after(): pass\n"}
        for wrong in (
            self.manifest(profile_fingerprint="0"*64),
            self.manifest(candidate_snapshot_id=PREFIX+"c"*40),
        ):
            with self.subTest(wrong=wrong),self.assertRaises(NamingDeltaError):
                self.compare(a,b,manifest=wrong)
        with self.assertRaises(NamingDeltaError):
            self.compare(a,b,snap_after="git:another/repo@"+"b"*40)
        unsupported=dict(before_path="src/a.py",before_owner="",
                         before_name="invented",after_path="src/a.py",
                         after_owner="",after_name="after",kind="function")
        with self.assertRaises(NamingDeltaError):
            self.compare(a,b,manifest=self.manifest(symbol_renames=[unsupported]))

    def test_unchanged_file_bytes_with_contradictory_relation_fail_closed(self):
        sources={"src/model.py":"def good_name(): pass\n"}
        a=self.observe(sources,FIRST)
        b=self.observe(sources,SECOND)
        one=next(x for x in b.symbols if x.kind=="function")
        corrupted=replace(b,symbols=tuple(
            replace(x,relation="LOCAL_OVERRIDE_MATCH") if x==one else x
            for x in b.symbols))
        with self.assertRaises(NamingDeltaError):
            compare_naming_snapshots(
                a,corrupted,sources,sources,
                profile=self.profile,manifest=self.manifest())

    def test_real_pinned_moose_base_guided_function_population(self):
        path="physics_harness/analysis/field_comparison.py"
        original=(ROOT/"fixtures/moose-p3-refactor/base.py.txt").read_text()
        changed=(ROOT/"fixtures/moose-p3-refactor/guided.py.txt").read_text()
        result=self.compare({path:original},{path:changed},
                            snap_before=MOOSE_BASE,snap_after=MOOSE_GUIDED)
        self.assertEqual(result.status,"COMPARABLE_STATIC_DECLARATIONS")
        self.assertTrue(any(x.relationship=="ADDED" and
                            x.after_name=="_compare_scalar_row"
                            for x in result.observations))
        self.assertGreater(result.candidate_symbol_count,result.baseline_symbol_count)
        self.assertEqual(result.to_document(),self.compare(
            {path:original},{path:changed},
            snap_before=MOOSE_BASE,snap_after=MOOSE_GUIDED).to_document())

    def test_frozen_delta_schema_unchanged(self):
        resource=ResourceRegistry(ROOT)
        self.assertEqual(resource.load_json("qa_delta_v02_schema")["$id"],
                         "urn:codeqa:qa:delta:v0.2")
        self.assertEqual(resource.load_json("naming_report_schema")["$id"],
                         "urn:codeqa:qa:naming:v0.1")


if __name__=="__main__":
    unittest.main()
