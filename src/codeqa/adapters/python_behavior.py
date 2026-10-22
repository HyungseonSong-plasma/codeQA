"""Python AST evidence for uniquely declared API call *syntax*, not effects.

A match requires a unique top-level import and an unchanged binding name
throughout the source module. This conservative global shadow check will miss
valid calls but avoids inventing their identities. Never import target code.
"""
from __future__ import annotations

import ast
from collections import Counter

from codeqa.adapters.python_snapshot import ParsedSnapshot
from codeqa.core.behavior import BehaviorObservation
from codeqa.core.evidence import EvidenceIndex


def _declared_bindings(tree: ast.Module) -> dict[str, tuple[str, str | None]]:
    candidates: dict[str, list[tuple[str, str | None]]] = {}
    for statement in tree.body:
        if isinstance(statement, ast.Import):
            for alias in statement.names:
                # Dotted imports without an alias do NOT bind the full module.
                if alias.asname is None and "." in alias.name:
                    continue
                name = alias.asname or alias.name
                candidates.setdefault(name, []).append((alias.name, None))
        elif isinstance(statement, ast.ImportFrom) and statement.level == 0 and statement.module:
            for alias in statement.names:
                if alias.name == "*":
                    return {}
                name = alias.asname or alias.name
                candidates.setdefault(name, []).append((statement.module, alias.name))

    reassigned: set[str] = {
        node.id for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del))
    }
    reassigned.update(
        node.arg for node in ast.walk(tree) if isinstance(node, ast.arg)
    )
    reassigned.update(
        name for node in ast.walk(tree)
        if isinstance(node, (ast.Global, ast.Nonlocal)) for name in node.names
    )
    reassigned.update(
        node.name for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    )
    reassigned.update(
        node.name for node in ast.walk(tree)
        if isinstance(node, ast.ExceptHandler) and node.name is not None
    )
    return {
        name: matches[0] for name, matches in candidates.items()
        if len(matches) == 1 and name not in reassigned
    }


class _Calls(ast.NodeVisitor):
    def __init__(self, path: str) -> None:
        self.path = path
        self.scopes: list[str] = []
        self.active: list[str] = []
        self.calls: list[tuple[str, ast.Call]] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scopes.append(node.name)
        # Calls in a class body are not attributed to an enclosing function.
        previous = self.active
        self.active = []
        for stmt in node.body:
            self.visit(stmt)
        self.active = previous
        self.scopes.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        name = ".".join((*self.scopes, node.name))
        node_id = f"def::{self.path}::{name}@{node.lineno}:{node.col_offset}"
        self.scopes.append(node.name)
        self.active.append(node_id)
        # Defaults and decorators execute outside the function body.
        for stmt in node.body:
            self.visit(stmt)
        self.active.pop()
        self.scopes.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return

    def visit_Call(self, node: ast.Call) -> None:
        if self.active:
            self.calls.append((self.active[-1], node))
        self.generic_visit(node)


def extract_python_behavior_observations(
    parsed: ParsedSnapshot,
    evidence: EvidenceIndex,
    signatures: dict[tuple[str, str], str],
) -> tuple[tuple[BehaviorObservation, ...], int, tuple[tuple[str, int], ...]]:
    """Extract cataloged calls using source evidence and existing parsed ASTs."""
    if not all(
        isinstance(m, str) and isinstance(s, str) and isinstance(k, str)
        for (m, s), k in signatures.items()
    ):
        raise ValueError("invalid API signature registry")
    facts = {
        (f.path, f.line, f.column, f.expression): f.evidence_id
        for f in evidence.facts if f.kind == "call"
    }
    seen: list[BehaviorObservation] = []
    excluded: Counter[str] = Counter()
    total = 0
    for file in parsed.files:
        tree = file.tree
        assert tree is not None
        bindings = _declared_bindings(tree)
        walker = _Calls(file.path)
        walker.visit(tree)
        for node_id, call in walker.calls:
            total += 1
            module = symbol = None
            fn = call.func
            if isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name):
                alias = bindings.get(fn.value.id)
                if alias and alias[1] is None:
                    module, symbol = alias[0], fn.attr
            elif isinstance(fn, ast.Name):
                alias = bindings.get(fn.id)
                if alias and alias[1] is not None:
                    module, symbol = alias
            if module is None or symbol is None:
                excluded["not_unique_unshadowed_explicit_import"] += 1
                continue
            kind = signatures.get((module, symbol))
            if kind is None:
                excluded["not_in_verified_api_catalog"] += 1
                continue
            expression = ast.unparse(fn)
            witness = facts.get((file.path, call.lineno, call.col_offset, expression))
            if witness is None:
                excluded["no_exact_call_source_witness"] += 1
                continue
            seen.append(BehaviorObservation(
                source_node_id=node_id, path=file.path,
                line=call.lineno, column=call.col_offset,
                expression=expression, declared_module=module,
                declared_symbol=symbol, behavior_kind=kind,
                evidence_id=witness,
            ))
    return (
        tuple(sorted(seen, key=lambda o: (
            o.path, o.line, o.column, o.source_node_id, o.behavior_kind,
        ))),
        total,
        tuple(sorted(excluded.items())),
    )
