"""B5: conservative, read-only migration and public-import impact evidence.

The caller supplies bytes from the same immutable Git snapshot as B1--B4.
This is a static impact inventory, not a rewrite plan, ABI proof or permission
to move modules. No package names or desired architecture are hard-coded.
"""
from __future__ import annotations

import ast
from collections.abc import Mapping
from hashlib import sha256
import json
from typing import Any


class ArchitectureMigrationError(ValueError):
    """Invalid, stale, contradictory or untrusted migration input."""


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _module(path: str) -> str | None:
    if not path.startswith("src/") or not path.endswith(".py"):
        return None
    parts = path[4:-3].split("/")
    if parts[-1] == "__init__":
        parts.pop()
    if not parts or not all(p.isidentifier() for p in parts):
        return None
    return ".".join(parts)


def _matches(name: str, old: str) -> bool:
    return name == old or name.startswith(old + ".")


def _relative(package: str, level: int, module: str | None) -> str | None:
    parts = package.split(".")
    if level > len(parts):
        return None
    prefix = parts[:len(parts) - level + 1]
    return ".".join(prefix + (module.split(".") if module else []))


def _record(path: str, line: int, kind: str, detail: str, digest: str,
            old: str, new: str, status: str) -> dict[str, Any]:
    return {
        "path": path, "line": line, "kind": kind, "expression": detail,
        "source_sha256": digest, "old_module": old, "proposed_module": new,
        "rewrite_status": status, "evidence_class": "SOURCE_STATIC_WITNESS",
    }


def _dynamic_helpers(tree: ast.AST) -> dict[ast.Call, str]:
    """Identify dynamic-import call syntax without leaking aliases across scopes.

    Conflicting local bindings are unresolved, not assumed to be import helpers.
    Explicit builtins.__import__ aliases follow the same level=0 rules as the
    builtin function; unknown relative levels remain unresolved.
    This remains static syntax evidence, not runtime binding verification.
    """
    # Comprehension targets bind in an implicit inner scope, never the outer
    # module/function. Otherwise they can suppress unrelated import witnesses.
    scope_types = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                   ast.ClassDef, ast.Lambda, ast.ListComp, ast.SetComp,
                   ast.DictComp, ast.GeneratorExp)
    parents: dict[ast.AST, ast.AST | None] = {tree: None}
    containing: dict[ast.AST, ast.AST] = {}

    def locate(node: ast.AST, scope: ast.AST) -> None:
        containing[node] = scope
        nested = node if isinstance(node, scope_types) else scope
        if nested is not scope:
            parents[node] = scope
        for child in ast.iter_child_nodes(node):
            if (isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp,
                                  ast.GeneratorExp)) and node.generators
                    and child is node.generators[0]):
                # Python evaluates the leftmost iterable in the enclosing
                # scope, before binding the comprehension's first target.
                # The target and its filters, like later generators and the
                # result expression, execute in the comprehension scope.
                containing[child] = nested
                locate(child.iter, scope)
                locate(child.target, nested)
                for condition in child.ifs:
                    locate(condition, nested)
            elif (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                    ast.ClassDef)) and (
                    child in node.decorator_list
                    or (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and child is node.returns)
                    or (isinstance(node, ast.ClassDef)
                        and (child in node.bases or child in node.keywords)))):
                # Decorators, bases, keywords and return annotations are
                # evaluated in the enclosing definition scope, not the
                # new function/class body scope.
                locate(child, scope)
            elif (isinstance(node, ast.arguments)
                  and (child in node.defaults or child in node.kw_defaults)):
                # Default values execute before function/lambda entry.
                locate(child, parents[scope])
            elif isinstance(node, ast.arg) and child is node.annotation:
                # Argument annotations use the enclosing definition scope
                # (or are deferred); parameters cannot shadow them here.
                locate(child, parents[scope])
            else:
                locate(child, nested)

    locate(tree, tree)
    # PEP 572: a named-expression target in a comprehension binds in the
    # containing scope, unlike an ordinary comprehension iteration target.
    walrus_targets = {
        node.target for node in containing
        if isinstance(node, ast.NamedExpr) and isinstance(node.target, ast.Name)
    }
    bindings: dict[ast.AST, dict[str, str | None]] = {
        scope: {} for scope in parents
    }

    def bind(scope: ast.AST, name: str, target: str | None) -> None:
        local = bindings[scope]
        if name not in local:
            local[name] = target
        elif local[name] != target:
            local[name] = None

    for node, scope in containing.items():
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname or alias.name.split(".")[0]
                # Unaliased dotted imports bind their root package:
                # 'import importlib.util' makes 'importlib' available, while
                # 'import importlib.util as util' binds only 'util'.
                root = alias.name.split(".")[0]
                target = (alias.name if alias.name in {"importlib", "pkgutil", "builtins"}
                          else root if alias.asname is None
                          and root in {"importlib", "pkgutil", "builtins"} else None)
                bind(scope, name, target)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                name = alias.asname or alias.name
                target = (node.module + "." + alias.name
                          if node.level == 0 and (
                              (node.module == "importlib" and alias.name == "import_module")
                              or (node.module == "pkgutil" and alias.name == "resolve_name")
                              or (node.module == "builtins" and alias.name == "__import__")
                          ) else None)
                bind(scope, name, target)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            # Deletion invalidates a previously imported helper in this scope.
            binding_scope = scope
            if node in walrus_targets:
                while isinstance(binding_scope, (ast.ListComp, ast.SetComp,
                                                 ast.DictComp, ast.GeneratorExp)):
                    binding_scope = parents[binding_scope]
            bind(binding_scope, node.id, None)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            # Exception aliases are stored as strings, not ast.Name(Store).
            bind(scope, node.name, None)
        elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
            # Capture patterns also bind string names rather than Name(Store).
            bind(scope, node.name, None)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            bind(scope, node.rest, None)
        elif isinstance(node, ast.arg):
            bind(scope, node.arg, None)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bind(scope, node.name, None)

    # A global/nonlocal directive redirects stores into an enclosing scope.
    # The initial binding inventory is scope-local, so conservatively taint
    # the target scope when a nested declaration also writes the helper name.
    # Without this, a mutation in a nested function could forge a known
    # dynamic-import consumer in an unrelated reader of the same binding.
    for node, scope in containing.items():
        if isinstance(node, ast.Global):
            for name in node.names:
                if name in bindings[scope]:
                    bind(tree, name, None)
        elif isinstance(node, ast.Nonlocal):
            for name in node.names:
                if name not in bindings[scope]:
                    continue
                outer = parents[scope]
                while outer is not None:
                    if (isinstance(outer, (ast.FunctionDef, ast.AsyncFunctionDef,
                                           ast.Lambda)) and name in bindings[outer]):
                        bind(outer, name, None)
                        break
                    outer = parents[outer]

    def resolve(name: str, scope: ast.AST) -> str | None:
        current: ast.AST | None = scope
        in_function = isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef,
                                         ast.Lambda, ast.ListComp, ast.SetComp,
                                         ast.DictComp, ast.GeneratorExp))
        while current is not None:
            # Python methods do not capture names assigned in a class body.
            if not (in_function and isinstance(current, ast.ClassDef)):
                if name in bindings[current]:
                    return bindings[current][name]
            if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef,
                                    ast.Lambda, ast.ListComp, ast.SetComp,
                                    ast.DictComp, ast.GeneratorExp)):
                in_function = True
            current = parents[current]
        return "__import__" if name == "__import__" else None

    calls: dict[ast.Call, str] = {}
    for node, scope in containing.items():
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            helper = resolve(func.id, scope)
        elif isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            module = resolve(func.value.id, scope)
            helper = module + "." + func.attr if module in {"importlib", "pkgutil", "builtins"} else None
        else:
            helper = None
        if helper in {"__import__", "builtins.__import__", "importlib.import_module", "pkgutil.resolve_name"}:
            calls[node] = helper
    return calls


def assess_architecture_migration(
    inventory: Mapping[str, Any],
    scenarios: Mapping[str, Any],
    source_texts: Mapping[str, str | bytes],
) -> dict[str, Any]:
    """Assess B4 candidates against caller-attested B1 source bytes.

    A B4 report's self-digest is checked, but not mistaken for independent
    authentication of the B2/B3 derivation. A trusted caller must supply those
    exact-head reports and independently validate them before invoking B5.
    """
    try:
        if not all(isinstance(x, Mapping) for x in (inventory, scenarios, source_texts)):
            raise ArchitectureMigrationError("mapping inputs required")
        files = inventory["files"]
        by_path = {item["path"]: item for item in files}
        identity = inventory["source_identity"]
        if (len(by_path) != len(files)
                or inventory["inventory_id"] != _digest({
                    k: v for k, v in inventory.items() if k != "inventory_id"
                })
                or scenarios["scenarios_id"] != _digest({
                    k: v for k, v in scenarios.items() if k != "scenarios_id"
                })
                or scenarios["snapshot_sha"] != identity["repository_commit_sha"]
                or scenarios["inventory_id"] != inventory["inventory_id"]
                or scenarios["role_policy_sha256"] != identity["role_policy_sha256"]
                or not isinstance(scenarios["candidates"], list)
                or not isinstance(scenarios["rejected"], list)
                or not set(source_texts) <= set(by_path)):
            raise ArchitectureMigrationError("B1/B4 identity or source scope mismatch")
        decoded: dict[str, str] = {}
        hashes: dict[str, str] = {}
        for path, raw in source_texts.items():
            if by_path[path]["read_state"] != "READ" or not isinstance(raw, (str, bytes)):
                raise ArchitectureMigrationError("unread or non-text source supplied")
            payload = raw.encode("utf-8") if isinstance(raw, str) else raw
            if sha256(payload).hexdigest() != by_path[path]["source_sha256"]:
                raise ArchitectureMigrationError("source hash differs from B1 snapshot")
            hashes[path] = sha256(payload).hexdigest()
            try:
                decoded[path] = payload.decode("utf-8")
            except UnicodeDecodeError:
                # Non-text resources can be present but cannot support text evidence.
                continue
        if any(item["read_state"] == "READ" and item["language"] == "python"
               and item["path"] not in decoded
               for item in files if item["path"] in {
                   move["from"] for candidate in scenarios["candidates"]
                   for move in candidate["path_mapping"]
               }):
            raise ArchitectureMigrationError("moved Python source bytes missing")
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        raise ArchitectureMigrationError("untrustworthy B1/B4 migration inputs") from exc

    missing = sorted(item["path"] for item in files
                     if item["read_state"] == "READ" and item["path"] not in decoded)
    python_paths = sorted(p for p in decoded if p.endswith(".py"))
    trees: dict[str, ast.AST] = {}
    syntax_errors: list[str] = []
    for path in python_paths:
        try:
            trees[path] = ast.parse(decoded[path], filename=path)
        except SyntaxError:
            syntax_errors.append(path)
    modules = {_module(p): p for p in by_path if _module(p)}
    # A module file can shadow a namespace-package directory even when its
    # destination .py path is free. Such a move may break child imports.
    # Derive potential namespace parents from the same tracked source census.
    namespace_descendants: dict[str, set[str]] = {}
    for tracked_path in by_path:
        if tracked_path.startswith("src/") and tracked_path.endswith(".py"):
            parts = tracked_path[4:].split("/")
            for depth in range(1, len(parts)):
                namespace_descendants.setdefault(
                    ".".join(parts[:depth]), set()
                ).add(tracked_path)
    results: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for candidate in scenarios["candidates"]:
        try:
            if (candidate["scenario_id"] != _digest({
                    k: v for k, v in candidate.items() if k != "scenario_id"
                }) or candidate["source_identity"]["snapshot_sha"] != scenarios["snapshot_sha"]
                or candidate["source_identity"]["inventory_id"] != inventory["inventory_id"]
                or candidate["source_identity"]["metrics_id"] != scenarios["metrics_id"]
                or candidate["source_identity"]["role_policy_sha256"] != scenarios["role_policy_sha256"]
                or candidate["source_identity"]["dependency_profile_id"] != scenarios["dependency_profile_id"]
                or candidate["scenario_id"] in seen_ids):
                raise ArchitectureMigrationError("invalid candidate identity")
            seen_ids.add(candidate["scenario_id"])
            path_map = {move["from"]: move["to"] for move in candidate["path_mapping"]}
            if len(path_map) != len(candidate["path_mapping"]) or not path_map:
                raise ArchitectureMigrationError("invalid or empty B4 mapping")
            old_to_new: dict[str, str] = {}
            new_to_path: dict[str, str] = {}
            for move in candidate["path_mapping"]:
                old, new = move["from"], move["to"]
                if (old not in by_path or by_path[old]["source_sha256"] != move["source_sha256"]
                        or old not in decoded or _module(old) is None or _module(new) is None):
                    raise ArchitectureMigrationError("unverified moved source/module")
                old_to_new[_module(old)] = _module(new)
                new_to_path[_module(new)] = new
            if len(old_to_new) != len(path_map) or len(new_to_path) != len(path_map):
                raise ArchitectureMigrationError("duplicate dotted module identity")
        except (KeyError, TypeError, ValueError) as exc:
            raise ArchitectureMigrationError("invalid B4 candidate") from exc

        # A path can be free while its Python module name collides with an
        # existing namespace package or __init__.py; block this independently.
        conflicts = sorted({
            new for old, new in old_to_new.items()
            if (new in modules and modules[new] not in path_map)
            or (not new_to_path[new].endswith("/__init__.py")
                and any(path not in path_map
                        for path in namespace_descendants.get(new, ())))
        })
        sites: list[dict[str, Any]] = []
        risk_flags: set[str] = set()
        exported_paths: set[str] = set()
        for path, tree in trees.items():
            source_module = _module(path)
            if source_module is None:
                # Tests and scripts outside src/ are still Python consumers.
                # A textual search misses split from-imports because the
                # complete old dotted name never appears on the source line:
                #     from orchard.sky import view
                # Record only these split imports here. Full dotted imports
                # remain covered by the existing text-reference scan below,
                # avoiding duplicate evidence for the same site.
                for node in ast.walk(tree):
                    if not isinstance(node, ast.ImportFrom) or node.level:
                        continue
                    base = node.module or ""
                    for alias in node.names:
                        if alias.name == "*":
                            # A star import from the moved module is already
                            # visible to the text scan. A star import from an
                            # ancestor package is not: it could re-export the
                            # moved child through __all__ or initializer code.
                            # This is a potential compatibility risk, NOT
                            # proof that the child is actually exported.
                            for old, new in old_to_new.items():
                                if _matches(base, old):
                                    risk_flags.add("STAR_IMPORT_REVIEW")
                                elif base and old.startswith(base + "."):
                                    sites.append(_record(
                                        path, node.lineno, "STAR_IMPORT",
                                        base + ":*", hashes[path],
                                        old, new, "REVIEW_REQUIRED",
                                    ))
                                    risk_flags.add("STAR_IMPORT_REVIEW")
                            continue
                        target = base + "." + alias.name if base else alias.name
                        for old, new in old_to_new.items():
                            if _matches(target, old) and not _matches(base, old):
                                sites.append(_record(
                                    path, node.lineno, "TEST_OR_SCRIPT_REFERENCE",
                                    base + ":" + alias.name, hashes[path],
                                    old, new, "REVIEW_REQUIRED",
                                ))
                continue
            package = source_module if path.endswith("/__init__.py") else source_module.rpartition(".")[0]
            moved_source = path in path_map
            dynamic_calls = _dynamic_helpers(tree)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        for old, new in old_to_new.items():
                            if _matches(alias.name, old):
                                kind = "ALIASED_IMPORT" if alias.asname else "STATIC_IMPORT"
                                sites.append(_record(path, node.lineno, kind,
                                    alias.name, hashes[path], old, new, "REVIEW_REQUIRED"))
                                if alias.asname:
                                    risk_flags.add("ALIASED_IMPORT_REVIEW")
                elif isinstance(node, ast.ImportFrom):
                    resolved = (_relative(package, node.level, node.module)
                                if node.level else (node.module or ""))
                    if resolved is None:
                        risk_flags.add("UNRESOLVED_RELATIVE_IMPORT")
                        continue
                    for alias in node.names:
                        target = resolved + "." + alias.name if resolved else alias.name
                        for old, new in old_to_new.items():
                            if (_matches(resolved, old) or _matches(target, old)
                                    or (moved_source and node.level > 0)
                                    or (alias.name == "*" and old.startswith(resolved + "."))):
                                if alias.name == "*":
                                    kind = "STAR_IMPORT"
                                    risk_flags.add("STAR_IMPORT_REVIEW")
                                elif node.level:
                                    kind = "RELATIVE_IMPORT"
                                    risk_flags.add("RELATIVE_IMPORT_REVIEW")
                                elif alias.asname:
                                    kind = "ALIASED_FROM_IMPORT"
                                    risk_flags.add("ALIASED_IMPORT_REVIEW")
                                else:
                                    kind = "FROM_IMPORT"
                                sites.append(_record(path, node.lineno, kind,
                                    ("." * node.level) + (node.module or "") + ":" + alias.name,
                                    hashes[path], old, new, "REVIEW_REQUIRED"))
                                if path.endswith("/__init__.py"):
                                    exported_paths.add(path)
                                    risk_flags.add("INIT_REEXPORT_REVIEW")
                elif isinstance(node, ast.Call):
                    helper = dynamic_calls.get(node)
                    if helper not in {"__import__", "builtins.__import__",
                                      "importlib.import_module", "pkgutil.resolve_name"}:
                        continue
                    # The first import target can be positional or supplied as
                    # the public 'name=' keyword on these three helpers.
                    # A starred/unknown expression is not a literal witness.
                    first_arg = (node.args[0] if node.args else next(
                        (kw.value for kw in node.keywords if kw.arg == "name"), None
                    ))
                    value = (first_arg.value if isinstance(first_arg, ast.Constant)
                             and isinstance(first_arg.value, str) else None)
                    # pkgutil.resolve_name accepts 'module:object' as well as
                    # dotted module names. Keep the full literal as evidence.
                    target = (value.split(":", 1)[0]
                              if value is not None and helper == "pkgutil.resolve_name"
                              else value)
                    if helper in {"__import__", "builtins.__import__"}:
                        # The fifth positional / level= argument changes
                        # __import__ from an absolute import into a relative
                        # import. A relative or dynamic level is not evidence
                        # that the literal names the proposed old module.
                        level_arg = (node.args[4] if len(node.args) > 4 else next(
                            (kw.value for kw in node.keywords if kw.arg == "level"),
                            None
                        ))
                        if (any(isinstance(arg, ast.Starred) for arg in node.args)
                                or any(kw.arg is None for kw in node.keywords)
                                or (level_arg is not None and (
                                    not isinstance(level_arg, ast.Constant)
                                    or type(level_arg.value) is not int
                                    or level_arg.value != 0))):
                            target = None
                    if (helper == "importlib.import_module" and value is not None
                            and value.startswith(".")):
                        # import_module('.child', package='pkg.parent') is an
                        # absolute consumer of pkg.parent.child. Without a
                        # literal package the target is not statically known.
                        package_arg = (node.args[1] if len(node.args) > 1 else next(
                            (kw.value for kw in node.keywords if kw.arg == "package"),
                            None
                        ))
                        package_name = (package_arg.value
                                        if isinstance(package_arg, ast.Constant)
                                        and isinstance(package_arg.value, str) else None)
                        dots = len(value) - len(value.lstrip("."))
                        parts = package_name.split(".") if package_name else []
                        suffix = value[dots:]
                        if (parts and all(part.isidentifier() for part in parts)
                                and dots <= len(parts)
                                and (not suffix or all(part.isidentifier()
                                                       for part in suffix.split(".")))):
                            target = ".".join(parts[:len(parts) - dots + 1]
                                              + (suffix.split(".") if suffix else []))
                        else:
                            target = None
                    for old, new in old_to_new.items():
                        if target is None:
                            risk_flags.add("DYNAMIC_IMPORT_TARGET_UNKNOWN")
                        elif _matches(target, old):
                            sites.append(_record(path, node.lineno, "DYNAMIC_IMPORT_LITERAL",
                                value, hashes[path], old, new, "REVIEW_REQUIRED"))
                            risk_flags.add("DYNAMIC_IMPORT_REVIEW")
                elif (path.endswith("/__init__.py") and isinstance(node, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == "__all__"
                              for t in node.targets)):
                    if any(source_module == old.rpartition(".")[0]
                           for old in old_to_new):
                        exported_paths.add(path)
                        risk_flags.add("INIT_ALL_EXPORT_REVIEW")

        # Non-Python consumers can contain import references, entrypoints,
        # package metadata, resource mappings or documentation links.
        for path, value in sorted(decoded.items()):
            if path.endswith(".py") and path.startswith("src/"):
                continue
            is_packaging = path.rsplit("/", 1)[-1] in {
                "pyproject.toml", "setup.cfg", "setup.py", "MANIFEST.in"
            }
            for number, line in enumerate(value.splitlines(), 1):
                for old, new in old_to_new.items():
                    if old in line or old.replace(".", "/") in line:
                        kind = ("PACKAGING_REFERENCE" if is_packaging
                                else "TEST_OR_SCRIPT_REFERENCE" if path.endswith(".py")
                                else "CONFIG_OR_DOC_REFERENCE")
                        sites.append(_record(path, number, kind, line.strip()[:240],
                                             hashes[path], old, new, "REVIEW_REQUIRED"))
                        if is_packaging:
                            risk_flags.add("PACKAGE_METADATA_REVIEW")
                        if ("script" in line.lower() or "entry" in line.lower() or (is_packaging and any(marker in value for marker in ("[project.scripts]", "[project.gui-scripts]", "[options.entry_points]", "[project.entry-points")))):
                            risk_flags.add("CLI_ENTRYPOINT_REVIEW")
        if conflicts:
            risk_flags.add("DOTTED_MODULE_NAMESPACE_COLLISION")
        if any(path not in decoded for path in inventory["package_metadata_paths"]):
            risk_flags.add("PACKAGE_METADATA_NOT_FULLY_OBSERVED")
        if syntax_errors:
            risk_flags.add("PYTHON_PARSE_GAPS")
        if missing:
            risk_flags.add("SOURCE_COVERAGE_GAPS")
        if any(item["read_state"] != "READ" for item in files):
            risk_flags.add("INVENTORY_UNREAD_PATHS")
        risk_flags.add("EXTERNAL_CONSUMERS_UNOBSERVED")
        risk_flags.add("RUNTIME_ABI_SEMANTICS_NOT_EVALUATED")
        risk_flags.add("DISTRIBUTION_AND_RESOURCE_RELOCATION_NOT_EVALUATED")
        if any(old.split(".")[0] != new.split(".")[0]
               for old, new in old_to_new.items()):
            risk_flags.add("CROSS_TOP_LEVEL_PACKAGE_DISTRIBUTION_UNKNOWN")
        sites.sort(key=lambda s: (s["path"], s["line"], s["kind"], s["old_module"]))
        count = len(sites)
        if conflicts:
            cost = "BLOCKED"
        elif count > 10 or any(x in risk_flags for x in (
                "STAR_IMPORT_REVIEW", "CLI_ENTRYPOINT_REVIEW",
                "DOTTED_MODULE_NAMESPACE_COLLISION",
                "CROSS_TOP_LEVEL_PACKAGE_DISTRIBUTION_UNKNOWN")):
            cost = "HIGH"
        elif count > 2 or len(path_map) > 1 or any(x in risk_flags for x in (
                "DYNAMIC_IMPORT_TARGET_UNKNOWN", "PACKAGE_METADATA_REVIEW",
                "INIT_REEXPORT_REVIEW", "RELATIVE_IMPORT_REVIEW")):
            cost = "MEDIUM"
        else:
            cost = "LOW"
        result = {
            "scenario_id": candidate["scenario_id"],
            "path_mapping": candidate["path_mapping"],
            "observed_sites": sites,
            "observed_site_count": count,
            "affected_file_count": len({s["path"] for s in sites}),
            "moved_file_count": len(path_map),
            "initializer_export_paths": sorted(exported_paths),
            "namespace_collisions": conflicts,
            "cost_band": cost,
            "cost_basis": {
                "static_and_text_reference_sites": count,
                "moved_files": len(path_map),
                "unresolved_risk_flag_count": len(risk_flags),
                "band_rules": "BLOCKED if namespace collision; HIGH if >10 sites or star/CLI/distribution risk; MEDIUM if >2 sites/multi-file or unresolved dynamic/metadata/export/relative; otherwise LOW",
            },
            "compatibility_status": "BLOCKED" if conflicts else "NOT_EVALUATED",
            "confidence": ("INSUFFICIENT_EVIDENCE" if missing or syntax_errors
                           or "INVENTORY_UNREAD_PATHS" in risk_flags
                           else "STATIC_PARTIAL"),
            "unknowns": sorted(risk_flags),
            "compatibility_options": [
                "forwarding module or facade subject to independent import tests",
                "versioned deprecation window subject to consumer contract",
                "separate distribution only after packaging and external-caller evidence",
            ],
        }
        results.append(result)

    report = {
        "schema_version": "0.1",
        "snapshot_sha": scenarios["snapshot_sha"],
        "inventory_id": inventory["inventory_id"],
        "scenarios_id": scenarios["scenarios_id"],
        "candidates": sorted(results, key=lambda c: c["scenario_id"]),
        "rejected_scenarios": scenarios["rejected"],
        "source_coverage": {
            "read_source_texts": len(decoded),
            "missing_read_source_texts": missing,
            "python_parse_failures": sorted(syntax_errors),
        },
        "decision": "NOT_EVALUATED",
        "evidence_status": "INCOMPLETE",
        "limitations": [
            "B4 digest is checked, but trusted caller must authenticate upstream B2/B3 provenance",
            "external consumers, runtime ABI and semantic parity are not proven",
            "source scanning is static and cannot guarantee absence of dynamic or downstream imports",
            "cost bands count observable sites and risk flags, not predicted engineering time",
            "no source, import, public API, package or distribution is modified",
        ],
    }
    report["migration_id"] = _digest(report)
    return report
