"""Source-only lexical import candidates for B8 architecture review.

A Name(Load) can refer to a shadowed or rebound name. Co-located import
bindings are not target-resolution, runtime-execution or ownership evidence.
"""
from __future__ import annotations

import ast
from collections.abc import Mapping
from hashlib import sha256
import json
import re
from typing import Any

from codeqa.evaluation.architecture.source_review_packets import (
    SourceReviewPacketError, _module_name, _observed_imports,
)


class ImportBindingUsageError(ValueError):
    """Untrusted source identity or import-witness denominator."""


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _sealed(value: Mapping[str, Any], key: str) -> bool:
    return value[key] == _digest({k: v for k, v in value.items() if k != key})


_SYNTAX_CONTEXTS = (
    "ANNOTATION_SYNTAX", "CALL_TARGET_SYNTAX",
    "ATTRIBUTE_ACCESS_SYNTAX", "OTHER_LOAD_SYNTAX",
)


def _load_syntax_context(
    node: ast.Name,
    parents: Mapping[int, tuple[ast.AST, str]],
) -> tuple[str, bool]:
    """Describe AST placement, never import binding or runtime target identity."""
    annotation = call = attribute = conditional = False
    # A Name inside an argument, subscript index or other nested expression
    # is not itself the receiver/callee merely because an outer expression
    # is called. Track only the AST receiver/callee spine toward the root.
    on_receiver_spine = True
    child: ast.AST = node
    while id(child) in parents:
        parent, field = parents[id(child)]
        if field in ("annotation", "returns") and isinstance(
            parent, (ast.arg, ast.AnnAssign, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            annotation = True
        if isinstance(parent, ast.Call) and field == "func" and on_receiver_spine:
            call = True
        if isinstance(parent, ast.Attribute) and field == "value" and on_receiver_spine:
            attribute = True
        if isinstance(parent, (ast.If, ast.IfExp)) and field in ("body", "orelse"):
            conditional = True
        # Review evidence must not treat loads in loop/handler/match/with
        # bodies as unguarded. This is syntactic reachability only: the
        # imported binding, runtime execution and ownership remain unknown.
        if (isinstance(parent, (ast.For, ast.AsyncFor, ast.While,
                                ast.With, ast.AsyncWith))
                and field in ("body", "orelse")):
            conditional = True
        if (isinstance(parent, (ast.Try, ast.TryStar))
                and field in ("handlers", "orelse")):
            conditional = True
        if isinstance(parent, ast.ExceptHandler) and field == "body":
            conditional = True
        if isinstance(parent, ast.match_case) and field in ("pattern", "guard", "body"):
            conditional = True
        if isinstance(parent, ast.Call):
            on_receiver_spine = on_receiver_spine and field == "func"
        elif isinstance(parent, (ast.Attribute, ast.Subscript)):
            on_receiver_spine = on_receiver_spine and field == "value"
        else:
            on_receiver_spine = False
        child = parent
    if annotation:
        return "ANNOTATION_SYNTAX", conditional
    if call:
        return "CALL_TARGET_SYNTAX", conditional
    if attribute:
        return "ATTRIBUTE_ACCESS_SYNTAX", conditional
    return "OTHER_LOAD_SYNTAX", conditional


def census_b8_import_binding_uses(
    selection: Mapping[str, Any],
    responsibility: Mapping[str, Any],
    source_bytes: Mapping[str, bytes],
) -> dict[str, Any]:
    """Enumerate lexical loads on each measured import line, without name resolution."""
    try:
        identity = selection["source_identity"]
        pairs = [tuple(pair) for pair in selection["pairs"]]
        edges = {(e["source_path"], e["target_path"]): e
                 for e in responsibility["edges"]}
        sources = {src for src, _ in pairs}
        hashes = selection["source_sha256"]
        if (selection["schema_version"] != "0.1"
                or responsibility["schema_version"] != "0.1"
                or not _sealed(selection, "selection_id")
                or not _sealed(responsibility, "responsibility_id")
                or identity["snapshot_sha"] != responsibility["source_identity"]["snapshot_sha"]
                or identity["responsibility_id"] != responsibility["responsibility_id"]
                or selection["decision"] != "NOT_EVALUATED"
                or responsibility["decision"] != "NOT_EVALUATED"
                or selection["observed_cross_role_pairs"] != len(pairs)
                or responsibility["observed_cross_role_pairs"] != len(edges)
                or len(pairs) != len(set(pairs))
                or len(edges) != len(responsibility["edges"])
                or set(pairs) != set(edges)
                or set(source_bytes) != sources
                or set(hashes) != {path for pair in pairs for path in pair}
                or not re.fullmatch(r"[0-9a-f]{40}", identity["snapshot_sha"])):
            raise ImportBindingUsageError("unbound source or pair denominator")

        import_nodes: dict[str, dict[int, list[ast.Import | ast.ImportFrom]]] = {}
        observed_imports: dict[str, dict[int, list[tuple[set[str], str, str]]]] = {}
        loads: dict[str, dict[str, list[dict[str, Any]]]] = {}
        for path in sorted(sources):
            raw = source_bytes[path]
            if not isinstance(raw, bytes) or sha256(raw).hexdigest() != hashes[path]:
                raise ImportBindingUsageError("source bytes do not match pinned hash")
            tree = ast.parse(raw, filename=path)
            by_line: dict[int, list[ast.Import | ast.ImportFrom]] = {}
            by_name: dict[str, list[dict[str, Any]]] = {}
            parents = {
                id(child): (node, field)
                for node in ast.walk(tree)
                for field, value in ast.iter_fields(node)
                for child in (value if isinstance(value, list) else [value])
                if isinstance(child, ast.AST)
            }
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    by_line.setdefault(node.lineno, []).append(node)
                elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                    kind, conditional = _load_syntax_context(node, parents)
                    by_name.setdefault(node.id, []).append({
                        "line": node.lineno, "column": node.col_offset,
                        "syntax_context": kind, "conditional_branch": conditional,
                    })
            import_nodes[path] = by_line
            # Use the same exact-module and expression resolver as B8 packets.
            # A co-located import on the same line is not enough to bind an edge.
            observed_imports[path] = _observed_imports(path, tree)
            loads[path] = by_name

        records = []
        for src, dst in sorted(pairs):
            witnesses = edges[(src, dst)]["import_witnesses"]
            if (not isinstance(witnesses, list) or not witnesses
                    or any(w["source_path"] != src
                           or w["target_path"] != dst
                           or w["source_sha256"] != hashes[src]
                           or type(w["line"]) is not int or w["line"] < 1
                           for w in witnesses)):
                raise ImportBindingUsageError("unbound static import witnesses")
            target_module, _ = _module_name(dst)
            for witness in witnesses:
                if not any(
                    target_module in modules
                    and witness["expression"] == expression
                    and witness["execution"] == execution
                    for modules, expression, execution
                    in observed_imports[src].get(witness["line"], ())
                ):
                    raise ImportBindingUsageError("witness does not bind the measured module")
            lines = sorted({w["line"] for w in witnesses})
            candidates = []
            for line in lines:
                expressions = {
                    w["expression"] for w in witnesses if w["line"] == line
                }
                nodes = import_nodes[src].get(line, [])
                if not nodes:
                    raise ImportBindingUsageError("witness line is not an AST import")
                for node in nodes:
                    if isinstance(node, ast.Import):
                        # A multi-alias import creates distinct module edges.
                        # Only aliases for this exact target belong to this pair.
                        aliases = [
                            alias for alias in node.names
                            if alias.name == target_module
                            and "import " + alias.name in expressions
                        ]
                    else:
                        # Imported members are still unverified: the dependency
                        # adapter binds the ImportFrom module, not its members.
                        aliases = node.names if ast.unparse(node) in expressions else []
                    for alias in aliases:
                        if isinstance(node, ast.ImportFrom):
                            name = alias.asname or alias.name
                        else:
                            name = alias.asname or alias.name.split(".")[0]
                        if name == "*":
                            candidates.append({
                                "line": line, "name": None, "lexical_load_count": 0,
                                "load_witnesses": [], "status": "STAR_IMPORT_UNRESOLVED",
                                "syntax_context_counts": {k: 0 for k in _SYNTAX_CONTEXTS},
                                "conditional_load_candidates": 0,
                            })
                            continue
                        positions = sorted(loads[src].get(name, []),
                                           key=lambda x: (x["line"], x["column"]))
                        candidates.append({
                            "line": line, "name": name,
                            "lexical_load_count": len(positions),
                            "load_witnesses": [
                                {"line": p["line"], "column": p["column"]}
                                for p in positions[:8]
                            ],
                            "syntax_context_counts": {
                                k: sum(p["syntax_context"] == k for p in positions)
                                for k in _SYNTAX_CONTEXTS
                            },
                            "conditional_load_candidates": sum(
                                bool(p["conditional_branch"]) for p in positions
                            ),
                            "status": ("NAME_LOAD_CANDIDATE" if positions
                                       else "NO_NAME_LOAD_IN_SOURCE"),
                        })
            records.append({
                "source_path": src,
                "target_path": dst,
                "source_sha256": hashes[src],
                "import_lines": lines,
                "candidate_bindings": candidates,
                "has_name_load_candidate": any(c["lexical_load_count"] for c in candidates),
                "syntax_context_counts": {
                    k: sum(c["syntax_context_counts"][k] for c in candidates)
                    for k in _SYNTAX_CONTEXTS
                },
                "conditional_load_candidates": sum(
                    c["conditional_load_candidates"] for c in candidates
                ),
                "binding_target_attribution": "LINE_COLOCATED_UNVERIFIED",
                "import_execution": "NOT_EVALUATED",
                "semantic_ownership": "NOT_EVALUATED",
            })
        result = {
            "schema_version": "0.1",
            "source_identity": identity,
            "selection_id": selection["selection_id"],
            "responsibility_id": responsibility["responsibility_id"],
            "static_pairs": len(records),
            "pairs_with_name_load_candidates": sum(x["has_name_load_candidate"] for x in records),
            "pairs_without_name_load_candidates": sum(not x["has_name_load_candidate"] for x in records),
            "records": records,
            "syntax_context_counts": {
                k: sum(r["syntax_context_counts"][k] for r in records)
                for k in _SYNTAX_CONTEXTS
            },
            "conditional_load_candidates": sum(
                r["conditional_load_candidates"] for r in records
            ),
            "evidence_class": "SOURCE_ONLY_LEXICAL_CANDIDATE_UNATTESTED",
            "import_execution": "NOT_EVALUATED",
            "semantic_ownership": "NOT_EVALUATED",
            "external_consumers": "NOT_EVALUATED",
            "public_api_compatibility": "NOT_EVALUATED",
            "decision": "NOT_EVALUATED",
            "limitations": [
                "import-line co-location does not attribute an alias to the target module",
                "lexical Name(Load) may be shadowed or rebound and is not runtime use proof",
                "no Name(Load) does not prove an import is unused or safe to remove",
                "AST annotation/call/attribute placements are syntax candidates, not ownership",
                "conditional branch placement does not prove branch execution",
                "annotations, reflection, wildcard and dynamic imports are not resolved",
                "external callers and package/public API compatibility remain unknown",
            ],
        }
        result["usage_id"] = _digest(result)
        return result
    except (KeyError, TypeError, AttributeError, ValueError,
            SyntaxError, SourceReviewPacketError) as exc:
        raise ImportBindingUsageError("invalid import binding usage evidence") from exc
