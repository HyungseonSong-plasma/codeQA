"""Fail-closed codeQA target admission for an isolated Samuel native PR-create E2E.

Authority is local and disabled by default.  This does not classify or clear
prior external safety denials, enable cross-repo writes, or create/merge a PR.
The actual writer is the immutable central Samuel native execution kernel.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

REPOSITORY = "HyungseonSong-plasma/codeQA"
SOURCE = "HyungseonSong-plasma/chatgpt-operation"
PIN = "b56b6cdc0d24f9a50e23165503ca6a4bbd70a771"
POLICY_ID = "codeqa-samuel-native-pr-create-e2e-v1"
ISSUE = 156
FIXTURE = "docs/samuel-native-pr-e2e-fixture.md"
BRANCH_PATTERN = r"^samuel/native-pr-create-e2e-156-[0-9]{8}$"
LABEL = "native-pr-e2e-authorized"
ACTOR = "HyungseonSong-plasma"


class NativePrE2EError(ValueError):
    """No authorization or insufficient exact-identity evidence."""


def _require(test: bool, reason: str) -> None:
    if not test:
        raise NativePrE2EError(reason)


def _sha(value: Any) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[a-f0-9]{40}", value))


def qualify(
    policy: Mapping[str, Any],
    request: Mapping[str, Any],
    observed: Mapping[str, Any],
) -> dict[str, Any]:
    """Return one closed-world native ActionPlan; no GitHub write is performed.

    Observations must come from fresh authenticated GitHub target reads by the
    target-owned workflow, never from dispatch input or a caller's assertion.
    """
    expected_policy = {
        "schema_version": 1,
        "policy_id": POLICY_ID,
        "enabled": True,
        "repository": REPOSITORY,
        "source_repository": SOURCE,
        "source_revision": PIN,
        "issue_number": ISSUE,
        "required_issue_label": LABEL,
        "allowed_dispatch_actor": ACTOR,
        "base_branch": "main",
        "head_pattern": BRANCH_PATTERN,
        "sole_fixture_path": FIXTURE,
        "expected_changes": 1,
        "allowed_operation": "pr.create",
        "auto_merge": False,
        "require_independent_review": True,
    }
    _require(isinstance(policy, Mapping) and dict(policy) == expected_policy,
             "policy disabled, altered, or not independently approved")
    _require(isinstance(request, Mapping) and set(request) ==
             {"head", "head_sha", "base_sha"}, "invalid request fields")
    head, head_sha, base_sha = (
        request.get("head"), request.get("head_sha"), request.get("base_sha")
    )
    _require(isinstance(head, str) and re.fullmatch(BRANCH_PATTERN, head) is not None,
             "branch outside isolated E2E namespace")
    _require(_sha(head_sha) and _sha(base_sha) and head_sha != base_sha,
             "missing distinct exact head/base identities")
    _require(isinstance(observed, Mapping) and set(observed) == {
        "repository", "actor", "event", "run_ref", "run_sha",
        "source_checkout_sha", "main_sha", "branch_sha", "issue",
        "comparison", "open_prs",
    }, "incomplete live target evidence")
    _require(
        observed["repository"] == REPOSITORY and observed["actor"] == ACTOR
        and observed["event"] == "workflow_dispatch"
        and observed["run_ref"] == "refs/heads/main"
        and observed["source_checkout_sha"] == PIN,
        "wrong execution principal, target repository or immutable engine",
    )
    _require(
        observed["run_sha"] == base_sha == observed["main_sha"]
        and observed["branch_sha"] == head_sha,
        "stale exact head/base or untrusted workflow revision",
    )
    issue = observed["issue"]
    _require(isinstance(issue, Mapping) and issue.get("number") == ISSUE
             and issue.get("state") == "open"
             and issue.get("url") ==
             f"https://api.github.com/repos/{REPOSITORY}/issues/{ISSUE}",
             "scoped E2E admission Issue missing")
    labels = issue.get("labels")
    _require(isinstance(labels, list)
             and LABEL in [x.get("name") if isinstance(x, dict) else x for x in labels],
             "explicit owner-managed E2E admission label missing")
    compare = observed["comparison"]
    _require(
        isinstance(compare, Mapping)
        and compare.get("status") == "ahead"
        and compare.get("ahead_by") == 1
        and compare.get("behind_by") == 0
        and compare.get("total_commits") == 1,
        "workload branch must contain exactly one new commit from current main",
    )
    files = compare.get("files")
    _require(
        isinstance(files, list) and len(files) == 1
        and files[0].get("filename") == FIXTURE
        and files[0].get("status") == "added"
        and isinstance(files[0].get("changes"), int)
        and 0 < files[0]["changes"] <= 100,
        "isolation violation: only one bounded non-production documentation fixture permitted",
    )
    prs = observed["open_prs"]
    _require(isinstance(prs, list) and len(prs) <= 1,
             "duplicate/ambiguous head-base PR records")
    if prs:
        item = prs[0]
        _require(
            isinstance(item, Mapping) and item.get("state") == "open"
            and item.get("head", {}).get("sha") == head_sha
            and item.get("head", {}).get("ref") == head
            and item.get("base", {}).get("ref") == "main",
            "open PR is not bound to the exact target head/base",
        )
    title = "test(samuel): isolated native PR-create E2E witness #156"
    body = (
        "Isolated native-executor acceptance witness for codeQA #156.\n\n"
        "Do not merge. This is not codeQA feature acceptance, #92 authorization "
        "or #93 safety-screening clearance. CI, independent review and cleanup "
        "remain separately controlled."
    )
    return {
        "schema_version": 1,
        "research_id": "codeqa:issue:156:native-pr-create-e2e",
        "stage": "implement",
        "executor": "github_native",
        "payload": {
            "action": "create_pr",
            "repository": REPOSITORY,
            "target": {"head": head, "base": "main", "title": title, "body": body},
            "preconditions": {"pr_present": False},
            "desired_postcondition": {"pr_present": True},
        },
        "expected_observation": "exact-head codeQA PR from target-owned Samuel native executor",
    }


def action_id(plan: Mapping[str, Any]) -> str:
    """Mirror the pinned Samuel ActionPlan semantic idempotency digest."""
    raw = {
        "research_id": plan["research_id"],
        "stage": plan["stage"],
        "executor": plan["executor"],
        "payload": plan["payload"],
        "expected_observation": plan["expected_observation"],
    }
    return hashlib.sha256(
        json.dumps(raw, sort_keys=True, separators=(",", ":"),
                   ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def verify_receipts(plan: Mapping[str, Any], first: Mapping[str, Any],
                    replay: Mapping[str, Any], pr: Mapping[str, Any],
                    expected_head_sha: str) -> int:
    """After actual Native Executor writes, verify PASS/NOOP and exact PR."""
    expected_id = action_id(plan)
    for result, state in ((first, "pass"), (replay, "noop")):
        _require(isinstance(result, Mapping)
                 and result.get("action_id") == expected_id
                 and result.get("research_id") == plan["research_id"]
                 and result.get("executor") == "github_native"
                 and result.get("status") == state,
                 f"native executor {state.upper()} receipt missing or inconsistent")
    after = first.get("details", {}).get("after", {})
    _require(isinstance(after, Mapping)
             and after.get("pr_present") is True
             and after.get("head_sha") == expected_head_sha
             and after.get("base") == "main"
             and type(after.get("pr_number")) is int,
             "native read-after did not prove exact PR identity")
    _require(
        pr.get("number") == after["pr_number"]
        and pr.get("state") == "open"
        and pr.get("head", {}).get("sha") == expected_head_sha
        and pr.get("head", {}).get("ref") == plan["payload"]["target"]["head"]
        and pr.get("base", {}).get("ref") == "main"
        and pr.get("merged_at") is None,
        "independent target PR readback did not match executor receipt",
    )
    return after["pr_number"]
