"""Snapshot-local, syntax-evidenced Python module dependency extraction.

Import edges describe unique source-module-path correspondence only, NEVER
proof of runtime loading or the identity of imported members/call targets.
"""
from __future__ import annotations

import ast
from collections import defaultdict
from collections.abc import Mapping

from codeqa.core.dependency import DependencyGraph, StaticDependency, UnknownDependency
from .python_snapshot import ParsedSnapshot, parse_python_snapshot


def _module_name(path: str) -> tuple[str, bool] | None:
    """Canonical source-root assumption: src/ layout or repository root."""
    if not path.endswith(".py"):
        return None
    relative = path.removeprefix("src/") if path.startswith("src/") else path
    parts = relative.removesuffix(".py").split("/")
    is_package = parts[-1] == "__init__"
    if is_package:
        parts.pop()
    if not parts or any(not part.isidentifier() for part in parts):
        return None
    return ".".join(parts), is_package


def _relative_name(module: str, package: bool, level: int, name: str | None) -> str | None:
    scope = module.split(".") if package else module.split(".")[:-1]
    if level < 1 or level > len(scope):
        return None
    prefix = scope[:len(scope) - (level - 1)]
    return ".".join([*prefix, *([name] if name else [])])


def _index_sources(
    parsed_snapshot: ParsedSnapshot,
) -> tuple[dict[str, tuple[ast.Module, str | None, bool]], dict[str, tuple[str, ...]]]:
    """Index previously parsed ASTs without parsing them again."""
    parsed: dict[str, tuple[ast.Module, str | None, bool]] = {}
    index: dict[str, set[str]] = defaultdict(set)
    for item in parsed_snapshot.files:
        assert item.tree is not None
        module = _module_name(item.path)
        name, package = module if module is not None else (None, False)
        parsed[item.path] = (item.tree, name, package)
        if name is not None:
            index[name].add(item.path)
    return parsed, {name: tuple(sorted(paths)) for name, paths in index.items()}


def _import_names(
    node: ast.Import | ast.ImportFrom, module: str | None, package: bool,
    path: str,
) -> tuple[list[tuple[str, str]], list[UnknownDependency]]:
    """Return observed import candidates or a structured unknown."""
    if isinstance(node, ast.Import):
        return [(item.name, f"import {item.name}") for item in node.names], []

    if node.level:
        target = (
            _relative_name(module, package, node.level, node.module)
            if module is not None else None
        )
        if target is None:
            return [], [UnknownDependency(
                path, node.lineno, ast.unparse(node),
                "invalid_relative" if module is not None else "unindexable_source_module",
            )]
    else:
        target = node.module or ""
    # \`from package import name\` depends on the package when present;
    # name may be a symbol, a submodule or a dynamic export: never guess.
    return [(target, ast.unparse(node))], []


def _is_obvious_dynamic_import(node: ast.Call) -> bool:
    return (
        isinstance(node.func, ast.Name) and node.func.id == "__import__"
        or isinstance(node.func, ast.Attribute) and node.func.attr == "import_module"
    )


def _observe_module(
    path: str,
    tree: ast.Module,
    module: str | None,
    package: bool,
    known: dict[str, tuple[str, ...]],
) -> tuple[list[StaticDependency], list[UnknownDependency]]:
    direct_ids = {id(statement) for statement in tree.body}
    elements = [
        node for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.Call))
    ]
    elements.sort(key=lambda n: (getattr(n, "lineno", 0), getattr(n, "col_offset", 0)))
    edges: list[StaticDependency] = []
    unknown: list[UnknownDependency] = []

    for node in elements:
        if isinstance(node, ast.Call):
            if _is_obvious_dynamic_import(node):
                unknown.append(UnknownDependency(
                    path, node.lineno, ast.unparse(node), "dynamic_import",
                ))
            continue
        names, exceptions = _import_names(node, module, package, path)
        unknown.extend(exceptions)
        for target_module, expression in names:
            matches = known.get(target_module, ())
            if len(matches) != 1:
                unknown.append(UnknownDependency(
                    path, node.lineno, expression,
                    "ambiguous" if matches else "outside_snapshot",
                ))
                continue
            if matches[0] != path:
                edges.append(StaticDependency(
                    source_path=path,
                    target_path=matches[0],
                    line=node.lineno,
                    expression=expression,
                    execution=(
                        "top_level" if id(node) in direct_ids
                        else "conditional_or_deferred"
                    ),
                ))
    return edges, unknown


def extract_parsed_dependencies(
    parsed_snapshot: ParsedSnapshot, *, snapshot_id: str,
) -> DependencyGraph:
    """Reuse the single parsed snapshot and rebuild cross-module bindings."""
    parsed, known = _index_sources(parsed_snapshot)
    edges: list[StaticDependency] = []
    unknown: list[UnknownDependency] = []
    for path, (tree, module, package) in sorted(parsed.items()):
        observed, unresolved = _observe_module(path, tree, module, package, known)
        edges.extend(observed)
        unknown.extend(unresolved)

    return DependencyGraph(
        snapshot_id=snapshot_id,
        analyzed_paths=parsed_snapshot.analyzed_paths,
        unprocessed_paths=tuple(path for path, _ in parsed_snapshot.unprocessed),
        edges=tuple(sorted(set(edges), key=lambda edge: (
            edge.source_path, edge.target_path, edge.line,
            edge.expression, edge.execution,
        ))),
        unknown=tuple(sorted(unknown, key=lambda item: (
            item.source_path, item.line, item.expression, item.reason,
        ))),
    )


def extract_python_dependencies(
    sources: Mapping[str, str], *, snapshot_id: str,
    analyzed_paths: tuple[str, ...],
    unprocessed_paths: tuple[str, ...] = (),
) -> DependencyGraph:
    """Standalone adapter: no reparse within this call, explicit CCG coverage."""
    if any(p not in sources or not p.endswith(".py") for p in analyzed_paths):
        raise ValueError("unsupported or missing analyzed Python path")
    subset = {path: sources[path] for path in analyzed_paths}
    parsed = parse_python_snapshot(subset)
    if parsed.unprocessed:
        raise ValueError("analyzed path has invalid Python syntax")
    result = extract_parsed_dependencies(parsed, snapshot_id=snapshot_id)
    return DependencyGraph(
        snapshot_id=result.snapshot_id,
        analyzed_paths=result.analyzed_paths,
        unprocessed_paths=tuple(sorted(unprocessed_paths)),
        edges=result.edges,
        unknown=result.unknown,
    )
