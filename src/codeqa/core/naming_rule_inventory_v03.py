"""Pinned 50-site #91 rule classification. Not a semantic Naming or rename PASS."""
from __future__ import annotations
from collections.abc import Mapping
from hashlib import sha1, sha256
from typing import Any

from codeqa.core.naming_declaration_evidence_v03 import observe_pinned_python
from codeqa.core.naming_field_classification_v03 import (
    FieldClassificationError, classify_pinned_class_annotation,
)
from codeqa.core.naming_review_worklist_v03 import build_review_worklist


class RuleInventoryError(ValueError):
    """Untrusted source, proposal, rule evidence, or incorrect claimed result."""


RESOLVED = frozenset((
    "AST_KIND_CONFIRMED", "DECORATOR_SYNTAX_ONLY", "FUTURE_DIRECTIVE_SYNTAX",
    "DATACLASS_FIELD_CANDIDATE", "NEGATIVE_CONTROL_RENAME_EXCLUDED",
))


def classify_exact_rule_inventory(
    proposal: Mapping[str, Any], *, source: bytes,
) -> dict[str, Any]:
    """Classify all original immutable sites; never execute reviewed code."""
    try:
        worklist = build_review_worklist(proposal)
    except (KeyError, TypeError, ValueError) as exc:
        raise RuleInventoryError("invalid unsigned historical proposal") from exc
    src = worklist["source"]
    if not isinstance(source, bytes):
        raise RuleInventoryError("source must be pinned bytes")
    digest = sha256(source).hexdigest()
    git_blob = sha1(b"blob " + str(len(source)).encode("ascii") +
                    b"\0" + source).hexdigest()
    if digest != src["sha256"] or git_blob != src["git_blob_sha"]:
        raise RuleInventoryError("historical source SHA-256 or Git blob drift")
    review = observe_pinned_python(source, expected_sha256=digest)
    rows = []
    for site in worklist["rows"]:
        sym, group = site["symbol"], site["group"]
        kind, status, reason = sym["kind"], "UNKNOWN", "NOT_UNAMBIGUOUSLY_OBSERVED"
        field = None
        if group == "negative_control_candidates":
            normalized = ("module_binding" if kind == "module_constant"
                          else kind)
            correlated = [d for d in review.declarations
                          if d.name == sym["name"] and d.line == sym["line"]
                          and d.kind == normalized]
            if len(correlated) == 1:
                status = "NEGATIVE_CONTROL_RENAME_EXCLUDED"
                reason = "RENAME_BLOCK_ONLY_NOT_SEMANTIC_NEGATIVE"
        elif group in ("original_candidates", "omitted_observation_candidates"):
            observed = review.classify_candidate(sym)
            if kind == "declared_field" and observed == "AST_OBSERVED":
                try:
                    evidence = classify_pinned_class_annotation(
                        source, expected_sha256=digest, owner=sym["owner"],
                        name=sym["name"], line=sym["line"])
                    field = evidence.classification
                    if field == "FIELD_CANDIDATE":
                        status, reason = (
                            "DATACLASS_FIELD_CANDIDATE",
                            "DIRECT_CLASS_ANNASSIGN_STATIC_PROOF")
                except FieldClassificationError:
                    reason = "FIELD_IDENTITY_NOT_PROVEN"
            elif kind == "decorator" and observed == "SYNTAX_ONLY":
                status, reason = ("DECORATOR_SYNTAX_ONLY",
                                  "DECORATOR_IS_NOT_DECLARATION_IDENTIFIER")
            elif (kind == "import_binding" and
                  sym["name"] == "annotations" and
                  group == "original_candidates" and
                  observed == "AST_OBSERVED"):
                status, reason = ("FUTURE_DIRECTIVE_SYNTAX",
                                  "NOT_ORDINARY_IMPORT_BINDING")
            elif observed == "AST_OBSERVED":
                status, reason = ("AST_KIND_CONFIRMED",
                                  "PINNED_EXACT_NAME_KIND_LINE_OWNER")
        else:
            raise RuleInventoryError("unknown candidate group")
        rows.append({
            "site_id": site["site_id"], "group": group,
            "ordinal": site["ordinal"], "symbol": dict(sym),
            "source_evidence": status, "reason_code": reason,
            "field_static_classification": field,
            "naming_semantics": "NOT_EVALUATED",
            "runtime_binding_graph": "NOT_EVALUATED",
            "external_compatibility": "NOT_EVALUATED",
            "rename_authorized": False,
        })
    if len(rows) != 50 or len({r["site_id"] for r in rows}) != 50:
        raise RuleInventoryError("historical worklist identity drift")
    unknown = sum(r["source_evidence"] not in RESOLVED for r in rows)
    return {
        "schema_version": "0.3-deterministic-source-inventory",
        "classification_authority": "PINNED_AST_RULES_NOT_HUMAN_APPROVAL",
        "source": dict(src), "proposal_sha256": worklist["proposal_sha256"],
        "total_sites": 50, "classified_sites": 50 - unknown,
        "unknown_sites": unknown,
        "closure_gate": "PASS" if unknown == 0 else "BLOCKED_UNKNOWN",
        "rows": rows,
        "semantic_glossary": "NOT_ADOPTED",
        "human_review_not_required_for_bounded_AST_axis": True,
        "policy_applicability": "NOT_EVALUATED",
        "external_dynamic_api_safety": "OUT_OF_SCOPE",
        "rename_authorized": False,
    }


def validate_exact_rule_inventory(
    proposal: Mapping[str, Any], *, source: bytes, submitted: Mapping[str, Any]
) -> dict[str, Any]:
    """Rebuild from independent inputs; reject any forged success or authority."""
    expected = classify_exact_rule_inventory(proposal, source=source)
    if not isinstance(submitted, Mapping) or dict(submitted) != expected:
        raise RuleInventoryError("rule inventory mismatch or unsound promotion")
    return expected
