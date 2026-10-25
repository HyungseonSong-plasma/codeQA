"""Target-owned Samuel codeQA #92 executor gate.

This module is deliberately independently implemented in codeQA. It does
not trust dispatch JSON or source Issue text as mutation authority.
The target-side policy is DISABLED until a separate owner-reviewed approval.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Any, Mapping

SOURCE = "HyungseonSong-plasma/chatgpt-operation"
TARGET = "HyungseonSong-plasma/codeQA"
WORK_ID = "github:HyungseonSong-plasma/codeQA:issue:92"
SOURCE_RUN_WORKFLOW = ".github/workflows/samuel-codeqa-foreign-cycle.yml"
TARGET_WORKFLOW = ".github/workflows/samuel-codeqa-issue-execute.yml"
LEDGER_MARKER = "<!-- samuel-codeqa-foreign-work-ledger-v1 -->"
HEAD_BRANCH = "samuel/92-governed-implementation"
BASE_SHA = "b48b50e00e0be6dd2b66181a8deed046a2c18ce0"
BOT_ID = 41898282
SOURCE_OWNER = "HyungseonSong-plasma"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA64 = re.compile(r"^[0-9a-f]{64}$")
ALLOWED_TARGET_PREFIXES = (
    "fixtures/python-sdk/",
    "src/codeqa/evaluation/",
    "tests/test_samuel_issue92_",
    "docs/python-sdk-",
)
FORBIDDEN_TARGET_PREFIXES = (
    ".github/", "automation/", "contracts/", "profiles/", "skills/",
    "src/codeqa/governance/",
)


class TargetExecutionError(ValueError):
    pass


def _sha(obj: Any, size: int) -> bool:
    return isinstance(obj, str) and bool((SHA40 if size == 40 else SHA64).fullmatch(obj))


def _hash_action_plan(plan: Mapping[str, Any]) -> str:
    semantics = {
        key: plan[key] for key in (
            "research_id", "stage", "executor", "payload", "expected_observation"
        )
    }
    return sha256(json.dumps(
        semantics, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()


def load_ledger(comments: Any) -> dict[str, Any]:
    if not isinstance(comments, list):
        raise TargetExecutionError("untrusted source ledger inventory")
    match = [
        c for c in comments if isinstance(c, dict)
        and LEDGER_MARKER in str(c.get("body", ""))
    ]
    if len(match) != 1:
        raise TargetExecutionError("missing or ambiguous source ledger")
    record = match[0]
    user = record.get("user")
    if (not isinstance(user, dict)
        or user.get("login") != "github-actions[bot]"
        or user.get("id") != BOT_ID):
        raise TargetExecutionError("source ledger author not trusted")
    body = record.get("body", "")
    start = LEDGER_MARKER + "\n~~~json\n"
    if not body.startswith(start) or not body.endswith("\n~~~"):
        raise TargetExecutionError("malformed source ledger envelope")
    try:
        data = json.loads(body[len(start):-4])
    except (ValueError, TypeError) as exc:
        raise TargetExecutionError("source ledger is not canonical JSON") from exc
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise TargetExecutionError("wrong source ledger schema")
    return data


@dataclass(frozen=True)
class ValidatedTargetAction:
    source_run_id: int
    base_sha: str
    action_id: str
    action: str
    path: str
    branch: str
    expected_sha: str | None
    desired_content: str


def validate_target_execution(
    *,
    source_run: Mapping[str, Any],
    source_issue: Mapping[str, Any],
    target_issue: Mapping[str, Any],
    source_comments: Any,
    target_policy: Mapping[str, Any],
    plan: Mapping[str, Any],
    source_run_id: int,
    requested_action_id: str,
    requested_base_sha: str,
    target_main_sha: str,
    target_workflow_run: Mapping[str, Any],
) -> ValidatedTargetAction:
    """Check independent source/target facts before allowing any API write."""
    if (not isinstance(target_policy, Mapping)
        or set(target_policy) != {
            "schema_version", "policy_id", "enabled", "repository",
            "repository_id", "base_branch", "base_sha", "head_branch",
            "path_prefixes", "operations", "merge_enabled",
        }
        or target_policy.get("schema_version") != 1
        or target_policy.get("policy_id") != "codeqa-samuel-issue92-target-executor-v1"
        or target_policy.get("enabled") is not True
        or target_policy.get("repository") != TARGET
        or target_policy.get("repository_id") != 1424293498
        or target_policy.get("base_branch") != "main"
        or target_policy.get("base_sha") != BASE_SHA
        or target_policy.get("head_branch") != HEAD_BRANCH
        or target_policy.get("path_prefixes") != list(ALLOWED_TARGET_PREFIXES)
        or target_policy.get("operations") != ["file.create", "file.update", "pr.create"]
        or target_policy.get("merge_enabled") is not False):
        raise TargetExecutionError("target policy disabled or not exactly approved")
    if (target_main_sha != BASE_SHA
        or requested_base_sha != BASE_SHA
        or not _sha(target_main_sha, 40)):
        raise TargetExecutionError("target main changed or base SHA was not pinned")
    if (type(source_run_id) is not int or source_run_id <= 0
        or not isinstance(source_run, Mapping)
        or source_run.get("id") != source_run_id
        or source_run.get("event") != "workflow_dispatch"
        or source_run.get("head_branch") != "main"
        or not _sha(source_run.get("head_sha"), 40)
        or source_run.get("path") not in (
            SOURCE_RUN_WORKFLOW, SOURCE_RUN_WORKFLOW + "@refs/heads/main",
        )
        or source_run.get("status") != "completed"
        or source_run.get("conclusion") != "success"
        or source_run.get("repository", {}).get("full_name") != SOURCE
        or source_run.get("actor", {}).get("login") != SOURCE_OWNER):
        raise TargetExecutionError("originating source workflow is not attested")
    if (not isinstance(target_workflow_run, Mapping)
        or target_workflow_run.get("event") != "workflow_dispatch"
        or target_workflow_run.get("head_branch") != "main"
        or target_workflow_run.get("head_sha") != BASE_SHA
        or target_workflow_run.get("path") not in (
            TARGET_WORKFLOW, TARGET_WORKFLOW + "@refs/heads/main",
        )
        or target_workflow_run.get("actor", {}).get("login") != SOURCE_OWNER
        or target_workflow_run.get("repository", {}).get("full_name") != TARGET):
        raise TargetExecutionError("target workflow execution identity not attested")
    for issue, repository, number in (
        (source_issue, SOURCE, 220),
        (target_issue, TARGET, 92),
    ):
        if (not isinstance(issue, Mapping)
            or type(issue.get("number")) is not int
            or issue["number"] != number
            or issue.get("state") != "open"
            or issue.get("pull_request") is not None
            or issue.get("url") != f"https://api.github.com/repos/{repository}/issues/{number}"):
            raise TargetExecutionError("source or target Issue identity invalid")
    ledger = load_ledger(source_comments)
    if (ledger.get("work_id") != WORK_ID
        or ledger.get("phase") not in {"dispatch_ready", "dispatched"}
        or ledger.get("base_sha") != BASE_SHA
        or not _sha(ledger.get("issue_sha"), 64)
        or not _sha(ledger.get("criteria_sha"), 64)
        or ledger.get("admission_run_id") != source_run_id
        or type(ledger.get("revision")) is not int
        or ledger.get("revision") < 2
        or ledger.get("action_id") != requested_action_id
        or not _sha(requested_action_id, 64)
        or not isinstance(ledger.get("action_plan"), dict)
        or ledger["action_plan"] != plan):
        raise TargetExecutionError("unapproved, stale or modified Controller action")
    if (not isinstance(plan, Mapping)
        or set(plan) not in (
            {"schema_version", "research_id", "stage", "executor", "payload", "expected_observation"},
            {"schema_version", "research_id", "stage", "executor", "payload", "expected_observation", "decision_risk"},
        )
        or plan.get("schema_version") != 1
        or plan.get("research_id") != WORK_ID
        or plan.get("stage") != "execute"
        or plan.get("executor") != "repository_mutation"
        or (plan.get("decision_risk") is not None)
        or not isinstance(plan.get("expected_observation"), str)
        or not plan["expected_observation"].strip()
        or _hash_action_plan(plan) != requested_action_id):
        raise TargetExecutionError("invalid or uncorrelated typed ActionPlan")
    payload = plan.get("payload")
    if (not isinstance(payload, dict)
        or set(payload) != {
            "schema_version","repository","resource","action","target",
            "expected","desired","commit_message",
        }
        or payload.get("schema_version") != 1
        or payload.get("repository") != TARGET
        or payload.get("resource") != "file"
        or payload.get("action") not in ("create","update")
        or not isinstance(payload.get("target"), dict)
        or set(payload["target"]) != {"path", "branch"}
        or not isinstance(payload.get("expected"), dict)
        or not isinstance(payload.get("desired"), dict)
        or set(payload["desired"]) != {"content"}
        or not isinstance(payload.get("commit_message"),str)
        or not payload["commit_message"].strip()):
        raise TargetExecutionError("unsupported or overly broad target mutation")
    path = payload["target"]["path"]
    branch = payload["target"]["branch"]
    if (not isinstance(path, str)
        or not path or path.startswith("/")
        or "\\" in path
        or any(x in ("", ".", "..") for x in path.split("/"))
        or not path.startswith(ALLOWED_TARGET_PREFIXES)
        or path.startswith(FORBIDDEN_TARGET_PREFIXES)
        or branch != HEAD_BRANCH):
        raise TargetExecutionError("target file or branch outside approved bounds")
    content = payload["desired"]["content"]
    if (not isinstance(content,str) or not content.strip()
        or len(content.encode("utf-8")) > 32_768):
        raise TargetExecutionError("file mutation content is missing or too large")
    if payload["action"] == "create":
        if payload["expected"] != {"absent": True}:
            raise TargetExecutionError("create requires an absent-file precondition")
        expected_sha = None
    else:
        if set(payload["expected"]) != {"sha"} or not _sha(payload["expected"]["sha"],40):
            raise TargetExecutionError("update requires exact content SHA")
        expected_sha = payload["expected"]["sha"]
    return ValidatedTargetAction(
        source_run_id,BASE_SHA,requested_action_id,payload["action"],
        path,branch,expected_sha,content,
    )
