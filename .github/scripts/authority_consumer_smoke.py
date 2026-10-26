#!/usr/bin/env python3
"""Consume the *actual* pinned Dafny CI receipt without promoting authority.

This is a round-trip consumer conformance check. It does not authenticate
GitHub API data, the Actions runner, or production deployment permissions.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from urllib.request import Request, urlopen

from codeqa.evaluation.authority_audit import audit_authority_propagation
from codeqa.evaluation.evidence_gate import GateDecision, RequirementDecision
from codeqa.evaluation.formal_generated_gate import GeneratedFixtureDecision


_SHA = re.compile(r"[0-9a-f]{40}\Z")
_RUN = re.compile(r"[1-9][0-9]*\Z")


_REPO = "HyungseonSong-plasma/codeQA"
_WORKFLOW = ".github/workflows/pinned-dafny-formal.yml"


def verify_github_run_source_readback(
    run: dict[str, object], commit: dict[str, object], *,
    source_sha: str, run_id: str, event: str, ref: str, attempt: str,
) -> dict[str, object]:
    """Independently compare GitHub's read-only run/commit records.

    This attests the run/source relationship, NOT the runner, artifact
    authenticity, Dafny soundness or production deployment authority.
    """
    if (not isinstance(run, dict) or not isinstance(commit, dict)
            or not _SHA.fullmatch(source_sha or "")
            or not _RUN.fullmatch(run_id or "")
            or not _RUN.fullmatch(attempt or "")
            or run.get("id") != int(run_id)
            or run.get("run_attempt") != int(attempt)
            or run.get("event") != event
            or run.get("path") != _WORKFLOW
            or not isinstance(run.get("repository"), dict)
            or run["repository"].get("full_name") != _REPO
            or not isinstance(run.get("head_repository"), dict)
            or run["head_repository"].get("full_name") != _REPO
            or not _SHA.fullmatch(str(run.get("head_sha") or ""))
            or run.get("status") not in {"in_progress", "completed"}
            or commit.get("sha") != source_sha):
        raise ValueError("GITHUB_REMOTE_RUN_OR_SOURCE_IDENTITY_UNVERIFIED")
    head = str(run["head_sha"])
    if event == "pull_request":
        matched = re.fullmatch(r"refs/pull/([1-9][0-9]*)/merge", ref or "")
        parents = commit.get("parents")
        prs = run.get("pull_requests")
        if (not matched or not isinstance(parents, list) or len(parents) != 2
                or not isinstance(parents[1], dict)
                or parents[1].get("sha") != head
                or not isinstance(prs, list)
                or not any(isinstance(pr, dict)
                           and pr.get("number") == int(matched.group(1))
                           and isinstance(pr.get("head"), dict)
                           and pr["head"].get("sha") == head for pr in prs)):
            raise ValueError("GITHUB_PR_MERGE_HEAD_RELATIONSHIP_UNVERIFIED")
    elif event in {"push", "workflow_dispatch"}:
        if (source_sha != head or not re.fullmatch(r"refs/heads/[A-Za-z0-9._/-]+", ref or "")
                or ".." in ref or "//" in ref):
            raise ValueError("GITHUB_BRANCH_HEAD_RELATIONSHIP_UNVERIFIED")
    else:
        raise ValueError("GITHUB_EVENT_NOT_SUPPORTED_FOR_SOURCE_READBACK")
    return {
        "status": "GITHUB_API_RUN_SOURCE_RELATIONSHIP_VERIFIED",
        "run_id": run_id, "attempt": attempt, "event": event,
        "source_sha": source_sha, "raw_run_head_sha": head,
        "workflow": _WORKFLOW,
        "runner_and_artifact_authenticity": "NOT_EVALUATED",
        "proof_applicability_and_deployment": "NOT_EVALUATED",
        "production_merge_authorized": False,
    }


def _read_github_json(path: str, token: str) -> dict[str, object]:
    if not token:
        raise ValueError("GITHUB_READ_ONLY_TOKEN_MISSING")
    request = Request(
        "https://api.github.com/repos/" + _REPO + "/" + path,
        headers={"Authorization": "Bearer " + token,
                 "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28"},
    )
    with urlopen(request, timeout=25) as response:
        value = json.load(response)
    if not isinstance(value, dict):
        raise ValueError("GITHUB_API_RESPONSE_NOT_OBJECT")
    return value


def consume_dafny_authority_artifact(
    artifact: dict[str, object], *, source_sha: str, run_id: str,
) -> dict[str, object]:
    """Require source-bound, serialized real fixture and blocked general Gate."""
    if not isinstance(artifact, dict) or not _SHA.fullmatch(source_sha or ""):
        raise ValueError("pinned source SHA and JSON object required")
    if not _RUN.fullmatch(run_id or ""):
        raise ValueError("real CI run ID required")
    gate_raw = artifact.get("gate")
    fixture_raw = artifact.get("generated_fixture_gate")
    if not isinstance(gate_raw, dict) or not isinstance(fixture_raw, dict):
        raise ValueError("both serialized decisions required")
    requirements = gate_raw.get("requirements")
    if not isinstance(requirements, list) or not all(isinstance(x, dict) for x in requirements):
        raise ValueError("Gate requirement records missing")
    gate = GateDecision(
        **{**gate_raw, "requirements": tuple(
            RequirementDecision(**{**item,
                "scope": tuple(item["scope"]), "reasons": tuple(item["reasons"])})
            for item in requirements
        ), "reasons": tuple(gate_raw["reasons"])}
    )
    fixture = GeneratedFixtureDecision(**{
        **fixture_raw, "reasons": tuple(fixture_raw["reasons"]),
        "requirement_ids": tuple(fixture_raw["requirement_ids"]),
    })
    # Reject dropped/renamed/forged JSON keys and lossy conversions.
    for typed, raw in ((gate, gate_raw), (fixture, fixture_raw)):
        if json.loads(typed.canonical_json()) != raw:
            raise ValueError("typed decision JSON round-trip drift")
    snapshot = "git:HyungseonSong-plasma/codeQA@" + source_sha
    if gate.snapshot_id != snapshot or fixture.snapshot_id != snapshot:
        raise ValueError("artifact not bound to exact CI source")
    if (gate.status != "UNKNOWN" or gate.authorization != "BLOCK"
            or fixture.status != "PASS"
            or fixture.authorization != "ALLOW_FIXTURE_ONLY"):
        raise ValueError("real Dafny fixture/general Gate authority unexpectedly changed")
    url = ("https://github.com/HyungseonSong-plasma/codeQA/actions/runs/"
           + run_id)
    def audit(decision, producer):
        receipt = {
            "schema_version": "0.1", "producer": producer,
            "decision_sha256": sha256(decision.canonical_json().encode("utf-8")).hexdigest(),
            "snapshot_id": snapshot,
            "policy_fingerprint": decision.policy_fingerprint,
            "source_sha": source_sha, "ci_run_url": url,
        }
        return audit_authority_propagation(
            decision, expected_snapshot_id=snapshot,
            expected_policy_fingerprint=decision.policy_fingerprint,
            expected_source_sha=source_sha, receipt=receipt,
        )
    formal = audit(fixture, "codeqa.formal_generated_gate")
    general = audit(gate, "codeqa.evidence_gate")
    if (formal.consumer_authorization != "FIXTURE_ONLY"
            or general.consumer_authorization != "BLOCK"
            or formal.production_merge_authorized
            or general.production_merge_authorized):
        raise ValueError("cross-boundary authority escalation detected")
    return {
        "schema_version": "0.1",
        "source_sha": source_sha,
        "ci_run_url": url,
        "artifact_authority": "CALLER_SUPPLIED_RUN_CONTEXT_NOT_REMOTE_ATTESTATION",
        "general_gate": general.to_document(),
        "generated_fixture_gate": formal.to_document(),
        "production_merge_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--remote-attest", action="store_true")
    parser.add_argument("--github-event")
    parser.add_argument("--github-ref")
    parser.add_argument("--github-attempt")
    args = parser.parse_args()
    document = json.loads(args.input.read_text(encoding="utf-8"))
    output = consume_dafny_authority_artifact(
        document, source_sha=args.source_sha, run_id=args.run_id,
    )
    if args.remote_attest:
        run = _read_github_json("actions/runs/" + args.run_id,
                                os.getenv("GITHUB_TOKEN", ""))
        commit = _read_github_json("commits/" + args.source_sha,
                                   os.getenv("GITHUB_TOKEN", ""))
        output["remote_run_attestation"] = verify_github_run_source_readback(
            run, commit, source_sha=args.source_sha, run_id=args.run_id,
            event=args.github_event, ref=args.github_ref,
            attempt=args.github_attempt,
        )
        output["artifact_authority"] = "GITHUB_API_RUN_SOURCE_READBACK_LIMITED"
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print("AUTHORITY_CONSUMER=PASS fixture=FIXTURE_ONLY general=BLOCK")


if __name__ == "__main__":
    main()
