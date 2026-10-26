"""Bounded exact-source role evidence for #144: no glossary or rename approval.

This module verifies generator/parameter/dataclass *source shapes* of thirteen
existing node_id declarations. It does NOT prove domain meaning, external
binding resolution, or compatibility with consumers.
"""
from __future__ import annotations

import ast
from collections.abc import Mapping
from hashlib import sha256
from typing import Any

from codeqa.core.naming_field_classification_v03 import (
    FieldClassificationError, classify_pinned_class_annotation,
)
from codeqa.core.naming_scope_discovery_v04 import scan_explicit_spellings


class NodeRoleEvidenceError(ValueError):
    """Historical source identity, rule shape, or claimed role evidence drift."""


_RULES = {
    "local_binding": "DECLARATION_ID_FSTRING_GENERATOR",
    "parameter": "STRING_ANNOTATED_PARAMETER",
    "class_annotation": "STDLIB_DATACLASS_STRING_FIELD_CANDIDATE",
}
_ROLE = "internal_declaration_node_identity_candidate"
_IDENTITY = ("path", "line", "owner", "name", "syntax_kind")


def _shape(source: bytes, row: Mapping[str, Any]) -> str:
    path, name, line, owner, kind = (row[k] for k in _IDENTITY)
    if kind not in _RULES or name != "node_id" or not isinstance(source, bytes):
        raise NodeRoleEvidenceError("unsupported exact site")
    observed = scan_explicit_spellings(
        source, path=path, targets=("time_step", "timestep", "node_id", "nodeid"))
    matches = [x for x in observed if
               (x["path"], x["name"], x["line"], x["owner"],
                x["source_kind"]) == (path, name, line, owner, kind)]
    if len(matches) != 1:
        raise NodeRoleEvidenceError("unique exact lexical AST site missing")
    tree = ast.parse(source.decode("utf-8"), filename=path)
    if kind == "class_annotation":
        try:
            field = classify_pinned_class_annotation(
                source, expected_sha256=sha256(source).hexdigest(),
                owner=owner, name=name, line=line)
        except FieldClassificationError as exc:
            raise NodeRoleEvidenceError("class field candidate not proven") from exc
        if field.classification != "FIELD_CANDIDATE":
            raise NodeRoleEvidenceError("not a static dataclass field candidate")
        nodes = [x for x in ast.walk(tree) if isinstance(x, ast.AnnAssign)
                 and x.lineno == line and isinstance(x.target, ast.Name)
                 and x.target.id == name and x.simple == 1
                 and isinstance(x.annotation, ast.Name)
                 and x.annotation.id == "str"]
        if len(nodes) != 1:
            raise NodeRoleEvidenceError("expected direct annotated string field")
    elif kind == "parameter":
        nodes = [x for x in ast.walk(tree) if isinstance(x, ast.arg)
                 and x.lineno == line and x.arg == name
                 and isinstance(x.annotation, ast.Name)
                 and x.annotation.id == "str"]
        if len(nodes) != 1:
            raise NodeRoleEvidenceError("expected unique typed string argument")
    else:
        nodes = [x for x in ast.walk(tree) if isinstance(x, ast.Assign)
                 and x.lineno == line and len(x.targets) == 1
                 and isinstance(x.targets[0], ast.Name)
                 and x.targets[0].id == name]
        if len(nodes) != 1 or not isinstance(nodes[0].value, ast.JoinedStr):
            raise NodeRoleEvidenceError("expected declaration-ID f-string")
        values = nodes[0].value.values
        literal = [v.value for v in values if isinstance(v, ast.Constant)]
        exprs = [ast.unparse(v.value) for v in values
                 if isinstance(v, ast.FormattedValue)]
        if literal != ["def::", "::", "@", ":"] or exprs not in (
                ["self.path", "name", "node.lineno", "node.col_offset"],
                ["self.path", "qualified", "node.lineno", "node.col_offset"]):
            raise NodeRoleEvidenceError("not a bounded declaration-ID pattern")
    return _RULES[kind]


def assess_pinned_node_role(
    discovered: Mapping[str, Any], *, sources: Mapping[str, bytes],
    fixture: Mapping[str, Any],
) -> dict[str, Any]:
    """Check all 13 sites, exact tree pin and source integrity.

    The caller first builds discovered using the independent full Git tree
    adapter. A source hash matches bytes, not an external-caller contract.
    """
    if (not isinstance(discovered, Mapping) or not isinstance(fixture, Mapping)
            or not isinstance(sources, Mapping)
            or set(fixture) != {
                "schema_version", "source_commit", "source_tree_sha", "status",
                "sites", "approved_scopes", "semantic_policy", "rename_authorized"
            } or fixture["schema_version"] != "0.4-node-id-role-witness"
            or fixture["status"] != "SOURCE_ROLE_CANDIDATES_ONLY"
            or fixture["approved_scopes"] != []
            or fixture["semantic_policy"] != "NOT_ADOPTED"
            or fixture["rename_authorized"] is not False):
        raise NodeRoleEvidenceError("not a non-authorizing role fixture")
    if (fixture["source_commit"] != discovered.get("source_commit")
            or fixture["source_tree_sha"] != discovered.get("source_tree_sha")):
        raise NodeRoleEvidenceError("source tree pin mismatch")
    candidates = discovered.get("proposed_path_role_scopes")
    declared = fixture["sites"]
    if not isinstance(candidates, list) or not isinstance(declared, list) \
            or len(candidates) != 13 or len(declared) != 13:
        raise NodeRoleEvidenceError("all 13 selected AST sites required")
    expected_sites = [{
        "path": x["path"], "line": x["source_line"],
        "owner": x["lexical_owner"], "name": x["source_name"],
        "syntax_kind": x["kind"],
    } for x in candidates]
    actual_sites = [{k: x.get(k) for k in _IDENTITY} for x in declared]
    if actual_sites != expected_sites:
        raise NodeRoleEvidenceError("forged, reordered, omitted or extra AST site")
    info = {f["path"]: f for f in discovered["file_evidence"]}
    outcomes = []
    for row in declared:
        if (not isinstance(row, Mapping)
                or set(row) != set(_IDENTITY) | {"evidence_rule", "role_candidate"}):
            raise NodeRoleEvidenceError("unexpected role/policy assertion")
        path = row["path"]
        if path not in sources or path not in info:
            raise NodeRoleEvidenceError("missing independently pinned source")
        data = sources[path]
        if not isinstance(data, bytes) or sha256(data).hexdigest() != info[path]["source_sha256"]:
            raise NodeRoleEvidenceError("source content not equal to audited blob")
        actual_rule = _shape(data, row)
        if row["evidence_rule"] != actual_rule or row["role_candidate"] != _ROLE:
            raise NodeRoleEvidenceError("unsupported or promoted semantic claim")
        outcomes.append({
            **{k: row[k] for k in _IDENTITY},
            "evidence_rule": actual_rule, "role_candidate": _ROLE,
            "source_sha256": sha256(data).hexdigest(),
            "runtime_value_semantics": "NOT_EVALUATED",
            "external_compatibility": "NOT_EVALUATED",
            "meaning_approved": False, "path_scope_approved": False,
            "rename_authorized": False,
        })
    return {
        "schema_version": "0.4-node-id-source-role-evidence",
        "source_commit": discovered["source_commit"],
        "source_tree_sha": discovered["source_tree_sha"],
        "source_python_file_count": discovered["selected_source_file_count"],
        "sites_checked": len(outcomes),
        "generator_patterns": sum(x["evidence_rule"] ==
                                  _RULES["local_binding"] for x in outcomes),
        "string_parameters": sum(x["evidence_rule"] ==
                                 _RULES["parameter"] for x in outcomes),
        "dataclass_field_candidates": sum(x["evidence_rule"] ==
                                          _RULES["class_annotation"] for x in outcomes),
        "source_role_candidate": _ROLE,
        "semantic_status": "NOT_EVALUATED",
        "approved_scopes": [],
        "external_compatibility": "NOT_EVALUATED",
        "rename_authorized": False,
        "sites": outcomes,
    }
