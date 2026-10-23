"""Bounded Python 3.12 AST complexity observations; no execution.

Separate from existing function-call context and CCG v0.1. All per-function
decision counting explicitly skips nested lexical definitions, decorators,
signature expressions and lambda bodies. Such unresolved constructs mark the
function NOT_EVALUATED rather than fabricating a low complexity result.
"""
from __future__ import annotations

import ast

from codeqa.core.complexity import ControlFlowObservation, BodyComplexityEvidence
from .python_snapshot import ParsedSnapshot


class _Decisions(ast.NodeVisitor):
    def __init__(self) -> None:
        self.decisions = 0
        self.depth = 0
        self.max_depth = 0
        self.limitations: set[str] = set()

    def branch(self, *groups: list[ast.AST]) -> None:
        self.depth += 1
        self.max_depth = max(self.max_depth, self.depth)
        for group in groups:
            for item in group:
                self.visit(item)
        self.depth -= 1

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return  # Child function gets its own independent observation.

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return  # No enclosing function score for a class definition.

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self.limitations.add("lambda_body_not_evaluated")

    def visit_If(self, node: ast.If) -> None:
        self.decisions += 1
        self.visit(node.test)
        self.branch(node.body, node.orelse)

    def visit_IfExp(self, node: ast.IfExp) -> None:
        self.decisions += 1
        self.visit(node.test)
        self.branch([node.body, node.orelse])

    def visit_For(self, node: ast.For) -> None:
        self.decisions += 1
        self.visit(node.target)
        self.visit(node.iter)
        self.branch(node.body, node.orelse)

    visit_AsyncFor = visit_For

    def visit_While(self, node: ast.While) -> None:
        self.decisions += 1
        self.visit(node.test)
        self.branch(node.body, node.orelse)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        self.decisions += max(0, len(node.values) - 1)
        for value in node.values:
            self.visit(value)

    def visit_Try(self, node: ast.Try) -> None:
        self.decisions += len(node.handlers)
        self.branch(node.body, node.handlers, node.orelse, node.finalbody)

    visit_TryStar = visit_Try

    def visit_Match(self, node: ast.Match) -> None:
        # Number of alternative outcomes minus one, *not* full pattern
        # matching/runtime exhaustiveness analysis.
        self.decisions += max(0, len(node.cases) - 1)
        self.visit(node.subject)
        self.branch(node.cases)

    def visit_comprehension(self, node: ast.comprehension) -> None:
        self.decisions += 1 + len(node.ifs)
        self.visit(node.target)
        self.visit(node.iter)
        for condition in node.ifs:
            self.visit(condition)

    def visit_TypeAlias(self, node: ast.AST) -> None:
        self.limitations.add("type_alias_semantics_not_evaluated")

    def generic_visit(self, node: ast.AST) -> None:
        super().generic_visit(node)


class _Declarations(ast.NodeVisitor):
    def __init__(self, path: str, *, body_only: bool = False) -> None:
        self.path = path
        self.body_only = body_only
        self.scope: list[str] = []
        self.results: list[ControlFlowObservation] = []
        self.ignored_declarations: list[tuple[str, tuple[str, ...]]] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scope.append(node.name)
        for child in node.body:
            self.visit(child)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        qualified = ".".join((*self.scope, node.name))
        identifier = f"def::{self.path}::{qualified}@{node.lineno}:{node.col_offset}"
        counter = _Decisions()
        for child in node.body:
            counter.visit(child)
        ignored: set[str] = set()
        if node.decorator_list:
            ignored.add("decorators_excluded_from_body_scope")
        arguments = node.args
        if (arguments.defaults or any(x is not None for x in arguments.kw_defaults)
                or node.returns is not None
                or any(a.annotation is not None for a in
                       (*arguments.posonlyargs, *arguments.args,
                        *arguments.kwonlyargs, *( [arguments.vararg] if arguments.vararg else []),
                        *( [arguments.kwarg] if arguments.kwarg else [])))):
            ignored.add("signature_expressions_excluded_from_body_scope")
        if self.body_only:
            if ignored:
                self.ignored_declarations.append((identifier, tuple(sorted(ignored))))
        else:
            for tag in ignored:
                counter.limitations.add({
                    "decorators_excluded_from_body_scope": "decorators_not_evaluated",
                    "signature_expressions_excluded_from_body_scope":
                        "signature_expressions_not_evaluated",
                }[tag])
        limited = bool(counter.limitations)
        self.results.append(ControlFlowObservation(
            node_id=identifier, path=self.path,
            start_line=node.lineno, end_line=node.end_lineno or node.lineno,
            decision_count=None if limited else counter.decisions,
            cyclomatic_proxy=None if limited else 1 + counter.decisions,
            branch_nesting_max=None if limited else counter.max_depth,
            limitations=tuple(sorted(counter.limitations)),
            status="NOT_EVALUATED" if limited else "MEASURED",
            producer="python-ast-body-complexity-v0.2" if self.body_only
                     else "python-ast-complexity-v0.1",
            method="bounded_body_ast_syntax_no_annotation_execution" if self.body_only
                   else "bounded_python_ast_syntax",
        ))
        self.scope.append(node.name)
        for child in node.body:
            self.visit(child)
        self.scope.pop()

    visit_AsyncFunctionDef = visit_FunctionDef


def extract_python_complexity(
    parsed: ParsedSnapshot,
) -> tuple[ControlFlowObservation, ...]:
    """Use caller-owned AST snapshot; no reparse, runtime or external IO."""
    results = []
    for item in parsed.files:
        if item.tree is None:
            raise ValueError("analyzed ParsedFile must contain AST")
        visitor = _Declarations(item.path)
        visitor.visit(item.tree)
        results.extend(visitor.results)
    return tuple(sorted(results, key=lambda x: x.node_id))


def extract_python_body_complexity(
    parsed: ParsedSnapshot,
) -> BodyComplexityEvidence:
    """Opt-in body-only analysis. Decorators/signatures are not traversed.

    Ignoring declaration expressions is a *declared scope exclusion*, not
    permission to count unknown lambda/type-alias bodies as complexity zero.
    Reuses the caller's parsed snapshot; never evaluates Python expressions.
    """
    results: list[ControlFlowObservation] = []
    ignored: list[tuple[str, tuple[str, ...]]] = []
    for item in parsed.files:
        if item.tree is None:
            raise ValueError("analyzed ParsedFile must contain AST")
        collector = _Declarations(item.path, body_only=True)
        collector.visit(item.tree)
        results.extend(collector.results)
        ignored.extend(collector.ignored_declarations)
    return BodyComplexityEvidence(
        observations=tuple(sorted(results, key=lambda x: x.node_id)),
        ignored_declarations=tuple(sorted(ignored)),
        unprocessed=tuple(sorted(parsed.unprocessed)),
        producer="python-ast-body-complexity-v0.2",
    )
