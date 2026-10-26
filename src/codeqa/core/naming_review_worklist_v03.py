"""Exact-candidate, non-authorizing human review worksheet for Naming #91.

A reviewer's textual attribution or GitHub URL is a CLAIM, not independently
authenticated human approval. No result of this module authorizes a rename,
policy adoption, Gate PASS, PR merge, or issue closure.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
import re
from collections.abc import Mapping
from typing import Any


class NamingReviewWorklistError(ValueError):
    """Malformed, incomplete, stale or inconsistent review worksheet."""


_GROUPS = (
    ("original_candidates", 26),
    ("omitted_observation_candidates", 17),
    ("negative_control_candidates", 7),
)
_SITE_KEYS = ("name", "kind", "line", "owner")
_HEX40 = re.compile(r"[0-9a-f]{40}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_LOGIN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})\Z")
_COMMENT = re.compile(
    r"https://github\.com/HyungseonSong-plasma/codeQA/issues/91"
    r"#issuecomment-[1-9][0-9]*\Z"
)
_DECISION_FIELDS = {"decision", "reviewer_login", "review_comment_url", "rationale"}
_ALLOWED = {
    "original_candidates": {"OBSERVATION_CONFIRMED", "OBSERVATION_REJECTED", "UNRESOLVED"},
    "omitted_observation_candidates": {"OBSERVATION_CONFIRMED", "OBSERVATION_REJECTED", "UNRESOLVED"},
    "negative_control_candidates": {"NEGATIVE_CONFIRMED", "NEGATIVE_REJECTED", "UNRESOLVED"},
}


def _canonical(data: Any) -> bytes:
    return json.dumps(data, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")


def _digest(data: Any) -> str:
    return sha256(_canonical(data)).hexdigest()


def _proposal_rows(proposal: Mapping[str, Any]) -> list[dict[str, Any]]:
    if (not isinstance(proposal, Mapping)
            or proposal.get("schema_version") != "0.3-source-ast-review-proposal"
            or proposal.get("review_status") != "PENDING_FINAL_ADJUDICATION"
            or proposal.get("approval_authority") != "PROJECT_OWNER_ONLY"
            or proposal.get("candidate_count") != 26):
        raise NamingReviewWorklistError("exact unsigned #91 proposal required")
    source = proposal.get("source")
    if (not isinstance(source, Mapping)
            or source.get("repository") != "HyungseonSong-plasma/codeQA"
            or not isinstance(source.get("path"), str)
            or not isinstance(source.get("commit"), str)
            or not _HEX40.fullmatch(source["commit"])
            or not isinstance(source.get("git_blob_sha"), str)
            or not _HEX40.fullmatch(source["git_blob_sha"])
            or not isinstance(source.get("sha256"), str)
            or not _HEX64.fullmatch(source["sha256"])):
        raise NamingReviewWorklistError("pinned source witness required")
    rows: list[dict[str, Any]] = []
    for group, expected_count in _GROUPS:
        candidates = proposal.get(group)
        if not isinstance(candidates, list) or len(candidates) != expected_count:
            raise NamingReviewWorklistError("candidate group missing, incomplete or duplicated")
        for number, candidate in enumerate(candidates, start=1):
            if not isinstance(candidate, Mapping):
                raise NamingReviewWorklistError("candidate must be an object")
            symbol = {key: candidate.get(key, "" if key == "owner" else None)
                      for key in _SITE_KEYS}
            if (not isinstance(symbol["name"], str) or not symbol["name"]
                    or not isinstance(symbol["kind"], str) or not symbol["kind"]
                    or type(symbol["line"]) is not int or symbol["line"] <= 0
                    or not isinstance(symbol["owner"], str)):
                raise NamingReviewWorklistError("invalid source site identity")
            if group == "original_candidates":
                if (candidate.get("index") != number
                        or candidate.get("human_adjudication") is not None
                        or candidate.get("ast_observation") not in
                           {"AST_OBSERVED", "SYNTAX_ONLY"}
                        or type(candidate.get("eligible_kind_only")) is not bool):
                    raise NamingReviewWorklistError("original observation not unsigned")
            elif group == "omitted_observation_candidates":
                if (candidate.get("human_adjudication") is not None
                        or candidate.get("ast_observation") != "AST_OBSERVED"
                        or candidate.get("extractor_false_negative") !=
                           "NOT_ESTABLISHED_WITHOUT_DECLARED_COVERAGE_DENOMINATOR"
                        or type(candidate.get("eligible_kind_only")) is not bool):
                    raise NamingReviewWorklistError("unverified omission marked as fact")
            elif (candidate.get("human_review_outcome") is not None
                  or candidate.get("ai_review") !=
                     "PROPOSED_VALID_NEGATIVE_FOR_AUTO_RENAME_ONLY"
                  or not isinstance(candidate.get("reason"), str)
                  or not candidate["reason"]):
                raise NamingReviewWorklistError("negative control already adjudicated")
            identity = {"source_sha256": source["sha256"], "group": group,
                        "ordinal": number, "symbol": symbol}
            site_id = "n91-" + _digest(identity)[:24]
            rows.append({
                "site_id": site_id, "group": group, "ordinal": number,
                "symbol": symbol,
                "source_sha256": source["sha256"],
                "observation": candidate.get("ast_observation", "NEGATIVE_REVIEW_CANDIDATE"),
                "decision": None, "reviewer_login": None,
                "review_comment_url": None, "rationale": None,
            })
    if len({row["site_id"] for row in rows}) != 50:
        raise NamingReviewWorklistError("nonunique review site identities")
    return rows


def build_review_worklist(proposal: Mapping[str, Any]) -> dict[str, Any]:
    """Prepare exactly 50 unsigned source-scoped review entries (no approvals)."""
    rows = _proposal_rows(proposal)
    return {
        "schema_version": "0.3-claimed-review-worklist",
        "proposal_sha256": _digest(proposal),
        "source": deepcopy(proposal["source"]),
        "status": "PENDING_FINAL_ADJUDICATION",
        "rows": rows,
        "human_signature_verified": False,
        "policy_adopted": False,
        "automatic_rename_authorized": False,
    }


@dataclass(frozen=True, slots=True)
class ReviewWorklistAssessment:
    total: int
    claimed_decisions: int
    unresolved: int
    remaining_without_decision: int
    status: str = "NOT_EVALUATED"
    independent_human_authentication: str = "NOT_EVALUATED"
    official_glossary_adoption: str = "NOT_EVALUATED"
    automatic_rename_authorized: bool = False


def assess_review_worklist(proposal: Mapping[str, Any],
                           submitted: Mapping[str, Any]) -> ReviewWorklistAssessment:
    """Check every row's integrity and claimed evidence, never authenticate it.

    An all-filled worksheet is not signed ground truth: read-only matching of
    URLs and reviewer names cannot verify their provenance or owner approval.
    """
    expected = build_review_worklist(proposal)
    if not isinstance(submitted, Mapping) or set(submitted) != set(expected):
        raise NamingReviewWorklistError("exact review envelope required")
    for key in expected.keys() - {"rows"}:
        if submitted[key] != expected[key]:
            raise NamingReviewWorklistError("source, proposal, or safety status drift")
    rows = submitted["rows"]
    if not isinstance(rows, list) or len(rows) != len(expected["rows"]):
        raise NamingReviewWorklistError("review rows missing or duplicated")
    claimed = unresolved = missing = 0
    for got, want in zip(rows, expected["rows"]):
        if not isinstance(got, Mapping) or set(got) != set(want):
            raise NamingReviewWorklistError("unexpected review row shape")
        for key in want.keys() - _DECISION_FIELDS:
            if got[key] != want[key]:
                raise NamingReviewWorklistError("source site, category or order was altered")
        values = [got[key] for key in ("decision", "reviewer_login",
                                        "review_comment_url", "rationale")]
        if all(value is None for value in values):
            missing += 1
            continue
        decision, reviewer, url, reason = values
        if (not isinstance(decision, str) or decision not in _ALLOWED[want["group"]]
                or not isinstance(reviewer, str) or not _LOGIN.fullmatch(reviewer)
                or not isinstance(url, str) or not _COMMENT.fullmatch(url)
                or not isinstance(reason, str) or not reason.strip()
                or reason != reason.strip()):
            raise NamingReviewWorklistError("partial or invalid claimed adjudication")
        claimed += 1
        if decision == "UNRESOLVED":
            unresolved += 1
    return ReviewWorklistAssessment(
        total=len(rows), claimed_decisions=claimed,
        unresolved=unresolved + missing,
        remaining_without_decision=missing,
    )
