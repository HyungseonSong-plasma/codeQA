"""Read-only Samuel→codeQA #92 handoff verifier.

This is a *preflight witness*, NOT an ActionPlan executor or merge approval.
GitHub Actions must fetch remote issues independently and pass the original
response bytes; untrusted Issue bodies are never evaluated or executed.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from collections.abc import Mapping


SOURCE_REPO = "HyungseonSong-plasma/chatgpt-operation"
TARGET_REPO = "HyungseonSong-plasma/codeQA"
SOURCE_ISSUE = 220
TARGET_ISSUE = 92
WORK_ID = "github:HyungseonSong-plasma/codeQA:issue:92"
_SHA = re.compile(r"^[a-f0-9]{40}$")
_APPROVED = frozenset({"HyungseonSong-plasma"})


class PreflightError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PreflightReceipt:
    schema_version: int
    status: str
    source_repository: str
    source_issue: int
    target_repository: str
    target_issue: int
    work_id: str
    controller_sha: str
    target_sha: str
    dispatch_actor: str
    execution_mode: str
    evidence_sha256: str
    allowed_mutations: tuple[str, ...]

    def to_document(self) -> dict[str, object]:
        return asdict(self)


def _issue(payload: Mapping[str, object], *, repo: str, number: int) -> None:
    if not isinstance(payload, Mapping):
        raise PreflightError("GitHub issue response absent")
    if type(payload.get("number")) is not int or payload["number"] != number:
        raise PreflightError("wrong issue number")
    if payload.get("state") != "open" or payload.get("pull_request") is not None:
        raise PreflightError("source/target issue closed or not an Issue")
    expected_url = f"https://api.github.com/repos/{repo}/issues/{number}"
    if payload.get("url") != expected_url:
        raise PreflightError("GitHub issue repository identity mismatch")


def evaluate_handoff(
    *,
    source_issue: Mapping[str, object],
    target_issue: Mapping[str, object],
    source_repository: str, target_repository: str,
    work_id: str, controller_sha: str,
    expected_target_sha: str, actual_target_sha: str,
    actor: str, github_run_id: str,
) -> PreflightReceipt:
    if source_repository != SOURCE_REPO or target_repository != TARGET_REPO:
        raise PreflightError("wrong cross-repository owner/scope")
    if work_id != WORK_ID:
        raise PreflightError("ambiguous, reused or wrong repository-qualified work ID")
    if not all(_SHA.fullmatch(x or "") for x in (controller_sha, expected_target_sha, actual_target_sha)):
        raise PreflightError("missing pinned source/target commit SHA")
    if expected_target_sha != actual_target_sha:
        raise PreflightError("target HEAD moved since request; stale dispatch")
    if actor not in _APPROVED:
        raise PreflightError("dispatch actor not explicitly approved")
    if not isinstance(github_run_id, str) or not github_run_id.isdecimal() or int(github_run_id) <= 0:
        raise PreflightError("missing real GitHub run identity")
    _issue(source_issue, repo=SOURCE_REPO, number=SOURCE_ISSUE)
    _issue(target_issue, repo=TARGET_REPO, number=TARGET_ISSUE)
    witness = {
        "source_issue": {"number": source_issue["number"], "url": source_issue["url"], "state": source_issue["state"]},
        "target_issue": {"number": target_issue["number"], "url": target_issue["url"], "state": target_issue["state"]},
        "controller_sha": controller_sha,
        "target_sha": actual_target_sha,
        "work_id": work_id,
        "actor": actor,
        "github_run_id": github_run_id,
    }
    digest = sha256(json.dumps(witness, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return PreflightReceipt(
        schema_version=1, status="READ_ONLY_PREFLIGHT_CONFIRMED",
        source_repository=SOURCE_REPO, source_issue=SOURCE_ISSUE,
        target_repository=TARGET_REPO, target_issue=TARGET_ISSUE,
        work_id=WORK_ID, controller_sha=controller_sha,
        target_sha=actual_target_sha, dispatch_actor=actor,
        execution_mode="READ_ONLY_NO_PR_NO_MERGE",
        evidence_sha256=digest, allowed_mutations=(),
    )
