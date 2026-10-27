"""#144: bounded direct Python import witnesses and source-scope admission.

A direct import syntax witness does NOT establish resolved runtime identity,
reexports, public SDK/DTO/DB callers, semantic domain ownership or safe rename.
"""
from __future__ import annotations

import ast
from collections.abc import Mapping
from hashlib import sha1, sha256
from typing import Any

from codeqa.core.naming_field_classification_v03 import (
    FieldClassificationError, classify_pinned_class_annotation,
)


class ImportScopeEvidenceError(ValueError):
    """Invalid pinned source, uncertain binding, or forged approval assertion."""


def _blob(source: bytes) -> str:
    return sha1(b"blob " + str(len(source)).encode("ascii") + b"\0" + source).hexdigest()


def _load(source: bytes, path: str) -> ast.Module:
    if not isinstance(source, bytes):
        raise ImportScopeEvidenceError("exact source bytes are mandatory")
    try:
        return ast.parse(source.decode("utf-8"), filename=path)
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise ImportScopeEvidenceError("source not parseable UTF-8 Python") from exc


def classify_direct_import(source: bytes, *, path: str, symbol: str,
                           module: str) -> dict[str, Any]:
    """Conservative direct import recognition without module execution.

    Reexports, star imports, ambiguous aliases, binding overrides, dynamic
    namespaces, conditional imports and external consumers are NOT resolved.
    """
    tree = _load(source, path)
    imports = []
    unsupported = set()
    name_refs = 0
    for stmt in tree.body:
        if isinstance(stmt, ast.ImportFrom):
            if any(a.name == "*" for a in stmt.names):
                unsupported.add("RELATIVE_OR_WILDCARD_IMPORT")
            for a in stmt.names:
                bound = a.asname or a.name
                if bound == symbol and (stmt.level != 0 or
                                        stmt.module != module or a.name != symbol):
                    unsupported.add("TOP_LEVEL_SHADOWED_IMPORT")
                if stmt.level == 0 and stmt.module == module and a.name == symbol:
                    if a.asname not in (None, symbol):
                        unsupported.add("ALIASED_IMPORT_OR_POSSIBLE_REEXPORT")
                    imports.append((stmt.lineno, a.asname or a.name))
        elif isinstance(stmt, (ast.Import, ast.FunctionDef, ast.AsyncFunctionDef,
                               ast.ClassDef)):
            bound = set()
            if isinstance(stmt, ast.Import):
                bound = {a.asname or a.name.split(".")[0] for a in stmt.names}
            else:
                bound = {stmt.name}
            if symbol in bound:
                unsupported.add("TOP_LEVEL_SHADOWED_NAME")
        elif isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
            if any(isinstance(t, ast.Name) and t.id == symbol for t in targets):
                unsupported.add("TOP_LEVEL_REBINDING")
        elif isinstance(stmt, (ast.If, ast.For, ast.While, ast.With, ast.Try,
                               ast.AsyncFor, ast.AsyncWith)):
            # Could hide an import, export or binding mutation.
            unsupported.add("DYNAMIC_OR_CONDITIONAL_MODULE_BODY")
        elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            fn = stmt.value.func
            if isinstance(fn, ast.Name) and fn.id in {
                "exec", "eval", "__import__", "globals", "locals", "setattr"
            }:
                unsupported.add("DYNAMIC_NAMESPACE")
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == symbol and isinstance(node.ctx, ast.Load):
            name_refs += 1
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id in {"exec", "eval", "__import__"}:
            unsupported.add("DYNAMIC_NAMESPACE")
    unique = len(imports) == 1 and imports[0][1] == symbol
    status = ("DIRECT_IMPORT_SYNTAX_WITNESSED" if
              unique and name_refs >= 1 and not unsupported else
              "UNKNOWN")
    return {
        "path": path,
        "module": module,
        "symbol": symbol,
        "import_line": imports[0][0] if unique else None,
        "load_references_observed": name_refs,
        "status": status,
        "reason_codes": sorted(unsupported) if unsupported else (
            [] if status != "UNKNOWN" else ["MISSING_UNIQUE_IMPORT_OR_LOAD"]),
        "runtime_binding_identity": "NOT_EVALUATED",
        "reexport_graph": "NOT_EVALUATED",
        "external_consumer_compatibility": "NOT_EVALUATED",
        "rename_authorized": False,
    }


def audit_pinned_import_scope(fixture: Mapping[str, Any], *,
                              sources: Mapping[str, bytes]) -> dict[str, Any]:
    """Evaluate exactly the declared source/module and selected consumer sites.

    Hash validation is keyed to repository Git blob IDs. Caller independently
    obtains the three exact historical Git files at source_commit.
    """
    keys = {"schema_version", "source_commit", "source_tree_sha", "declaration",
            "consumers", "external_client_evidence", "owner_approval",
            "glossary_policy", "rename_authorized"}
    if (not isinstance(fixture, Mapping) or set(fixture) != keys
            or fixture["schema_version"] != "0.4-pinned-import-source-gate"
            or fixture["source_commit"] != "0177958aeb82ecdb019655244e35aef97e9e0fea"
            or fixture["source_tree_sha"] != "733afb47bda364d61976ebf82c3e188fde665e44"
            or fixture["external_client_evidence"] != "NOT_SUPPLIED"
            or fixture["owner_approval"] != "NOT_ADOPTED"
            or fixture["glossary_policy"] != "NOT_ADOPTED"
            or fixture["rename_authorized"] is not False):
        raise ImportScopeEvidenceError("non-authorizing exact pinned charter required")
    owner = fixture["declaration"]
    consumers = fixture["consumers"]
    if (not isinstance(owner, Mapping) or set(owner) != {
            "path", "blob_sha", "owner", "field_name", "line"}
            or not isinstance(consumers, list) or len(consumers) != 2
            or not isinstance(sources, Mapping)):
        raise ImportScopeEvidenceError("exact class owner and two selected consumers required")
    expected = (
        ("src/codeqa/core/complexity.py", "3b883e0daaf915b653da07650c533317a596623b"),
        ("src/codeqa/adapters/python_complexity.py", "caadcb45638869efc327f589d3a300c8ba2d9456"),
        ("src/codeqa/evaluation/complexity.py", "31587ca465dc2659c806cf6858715bb55c3e64c1"),
    )
    supplied = ((owner.get("path"), owner.get("blob_sha")),) + tuple(
        (c.get("path"), c.get("blob_sha")) for c in consumers)
    if supplied != expected or set(sources) != {p for p, _ in expected}:
        raise ImportScopeEvidenceError("source denominator/path/blob identity drift")
    for path, digest in expected:
        if not isinstance(sources[path], bytes) or _blob(sources[path]) != digest:
            raise ImportScopeEvidenceError("selected pinned Git blob does not match")
    if (owner["owner"], owner["field_name"], owner["line"]) != (
            "ControlFlowObservation", "node_id", 10):
        raise ImportScopeEvidenceError("not the source-identical node field")
    core = sources[owner["path"]]
    try:
        field = classify_pinned_class_annotation(
            core, expected_sha256=sha256(core).hexdigest(),
            owner="ControlFlowObservation", name="node_id", line=10)
    except FieldClassificationError as exc:
        raise ImportScopeEvidenceError("field owner not syntactically witnessed") from exc
    if field.classification != "FIELD_CANDIDATE":
        raise ImportScopeEvidenceError("field not a stdlib dataclass candidate")
    tree = _load(core, owner["path"])
    has_class = sum(isinstance(n, ast.ClassDef) and n.name == "ControlFlowObservation"
                    for n in tree.body)
    if has_class != 1:
        raise ImportScopeEvidenceError("declaration owner ambiguous")
    outcomes = []
    for consumer in consumers:
        if (not isinstance(consumer, Mapping)
                or set(consumer) != {"path", "blob_sha", "import_line"}
                or not isinstance(consumer["import_line"], int)):
            raise ImportScopeEvidenceError("malformed caller source witness")
        p = consumer["path"]
        witness = classify_direct_import(
            sources[p], path=p, symbol="ControlFlowObservation",
            module="codeqa.core.complexity")
        if (witness["status"] != "DIRECT_IMPORT_SYNTAX_WITNESSED"
                or witness["import_line"] != consumer["import_line"]):
            raise ImportScopeEvidenceError("exact direct import source evidence missing")
        outcomes.append(witness)
    return {
        "schema_version": "0.4-internal-source-import-scope-evidence",
        "source_commit": fixture["source_commit"],
        "source_tree_sha": fixture["source_tree_sha"],
        "selected_file_count": len(expected),
        "direct_import_witnesses": len(outcomes),
        "declaration_field_status": "FIELD_CANDIDATE",
        "source_role_scope": "SOURCE_SHAPE_ADMISSIBLE_ONLY",
        "reexport_graph": "NOT_EVALUATED",
        "transitive_binding_graph": "NOT_EVALUATED",
        "external_client_evidence": "NOT_SUPPLIED",
        "external_api_compatibility": "UNKNOWN",
        "domain_meaning": "NOT_EVALUATED",
        "owner_approval": "NOT_ADOPTED",
        "glossary_policy": "NOT_ADOPTED",
        "semantic_policy_gate": "UNKNOWN",
        "rename_authorized": False,
        "consumers": outcomes,
    }
