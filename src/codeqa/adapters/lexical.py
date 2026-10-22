"""Conservative, source-local Python function binding evidence.

Only direct, undecorated module-level functions with a unique unshadowed
binding are candidates. "Resolved" denotes a statically observed lexical
binding, not a guarantee of the runtime callable in dynamic Python.
"""
from __future__ import annotations

import ast
from collections import Counter


class _Bindings(ast.NodeVisitor):
    """Collect names assigned in one scope, without entering nested scopes."""

    def __init__(self) -> None:
        self.names: list[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.names.append(node.name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.names.append(node.name)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.names.append(node.name)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return

    def visit_Import(self, node: ast.Import) -> None:
        self.names.extend(a.asname or a.name.split(".")[0] for a in node.names)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self.names.extend(a.asname or a.name for a in node.names)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self.names.append(node.id)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name:
            self.names.append(node.name)
        self.generic_visit(node)

    def visit_MatchAs(self, node: ast.MatchAs) -> None:
        if node.name:
            self.names.append(node.name)
        self.generic_visit(node)

    def visit_MatchStar(self, node: ast.MatchStar) -> None:
        if node.name:
            self.names.append(node.name)

    def visit_MatchMapping(self, node: ast.MatchMapping) -> None:
        if node.rest:
            self.names.append(node.rest)
        self.generic_visit(node)


def _local_bindings(function: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    args = function.args
    bound = {arg.arg for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs)}
    for item in (args.vararg, args.kwarg):
        if item is not None:
            bound.add(item.arg)
    visitor = _Bindings()
    for statement in function.body:
        visitor.visit(statement)
    bound.update(visitor.names)
    # Explicit global/nonlocal declarations and rebinding make any inferred
    # local target ambiguous, even if the syntax also contains a static def.
    for statement in function.body:
        for child in ast.walk(statement):
            if isinstance(child, (ast.Global, ast.Nonlocal)):
                bound.update(child.names)
    return bound


class ModuleBindings:
    """Resolve only a uniquely declared, unshadowed direct module function."""

    def __init__(self, tree: ast.Module, path: str) -> None:
        collector = _Bindings()
        for statement in tree.body:
            collector.visit(statement)
        counts = Counter(collector.names)
        # Any explicit global assignment from nested code may overwrite a
        # module binding; exclude such names rather than guessing.
        globals_declared = {
            name
            for item in ast.walk(tree)
            if isinstance(item, ast.Global)
            for name in item.names
        }
        self.targets = {
            item.name: f"def::{path}::{item.name}@{item.lineno}:{item.col_offset}"
            for item in tree.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not item.decorator_list
            and counts[item.name] == 1
            and item.name not in globals_declared
        }

    def target(
        self, callee: ast.expr, caller: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> str | None:
        if not isinstance(callee, ast.Name):
            return None
        if callee.id in _local_bindings(caller):
            return None
        return self.targets.get(callee.id)
