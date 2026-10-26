"""Source-scoped AST *observations* for #91; never a signed Naming verdict.

The source hash authenticates supplied bytes only. Git commit/blob provenance must
be verified separately by the caller. Observations are not a complete Python
binding graph, human adjudication, or permission to rename.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from hashlib import sha256
import re
from typing import Any, Mapping


class DeclarationEvidenceError(ValueError):
    """Invalid or stale source for an opt-in declaration review."""


@dataclass(frozen=True, slots=True)
class DeclarationObservation:
    name: str
    kind: str
    line: int
    owner: str
    ast_node: str

    @property
    def eligible_kind(self) -> bool:
        """Kind-level eligibility only; ownership/API review is still required."""
        return self.kind in {"function", "method", "parameter", "declared_field"}


@dataclass(frozen=True, slots=True)
class DecoratorObservation:
    expression: str
    callee: str
    line: int
    owner: str


@dataclass(frozen=True, slots=True)
class PythonDeclarationReview:
    source_sha256: str
    declarations: tuple[DeclarationObservation, ...]
    decorators: tuple[DecoratorObservation, ...]
    review_status: str = "PENDING_FINAL_ADJUDICATION"
    semantic_proven: bool = False
    human_review_required: bool = True

    def classify_candidate(self, candidate: Mapping[str, Any]) -> str:
        """Return structural observation only, never human ACCEPT/PASS."""
        if not isinstance(candidate, Mapping):
            raise DeclarationEvidenceError("candidate must be an object")
        try:
            name, kind, line, owner = (
                candidate["name"], candidate["kind"],
                candidate["line"], candidate["owner"],
            )
        except KeyError as exc:
            raise DeclarationEvidenceError("candidate missing identity") from exc
        if (not isinstance(name, str) or not isinstance(kind, str)
                or type(line) is not int or not isinstance(owner, str)):
            raise DeclarationEvidenceError("candidate identity has invalid types")
        if kind == "decorator":
            # Compare parsed syntax, not whitespace-stripped text: whitespace
            # inside a literal is semantically significant.
            try:
                candidate_ast = ast.dump(ast.parse(name, mode="eval").body,
                                         include_attributes=False)
            except SyntaxError:
                return "NOT_EVALUATED"
            return ("SYNTAX_ONLY" if any(
                d.line == line and d.owner == owner
                and ast.dump(ast.parse(d.expression, mode="eval").body,
                             include_attributes=False) == candidate_ast
                for d in self.decorators
            ) else "NOT_EVALUATED")
        if any(d.name == name and d.kind == kind and d.line == line
               and d.owner == owner for d in self.declarations):
            return "AST_OBSERVED"
        return "NOT_EVALUATED"


class _Collector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.scope: list[tuple[str, str]] = []
        self.declarations: list[DeclarationObservation] = []
        self.decorators: list[DecoratorObservation] = []
        # AST annotation spellings only; never attest runtime semantics.
        self._nonfield_annotation_names = {"ClassVar", "Final"}

    def owner(self) -> str:
        return ".".join(name for name, _ in self.scope)

    def record(self, name: str, kind: str, node: ast.AST) -> None:
        self.declarations.append(DeclarationObservation(
            name, kind, node.lineno, self.owner(), type(node).__name__,
        ))

    def decorated(self, node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        for expr in node.decorator_list:
            target = expr.func if isinstance(expr, ast.Call) else expr
            callee = ast.unparse(target)
            self.decorators.append(DecoratorObservation(
                ast.unparse(expr), callee, expr.lineno, node.name,
            ))

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.record(node.name, "class", node)
        self.decorated(node)
        self.scope.append((node.name, "class"))
        for stmt in node.body:
            self.visit(stmt)
        self.scope.pop()

    def _function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        kind = "method" if self.scope and self.scope[-1][1] == "class" else "function"
        self.record(node.name, kind, node)
        self.decorated(node)
        self.scope.append((node.name, "function"))
        arguments = node.args
        params = (arguments.posonlyargs + arguments.args + arguments.kwonlyargs
                  + ([arguments.vararg] if arguments.vararg else [])
                  + ([arguments.kwarg] if arguments.kwarg else []))
        for param in params:
            self.record(param.arg, "parameter", param)
        for stmt in node.body:
            self.visit(stmt)
        self.scope.pop()

    visit_FunctionDef = _function
    visit_AsyncFunctionDef = _function

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.record(alias.asname or alias.name.split(".")[0], "import_binding", node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            if alias.name != "*":
                self.record(alias.asname or alias.name, "import_binding", node)
                if (not self.scope and node.level == 0
                        and node.module in {"typing", "typing_extensions"}
                        and alias.name in {"ClassVar", "Final"}):
                    self._nonfield_annotation_names.add(alias.asname or alias.name)

    def _unresolved_class_annotation(self, annotation: ast.AST) -> bool:
        """ClassVar/Final syntax is not a proved instance/dataclass field.

        Final may denote instance state, not necessarily a class constant.
        Unresolved qualified spellings are conservatively excluded rather
        than assuming import/runtime identity or granting Naming eligibility.
        """
        base = annotation.value if isinstance(annotation, ast.Subscript) else annotation
        if isinstance(base, ast.Name):
            return base.id in self._nonfield_annotation_names
        return isinstance(base, ast.Attribute) and base.attr in {"ClassVar", "Final"}

    @staticmethod
    def _names(target: ast.AST) -> list[str]:
        if isinstance(target, ast.Name):
            return [target.id]
        if isinstance(target, (ast.Tuple, ast.List)):
            return [name for item in target.elts for name in _Collector._names(item)]
        if isinstance(target, ast.Starred):
            return _Collector._names(target.value)
        # Attribute/subscript assignment is not a locally declared identifier.
        return []

    def _binding_kind(self, *, annotated: bool = False) -> str:
        if not self.scope:
            return "module_binding"
        if self.scope[-1][1] == "class":
            return "declared_field" if annotated else "class_binding"
        return "local_binding"

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            for name in self._names(target):
                self.record(name, self._binding_kind(), node)
        self.visit(node.value)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        kind = self._binding_kind(annotated=True)
        if kind == "declared_field" and self._unresolved_class_annotation(node.annotation):
            kind = "class_annotation_unresolved"
        for name in self._names(node.target):
            self.record(name, kind, node)
        if node.value is not None:
            self.visit(node.value)

    def visit_For(self, node: ast.For | ast.AsyncFor) -> None:
        for name in self._names(node.target):
            self.record(name, "loop_binding", node)
        self.visit(node.iter)
        for stmt in node.body + node.orelse:
            self.visit(stmt)

    visit_AsyncFor = visit_For

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        for name in self._names(node.target):
            self.record(name, self._binding_kind(), node)
        self.visit(node.value)


def observe_pinned_python(source: bytes, *, expected_sha256: str) -> PythonDeclarationReview:
    """Require exact bytes; record AST sites without certifying their semantics."""
    if (not isinstance(source, bytes) or not isinstance(expected_sha256, str)
            or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256)):
        raise DeclarationEvidenceError("exact source bytes and SHA-256 required")
    actual = sha256(source).hexdigest()
    if actual != expected_sha256:
        raise DeclarationEvidenceError("source SHA-256 drift")
    try:
        tree = ast.parse(source.decode("utf-8"))
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise DeclarationEvidenceError("unparseable Python source") from exc
    collector = _Collector()
    collector.visit(tree)
    return PythonDeclarationReview(
        actual, tuple(collector.declarations), tuple(collector.decorators),
    )
