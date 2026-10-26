"""Pinned-source scope discovery for Naming #144; no domain-role inference.

This module only classifies exact Python AST spellings; method owners,
runtime bindings, external consumers and semantic roles are NOT verified.
"""
from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
from hashlib import sha256
import re


_TARGET = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*\Z")
_SOURCE_KINDS = frozenset({
    "function", "method", "parameter", "class", "class_annotation",
    "class_binding", "module_binding", "local_binding", "import_alias",
    "attribute_unresolved", "name_reference_unresolved",
})


class ScopeDiscoveryError(ValueError):
    """Invalid target selection or an invalid pinned Python source."""


@dataclass(frozen=True, slots=True)
class ScopeSite:
    path: str
    name: str
    line: int
    column: int
    owner: str
    source_kind: str
    source_sha256: str
    role_evidence: str = "NOT_EVALUATED"
    semantic_proven: bool = False
    approved_path_scope: bool = False
    rename_authorized: bool = False


class _Sites(ast.NodeVisitor):
    def __init__(self, path: str, names: frozenset[str], digest: str) -> None:
        self.path = path
        self.names = names
        self.digest = digest
        self.scope: list[tuple[str, str]] = []
        self.found: list[ScopeSite] = []

    @property
    def owner(self) -> str:
        return ".".join(x[1] for x in self.scope)

    def put(self, name: str, kind: str, node: ast.AST) -> None:
        if name not in self.names:
            return
        if kind not in _SOURCE_KINDS:
            raise ScopeDiscoveryError("unsupported lexical AST site")
        self.found.append(ScopeSite(
            self.path, name, node.lineno, node.col_offset, self.owner,
            kind, self.digest,
        ))

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.put(node.name, "class", node)
        self.scope.append(("class", node.name))
        for child in node.body:
            self.visit(child)
        self.scope.pop()

    def _function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        kind = "method" if self.scope and self.scope[-1][0] == "class" else "function"
        self.put(node.name, kind, node)
        self.scope.append(("function", node.name))
        args = node.args
        for arg in args.posonlyargs + args.args + args.kwonlyargs + (
                [args.vararg] if args.vararg else []) + (
                [args.kwarg] if args.kwarg else []):
            self.put(arg.arg, "parameter", arg)
        for child in node.body:
            self.visit(child)
        self.scope.pop()

    visit_FunctionDef = _function
    visit_AsyncFunctionDef = _function

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if isinstance(node.target, ast.Name):
            kind = ("class_annotation" if self.scope and
                    self.scope[-1][0] == "class" else
                    "local_binding" if self.scope else "module_binding")
            self.put(node.target.id, kind, node)
        # Annotation and assigned value contain possible references, not
        # additional independently proven declarations.
        self.visit(node.annotation)
        if node.value is not None:
            self.visit(node.value)

    def visit_Assign(self, node: ast.Assign) -> None:
        kind = ("class_binding" if self.scope and self.scope[-1][0] == "class"
                else "local_binding" if self.scope else "module_binding")
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.put(target.id, kind, node)
        self.visit(node.value)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.put(alias.asname or alias.name.split(".")[0], "import_alias", node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            if alias.name != "*":
                self.put(alias.asname or alias.name, "import_alias", node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        # A syntactically spelled attribute is NOT a declared field or a
        # resolved graph edge (could be external, a descriptor or dynamic).
        self.put(node.attr, "attribute_unresolved", node)
        self.visit(node.value)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            self.put(node.id, "name_reference_unresolved", node)


def scan_explicit_spellings(
    source: bytes, *, path: str, targets: tuple[str, ...],
) -> tuple[dict[str, object], ...]:
    """Collect only exact AST names from one selected UTF-8 Python source file.

    No substring matches, string/comment matches, or CamelCase normalization.
    The record retains SHA-256 of its exact source file bytes. Git provenance
    and the entire selected-file denominator are verified separately.
    """
    if (not isinstance(source, bytes) or not isinstance(path, str)
            or not path.startswith("src/codeqa/")
            or not path.endswith(".py") or ".." in path.split("/")
            or not isinstance(targets, tuple)
            or not targets or len(set(targets)) != len(targets)
            or any(not isinstance(s, str) or not _TARGET.fullmatch(s) for s in targets)):
        raise ScopeDiscoveryError("exact nonempty target/path evidence required")
    try:
        tree = ast.parse(source.decode("utf-8"), filename=path)
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise ScopeDiscoveryError("selected source not valid UTF-8 Python") from exc
    collector = _Sites(path, frozenset(targets), sha256(source).hexdigest())
    collector.visit(tree)
    return tuple(asdict(x) for x in sorted(
        collector.found,
        key=lambda s: (s.line, s.column, s.owner, s.source_kind, s.name)))
