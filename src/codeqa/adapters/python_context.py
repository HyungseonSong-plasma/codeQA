"""Non-scoring syntactic context for interpreting CCG call-volume warnings.

All observations are source AST facts. "Chained attribute" is an AST shape,
not verified library identity, fluent semantics, a runtime call target or a
reason to suppress Mechanical v0.1 quality review.
"""
from __future__ import annotations

import ast
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any

from .python_snapshot import ParsedSnapshot


@dataclass(frozen=True, slots=True)
class FunctionSyntaxContext:
    node_id: str
    call_sites: int
    name_calls: int
    attribute_calls: int
    chained_attribute_calls: int
    other_calls: int
    distinct_callee_syntax: int
    frequent_callee_syntax: tuple[tuple[str, int], ...]
    branch_constructs: int
    loop_constructs: int
    try_constructs: int
    raise_statements: int
    return_statements: int
    call_expression_nesting_max: int
    interpretation: str = "SYNTAX_ONLY"

    def to_document(self) -> dict[str, Any]:
        return asdict(self)


class _ContextVisitor(ast.NodeVisitor):
    def __init__(self, path: str) -> None:
        self.path = path
        self.scopes: list[str] = []
        self.data: dict[str, dict[str, Any]] = {}
        self.active: list[str] = []
        self.call_depth = 0

    def _definition(self, node: ast.AST, name: str) -> None:
        qualified = ".".join((*self.scopes, name))
        identifier = f"def::{self.path}::{qualified}@{node.lineno}:{node.col_offset}"
        self.scopes.append(name)
        if isinstance(node, ast.ClassDef):
            # Class body executes in its own scope. CCG calls there are
            # associated with the class, not an enclosing function.
            suspended = self.active
            old_depth = self.call_depth
            self.active = []
            self.call_depth = 0
            for child in node.body:
                self.visit(child)
            self.active = suspended
            self.call_depth = old_depth
        else:
            self.data[identifier] = {
                "forms": Counter(), "hints": Counter(),
                "branches": 0, "loops": 0, "tries": 0,
                "raises": 0, "returns": 0, "depth": 0,
            }
            self.active.append(identifier)
            # Signature defaults and decorators are excluded, as in CCG v0.1.
            for child in node.body:
                self.visit(child)
            self.active.pop()
        self.scopes.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._definition(node, node.name)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._definition(node, node.name)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return  # CCG v0.1 also skips lambda scope.

    def visit_Call(self, node: ast.Call) -> None:
        if not self.active:
            self.generic_visit(node)
            return
        data = self.data[self.active[-1]]
        if isinstance(node.func, ast.Name):
            shape = "name"
        elif isinstance(node.func, ast.Attribute):
            shape = "chained" if isinstance(node.func.value, ast.Call) else "attribute"
        else:
            shape = "other"
        data["forms"][shape] += 1
        data["hints"][ast.unparse(node.func)] += 1
        self.call_depth += 1
        data["depth"] = max(data["depth"], self.call_depth)
        self.generic_visit(node)
        self.call_depth -= 1

    def generic_visit(self, node: ast.AST) -> None:
        if self.active:
            data = self.data[self.active[-1]]
            if isinstance(node, (
                ast.If, ast.IfExp, ast.While, ast.For, ast.AsyncFor,
                ast.ExceptHandler, ast.Match,
            )):
                data["branches"] += 1
            if isinstance(node, (ast.While, ast.For, ast.AsyncFor)):
                data["loops"] += 1
            if isinstance(node, (ast.Try, ast.TryStar)):
                data["tries"] += 1
            if isinstance(node, ast.Raise):
                data["raises"] += 1
            if isinstance(node, ast.Return):
                data["returns"] += 1
        super().generic_visit(node)

    def finish(self) -> tuple[FunctionSyntaxContext, ...]:
        observations = []
        for node_id, data in sorted(self.data.items()):
            count = data["forms"]
            hints = data["hints"]
            observations.append(FunctionSyntaxContext(
                node_id=node_id,
                call_sites=sum(count.values()),
                name_calls=count["name"],
                attribute_calls=count["attribute"],
                chained_attribute_calls=count["chained"],
                other_calls=count["other"],
                distinct_callee_syntax=len(hints),
                frequent_callee_syntax=tuple(sorted(
                    hints.items(), key=lambda item: (-item[1], item[0])
                )[:8]),
                branch_constructs=data["branches"],
                loop_constructs=data["loops"],
                try_constructs=data["tries"],
                raise_statements=data["raises"],
                return_statements=data["returns"],
                call_expression_nesting_max=data["depth"],
            ))
        return tuple(observations)


def extract_function_context(parsed: ParsedSnapshot) -> tuple[FunctionSyntaxContext, ...]:
    result: list[FunctionSyntaxContext] = []
    for item in parsed.files:
        assert item.tree is not None
        visitor = _ContextVisitor(item.path)
        visitor.visit(item.tree)
        result.extend(visitor.finish())
    return tuple(sorted(result, key=lambda observation: observation.node_id))
