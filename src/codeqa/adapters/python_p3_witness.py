"""Python AST-only call fingerprints for extraction-aware P3 companions.

Source parsing, lexical ownership and AST syntax belong to the Adapter.
Evaluation receives language-neutral immutable witnesses and CCG facts.
"""
from __future__ import annotations

import ast
from hashlib import sha256
from collections.abc import Mapping

from codeqa.core.p3_witness import P3CallEvidence, P3CallWitness
from .python_snapshot import parse_python_snapshot


class _Calls(ast.NodeVisitor):
    def __init__(self, path: str, node_id: str, owner: str) -> None:
        self.path = path
        self.node_id = node_id
        self.owner = owner
        self.items: list[P3CallWitness] = []

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        return  # Nested function calls belong to the nested declaration.

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return  # CCG v0.1 excludes lambda's independent execution scope.

    def visit_Call(self, node: ast.Call) -> None:
        syntax = ast.dump(node, include_attributes=False)
        self.items.append(P3CallWitness(
            node_id=self.node_id, owner=self.owner, path=self.path,
            line=node.lineno, expression=ast.unparse(node),
            callee_spelling=ast.unparse(node.func),
            syntax_sha256=sha256(syntax.encode("utf-8")).hexdigest(),
        ))
        self.generic_visit(node)


class _Functions(ast.NodeVisitor):
    def __init__(self, path: str) -> None:
        self.path = path
        self.prefix: list[str] = []
        self.witnesses: dict[str, tuple[P3CallWitness, ...]] = {}

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.prefix.append(node.name)
        for statement in node.body:
            self.visit(statement)
        self.prefix.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        qualified = ".".join((*self.prefix, node.name))
        node_id = f"def::{self.path}::{qualified}@{node.lineno}:{node.col_offset}"
        if node_id in self.witnesses:
            raise ValueError("duplicate lexical AST owner ID")
        visitor = _Calls(self.path, node_id, qualified)
        for statement in node.body:
            visitor.visit(statement)
        self.witnesses[node_id] = tuple(sorted(
            visitor.items,
            key=lambda x: (x.syntax_sha256, x.line, x.expression),
        ))
        self.prefix.append(node.name)
        for statement in node.body:
            self.visit(statement)
        self.prefix.pop()

    visit_AsyncFunctionDef = visit_FunctionDef


def extract_python_p3_call_evidence(
    sources: Mapping[str, str],
) -> P3CallEvidence:
    """Extract from exact caller source bytes; never import or execute them."""
    parsed = parse_python_snapshot(sources)
    calls = []
    for item in parsed.files:
        assert item.tree is not None
        visitor = _Functions(item.path)
        visitor.visit(item.tree)
        calls.extend(visitor.witnesses.items())
    return P3CallEvidence(
        producer="python-ast-p3-v0.1",
        source_sha256=tuple(sorted(
            (path, sha256(content.encode("utf-8")).hexdigest())
            for path, content in sources.items()
        )),
        analyzed_paths=parsed.analyzed_paths,
        unprocessed=tuple(sorted(parsed.unprocessed)),
        calls=tuple(sorted(calls, key=lambda entry: entry[0])),
    )
