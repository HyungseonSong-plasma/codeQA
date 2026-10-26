"""Additive, non-authorizing field evidence alongside #91's frozen 50-site review.

A shadow evidence packet does not modify an AST observer's legacy kind, create
human approval, execute reviewed source, or authorize a Naming rename.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha1, sha256
from collections.abc import Mapping
from typing import Any

from codeqa.core.naming_field_classification_v03 import (
    FieldClassificationError, classify_pinned_class_annotation,
)
from codeqa.core.naming_review_worklist_v03 import (
    NamingReviewWorklistError, build_review_worklist,
)


class FieldEvidenceError(ValueError):
    """An exact source, legacy site, or additive field-evidence packet drifted."""


SCHEMA_VERSION = "0.3-shadow-field-evidence"
MIGRATION_MODE = "ADDITIVE_SHADOW_ONLY"


def build_shadow_field_evidence(
    proposal: Mapping[str, Any], *, source: bytes,
) -> dict[str, Any]:
    """Project all *original* legacy field sites, preserving every worklist ID.

    The caller must independently obtain source bytes from the named immutable
    Git revision. SHA-1/SHA-256 integrity is checked here, but a hash alone is
    not independently authenticated Git provenance or human sign-off.
    """
    try:
        worklist = build_review_worklist(proposal)
    except (NamingReviewWorklistError, TypeError, KeyError) as exc:
        raise FieldEvidenceError("invalid unsigned legacy review proposal") from exc
    identity = worklist["source"]
    if not isinstance(source, bytes):
        raise FieldEvidenceError("source must be exact immutable Git bytes")
    actual_sha256 = sha256(source).hexdigest()
    actual_git_blob = sha1(
        b"blob " + str(len(source)).encode("ascii") + b"\0" + source
    ).hexdigest()
    if (actual_sha256 != identity["sha256"]
            or actual_git_blob != identity["git_blob_sha"]):
        raise FieldEvidenceError("pinned historical source identity drift")

    rows = []
    for site in worklist["rows"]:
        if (site["group"] != "original_candidates"
                or site["symbol"]["kind"] != "declared_field"):
            continue
        symbol = site["symbol"]
        try:
            evidence = classify_pinned_class_annotation(
                source, expected_sha256=actual_sha256,
                owner=symbol["owner"], name=symbol["name"],
                line=symbol["line"],
            )
        except FieldClassificationError as exc:
            # A claimed legacy field without an exact directly annotated
            # historical source location is invalid evidence, not a PASS.
            raise FieldEvidenceError(
                "legacy field not supported by pinned direct AST site: "
                + site["site_id"]
            ) from exc
        if (evidence.ast_node != "AnnAssign"
                or evidence.annotation_site != "DIRECT_CLASS_ANNASSIGN"):
            raise FieldEvidenceError("non-direct legacy field evidence")
        rows.append({
            "site_id": site["site_id"],
            "legacy_kind": "declared_field",
            "symbol": deepcopy(symbol),
            "ast_site": evidence.annotation_site,
            "static_classification": evidence.classification,
            "reason_codes": list(evidence.reasons),
            "runtime_field_verification": "NOT_EVALUATED",
            "human_decision": "NOT_IMPORTED_FROM_REVIEW_LEDGER",
            "naming_policy_applicability": "NOT_EVALUATED",
            "automatic_rename_authorized": False,
        })
    if not rows:
        raise FieldEvidenceError("no original declared_field sites to project")
    return {
        "schema_version": SCHEMA_VERSION,
        "migration_mode": MIGRATION_MODE,
        "source": deepcopy(identity),
        "proposal_sha256": worklist["proposal_sha256"],
        "legacy_worklist_sites": len(worklist["rows"]),
        "projected_field_sites": len(rows),
        "fields": rows,
        "runtime_field_verification": "NOT_EVALUATED",
        "human_approval": "NOT_EVALUATED",
        "policy_adoption": "NOT_ADOPTED",
        "automatic_rename_authorized": False,
        "issue_close_authorized": False,
    }


def validate_shadow_field_evidence(
    proposal: Mapping[str, Any], *, source: bytes,
    submitted: Mapping[str, Any],
) -> dict[str, Any]:
    """Strictly compare source-derived packet to alleged evidence.

    Rejects extra PASS/approval fields, reordered or removed sites, guessed
    runtime certifications, and changes to source/proposal/legacy identities.
    """
    expected = build_shadow_field_evidence(proposal, source=source)
    if (not isinstance(submitted, Mapping) or type(submitted) is not dict
            or submitted != expected):
        raise FieldEvidenceError("untrusted or promoted shadow field evidence")
    return expected
