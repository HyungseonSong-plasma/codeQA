"""Source-bound lexical caller contexts for sampled cross-role Python calls.

A Python frame call and an AST function span are evidence of a sampled call
site, not evidence of intentional orchestration, correct ownership, import
binding, or API compatibility. No code is moved or executed here.
"""
from __future__ import annotations

import ast
from collections.abc import Mapping
from hashlib import sha256
import json
import re
from typing import Any


class CallsiteContextError(ValueError):
    """The call witness cannot be bound to a single selected source snapshot."""


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _sealed(value: Mapping[str, Any], key: str) -> bool:
    return value[key] == _digest({k: v for k, v in value.items() if k != key})


def _module_name(path: str) -> str | None:
    """Map a selected src-layout Python path to a lexical module name."""
    if not path.startswith("src/") or not path.endswith(".py"):
        return None
    parts = path[4:-3].split("/")
    if parts[-1] == "__init__":
        parts.pop()
    if not parts or not all(part.isidentifier() for part in parts):
        return None
    return ".".join(parts)


def _module_level_target_aliases(
    tree: ast.Module, source_path: str, target_path: str,
) -> dict[str, list[int]]:
    """Find module-level import spellings that *could* bind a target.

    Does not resolve shadowing, rebinding, control flow, star imports, or
    runtime objects. This is a lexical candidate census, not attribution.
    """
    target = _module_name(target_path)
    source = _module_name(source_path)
    if target is None or source is None:
        return {}
    package = source if source_path.endswith("/__init__.py") else source.rpartition(".")[0]
    aliases: dict[str, set[int]] = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == target:
                    name = alias.asname or alias.name.split(".")[0]
                    aliases.setdefault(name, set()).add(node.lineno)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = package.split(".") if package else []
                if node.level > len(parts):
                    continue
                prefix = ".".join(parts[:len(parts) - node.level + 1])
                module = ".".join(filter(None, (prefix, node.module or "")))
            else:
                module = node.module or ""
            for alias in node.names:
                if alias.name == "*":
                    continue
                if module == target or ".".join((module, alias.name)) == target:
                    aliases.setdefault(alias.asname or alias.name, set()).add(node.lineno)
    return {name: sorted(lines) for name, lines in sorted(aliases.items())}



def _unaliased_module_import_prefixes(
    tree: ast.Module, target_path: str,
    target_aliases: Mapping[str, list[int]],
) -> dict[str, str]:
    """Restrict a bare package root to its actually imported module path.

    For ``import pkg.core.target``, Python binds ``pkg``, but a call
    to ``pkg.other.run()`` is not a lexical call through that import.
    If another target import binds the same root, preserve uncertainty.
    """
    target = _module_name(target_path)
    if target is None:
        return {}
    root = target.partition(".")[0]
    lines = {
        node.lineno
        for node in tree.body if isinstance(node, ast.Import)
        for alias in node.names
        if alias.name == target and alias.asname is None
    }
    if lines and set(target_aliases.get(root, [])) == lines:
        return {root: target}
    return {}


def _callee_root(node: ast.expr) -> str | None:
    while isinstance(node, ast.Attribute):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _enclosing_parameter_names(tree: ast.AST, line: int) -> set[str]:
    """Find lexical function parameters enclosing a sampled caller line.

    This is a conservative *warning* only: global/nonlocal declarations,
    runtime rebinding, decorators, and implicit call targets are not resolved.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if (not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                or not node.body or node.end_lineno is None
                or not node.body[0].lineno <= line <= node.end_lineno):
            continue
        args = node.args
        names.update(arg.arg for arg in (
            args.posonlyargs + args.args + args.kwonlyargs
        ))
        if args.vararg is not None:
            names.add(args.vararg.arg)
        if args.kwarg is not None:
            names.add(args.kwarg.arg)
    return names


def _enclosing_local_binding_names(tree: ast.AST, line: int) -> set[str]:
    """Conservatively find function-local names that may mask module imports.

    Python treats a name assigned anywhere in a function as local, even if
    the assignment occurs after the sampled call. Nested function bodies and
    comprehension targets have separate scopes and are not traversed.
    """
    class ComprehensionAssignments(ast.NodeVisitor):
        """Walrus targets bind the containing function, not comprehension locals.

        Generator targets remain in the comprehension's own scope. A lambda
        nested in a comprehension has a separate scope and is not inspected.
        """
        def __init__(self) -> None:
            self.names: set[str] = set()

        def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
            self.names.update(
                child.id for child in ast.walk(node.target)
                if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store)
            )
            self.visit(node.value)

        def visit_comprehension(self, node: ast.comprehension) -> None:
            self.visit(node.iter)
            for condition in node.ifs:
                self.visit(condition)

        def visit_Lambda(self, node: ast.Lambda) -> None:
            pass

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            pass

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            pass

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            pass

    class LocalBindings(ast.NodeVisitor):
        def __init__(self) -> None:
            self.names: set[str] = set()
            self.global_names: set[str] = set()
            self.nonlocal_names: set[str] = set()

        def visit_Name(self, node: ast.Name) -> None:
            if isinstance(node.ctx, ast.Store):
                self.names.add(node.id)

        def visit_Import(self, node: ast.Import) -> None:
            self.names.update(alias.asname or alias.name.split(".")[0]
                              for alias in node.names)

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            self.names.update(alias.asname or alias.name
                              for alias in node.names if alias.name != "*")

        def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
            if node.name:
                self.names.add(node.name)
            self.generic_visit(node)

        def visit_MatchAs(self, node: ast.MatchAs) -> None:
            if node.name:
                self.names.add(node.name)
            self.generic_visit(node)

        def visit_MatchStar(self, node: ast.MatchStar) -> None:
            if node.name:
                self.names.add(node.name)

        def visit_MatchMapping(self, node: ast.MatchMapping) -> None:
            if node.rest:
                self.names.add(node.rest)
            self.generic_visit(node)

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self.names.add(node.name)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self.names.add(node.name)

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            self.names.add(node.name)

        def visit_Lambda(self, node: ast.Lambda) -> None:
            pass

        def _visit_comprehension(self, node: ast.AST) -> None:
            assignments = ComprehensionAssignments()
            assignments.visit(node)
            self.names.update(assignments.names)

        visit_ListComp = _visit_comprehension
        visit_SetComp = _visit_comprehension
        visit_DictComp = _visit_comprehension
        visit_GeneratorExp = _visit_comprehension

        def visit_Global(self, node: ast.Global) -> None:
            self.global_names.update(node.names)

        def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
            self.nonlocal_names.update(node.names)

    names: set[str] = set()
    for scope in ast.walk(tree):
        if (not isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef))
                or not scope.body or scope.end_lineno is None
                or not scope.body[0].lineno <= line <= scope.end_lineno):
            continue
        bindings = LocalBindings()
        for statement in scope.body:
            bindings.visit(statement)
        names.update(bindings.names - bindings.global_names - bindings.nonlocal_names)
    return names


def _function_context(tree: ast.AST, line: int) -> dict[str, Any]:
    """Find the innermost *lexical* function body covering a sampled line."""
    parents = {child: parent for parent in ast.walk(tree)
               for child in ast.iter_child_nodes(parent)}
    functions = [
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.body and node.end_lineno is not None
        and node.body[0].lineno <= line <= node.end_lineno
    ]
    if not functions:
        return {"lexical_context": "MODULE_OR_CLASS_BODY",
                "function_qualname": None, "function_line": None}
    node = min(functions, key=lambda item: (
        item.end_lineno - item.lineno, -item.lineno,
    ))
    names = [node.name]
    parent = parents.get(node)
    while parent is not None:
        if isinstance(parent, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.append(parent.name)
        parent = parents.get(parent)
    return {"lexical_context": "FUNCTION_BODY",
            "function_qualname": ".".join(reversed(names)),
            "function_line": node.lineno}


def _callsite_syntax(
    tree: ast.AST, line: int, target_aliases: Mapping[str, list[int]],
    qualified_import_prefixes: Mapping[str, str],
) -> dict[str, Any]:
    """Describe source AST spans, without attributing a call to a target.

    A frame's caller line can cover multiple nested calls or no explicit
    ``ast.Call`` at all (e.g. implicit interpreter calls). Neither outcome
    authenticates or disproves the callee observed by the runtime sampler.
    """
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and node.end_lineno is not None
        and node.lineno <= line <= node.end_lineno
    ]
    statements = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.stmt) and node.end_lineno is not None
        and node.lineno <= line <= node.end_lineno
    ]
    statement = min(
        statements, key=lambda node: (node.end_lineno - node.lineno, -node.lineno)
    ) if statements else None
    alias_candidates = []
    for call in calls:
        root = _callee_root(call.func)
        expression = ast.unparse(call.func)
        prefix = qualified_import_prefixes.get(root)
        if (root in target_aliases
                and (prefix is None or expression == prefix
                     or expression.startswith(prefix + "."))):
            alias_candidates.append({
                "callee_expression": expression,
                "root_name": root,
                "call_line": call.lineno,
                "call_column": call.col_offset,
                "target_import_lines": target_aliases[root],
            })
    alias_candidates.sort(key=lambda item: (
        item["call_line"], item["call_column"], item["callee_expression"]
    ))
    # Source-only receiver shapes help explain sampled calls that do not
    # syntactically invoke an imported alias. They never identify the callee.
    indirect_receivers = []
    for call in calls:
        root = _callee_root(call.func)
        if root in target_aliases or not isinstance(call.func, ast.Attribute):
            continue
        indirect_receivers.append({
            "callee_expression": ast.unparse(call.func),
            "root_name": root,
            "receiver_kind": (
                "SELF_ATTRIBUTE_RECEIVER" if root == "self"
                else "NAMED_RECEIVER" if root is not None
                else "COMPUTED_RECEIVER"
            ),
            "call_line": call.lineno,
            "call_column": call.col_offset,
        })
    indirect_receivers.sort(key=lambda item: (
        item["call_line"], item["call_column"], item["callee_expression"]
    ))
    parameter_names = _enclosing_parameter_names(tree, line)
    local_binding_names = _enclosing_local_binding_names(tree, line)
    parameter_warnings = sorted({
        candidate["root_name"] for candidate in alias_candidates
        if candidate["root_name"] in parameter_names
    })
    local_binding_warnings = sorted({
        candidate["root_name"] for candidate in alias_candidates
        if candidate["root_name"] in local_binding_names
    })
    return {
        "target_import_alias_call_candidates": alias_candidates,
        "unmatched_indirect_receiver_call_candidates": indirect_receivers,
        "target_import_alias_parameter_shadowing_warnings": parameter_warnings,
        "target_import_alias_local_binding_warnings": local_binding_warnings,
        "target_import_alias_call_status": (
            "LEXICAL_ALIAS_CALL_CANDIDATE" if alias_candidates
            else "NO_DIRECT_ALIAS_CALL_CANDIDATE"
        ),
        "ast_call_expression_candidates": len(calls),
        "ast_call_line_context": (
            "AST_CALL_SPAN_CANDIDATE" if calls else "NO_AST_CALL_SPAN_CANDIDATE"
        ),
        "enclosing_statement_kind": type(statement).__name__ if statement else None,
    }


def census_b8_callsite_context(
    selection: Mapping[str, Any],
    correlation: Mapping[str, Any],
    source_bytes: Mapping[str, bytes],
) -> dict[str, Any]:
    """Join every selected pair to bounded caller-line AST context.

    The result is deliberately source-only and sample-limited. It cannot
    distinguish a correct orchestration call from misplaced domain logic.
    """
    try:
        identity = selection["source_identity"]
        pairs = [tuple(pair) for pair in selection["pairs"]]
        correlated = {(edge["source_path"], edge["target_path"]): edge
                      for edge in correlation["edges"]}
        sources = {source for source, _ in pairs}
        hashes = selection["source_sha256"]
        if (selection["schema_version"] != "0.1"
                or correlation["schema_version"] != "0.1"
                or not _sealed(selection, "selection_id")
                or not _sealed(correlation, "correlation_id")
                or identity != correlation["source_identity"]
                or correlation["selection_id"] != selection["selection_id"]
                or selection["decision"] != "NOT_EVALUATED"
                or correlation["decision"] != "NOT_EVALUATED"
                or correlation["semantic_ownership"] != "NOT_EVALUATED"
                or correlation["static_import_edge_traversal"] != "NOT_EVALUATED"
                or correlation["public_api_compatibility"] != "NOT_EVALUATED"
                or selection["observed_cross_role_pairs"] != len(pairs)
                or correlation["static_pairs"] != len(pairs)
                or len(pairs) != len(set(pairs))
                or len(correlated) != len(correlation["edges"])
                or set(correlated) != set(pairs)
                or set(source_bytes) != sources
                or set(hashes) != {path for pair in pairs for path in pair}
                or re.fullmatch(r"[0-9a-f]{40}", identity["snapshot_sha"]) is None):
            raise CallsiteContextError("untrusted source or pair denominator")

        trees = {}
        lengths = {}
        for source in sorted(sources):
            raw = source_bytes[source]
            if (not isinstance(raw, bytes)
                    or sha256(raw).hexdigest() != hashes[source]):
                raise CallsiteContextError("source bytes differ from selected hash")
            trees[source] = ast.parse(raw, filename=source)
            lengths[source] = len(raw.splitlines())

        records = []
        for source, target in sorted(pairs):
            edge = correlated[(source, target)]
            target_aliases = _module_level_target_aliases(
                trees[source], source, target,
            )
            qualified_import_prefixes = _unaliased_module_import_prefixes(
                trees[source], target, target_aliases,
            )
            calls = edge["direct_python_calls"]
            witnesses = edge["call_witnesses"]
            if (type(calls) is not int or calls < 0
                    or not isinstance(witnesses, list)
                    or len(witnesses) > calls
                    or (calls > 0 and not witnesses)
                    or edge["witnesses_truncated"] is not (calls > len(witnesses))
                    or edge["semantic_ownership"] != "NOT_EVALUATED"
                    or edge["static_import_edge_traversal"] != "NOT_EVALUATED"
                    or not isinstance(edge["target_role"], str)
                    or not isinstance(edge["source_role"], str)):
                raise CallsiteContextError("untrustworthy call count or role")
            contexts = []
            for witness in witnesses:
                line = witness["caller_line"]
                if (type(line) is not int or not 1 <= line <= lengths[source]
                        or type(witness["callee_first_line"]) is not int
                        or witness["callee_first_line"] < 1
                        or not isinstance(witness["test_id"], str)
                        or not witness["test_id"]):
                    raise CallsiteContextError("caller line or test identity is invalid")
                contexts.append({
                    **witness,
                    **_function_context(trees[source], line),
                    **_callsite_syntax(trees[source], line, target_aliases,
                                       qualified_import_prefixes),
                })
            records.append({
                "source_path": source,
                "target_path": target,
                "source_sha256": hashes[source],
                "source_role": edge["source_role"],
                "target_role": edge["target_role"],
                "declared_policy_direction": edge["declared_policy_direction"],
                "direct_python_calls": calls,
                "sampled_call_witnesses": contexts,
                "witnesses_truncated": edge["witnesses_truncated"],
                "lexical_context_evidence": "AST_FUNCTION_SPAN_CANDIDATE",
                "semantic_ownership": "NOT_EVALUATED",
            })
        observed = sum(item["direct_python_calls"] > 0 for item in records)
        if (observed != correlation["direct_call_observed_pairs"]
                or len(records) - observed != correlation["not_observed_in_sample_pairs"]
                or sum(item["direct_python_calls"] for item in records)
                   != correlation["direct_python_calls"]):
            raise CallsiteContextError("runtime denominator mismatch")
        witness_count = sum(len(item["sampled_call_witnesses"]) for item in records)
        function_count = sum(
            witness["lexical_context"] == "FUNCTION_BODY"
            for item in records for witness in item["sampled_call_witnesses"]
        )
        syntax_candidates = sum(
            witness["ast_call_expression_candidates"] > 0
            for item in records for witness in item["sampled_call_witnesses"]
        )
        import_alias_witnesses = sum(
            bool(w["target_import_alias_call_candidates"])
            for item in records for w in item["sampled_call_witnesses"]
        )
        parameter_warning_count = sum(
            bool(w["target_import_alias_parameter_shadowing_warnings"])
            for item in records for w in item["sampled_call_witnesses"]
        )
        local_binding_warning_count = sum(
            bool(w["target_import_alias_local_binding_warnings"])
            for item in records for w in item["sampled_call_witnesses"]
        )
        indirect_receiver_count = sum(
            not w["target_import_alias_call_candidates"]
            and bool(w["unmatched_indirect_receiver_call_candidates"])
            for item in records for w in item["sampled_call_witnesses"]
        )
        result = {
            "schema_version": "0.1",
            "source_identity": identity,
            "selection_id": selection["selection_id"],
            "correlation_id": correlation["correlation_id"],
            "static_pairs": len(records),
            "direct_call_observed_pairs": observed,
            "not_observed_in_sample_pairs": len(records) - observed,
            "direct_python_calls": correlation["direct_python_calls"],
            "sampled_call_witnesses": witness_count,
            "sampled_function_body_witnesses": function_count,
            "sampled_ast_call_candidate_witnesses": syntax_candidates,
            "sampled_no_ast_call_candidate_witnesses": witness_count - syntax_candidates,
            "sampled_import_alias_call_candidate_witnesses": import_alias_witnesses,
            "sampled_alias_parameter_shadowing_warning_witnesses": parameter_warning_count,
            "sampled_alias_local_binding_warning_witnesses": local_binding_warning_count,
            "sampled_no_direct_alias_with_indirect_receiver_candidate": indirect_receiver_count,
            "sampled_without_direct_import_alias_call_candidate": (
                witness_count - import_alias_witnesses
            ),
            "edges": records,
            "evidence_class": "SOURCE_AST_CALLSITE_CONTEXT_UNATTESTED",
            "semantic_ownership": "NOT_EVALUATED",
            "intentional_orchestration": "NOT_EVALUATED",
            "external_consumers": "NOT_EVALUATED",
            "public_api_compatibility": "NOT_EVALUATED",
            "decision": "NOT_EVALUATED",
            "limitations": [
                "function spans describe lexical context, not responsibility or intent",
                "AST Call spans and statement kinds are source-only candidates, not runtime callee identity",
                "matching a call root to a module-level target import is lexical only; bare dotted imports require a matching qualified callee prefix; alias shadowing and rebinding are unresolved",
                "enclosing function parameter collisions are source-only warnings, not runtime binding proof; lambda, global and nonlocal behavior remain unresolved",
                "function-local bindings include pattern captures and comprehension walrus targets; they are compile-time warnings, not proof of the sampled runtime object; dynamic rebinding remains unresolved",
                "a call through a local variable or re-export may have no direct import alias candidate",
                "indirect receiver shapes are source-only AST syntax, not binding provenance or proof of the sampled callee",
                "a sampled caller line may contain multiple calls or no explicit AST Call",
                "sampled frame calls do not establish import binding or module ownership",
                "bounded call witnesses may omit sites and cannot certify all tests",
                "runtime frame source identity and interpreter-loaded bytes are not independently attested",
                "external consumers, public API and behavior-preserving migration remain NOT_EVALUATED",
            ],
        }
        result["context_id"] = _digest(result)
        return result
    except (KeyError, TypeError, AttributeError, ValueError, SyntaxError) as exc:
        raise CallsiteContextError("invalid source-bound callsite context") from exc
