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


def _callsite_syntax(tree: ast.AST, line: int) -> dict[str, Any]:
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
    return {
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
                    **_callsite_syntax(trees[source], line),
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
