"""AST-only exact external declaration matching; not Python runtime MRO checking."""
from __future__ import annotations

import ast
from collections.abc import Mapping
from hashlib import sha256

from codeqa.core.naming_ancestor import (
    ExternalAncestorError, ExternalAncestorEvidence, ExternalAncestorProfile,
    ExternalMemberWitness,
)
from .python_snapshot import ParsedSnapshot


def _qualified(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _qualified(node.value)
        return parent + "." + node.attr if parent else None
    return None


def _provider_members(source: str, name: str) -> dict[str, int]:
    tree = ast.parse(source, filename="pinned_external_stub.py")
    cls = name.rsplit(".", 1)[-1]
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls]
    if len(classes) != 1:
        raise ExternalAncestorError("pinned provider class missing or ambiguous")
    c = classes[0]
    # We do not know Python MRO for inherited/external/dynamic provider members.
    if c.bases or c.keywords or c.decorator_list:
        raise ExternalAncestorError("provider declaration not a closed direct class")
    members: dict[str, int] = {}
    for stmt in c.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if stmt.name in members:
                raise ExternalAncestorError("duplicate provider member declaration")
            members[stmt.name] = stmt.lineno
    return members


def _import_bindings(tree: ast.Module) -> dict[str, str]:
    imported: dict[str, str] = {}
    collisions: set[str] = set()
    for stmt in tree.body:
        if isinstance(stmt, ast.Import):
            for alias in stmt.names:
                name = alias.asname or alias.name.split(".")[0]
                if name in imported:
                    collisions.add(name)
                imported[name] = alias.name if alias.asname else name
        if isinstance(stmt, ast.ImportFrom) and stmt.level == 0 and stmt.module:
            for alias in stmt.names:
                if alias.name == "*":
                    continue
                name = alias.asname or alias.name
                if name in imported:
                    collisions.add(name)
                imported[name] = f"{stmt.module}.{alias.name}"
        # Any reassignment or local class/function with the same name makes the
        # binding ambiguous; source-only checking cannot prove runtime imports.
        target_names = []
        if isinstance(stmt, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            target_names = [stmt.name]
        elif isinstance(stmt, ast.Assign):
            target_names = [t.id for t in stmt.targets if isinstance(t, ast.Name)]
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            target_names = [stmt.target.id]
        for name in target_names:
            collisions.add(name)
    return {k: v for k, v in imported.items() if k not in collisions}


def extract_python_pinned_ancestor_evidence(
    parsed: ParsedSnapshot,
    sources: Mapping[str, str],
    provider_sources: Mapping[str, str],
    *,
    snapshot_id: str,
    profile: ExternalAncestorProfile,
) -> ExternalAncestorEvidence:
    if not isinstance(profile, ExternalAncestorProfile) or not isinstance(snapshot_id, str) or not snapshot_id:
        raise ExternalAncestorError("missing explicit source and profile identity")
    inventory = set(parsed.analyzed_paths) | {x for x, _ in parsed.unprocessed}
    if set(sources) != inventory or any(not isinstance(x, str) for x in sources.values()):
        raise ExternalAncestorError("selected source inventory disagrees with parsed source")
    if set(provider_sources) != {p.source_path for p in profile.providers}:
        raise ExternalAncestorError("pinned provider source set differs from profile")
    members = {}
    for provider in profile.providers:
        src = provider_sources[provider.source_path]
        if not isinstance(src, str) or sha256(src.encode("utf-8")).hexdigest() != provider.source_sha256:
            raise ExternalAncestorError("pinned provider SHA-256 drift")
        members[provider.qualified_class] = _provider_members(src, provider.qualified_class)
    witnesses = []
    for file in parsed.files:
        if file.tree is None or sha256(sources[file.path].encode("utf-8")).hexdigest() != file.digest:
            raise ExternalAncestorError("stale parsed AST for selected source")
        bindings = _import_bindings(file.tree)
        classes = [n for n in file.tree.body if isinstance(n, ast.ClassDef)]
        for cls in classes:
            if len(cls.bases) != 1 or cls.keywords or cls.decorator_list:
                continue
            spelling = _qualified(cls.bases[0])
            if not spelling:
                continue
            parts = spelling.split(".")
            imported = bindings.get(parts[0])
            if not imported:
                continue
            ancestor = ".".join((imported, *parts[1:]))
            # Only explicit pinned provider classes can be considered.
            if ancestor not in members:
                continue
            for method in cls.body:
                if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                line = members[ancestor].get(method.name)
                witnesses.append(ExternalMemberWitness(
                    path=file.path, owner=cls.name, name=method.name,
                    line=method.lineno, column=method.col_offset +
                    (len("async def ") if isinstance(method, ast.AsyncFunctionDef) else len("def ")),
                    ancestor=ancestor,
                    external_source_sha256=next(
                        p.source_sha256 for p in profile.providers
                        if p.qualified_class == ancestor
                    ),
                    external_declaration_line=line,
                    state="PINNED_MEMBER_DECLARED" if line is not None
                          else "PINNED_MEMBER_NOT_DECLARED",
                    explanation="exact_source_declaration_only_not_runtime_override",
                ))
    return ExternalAncestorEvidence(
        snapshot_id=snapshot_id,
        profile_fingerprint=profile.fingerprint(),
        source_sha256=tuple(sorted(
            (path, sha256(src.encode("utf-8")).hexdigest()) for path, src in sources.items()
        )),
        provider_sha256=tuple(sorted(
            (path, sha256(src.encode("utf-8")).hexdigest())
            for path, src in provider_sources.items()
        )),
        witnesses=tuple(sorted(witnesses, key=lambda w:(
            w.path, w.owner, w.line, w.name
        ))),
    )
