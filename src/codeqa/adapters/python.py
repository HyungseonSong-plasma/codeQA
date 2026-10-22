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

from .lexical import ModuleBindings


_PROVENANCE = {"producer": "python-ast", "method": "syntax"}


def _location(path: str, node: ast.AST) -> dict[str, Any]:
    return {
        "path": path,
        "start_line": node.lineno,
        "end_line": getattr(node, "end_lineno", node.lineno),
    }


class _Extract(ast.NodeVisitor):
    """Extract only syntax that can be established without type inference."""

    def __init__(self, path: str, tree: ast.Module) -> None:
        self.path = path
        self.bindings = ModuleBindings(tree, path)
        self.function_stack: list[ast.FunctionDef | ast.AsyncFunctionDef | None] = []
        self.dynamic_scope_depth = 0
        self.nodes: list[dict[str, Any]] = [{
            "id": f"file::{path}",
            "kind": "file",
            "name": path,
            "provenance": _PROVENANCE.copy(),
        }]
        self.edges: list[dict[str, Any]] = []
        self.scopes: list[tuple[str, str, str]] = [(f"file::{path}", "", "file")]

    def _edge(self, kind: str, node: ast.AST, *, source: str | None = None,
              target: str | None = None, hint: str | None = None,
              method: str = "syntax") -> None:
        edge: dict[str, Any] = {
            "source": source or self.scopes[-1][0],
            "kind": kind,
            "resolution": "resolved" if target is not None else "unresolved",
            "provenance": {"producer": "python-ast", "method": method},
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
        self.function_stack.append(node if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else None)
        # v0.1 deliberately excludes signature/decorator expression traversal:
        # those expressions execute in a different lexical context.
        for child in node.body:
            self.visit(child)
        self.function_stack.pop()
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

    def visit_Lambda(self, node: ast.Lambda) -> None:
        # Lambda scope and arguments are not yet modeled as CCG nodes.
        # Do not borrow an enclosing function's bindings for this body.
        return

    def visit_Call(self, node: ast.Call) -> None:
        # Only a direct module-level function body is eligible for local
        # lexical resolution; calls in methods/nested definitions remain hints.
        target = None
        if (
            len(self.scopes) == 2
            and self.scopes[-1][2] == "function"
            and self.dynamic_scope_depth == 0
            and self.function_stack[-1] is not None
        ):
            target = self.bindings.target(node.func, self.function_stack[-1])
        if target is not None:
            self._edge("calls", node, target=target, method="lexical_module_binding")
        else:
            self._edge("calls", node, hint=ast.unparse(node.func))
        self.generic_visit(node)

    def _comprehension(self, node: ast.AST) -> None:
        # Comprehension iteration targets may shadow module names.
        self.dynamic_scope_depth += 1
        self.generic_visit(node)
        self.dynamic_scope_depth -= 1

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self._comprehension(node)

    def visit_SetComp(self, node: ast.SetComp) -> None:
        self._comprehension(node)

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self._comprehension(node)

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self._comprehension(node)


def _extract_file(path: str, source: str) -> _Extract:
    """Parse and extract one file; the caller owns cross-file coverage accounting."""
    syntax = ast.parse(source, filename=path)
    result = _Extract(path, syntax)
    result.visit(syntax)
    return result


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
            result = _extract_file(path, sources[path])
        except SyntaxError as exc:
            unprocessed.append({"path": path, "reason": "syntax_error"})
            diagnostics.append({
                "severity": "error",
                "code": "PYTHON_SYNTAX_ERROR",
                "message": exc.msg,
                "path": path,
            })
            continue
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
