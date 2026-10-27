"""Proposal-only, source-bound official Naming adoption readiness (#144).

This validates a narrowly chosen internal Python declaration and owner policy
direction. It never adopts a glossary, attests a human signature, produces a
Naming PASS, or authorizes source changes.
"""
from __future__ import annotations

import ast
from collections.abc import Mapping
from hashlib import sha1, sha256
import json
from typing import Any

from codeqa.core.naming_field_classification_v03 import (
    FieldClassificationError, classify_pinned_class_annotation,
)


class NamingAdoptionError(ValueError):
    """Invalid owner-direction proposal, historical source or authority claim."""


_REPO = "HyungseonSong-plasma/codeQA"
_COMMIT = "1fca848833167829752b4fda8632ef06aa77dd49"
_TREE = "56305f69aebae3a07f0d7255a9b3e9f5c1efeec5"
_PATH = "src/codeqa/core/complexity.py"
_BLOB = "3b883e0daaf915b653da07650c533317a596623b"
_TERMS = (
    {"canonical": "time_step", "noncanonical_spelling": "timestep",
     "path_scopes": [], "meaning": "NOT_EVALUATED"},
    {"canonical": "node_id", "noncanonical_spelling": "nodeid",
     "path_scopes": [_PATH], "meaning": "INTERNAL_SOURCE_ROLE_CANDIDATE_ONLY"},
)
_FIELDS = {
    "schema_version", "policy_id", "repository", "status", "owner_decision",
    "source_witness", "terms", "declaration_scope", "exceptions",
    "review_interval_days", "adoption_date", "next_review_date",
    "external_clients", "external_reference_issue", "default_v01_unchanged",
    "semantic_glossary_pass", "automatic_rename_authorized",
}
_SCOPE = {
    "path": _PATH, "owner": "ControlFlowObservation", "line": 10,
    "kind": "field", "identifier": "node_id",
    "role_candidate": "internal_ccg_declaration_identifier_candidate",
    "source_classification": "FIELD_CANDIDATE",
    "owner_role_approval": "PENDING_FINAL_OWNER_APPROVAL",
}
_SOURCE = {
    "commit": _COMMIT, "tree_sha": _TREE, "path": _PATH,
    "git_blob_sha": _BLOB,
}


def assess_official_naming_adoption_proposal(
    proposal: Mapping[str, Any], *, source: bytes,
) -> dict[str, Any]:
    """Return owner-decision readiness, not a policy adoption decision.

    Historical Git commit->tree->blob linkage is verified by the caller's
    trusted GitReader. This pure step also verifies exact blob bytes.
    """
    if not isinstance(proposal, Mapping) or set(proposal) != _FIELDS:
        raise NamingAdoptionError("unexpected official proposal schema")
    if (proposal["schema_version"] != "0.5-scoped-owner-approval-proposal"
            or proposal["policy_id"] != "codeqa_python_naming_scoped_v05"
            or proposal["repository"] != _REPO
            or proposal["status"] != "PENDING_FINAL_OWNER_APPROVAL"
            or proposal["owner_decision"] != "EXPLICIT_SEPARATE_APPROVAL_REQUIRED"
            or proposal["source_witness"] != _SOURCE
            or proposal["terms"] != list(_TERMS)
            or proposal["declaration_scope"] != _SCOPE
            or proposal["exceptions"] != []
            or type(proposal["review_interval_days"]) is not int
            or proposal["review_interval_days"] != 180
            or proposal["adoption_date"] is not None
            or proposal["next_review_date"] is not None
            or proposal["external_clients"] != "NOT_EVALUATED"
            or proposal["external_reference_issue"] != 147
            or proposal["default_v01_unchanged"] is not True
            or proposal["semantic_glossary_pass"] is not False
            or proposal["automatic_rename_authorized"] is not False):
        raise NamingAdoptionError("adoption, owner or policy scope not authorized")
    if not isinstance(source, bytes):
        raise NamingAdoptionError("exact historical source bytes required")
    blob = sha1(b"blob " + str(len(source)).encode("ascii") +
                b"\0" + source).hexdigest()
    if blob != _BLOB:
        raise NamingAdoptionError("pinned Git blob has changed")
    try:
        tree = ast.parse(source.decode("utf-8"), filename=_PATH)
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise NamingAdoptionError("unparseable source evidence") from exc
    classes = [node for node in tree.body
               if isinstance(node, ast.ClassDef) and node.name == "ControlFlowObservation"]
    if len(classes) != 1:
        raise NamingAdoptionError("source class owner ambiguous")
    nodes = [
        n for n in classes[0].body
        if isinstance(n, ast.AnnAssign) and n.lineno == 10
        and n.simple == 1 and isinstance(n.target, ast.Name)
        and n.target.id == "node_id"
        and isinstance(n.annotation, ast.Name) and n.annotation.id == "str"
    ]
    if len(nodes) != 1:
        raise NamingAdoptionError("exact source declaration/type not witnessed")
    try:
        field = classify_pinned_class_annotation(
            source, expected_sha256=sha256(source).hexdigest(),
            owner="ControlFlowObservation", name="node_id", line=10,
        )
    except FieldClassificationError as exc:
        raise NamingAdoptionError("field classifier did not certify candidate") from exc
    if field.classification != "FIELD_CANDIDATE":
        raise NamingAdoptionError("not a proven stdlib dataclass field candidate")

    digest = sha256(json.dumps(proposal, sort_keys=True, ensure_ascii=False,
                               separators=(",", ":"), allow_nan=False)
                    .encode("utf-8")).hexdigest()
    return {
        "schema_version": "0.5-scoped-adoption-readiness",
        "proposal_sha256": digest,
        "source_commit": _COMMIT, "source_tree_sha": _TREE,
        "source_git_blob_sha": blob, "source_sha256": sha256(source).hexdigest(),
        "verified_source_sites": 1,
        "source_classification": "FIELD_CANDIDATE",
        "approved_policy_principles": (
            "EXPLICIT_CANONICAL_SPELLING", "PYTHON_OPT_IN",
            "EXACT_AST_EVIDENCE", "OWNER_FINAL_AUTHORITY_AND_180D_REVIEW",
        ),
        "scope": dict(_SCOPE),
        "time_step_source_scope": "NOT_ADOPTED",
        "node_id_alias_semantics": "NO_EQUIVALENCE_INFERRED",
        "readiness": "SOURCE_EVIDENCE_READY_OWNER_DECISION_REQUIRED",
        "official_policy_adopted": False,
        "domain_meaning_verified": False,
        "external_compatibility": "UNKNOWN",
        "external_reference_issue": 147,
        "naming_pass_authorized": False,
        "automatic_rename_authorized": False,
        "default_v01_unchanged": True,
    }
