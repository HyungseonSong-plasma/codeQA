"""Issue #144: bounded static import/reexport *syntax* evidence for one symbol.

Pure AST analyzer; does not execute imports, resolve runtime identity, assert a
complete graph, or authorize semantic Naming decisions and renames.
"""
from __future__ import annotations

import ast
from collections.abc import Mapping
from typing import Any


TARGET = "ControlFlowObservation"
ORIGIN_MODULE = "codeqa.core.complexity"


class InternalImportGraphError(ValueError):
    """Invalid source identity, path/module mapping or AST witness."""


def module_for_path(path: str) -> str:
    if (not isinstance(path, str) or not path.startswith("src/codeqa/")
            or not path.endswith(".py") or
            any(p in ("", ".", "..") for p in path.split("/"))):
        raise InternalImportGraphError("expected tracked src/codeqa Python path")
    stem = path.removeprefix("src/").removesuffix(".py")
    if stem.endswith("/__init__"):
        stem = stem.removesuffix("/__init__")
    return stem.replace("/", ".")


def resolve_from(module: str, *, path: str, level: int) -> str | None:
    """Resolve only lexical Python module paths; never import target code."""
    if level == 0:
        return module
    current = module_for_path(path)
    package = current if path.endswith("/__init__.py") else current.rpartition(".")[0]
    pieces = package.split(".")
    if level > len(pieces) or not pieces or pieces[0] != "codeqa":
        return None
    parent = pieces[:len(pieces) + 1 - level]
    if not parent or parent[0] != "codeqa":
        return None
    return ".".join(parent + ([module] if module else []))


def scan_module_imports(source: bytes, *, path: str) -> dict[str, Any]:
    """Report all import statements, target edges, syntax-only uncertainty."""
    mod = module_for_path(path)
    if not isinstance(source, bytes):
        raise InternalImportGraphError("immutable source bytes required")
    try:
        tree = ast.parse(source.decode("utf-8"), filename=path)
    except (SyntaxError, UnicodeDecodeError) as exc:
        raise InternalImportGraphError("unparseable selected Python source") from exc

    edges: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    statements = 0
    root_class = 0

    # Track module-scope statements separately from nested/conditional imports.
    for s in tree.body:
        if isinstance(s, ast.ClassDef) and s.name == TARGET:
            root_class += 1
        if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef,
                          ast.ClassDef)) and s.name == TARGET:
            unresolved.append({"line": s.lineno, "reason": "LOCAL_ROOT_SYMBOL_DEFINITION"})
        if isinstance(s, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = s.targets if isinstance(s, ast.Assign) else [s.target]
            if any(isinstance(t, ast.Name) and t.id == TARGET for t in targets):
                unresolved.append({"line": s.lineno, "reason": "MODULE_SYMBOL_REBINDING"})
        if isinstance(s, ast.FunctionDef) and s.name == "__getattr__":
            unresolved.append({"line": s.lineno, "reason": "DYNAMIC_MODULE_GETATTR"})

    # A valid first import is not enough if later module-level statements
    # may bind or delete the same name. This is source-only evidence.
    symbol_bindings: list[tuple[int, str]] = []

    def binds_target(node: ast.AST) -> bool:
        if isinstance(node, ast.Name):
            return node.id == TARGET
        if isinstance(node, (ast.Tuple, ast.List)):
            return any(binds_target(x) for x in node.elts)
        return isinstance(node, ast.Starred) and binds_target(node.value)

    for stmt in tree.body:
        if isinstance(stmt, ast.ImportFrom):
            for alias in stmt.names:
                if (alias.asname or alias.name) == TARGET:
                    symbol_bindings.append((stmt.lineno, "FROM"))
        elif isinstance(stmt, ast.Import):
            for alias in stmt.names:
                if (alias.asname or alias.name.split(".")[0]) == TARGET:
                    symbol_bindings.append((stmt.lineno, "MODULE_IMPORT"))
        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if stmt.name == TARGET:
                symbol_bindings.append((stmt.lineno, "DEFINITION"))
            if any(isinstance(n, ast.Global) and TARGET in n.names
                   for n in ast.walk(stmt)):
                symbol_bindings.append((stmt.lineno, "GLOBAL_UNRESOLVED"))
        elif isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
            if any(binds_target(x) for x in targets):
                symbol_bindings.append((stmt.lineno, "ASSIGNMENT"))
        elif isinstance(stmt, ast.Delete):
            if any(binds_target(x) for x in stmt.targets):
                symbol_bindings.append((stmt.lineno, "DELETION"))
        elif isinstance(stmt, (ast.If, ast.For, ast.AsyncFor, ast.While,
                               ast.With, ast.AsyncWith, ast.Try, ast.Match)):
            if any(
                (isinstance(n, ast.Name) and n.id == TARGET
                 and isinstance(n.ctx, (ast.Store, ast.Del)))
                or (isinstance(n, ast.ExceptHandler) and n.name == TARGET)
                # Pattern capture names are strings on AST pattern nodes;
                # they do not appear as Name(Store) in ast.walk.
                or (isinstance(n, (ast.MatchAs, ast.MatchStar)) and n.name == TARGET)
                or (isinstance(n, ast.MatchMapping) and n.rest == TARGET)
                # Conditional imports and function/class declarations bind
                # names without producing Name(Store) nodes in the AST.
                or (isinstance(n, ast.ImportFrom) and any(
                    (alias.asname or alias.name) == TARGET
                    for alias in n.names
                ))
                or (isinstance(n, ast.Import) and any(
                    (alias.asname or alias.name.split(".")[0]) == TARGET
                    for alias in n.names
                ))
                or (isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef,
                                   ast.ClassDef)) and n.name == TARGET)
                for n in ast.walk(stmt)
            ):
                symbol_bindings.append((stmt.lineno, "CONDITIONAL_BINDING"))
        if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef)):
            if any(isinstance(n, ast.NamedExpr) and binds_target(n.target)
                   for n in ast.walk(stmt)):
                symbol_bindings.append((stmt.lineno, "NAMED_EXPRESSION"))

    if len(symbol_bindings) > 1:
        unresolved.append({"line": min(x[0] for x in symbol_bindings),
                           "reason": "AMBIGUOUS_TARGET_MODULE_BINDING"})
    elif symbol_bindings and symbol_bindings[0][1] not in ("FROM", "DEFINITION"):
        unresolved.append({"line": symbol_bindings[0][0],
                           "reason": "UNSUPPORTED_TARGET_MODULE_BINDING"})

    def visit(stmt: ast.AST, *, top_level: bool) -> None:
        nonlocal statements
        if isinstance(stmt, ast.ImportFrom):
            statements += 1
            resolved = resolve_from(stmt.module or "", path=path, level=stmt.level)
            if resolved is None:
                unresolved.append({"line": stmt.lineno, "reason": "RELATIVE_IMPORT_BEYOND_PACKAGE"})
            for alias in stmt.names:
                if alias.name == "*":
                    unresolved.append({"line": stmt.lineno,
                                       "reason": "WILDCARD_IMPORT_UNRESOLVED"})
                if alias.name != TARGET and (alias.asname or "") != TARGET:
                    continue
                item = {
                    "importer": mod, "path": path, "line": stmt.lineno,
                    "source_module": resolved,
                    "imported_name": alias.name, "bound_name": alias.asname or alias.name,
                    "syntax": "TOP_LEVEL_FROM" if top_level else "NESTED_FROM",
                    "provenance": "UNKNOWN",
                }
                if not top_level:
                    unresolved.append({"line": stmt.lineno,
                                       "reason": "NESTED_TARGET_IMPORT_NOT_GLOBAL"})
                edges.append(item)
        elif isinstance(stmt, ast.Import):
            statements += 1
            if any(a.name == ORIGIN_MODULE or a.asname == TARGET for a in stmt.names):
                unresolved.append({"line": stmt.lineno,
                                   "reason": "QUALIFIED_OR_ALIAS_MODULE_IMPORT_UNRESOLVED"})
        for child in ast.iter_child_nodes(stmt):
            # Only direct children of module are top-level imports. Every other
            # import inside a function/if/try/class is syntactically nested.
            visit(child, top_level=False)

    for s in tree.body:
        visit(s, top_level=True)

    # Dynamic introspection is a reason NOT to claim graph completeness.
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            if (isinstance(fn, ast.Name) and fn.id in (
                    "exec", "eval", "__import__", "getattr", "setattr", "globals", "locals")
                or isinstance(fn, ast.Attribute) and fn.attr == "import_module"):
                unresolved.append({"line": node.lineno, "reason": "DYNAMIC_BINDING_OR_IMPORT"})
    return {
        "path": path, "module": mod, "import_statement_count": statements,
        "top_level_target_class_count": root_class,
        "target_import_edges": edges,
        "unresolved": sorted(unresolved, key=lambda x: (x["line"], x["reason"])),
    }


def classify_static_import_chains(
    scans: Mapping[str, Mapping[str, Any]],
    *, origin: str = ORIGIN_MODULE,
) -> dict[str, Any]:
    """Find source-only chains of exact-name top-level imports.

    Provenance is a *candidate* even for a direct origin import: Python
    execution and dynamic rebinding are not certified here.
    """
    if not isinstance(scans, Mapping) or origin not in scans:
        raise InternalImportGraphError("origin module missing from corpus")
    if scans[origin].get("top_level_target_class_count") != 1:
        raise InternalImportGraphError("origin class not uniquely declared")
    reached = {origin}
    by_module: dict[str, list[dict[str, Any]]] = {
        m: list(v["target_import_edges"]) for m, v in scans.items()
    }
    # An import chain with any observed namespace ambiguity is NOT admitted.
    safe = {m for m, v in scans.items()
            if not any(x["reason"] in (
                "LOCAL_ROOT_SYMBOL_DEFINITION", "MODULE_SYMBOL_REBINDING",
                "DYNAMIC_MODULE_GETATTR", "WILDCARD_IMPORT_UNRESOLVED",
                "NESTED_TARGET_IMPORT_NOT_GLOBAL", "DYNAMIC_BINDING_OR_IMPORT",
                "AMBIGUOUS_TARGET_MODULE_BINDING",
                "UNSUPPORTED_TARGET_MODULE_BINDING",
            ) for x in v["unresolved"])}
    for _ in range(len(scans)):
        previous = len(reached)
        for importer, imports in by_module.items():
            if importer not in safe or importer in reached:
                continue
            if any(e["syntax"] == "TOP_LEVEL_FROM"
                   and e["imported_name"] == TARGET and e["bound_name"] == TARGET
                   and e["source_module"] in reached
                   for e in imports):
                reached.add(importer)
        if len(reached) == previous:
            break
    out = []
    for mod, imports in sorted(by_module.items()):
        for edge in imports:
            e = dict(edge)
            if (e["syntax"] == "TOP_LEVEL_FROM"
                    and e["imported_name"] == TARGET
                    and e["bound_name"] == TARGET
                    and e["source_module"] in reached and mod in reached
                    and mod != origin):
                e["provenance"] = (
                    "DIRECT_OR_CHAINED_IMPORT_SYNTAX_CANDIDATE"
                )
            else:
                e["provenance"] = "UNKNOWN"
            e["runtime_binding_verified"] = False
            e["semantic_approval"] = False
            e["rename_authorized"] = False
            out.append(e)
    return {
        "root_module": origin,
        "root_symbol": TARGET,
        "source_syntax_chain_modules": sorted(reached),
        "target_from_import_edges": out,
        "syntax_candidate_edges": sum(
            x["provenance"] == "DIRECT_OR_CHAINED_IMPORT_SYNTAX_CANDIDATE"
            for x in out),
        "unresolved_target_edges": sum(x["provenance"] == "UNKNOWN" for x in out),
        "graph_completeness": "NOT_EVALUATED",
        "runtime_symbol_identity": "NOT_EVALUATED",
        "external_caller_compatibility": "UNKNOWN",
        "semantic_policy": "NOT_ADOPTED",
        "rename_authorized": False,
    }
