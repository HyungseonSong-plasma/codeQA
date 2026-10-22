"""Conservative Python syntax-to-CCG v0.1 adapter.

Input is a pinned, in-memory source snapshot supplied by the caller.
No Git, filesystem, imports/execution, or speculative symbol resolution.
Coverage status describes parse coverage, not semantic completeness.
"""
from __future__ import annotations

import ast
from collections.abc import Mapping
from typing import Any

from codeqa.core import Graph, parse_graph


_PROVENANCE = {"producer": "python-ast", "method": "syntax"}


def _location(path: str, node: ast.AST) -> dict[str, Any]:
    return {
        "path": path,
        "start_line": node.lineno,
        "end_line": getattr(node, "end_lineno", node.lineno),
    }


class _Extract(ast.NodeVisitor):
    """Extract only syntax that can be established without type inference."""

    def __init__(self, path: str) -> None:
        self.path = path
        self.nodes: list[dict[str, Any]] = [{
            "id": f"file::{path}",
            "kind": "file",
            "name": path,
            "provenance": _PROVENANCE.copy(),
        }]
        self.edges: list[dict[str, Any]] = []
        self.scopes: list[tuple[str, str, str]] = [(f"file::{path}", "", "file")]

    def _edge(self, kind: str, node: ast.AST, *, source: str | None = None,
              target: str | None = None, hint: str | None = None) -> None:
        edge: dict[str, Any] = {
            "source": source or self.scopes[-1][0],
            "kind": kind,
            "resolution": "resolved" if target is not None else "unresolved",
            "provenance": _PROVENANCE.copy(),
            "location": _location(self.path, node),
        }
        if target is not None:
            edge["target"] = target
        else:
            edge["target_hint"] = hint
        self.edges.append(edge)

    def _definition(self, node: ast.AST, name: str, kind: str) -> None:
        parent_id, prefix, _ = self.scopes[-1]
        qualified = f"{prefix}.{name}" if prefix else name
        identifier = f"def::{self.path}::{qualified}@{node.lineno}:{node.col_offset}"
        self.nodes.append({
            "id": identifier,
            "kind": kind,
            "name": name,
            "provenance": _PROVENANCE.copy(),
            "location": _location(self.path, node),
        })
        self._edge("defines", node, source=parent_id, target=identifier)
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                self._edge("inherits", base, source=identifier, hint=ast.unparse(base))
        self.scopes.append((identifier, qualified, kind))
        # v0.1 deliberately excludes signature/decorator expression traversal:
        # those expressions execute in a different lexical context.
        for child in node.body:
            self.visit(child)
        self.scopes.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._definition(node, node.name, "class")

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        kind = "method" if self.scopes[-1][2] == "class" else "function"
        self._definition(node, node.name, kind)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        kind = "method" if self.scopes[-1][2] == "class" else "function"
        self._definition(node, node.name, kind)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._edge("imports", node, hint=alias.name)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        base = "." * node.level + (node.module or "")
        for alias in node.names:
            hint = f"{base}.{alias.name}" if base else alias.name
            self._edge("imports", node, hint=hint)

    def visit_Call(self, node: ast.Call) -> None:
        # ast.unparse is observed source syntax, NOT a resolved callee.
        self._edge("calls", node, hint=ast.unparse(node.func))
        self.generic_visit(node)


def adapt_python_sources(
    sources: Mapping[str, str],
    *,
    snapshot_id: str,
    schema: Mapping[str, Any],
) -> Graph:
    """Produce a Core-validated graph from a pinned mapping of source paths.

    The caller owns immutable snapshot acquisition. Syntax errors and unsupported
    extensions remain explicit unprocessed entries; they never become PASS.
    """
    if not isinstance(sources, Mapping) or not all(
        isinstance(p, str) and isinstance(text, str) for p, text in sources.items()
    ):
        raise TypeError("sources must map relative paths to Python source strings")
    if not isinstance(snapshot_id, str) or not snapshot_id:
        raise ValueError("snapshot_id must identify an immutable input snapshot")

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    analyzed: list[str] = []
    unprocessed: list[dict[str, str]] = []

    for path in sorted(sources):
        if not path.endswith(".py"):
            unprocessed.append({"path": path, "reason": "unsupported_extension"})
            continue
        try:
            syntax = ast.parse(sources[path], filename=path)
        except SyntaxError as exc:
            unprocessed.append({"path": path, "reason": "syntax_error"})
            diagnostics.append({
                "severity": "error",
                "code": "PYTHON_SYNTAX_ERROR",
                "message": exc.msg,
                "path": path,
            })
            continue
        result = _Extract(path)
        result.visit(syntax)
        nodes.extend(result.nodes)
        edges.extend(result.edges)
        analyzed.append(path)

    coverage = {
        "status": "partial" if analyzed and unprocessed
                  else "complete" if analyzed and not unprocessed else "none",
        "analyzed_paths": analyzed,
        "unprocessed": unprocessed,
    }
    return parse_graph({
        "schema_version": "0.1",
        "snapshot": {"id": snapshot_id},
        "nodes": nodes,
        "edges": edges,
        "coverage": coverage,
        "diagnostics": diagnostics,
    }, schema)
