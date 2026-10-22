"""Conservative Python cross-module callable declaration correspondence.

Only module-scope imports into unique, unshadowed names and direct
module-scope, undecorated function declarations are eligible. Calls are
inspected inside direct module-level function bodies only. No package
re-export, object method, wildcard, nested import, runtime loading,
monkey-patch, class, decorator, inheritance or dispatch is resolved.
"""
from __future__ import annotations

import ast
from collections import Counter, defaultdict

from codeqa.core.evidence import EvidenceIndex
from codeqa.core.symbols import SymbolCallCandidate, SymbolCallReport
from .lexical import ModuleBindings, _Bindings, _local_bindings
from .python_dependencies import _module_name, _relative_name
from .python_snapshot import ParsedSnapshot


def _module_index(parsed: ParsedSnapshot) -> dict[str, tuple[str, ...]]:
    modules: dict[str, set[str]] = defaultdict(set)
    for file in parsed.files:
        module = _module_name(file.path)
        if module is not None:
            modules[module[0]].add(file.path)
    return {module: tuple(sorted(paths)) for module, paths in modules.items()}


def _binding_candidates(
    tree: ast.Module, source_module: str | None, source_is_package: bool,
) -> dict[str, tuple[str, str, str]]:
    """Map local import names to declared source module and function name."""
    collector = _Bindings()
    for statement in tree.body:
        collector.visit(statement)
    counts = Counter(collector.names)
    globals_declared = {
        name for node in ast.walk(tree) if isinstance(node, (ast.Global, ast.Nonlocal))
        for name in node.names
    }
    if any(
        isinstance(node, ast.ImportFrom)
        and any(alias.name == "*" for alias in node.names)
        for node in ast.walk(tree)
    ):
        return {}

    bindings: dict[str, tuple[str, str, str]] = {}
    for stmt in tree.body:
        if isinstance(stmt, ast.Import):
            for alias in stmt.names:
                # Importing a dotted name without an alias binds only the
                # first component. Require an explicit module alias.
                if alias.asname is None:
                    continue
                name = alias.asname
                if counts[name] == 1 and name not in globals_declared:
                    bindings[name] = (alias.name, "", "module_alias")
        elif isinstance(stmt, ast.ImportFrom):
            if stmt.level:
                module = (
                    _relative_name(source_module, source_is_package, stmt.level, stmt.module)
                    if source_module is not None else None
                )
            else:
                module = stmt.module
            if not module:
                continue
            for alias in stmt.names:
                name = alias.asname or alias.name
                if counts[name] == 1 and name not in globals_declared:
                    bindings[name] = (module, alias.name, "direct_symbol_import")
    return bindings


class _Calls(ast.NodeVisitor):
    """Visit one function body without attributing nested scopes."""

    def __init__(self) -> None:
        self.calls: list[ast.Call] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return

    visit_AsyncFunctionDef = visit_FunctionDef
    visit_ClassDef = visit_FunctionDef
    visit_Lambda = visit_FunctionDef

    def visit_Call(self, node: ast.Call) -> None:
        self.calls.append(node)
        self.generic_visit(node)


def _candidate_signature(
    func: ast.expr, bindings: dict[str, tuple[str, str, str]],
) -> tuple[str, str, str, str] | None:
    if isinstance(func, ast.Name):
        selected = bindings.get(func.id)
        if selected and selected[2] == "direct_symbol_import":
            module, target_name, kind = selected
            return func.id, module, target_name, kind
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        selected = bindings.get(func.value.id)
        if selected and selected[2] == "module_alias":
            module, _, kind = selected
            return func.value.id, module, func.attr, kind
    return None


def extract_symbol_call_candidates(
    parsed: ParsedSnapshot, evidence: EvidenceIndex, *, snapshot_id: str,
) -> SymbolCallReport:
    if evidence.snapshot_id != snapshot_id:
        raise ValueError("source evidence and symbol lookup must share snapshot")

    modules = _module_index(parsed)
    by_path = {file.path: file.tree for file in parsed.files}
    function_targets = {
        path: ModuleBindings(tree, path).targets
        for path, tree in by_path.items() if tree is not None
    }
    witnesses = {
        (fact.path, fact.line, fact.column, fact.expression): fact.evidence_id
        for fact in evidence.facts if fact.kind == "call"
    }
    skips: Counter[str] = Counter()
    candidates: list[SymbolCallCandidate] = []
    scanned = 0
    for file in parsed.files:
        tree = file.tree
        assert tree is not None
        module = _module_name(file.path)
        bindings = _binding_candidates(
            tree,
            module[0] if module else None,
            module[1] if module else False,
        )
        for fn in tree.body:
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            scope = _local_bindings(fn)
            visitor = _Calls()
            for stmt in fn.body:
                visitor.visit(stmt)
            for call in visitor.calls:
                scanned += 1
                signature = _candidate_signature(call.func, bindings)
                if signature is None:
                    skips["not_explicit_module_or_symbol_import"] += 1
                    continue
                binding, target_module, symbol, kind = signature
                if binding in scope:
                    skips["locally_shadowed_binding"] += 1
                    continue
                paths = modules.get(target_module, ())
                if len(paths) != 1:
                    skips["ambiguous_or_outside_snapshot_module"] += 1
                    continue
                target_path = paths[0]
                target = function_targets[target_path].get(symbol)
                if target is None:
                    skips["symbol_not_unambiguous_plain_function"] += 1
                    continue
                expression = ast.unparse(call.func)
                witness = witnesses.get((
                    file.path, call.lineno, call.col_offset, expression,
                ))
                if witness is None:
                    skips["missing_exact_source_witness"] += 1
                    continue
                candidates.append(SymbolCallCandidate(
                    source_path=file.path,
                    source_node_id=(
                        f"def::{file.path}::{fn.name}@{fn.lineno}:{fn.col_offset}"
                    ),
                    call_line=call.lineno,
                    call_column=call.col_offset,
                    call_expression=expression,
                    import_binding=binding,
                    import_kind=kind,
                    imported_module=target_module,
                    target_path=target_path,
                    target_node_id=target,
                    evidence_id=witness,
                ))
    return SymbolCallReport(
        snapshot_id=snapshot_id,
        scanned_call_sites=scanned,
        candidates=tuple(sorted(candidates, key=lambda c: (
            c.source_path, c.call_line, c.call_column,
            c.target_path, c.target_node_id,
        ))),
        excluded_by_reason=tuple(sorted(skips.items())),
    )
