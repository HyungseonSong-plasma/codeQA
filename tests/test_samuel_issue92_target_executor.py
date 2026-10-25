"""Negative controls for target-owned codeQA #92 mutation admission."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import unittest

from codeqa.governance.samuel_issue_executor import (
    BASE_SHA, HEAD_BRANCH, SOURCE, TARGET, WORK_ID, LEDGER_MARKER,
    ALLOWED_TARGET_PREFIXES, TargetExecutionError,
    load_ledger, validate_target_execution,
)


def plan(path="fixtures/python-sdk/samuel-issue92-contract.py",
         branch=HEAD_BRANCH):
    return {
        "schema_version":1,"research_id":WORK_ID,"stage":"execute",
        "executor":"repository_mutation",
        "payload":{
            "schema_version":1,"repository":TARGET,
            "resource":"file","action":"create",
            "target":{"path":path,"branch":branch},
            "expected":{"absent":True},
            "desired":{"content":"# A reviewed Python SDK fixture, not arbitrary code execution.\n"},
            "commit_message":"test(#92): add versioned external contract fixture",
        },
        "expected_observation":"Independent Draft PR and exact HEAD CI",
    }


def action_id(p):
    x={k:p[k] for k in (
        "research_id","stage","executor","payload","expected_observation"
    )}
    return hashlib.sha256(json.dumps(
        x,sort_keys=True,separators=(",", ":"),ensure_ascii=False
    ).encode()).hexdigest()


def policy(enabled=True):
    return {
        "schema_version":1,
        "policy_id":"codeqa-samuel-issue92-target-executor-v1",
        "enabled":enabled,"repository":TARGET,"repository_id":1424293498,
        "base_branch":"main","base_sha":BASE_SHA,
        "head_branch":HEAD_BRANCH,"path_prefixes":list(ALLOWED_TARGET_PREFIXES),
        "operations":["file.create","file.update","pr.create"],
        "merge_enabled":False,
    }


def origin():
    return {
        "id":40233488526,"event":"workflow_dispatch",
        "head_branch":"main",
        "head_sha":"03bdbc1b694f8c963d526cac2d2aca78edfc43ea",
        "status":"completed","conclusion":"success",
        "path":".github/workflows/samuel-codeqa-foreign-cycle.yml",
        "actor":{"login":"HyungseonSong-plasma"},
        "repository":{"full_name":SOURCE},
    }


def target_run():
    return {
        "id":3,"event":"workflow_dispatch","head_branch":"main",
        "head_sha":BASE_SHA,
        "path":".github/workflows/samuel-codeqa-issue-execute.yml",
        "actor":{"login":"HyungseonSong-plasma"},
        "repository":{"full_name":TARGET},
    }


ISSUE92_BODY="## Acceptance\\n- Require pinned external SDK consumer evidence\\n"


def issue(repo,number):
    return {
        "number":number,"state":"open",
        "body":ISSUE92_BODY if repo==TARGET else "Controller policy Issue",
        "url":f"https://api.github.com/repos/{repo}/issues/{number}",
    }


def comments(p=None,*,phase="dispatch_ready",author="github-actions[bot]",
             user_id=41898282):
    p=p or plan()
    ledger={
        "schema_version":1,"work_id":WORK_ID,
        "phase":phase,"revision":2,"admission_run_id":40233488526,
        "base_sha":BASE_SHA,"issue_sha":hashlib.sha256(ISSUE92_BODY.encode()).hexdigest(),"criteria_sha":"b"*64,
        "action_plan":p,"action_id":action_id(p),
        "receipt":None,"target_pr":None,"ci_evidence":[],
        "last_failure":None,
    }
    return [{
        "id":50,"user":{"login":author,"id":user_id},
        "body":LEDGER_MARKER+"\n~~~json\n"+
            json.dumps(ledger,sort_keys=True,separators=(",",":"))+"\n~~~",
    }]


def params(p=None):
    p=p or plan()
    return {
        "source_run":origin(),"source_issue":issue(SOURCE,220),
        "target_issue":issue(TARGET,92),
        "source_comments":comments(p),
        "target_policy":policy(),
        "plan":p,"source_run_id":40233488526,
        "requested_action_id":action_id(p),
        "requested_base_sha":BASE_SHA,
        "target_main_sha":BASE_SHA,
        "target_workflow_run":target_run(),
    }


class TargetExecutorTests(unittest.TestCase):
    def test_canonical_source_ledger_and_exact_single_file_action(self):
        args=params()
        result=validate_target_execution(**args)
        self.assertEqual(result.path,"fixtures/python-sdk/samuel-issue92-contract.py")
        self.assertEqual(result.action_id,args["requested_action_id"])
        self.assertEqual(result.source_run_id,40233488526)
        self.assertEqual(result.action,"create")
        self.assertIsNone(result.expected_sha)
        self.assertEqual(load_ledger(args["source_comments"])["revision"],2)

    def test_disabled_target_policy_prevents_any_mutation(self):
        args=params()
        args["target_policy"]["enabled"]=False
        with self.assertRaisesRegex(TargetExecutionError,"policy disabled"):
            validate_target_execution(**args)

    def test_no_broadening_policy_fields_or_paths(self):
        for k,v in [
            ("merge_enabled",True),("repository",SOURCE),
            ("repository_id",1),("base_sha","c"*40),
            ("head_branch","main"),("operations",["file.create","pr.merge"]),
            ("path_prefixes",["src/"]),("enabled",False),
        ]:
            with self.subTest(field=k):
                a=params()
                a["target_policy"][k]=v
                with self.assertRaisesRegex(TargetExecutionError,"policy"):
                    validate_target_execution(**a)

    def test_untrusted_source_run_actor_path_or_event_rejected(self):
        for k,v in [
            ("id",15),("event","pull_request"),
            ("head_branch","develop"),("status","in_progress"),
            ("conclusion","failure"),
            ("actor",{"login":"attacker"}),
            ("path",".github/workflows/samuel-codeqa-write-execute.yml"),
            ("repository",{"full_name":TARGET}),
        ]:
            with self.subTest(field=k):
                a=params()
                a["source_run"][k]=v
                with self.assertRaisesRegex(TargetExecutionError,"originating"):
                    validate_target_execution(**a)

    def test_target_workflow_and_target_sha_cannot_be_spoofed(self):
        for k,v in [
            ("event","pull_request"),("head_branch","other"),
            ("head_sha","e"*40),("actor",{"login":"attacker"}),
            ("path",".github/workflows/layout.yml"),
            ("repository",{"full_name":SOURCE}),
        ]:
            with self.subTest(field=k):
                a=params()
                a["target_workflow_run"][k]=v
                with self.assertRaisesRegex(TargetExecutionError,"target workflow"):
                    validate_target_execution(**a)
        a=params()
        a["target_main_sha"]="c"*40
        with self.assertRaisesRegex(TargetExecutionError,"main changed"):
            validate_target_execution(**a)

    def test_source_ledger_is_independent_authority(self):
        bad=[
            comments(author="random"),
            comments(user_id=18),
            comments(phase="reasoning_required"),
            [],
            comments()+comments(),
        ]
        for ls in bad:
            with self.subTest(comments=ls):
                a=params()
                a["source_comments"]=ls
                with self.assertRaises(TargetExecutionError):
                    validate_target_execution(**a)
        a=params()
        a["source_comments"][0]["body"]="malformed"
        with self.assertRaises(TargetExecutionError):
            validate_target_execution(**a)

    def test_changed_live_issue_body_denies_stale_ledger_plan(self):
        a=params()
        a["target_issue"]["body"]+="\n- New unreviewed requirement"
        with self.assertRaisesRegex(TargetExecutionError,"content changed"):
            validate_target_execution(**a)

    def test_action_id_is_immutable_and_plan_cannot_be_substituted(self):
        a=params()
        a["requested_action_id"]="b"*64
        with self.assertRaises(TargetExecutionError):
            validate_target_execution(**a)
        a=params()
        a["plan"]["payload"]["desired"]["content"]="malicious replacement"
        with self.assertRaises(TargetExecutionError):
            validate_target_execution(**a)
        a=params()
        a["source_run_id"]=1234
        with self.assertRaises(TargetExecutionError):
            validate_target_execution(**a)

    def test_reject_source_workflow_token_or_arbitrary_paths(self):
        for path in [
            ".github/workflows/write.yml",
            "automation/samuel/policy.json",
            "profiles/rules.json",
            "contracts/qa/schema.json",
            "src/codeqa/governance/unsafe.py",
            "tests/test_other.py",
            "src/../.github/workflows/evil.yml",
            "fixtures/python-sdk/../../src/codeqa/evaluation/a.py",
            "/fixtures/python-sdk/not-relative.py",
            "README.md",
        ]:
            with self.subTest(path=path):
                a=params(plan(path=path))
                with self.assertRaisesRegex(TargetExecutionError,"target file"):
                    validate_target_execution(**a)

    def test_fails_closed_on_issue_and_unsafe_file_update(self):
        a=params()
        a["target_issue"]["state"]="closed"
        with self.assertRaisesRegex(TargetExecutionError,"Issue identity"):
            validate_target_execution(**a)
        p=plan()
        p["payload"]["action"]="update"
        p["payload"]["expected"]={"sha":"c"*40}
        a=params(p)
        result=validate_target_execution(**a)
        self.assertEqual(result.expected_sha,"c"*40)
        p["payload"]["expected"]={"absent":True}
        with self.assertRaises(TargetExecutionError):
            validate_target_execution(**params(p))

    def test_large_payload_needs_bounded_content(self):
        p=plan()
        p["payload"]["desired"]["content"]="x"*35000
        with self.assertRaisesRegex(TargetExecutionError,"too large"):
            validate_target_execution(**params(p))
