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
    source_run_id: str
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


def verify_origin_workflow(
    run: Mapping[str, object], *, source_run_id: str, controller_sha: str,
) -> None:
    """Read-back a real controller-side workflow run, never trust input only."""
    if not isinstance(run, Mapping):
        raise PreflightError("origin workflow record missing")
    if (not isinstance(source_run_id, str) or not source_run_id.isdecimal()
            or int(source_run_id) <= 0 or run.get("id") != int(source_run_id)):
        raise PreflightError("origin workflow run identity mismatch")
    if run.get("event") != "workflow_dispatch":
        raise PreflightError("origin was not explicit governed workflow dispatch")
    if run.get("head_sha") != controller_sha:
        raise PreflightError("origin controller SHA mismatch")
    # GitHub Actions REST workflow-run.path can be the bare workflow path;
    # some historical responses include the fully qualified branch ref.
    # Verify the independently returned branch identity separately rather than
    # requiring that the branch suffix be embedded in the file path.
    if run.get("head_branch") != "main":
        raise PreflightError("origin controller ref is not main")
    path = run.get("path")
    approved_path = ".github/workflows/samuel-codeqa-preflight.yml"
    if path not in (approved_path, approved_path + "@refs/heads/main"):
        raise PreflightError("origin workflow is not approved controller preflight")
    repository = run.get("repository")
    if not isinstance(repository, Mapping) or repository.get("full_name") != SOURCE_REPO:
        raise PreflightError("origin workflow repository mismatch")
    actor = run.get("actor")
    if not isinstance(actor, Mapping) or actor.get("login") not in _APPROVED:
        raise PreflightError("origin workflow actor not approved")


def evaluate_handoff(
    *,
    source_issue: Mapping[str, object],
    target_issue: Mapping[str, object],
    source_repository: str, target_repository: str,
    work_id: str, controller_sha: str,
    expected_target_sha: str, actual_target_sha: str,
    actor: str, github_run_id: str, source_run_id: str,
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
    if not isinstance(source_run_id, str) or not source_run_id.isdecimal() or int(source_run_id) <= 0:
        raise PreflightError("missing source workflow run identity")
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
        "source_run_id": source_run_id,
    }
    digest = sha256(json.dumps(witness, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return PreflightReceipt(
        schema_version=1, status="READ_ONLY_PREFLIGHT_CONFIRMED",
        source_repository=SOURCE_REPO, source_issue=SOURCE_ISSUE,
        target_repository=TARGET_REPO, target_issue=TARGET_ISSUE,
        work_id=WORK_ID, controller_sha=controller_sha,
        target_sha=actual_target_sha, dispatch_actor=actor,
        source_run_id=source_run_id,
        execution_mode="READ_ONLY_NO_PR_NO_MERGE",
        evidence_sha256=digest, allowed_mutations=(),
    )
