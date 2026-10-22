"""Conservative Python import-to-snapshot correspondence, without execution.

Unlike CCG v0.1 \`imports\` edges (which remain unchanged), these observations
link a syntactically referenced module to an exact analyzed source file.
Neither \`import x\` nor \`from x import y\` proves which file Python loads at
runtime when sys.path, module cache and package hooks may vary.
"""
from __future__ import annotations

import ast
from collections import defaultdict
from collections.abc import Mapping

from codeqa.core.dependency import DependencyGraph, StaticDependency, UnknownDependency


def _module_name(path: str) -> tuple[str, bool] | None:
    """Source-root model: src/ layout or repository-root Python modules."""
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
    prefix = scope[: len(scope) - (level - 1)]
    return ".".join([*prefix, *([name] if name else [])])


def extract_python_dependencies(
    sources: Mapping[str, str],
    *,
    snapshot_id: str,
    analyzed_paths: tuple[str, ...],
    unprocessed_paths: tuple[str, ...] = (),
) -> DependencyGraph:
    """Index only successfully parsed sources, fail closed on malformed inputs.

    analyzed_paths come from a previously validated CCG Coverage record.
    The caller supplies immutable source bytes; this adapter performs no I/O.
    """
    candidates: dict[str, set[str]] = defaultdict(set)
    parsed: dict[str, tuple[ast.Module, str | None, bool]] = {}

    for path in sorted(analyzed_paths):
        module = _module_name(path)
        if path not in sources or not path.endswith(".py"):
            raise ValueError(f"unsupported or missing analyzed Python path: {path}")
        tree = ast.parse(sources[path], filename=path)
        name, package = module if module is not None else (None, False)
        if name is not None:
            candidates[name].add(path)
        parsed[path] = (tree, name, package)

    known = {name: tuple(sorted(paths)) for name, paths in candidates.items()}
    edges: list[StaticDependency] = []
    unknown: list[UnknownDependency] = []

    for path, (tree, module, package) in sorted(parsed.items()):
        # A statement nested under a condition/function can be a potential
        # dependency without being imported on every execution path.
        direct_ids = {id(statement) for statement in tree.body}
        imports = [
            node for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom, ast.Call))
        ]
        imports.sort(key=lambda node: (
            getattr(node, "lineno", 0), getattr(node, "col_offset", 0)
        ))
        for node in imports:
            if isinstance(node, ast.Call):
                # Dynamic imports are only detected for obvious call syntax;
                # a renamed importlib or reflective import is beyond v0.1.
                dynamic = (
                    isinstance(node.func, ast.Name) and node.func.id == "__import__"
                    or isinstance(node.func, ast.Attribute)
                    and node.func.attr == "import_module"
                )
                if dynamic:
                    unknown.append(UnknownDependency(
                        path, node.lineno, ast.unparse(node),
                        "dynamic_import",
                    ))
                continue

            if isinstance(node, ast.Import):
                names = [(alias.name, f"import {alias.name}") for alias in node.names]
            else:
                if node.level:
                    target = (
                        _relative_name(module, package, node.level, node.module)
                        if module is not None else None
                    )
                    if target is None:
                        unknown.append(UnknownDependency(
                            path, node.lineno, ast.unparse(node),
                            "invalid_relative" if module is not None
                            else "unindexable_source_module",
                        ))
                        continue
                else:
                    target = node.module or ""
                # from package import symbol requires importing package;
                # \`symbol\` may be a submodule or attribute: never invent
                # an edge to package.symbol. Package self-import is skipped.
                names = [(target, ast.unparse(node))]

            for target_module, statement in names:
                matches = known.get(target_module, ())
                if len(matches) == 1:
                    target_path = matches[0]
                    if target_path != path:
                        edges.append(StaticDependency(
                            source_path=path,
                            target_path=target_path,
                            line=node.lineno,
                            expression=statement,
                            execution=(
                                "top_level" if id(node) in direct_ids
                                else "conditional_or_deferred"
                            ),
                        ))
                else:
                    unknown.append(UnknownDependency(
                        source_path=path, line=node.lineno,
                        expression=statement,
                        reason="ambiguous" if matches else "outside_snapshot",
                    ))

    return DependencyGraph(
        snapshot_id=snapshot_id,
        analyzed_paths=tuple(sorted(analyzed_paths)),
        unprocessed_paths=tuple(sorted(unprocessed_paths)),
        edges=tuple(sorted(set(edges), key=lambda edge: (
            edge.source_path, edge.target_path, edge.line,
            edge.expression, edge.execution,
        ))),
        unknown=tuple(sorted(unknown, key=lambda item: (
            item.source_path, item.line, item.expression, item.reason,
        ))),
    )
