#!/usr/bin/env python3
"""codeQA-owned, fail-closed Samuel Issue #92 mutation and Draft PR runner.

A codeQA Actions GITHUB_TOKEN does target writes. No Samuel-supplied token,
Issue text, PR metadata, or workflow dispatch alone is accepted as authority.
The checked-in codeQA target policy is DISABLED by default.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from codeqa.governance.samuel_issue_executor import (
    BASE_SHA, HEAD_BRANCH, SOURCE, TARGET, TargetExecutionError,
    validate_target_execution,
)

POLICY_FILE=Path("profiles/samuel-issue92-target-executor-v1.json")
RECEIPT_FILE=Path("samuel-issue92-target-execution-receipt.json")
ISSUE_ID=92


class APIError(RuntimeError):
    def __init__(self, status: int):
        self.status=status
        super().__init__("GitHub API request denied")


class API:
    def __init__(self, token: str):
        if not token:
            raise TargetExecutionError("missing target-owned Actions credential")
        self.token=token

    def call(self, method: str, path: str, payload: dict | None=None):
        raw=None if payload is None else json.dumps(payload).encode("utf-8")
        req=Request("https://api.github.com"+path,method=method,data=raw,
                    headers={"Accept":"application/vnd.github+json",
                             "Authorization":"Bearer "+self.token,
                             "X-GitHub-Api-Version":"2022-11-28",
                             "Content-Type":"application/json",
                             "User-Agent":"codeqa-target-samuel-executor"})
        try:
            with urlopen(req,timeout=30) as response:
                content=response.read()
                return json.loads(content) if content else {}
        except HTTPError as exc:
            # Never serialize server response, headers, input plan or token.
            raise APIError(exc.code) from None

    def get(self, path: str):
        return self.call("GET",path)


def run() -> dict:
    env=os.environ
    if (env.get("GITHUB_ACTIONS")!="true"
        or env.get("GITHUB_REPOSITORY")!=TARGET
        or env.get("GITHUB_REF")!="refs/heads/main"
        or env.get("GITHUB_EVENT_NAME")!="workflow_dispatch"
        or env.get("GITHUB_ACTOR")!="HyungseonSong-plasma"
        or not env.get("GITHUB_RUN_ID","").isdigit()):
        raise TargetExecutionError("not a mainline target-owner dispatch")
    policy=json.loads(POLICY_FILE.read_text())
    if policy.get("enabled") is not True:
        raise TargetExecutionError("target issue execution policy disabled")
    source_run_id_str=env.get("INPUT_SOURCE_RUN_ID","")
    if not source_run_id_str.isdecimal() or int(source_run_id_str)<1:
        raise TargetExecutionError("missing numeric source origin")
    source_run_id=int(source_run_id_str)
    action_id=env.get("INPUT_SAMUEL_ACTION_ID","")
    base_sha=env.get("INPUT_BASE_SHA","")
    plan_str=env.get("INPUT_PLAN_JSON","")
    if len(plan_str)>60000:
        raise TargetExecutionError("input plan size limit exceeded")
    plan=json.loads(plan_str)
    if not isinstance(plan,dict):
        raise TargetExecutionError("untyped ActionPlan input")

    api=API(env.get("GITHUB_TOKEN",""))
    s="/repos/"+SOURCE
    t="/repos/"+TARGET
    first=api.get(s+"/issues/220/comments?per_page=100&page=1")
    second=api.get(s+"/issues/220/comments?per_page=100&page=2")
    if not isinstance(first,list) or not isinstance(second,list) or second:
        raise TargetExecutionError("source ledger enumeration incomplete")
    target_run=api.get(t+"/actions/runs/"+env["GITHUB_RUN_ID"])
    verified=validate_target_execution(
        source_run=api.get(s+"/actions/runs/"+str(source_run_id)),
        source_issue=api.get(s+"/issues/220"),
        target_issue=api.get(t+"/issues/92"),
        source_comments=first,
        target_policy=policy,
        plan=plan,source_run_id=source_run_id,
        requested_action_id=action_id,requested_base_sha=base_sha,
        target_main_sha=api.get(t+"/git/ref/heads/main")["object"]["sha"],
        target_workflow_run=target_run,
    )
    result={
        "schema_version":1,"status":"IN_PROGRESS",
        "work_id":plan["research_id"],
        "action_id":verified.action_id,
        "source_run_id":source_run_id,
        "base_sha":BASE_SHA,
        "target_repository":TARGET,
        "operations":[],
        "merge_performed":False,
    }
    def record():
        RECEIPT_FILE.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    record()
    # Branch creation is conditional on a pinned immutable base SHA.
    ref_path=t+"/git/ref/heads/"+quote(HEAD_BRANCH,safe="")
    try:
        existing_ref=api.get(ref_path)
    except APIError as exc:
        if exc.status!=404:
            raise
        existing_ref=None
    if existing_ref is None:
        api.call("POST",t+"/git/refs",{
            "ref":"refs/heads/"+HEAD_BRANCH,"sha":BASE_SHA,
        })
        result["operations"].append("branch_created")
        record()
    # Existing branch is allowed only if its entire base/head diff was
    # created by this exact single-file ActionPlan. This supports retries
    # after a partial GitHub API failure without widening the change.
    file_url=t+"/contents/"+quote(verified.path,safe="/")
    try:
        current=api.get(file_url+"?ref="+quote(HEAD_BRANCH,safe=""))
    except APIError as exc:
        if exc.status!=404:
            raise
        current=None
    if verified.action=="create":
        if current is None:
            api.call("PUT",file_url,{
                "message":"test(#92): governed source/consumer conformance action",
                "content":base64.b64encode(verified.desired_content.encode()).decode(),
                "branch":HEAD_BRANCH,
            })
            result["operations"].append("file_created")
            record()
        else:
            original=base64.b64decode(current.get("content","")).decode("utf-8")
            if original!=verified.desired_content:
                raise TargetExecutionError("replayed create encountered different content")
    else:
        if current is None or current.get("sha")!=verified.expected_sha:
            raise TargetExecutionError("file update precondition changed")
        api.call("PUT",file_url,{
            "message":"test(#92): governed source/consumer conformance action",
            "content":base64.b64encode(verified.desired_content.encode()).decode(),
            "branch":HEAD_BRANCH,
            "sha":verified.expected_sha,
        })
        result["operations"].append("file_updated")
        record()
    actual=api.get(file_url+"?ref="+quote(HEAD_BRANCH,safe=""))
    if base64.b64decode(actual.get("content","")).decode()!=verified.desired_content:
        raise TargetExecutionError("file readback content mismatch")
    head=api.get(ref_path).get("object",{}).get("sha")
    if not isinstance(head,str) or len(head)!=40:
        raise TargetExecutionError("target branch HEAD unavailable")
    diff=api.get(t+"/compare/"+BASE_SHA+"..."+head)
    changed=diff.get("files")
    if (not isinstance(changed,list) or len(changed)!=1
        or changed[0].get("filename")!=verified.path
        or changed[0].get("status")!=(
            "added" if verified.action=="create" else "modified"
        )
        or diff.get("too_large") is True):
        raise TargetExecutionError("unauthorized base-to-head file changes detected")
    # Revalidate main has not advanced during mutation.
    if api.get(t+"/git/ref/heads/main").get("object",{}).get("sha")!=BASE_SHA:
        raise TargetExecutionError("target main advanced before Draft PR")
    title="[Samuel #220 / codeQA #92] Reviewed foreign ActionPlan conformance"
    body=(
        "Foreign codeQA Issue #92 governed ActionPlan\n\n"
        "Source run: "+str(source_run_id)+"\n"
        "Action ID: "+verified.action_id+"\n"
        "Pinned base: "+BASE_SHA+"\n"
        "One exact file: "+verified.path+"\n\n"
        "DRAFT ONLY. No merge authority or acceptance claim."
    )
    q=urlencode({"state":"open","head":"HyungseonSong-plasma:"+HEAD_BRANCH,"base":"main"})
    existing=api.get(t+"/pulls?"+q)
    if not isinstance(existing,list) or len(existing)>1:
        raise TargetExecutionError("ambiguous existing target Draft PR")
    if existing:
        pr_id=existing[0].get("number")
    else:
        created=api.call("POST",t+"/pulls",{
            "head":HEAD_BRANCH,"base":"main","draft":True,
            "title":title,"body":body,
        })
        pr_id=created.get("number")
        result["operations"].append("draft_pr_created")
        record()
    if type(pr_id) is not int:
        raise TargetExecutionError("target Draft PR identity not returned")
    pr=api.get(t+"/pulls/"+str(pr_id))
    if (pr.get("head",{}).get("sha")!=head
        or pr.get("head",{}).get("ref")!=HEAD_BRANCH
        or pr.get("head",{}).get("repo",{}).get("full_name")!=TARGET
        or pr.get("base",{}).get("ref")!="main"
        or pr.get("base",{}).get("repo",{}).get("full_name")!=TARGET
        or pr.get("draft") is not True or pr.get("merged") is True
        or pr.get("body")!=body or pr.get("title")!=title):
        raise TargetExecutionError("Draft PR independently observed identity mismatch")
    result.update({
        "status":"EXECUTED_DRAFT_PR","pr_number":pr_id,
        "head_sha":head,"file_path":verified.path,
        "source_target_workflow_run_id":int(env["GITHUB_RUN_ID"]),
        "merge_performed":False,
    })
    return result


def main() -> int:
    try:
        result=run()
        rc=0
    except Exception as exc:
        try:
            old=json.loads(RECEIPT_FILE.read_text()) if RECEIPT_FILE.exists() else {}
        except (ValueError,OSError):
            old={}
        result={
            **old,"status":"HARD_STOP","error_type":type(exc).__name__,
            "error_code":"TARGET_GITHUB_API_REJECTED" if isinstance(exc,APIError)
            else "TARGET_SCOPE_OR_EXECUTION_REJECTED",
            "merge_performed":False,
        }
        if isinstance(exc,APIError):
            result["http_status"]=exc.status
        rc=2
    RECEIPT_FILE.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print("SAMUEL_CODEQA_ISSUE92="+result["status"])
    return rc


if __name__=="__main__":
    raise SystemExit(main())
