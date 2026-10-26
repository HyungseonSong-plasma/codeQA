"""Pinned repository-wide Python declaration *structural* coverage for #91.

Exhaustiveness is only relative to explicitly selected tracked Python files
and syntax node families, not runtime symbols, binding semantics, or end users.
This read-only module never grants a Naming PASS or a rename permission.
"""
from __future__ import annotations

import ast
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha1, sha256
from pathlib import Path
import re
import subprocess

from codeqa.core.naming_declaration_evidence_v03 import observe_pinned_python
from codeqa.infrastructure.git import GitReader


class NamingSnapshotCoverageError(ValueError):
    """Missing or forged selected source, Git tree, or census denominator."""


_SHA = re.compile(r"[0-9a-f]{40}\Z")
_PATH = re.compile(r"src/codeqa/(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.py\Z")
SUPPORTED = frozenset({"function", "method", "parameter"})
# Fields are excluded from the denominator until class/dataclass/DTO ownership
# is independently reviewed. Annotations alone do not prove instance fields.


@dataclass(frozen=True, slots=True)
class NamingSnapshotCoverage:
    revision: str
    selected_paths: tuple[str, ...]
    source_digests: tuple[tuple[str, str], ...]
    examined_files: int
    expected_structural_sites: int
    observed_structural_sites: int
    matched_sites: int
    missing_sites: tuple[str, ...]
    unexpected_sites: tuple[str, ...]
    other_observed_kinds: tuple[tuple[str, int], ...]
    uncertainty_categories: tuple[tuple[str, int], ...]
    status: str = "NOT_EVALUATED"
    semantic_false_positive_rate: str = "NOT_EVALUATED"
    semantic_false_negative_rate: str = "NOT_EVALUATED"
    external_compatibility: str = "NOT_EVALUATED"
    rename_authorized: bool = False


def _site(path: str, kind: str, name: str, line: int, owner: str) -> str:
    return f"{path}:{line}:{owner}:{kind}:{name}"


class _IndependentSyntaxCensus(ast.NodeVisitor):
    """Separate AST traversal for function/method and all argument positions."""

    def __init__(self, path: str) -> None:
        self.path = path
        self.scope: list[tuple[str, str]] = []
        self.sites: list[str] = []

    def _owner(self) -> str:
        return ".".join(x for x, _ in self.scope)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scope.append((node.name, "class"))
        for statement in node.body:
            self.visit(statement)
        self.scope.pop()

    def _function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        kind = ("method" if self.scope and self.scope[-1][1] == "class"
                else "function")
        self.sites.append(_site(self.path, kind, node.name,
                                node.lineno, self._owner()))
        self.scope.append((node.name, "function"))
        args = node.args
        parameters = (args.posonlyargs + args.args + args.kwonlyargs
                      + ([args.vararg] if args.vararg else [])
                      + ([args.kwarg] if args.kwarg else []))
        for arg in parameters:
            self.sites.append(_site(self.path, "parameter", arg.arg,
                                    arg.lineno, self._owner()))
        for statement in node.body:
            self.visit(statement)
        self.scope.pop()

    visit_FunctionDef = _function
    visit_AsyncFunctionDef = _function


def _validated_source_paths(sources: Mapping[str, bytes],
                            expected_digests: Mapping[str, str]) -> tuple[str, ...]:
    if (not isinstance(sources, Mapping) or not isinstance(expected_digests, Mapping)
            or not sources or set(sources) != set(expected_digests)):
        raise NamingSnapshotCoverageError("exact selected path set and digests required")
    paths = tuple(sorted(sources))
    for path in paths:
        if (not isinstance(path, str) or not _PATH.fullmatch(path)
                or any(component in {".", ".."} or component.endswith((".", " "))
                       for component in path.split("/"))
                or not isinstance(sources[path], bytes)
                or not isinstance(expected_digests[path], str)
                or not re.fullmatch(r"[0-9a-f]{64}", expected_digests[path])
                or sha256(sources[path]).hexdigest() != expected_digests[path]):
            raise NamingSnapshotCoverageError("untrusted source path, bytes or SHA-256")
    return paths


def scan_selected_python(*, revision: str, sources: Mapping[str, bytes],
                         expected_digests: Mapping[str, str]) -> NamingSnapshotCoverage:
    """Audit declared AST node kinds across an explicit, exact selected path set.

    Caller-provided revision is not Git-attested here; use scan_pinned_git
    for an independently read-only pinned Git tree and blob inventory.
    """
    if not isinstance(revision, str) or not _SHA.fullmatch(revision):
        raise NamingSnapshotCoverageError("full lower-case commit SHA required")
    paths = _validated_source_paths(sources, expected_digests)
    expected: Counter[str] = Counter()
    observed: Counter[str] = Counter()
    other: Counter[str] = Counter()
    unknown: Counter[str] = Counter()
    for path in paths:
        body = sources[path]
        try:
            tree = ast.parse(body.decode("utf-8"), filename=path)
        except (SyntaxError, UnicodeDecodeError) as exc:
            raise NamingSnapshotCoverageError("selected Python source is unparseable: " + path) from exc
        census = _IndependentSyntaxCensus(path)
        census.visit(tree)
        expected.update(census.sites)
        review = observe_pinned_python(body, expected_sha256=expected_digests[path])
        for symbol in review.declarations:
            if symbol.kind in SUPPORTED:
                observed[_site(path, symbol.kind, symbol.name,
                               symbol.line, symbol.owner)] += 1
            else:
                other[symbol.kind] += 1
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and any(a.name == "*" for a in node.names):
                unknown["wildcard_import"] += 1
            if isinstance(node, ast.ImportFrom) and node.level:
                unknown["relative_import_requires_resolution"] += 1
            if isinstance(node, ast.Call):
                target = node.func
                if isinstance(target, ast.Name) and target.id in {
                    "exec", "eval", "setattr", "delattr", "__import__"
                }:
                    unknown["dynamic_call_requires_resolution"] += 1
            if isinstance(node, (ast.Global, ast.Nonlocal)):
                unknown["global_nonlocal_binding"] += len(node.names)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if not node.name.isascii():
                    unknown["unicode_identifier"] += 1
                if node.name.startswith("__") and node.name.endswith("__"):
                    unknown["dunder_public_binding"] += 1
        if any(x.kind in {"declared_field", "class_annotation_unresolved", "class_binding"}
               for x in review.declarations):
            unknown["field_ownership_not_in_denominator"] += 1
        if any(x.kind in {"import_binding"} for x in review.declarations):
            unknown["import_alias_or_reexport_not_resolved"] += 1
    missing = expected - observed
    extra = observed - expected
    return NamingSnapshotCoverage(
        revision=revision, selected_paths=paths,
        source_digests=tuple((p, expected_digests[p]) for p in paths),
        examined_files=len(paths), expected_structural_sites=sum(expected.values()),
        observed_structural_sites=sum(observed.values()),
        matched_sites=sum((expected & observed).values()),
        missing_sites=tuple(sorted(site for site, n in missing.items() for _ in range(n))),
        unexpected_sites=tuple(sorted(site for site, n in extra.items() for _ in range(n))),
        other_observed_kinds=tuple(sorted(other.items())),
        uncertainty_categories=tuple(sorted(unknown.items())),
    )


def scan_pinned_git(root: Path, *, revision: str) -> NamingSnapshotCoverage:
    """Read the exact committed tree and verify every Git blob before scanning.

    Uses only git ls-tree/show locally. Never executes imported repository code,
    never traverses the working tree, and never trusts a caller's file list.
    """
    if not isinstance(revision, str) or not _SHA.fullmatch(revision):
        raise NamingSnapshotCoverageError("full lower-case commit SHA required")
    reader = GitReader(root)
    try:
        result = subprocess.run(
            ["git", "ls-tree", "-rz", revision, "--", "src/codeqa"],
            cwd=reader.root, capture_output=True, check=False,
        )
    except OSError as exc:
        raise NamingSnapshotCoverageError("git unavailable") from exc
    if result.returncode != 0:
        raise NamingSnapshotCoverageError("cannot independently read pinned tree")
    sources: dict[str, bytes] = {}
    digests: dict[str, str] = {}
    for record in result.stdout.split(b"\0"):
        if not record:
            continue
        try:
            metadata, path_raw = record.split(b"\t", 1)
            mode, object_type, blob_raw = metadata.split(b" ", 2)
            path = path_raw.decode("utf-8", errors="strict")
            blob = blob_raw.decode("ascii", errors="strict")
        except (ValueError, UnicodeDecodeError) as exc:
            raise NamingSnapshotCoverageError("malformed tracked Git tree record") from exc
        if not path.endswith(".py"):
            continue
        if (mode not in {b"100644", b"100755"} or object_type != b"blob"
                or not _PATH.fullmatch(path)
                or any(c in {".", ".."} or c.endswith((".", " "))
                       for c in path.split("/"))
                or not _SHA.fullmatch(blob)
                or path in sources):
            raise NamingSnapshotCoverageError("unsafe, ambiguous or untracked Python Git entry")
        body = reader.read_file(revision, path)
        if sha1(b"blob " + str(len(body)).encode() + b"\0" + body).hexdigest() != blob:
            raise NamingSnapshotCoverageError("Git tree/blob source mismatch")
        sources[path] = body
        digests[path] = sha256(body).hexdigest()
    if not sources:
        raise NamingSnapshotCoverageError("empty pinned Python repository selection")
    return scan_selected_python(revision=revision, sources=sources, expected_digests=digests)
