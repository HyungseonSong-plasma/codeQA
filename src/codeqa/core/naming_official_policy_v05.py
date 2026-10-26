"""Owner-approved, exact-declaration lexical Naming v0.5 opt-in gate (#144).

A scoped *Naming convention* adoption is not proof of identifier meaning,
runtime binding, external compatibility or rename safety. The draft
proposal is retained separately and never implicitly adopted.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, timedelta
from hashlib import sha256
import json
from typing import Any

from codeqa.core.naming_official_adoption_v05 import (
    NamingAdoptionError, assess_official_naming_adoption_proposal,
)


@dataclass(frozen=True, slots=True)
class OfficialNamingV05Decision:
    status: str
    reason: str
    policy_id: str
    policy_sha256: str
    source_commit: str
    declaration: str
    source_line: int
    adoption_date: str
    next_review_date: str
    policy_scope: str = "EXACT_DECLARATION_LEXICAL_ONLY"
    semantic_meaning_verified: bool = False
    runtime_binding_verified: bool = False
    external_compatibility: str = "UNKNOWN"
    rename_authorized: bool = False


def _expected_approved(proposal: Mapping[str, Any]) -> dict[str, Any]:
    expected = deepcopy(dict(proposal))
    expected["schema_version"] = "0.5-scoped-official-lexical-policy"
    expected["status"] = "ADOPTED_SCOPED_LEXICAL_ONLY"
    expected["owner_decision"] = "PROJECT_OWNER_EXPLICIT_APPROVAL_2026-10-26"
    expected["declaration_scope"]["owner_role_approval"] = (
        "APPROVED_EXACT_LEXICAL_SCOPE_ONLY")
    expected["adoption_date"] = "2026-10-26"
    expected["next_review_date"] = "2027-04-24"
    return expected


def evaluate_official_naming_v05(
    policy: Mapping[str, Any], *, proposal: Mapping[str, Any],
    source: bytes, as_of: date, path: str, owner: str,
    name: str, kind: str, line: int,
) -> OfficialNamingV05Decision:
    """Apply the explicitly accepted single-site convention, never QA PASS.

    Source authenticity and Git commit/tree relationships are separately
    checked by the optional pipeline using the trusted GitReader.
    """
    if not isinstance(policy, Mapping) or not isinstance(proposal, Mapping):
        raise NamingAdoptionError("explicit adopted policy and original proposal required")
    # Reuse the proposal's original strict AST + source digest gate.
    attestation = assess_official_naming_adoption_proposal(
        proposal, source=source)
    expected = _expected_approved(proposal)
    if dict(policy) != expected:
        raise NamingAdoptionError("official adoption differs from exact owner-approved scope")
    if (not isinstance(as_of, date) or isinstance(as_of, type(None))
            or type(line) is not int or not all(isinstance(x, str) for x in
                (path, owner, name, kind))):
        raise NamingAdoptionError("invalid policy evaluation request")
    since = date.fromisoformat(expected["adoption_date"])
    review = date.fromisoformat(expected["next_review_date"])
    if review != since + timedelta(days=180):
        raise NamingAdoptionError("180-day review date mismatch")
    data = json.dumps(policy, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")
    digest = sha256(data).hexdigest()
    scope = policy["declaration_scope"]
    identity = (path, owner, name, kind, line)
    target = (scope["path"], scope["owner"], scope["identifier"],
              scope["kind"], scope["line"])
    if as_of < since:
        status, reason = "NOT_APPLICABLE", "POLICY_NOT_YET_EFFECTIVE"
    elif as_of > review:
        status, reason = "REVIEW_REQUIRED", "OWNER_REVIEW_OVERDUE"
    elif identity != target:
        status, reason = "NOT_APPLICABLE", "DECLARATION_OUTSIDE_EXACT_SCOPE"
    else:
        status, reason = ("SCOPED_LEXICAL_CONFORMANT",
                          "EXACT_SOURCE_FIELD_SPELLING_OBSERVED")
    return OfficialNamingV05Decision(
        status=status, reason=reason, policy_id=policy["policy_id"],
        policy_sha256=digest, source_commit=attestation["source_commit"],
        declaration=scope["owner"] + "." + scope["identifier"],
        source_line=scope["line"],
        adoption_date=policy["adoption_date"],
        next_review_date=policy["next_review_date"],
    )
