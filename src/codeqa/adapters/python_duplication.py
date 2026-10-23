"""Deterministic Python 3.12 function-body token fingerprints.

Only exact normalized token-block matches are assessed. No semantic clones,
near-duplicate promise, execution or repository discovery.
"""
from __future__ import annotations

import ast
from hashlib import sha256
import io
import json
import keyword
import token
import tokenize
from collections.abc import Mapping

from codeqa.core.duplication import TokenBlock, TokenEvidence
from .python_snapshot import ParsedSnapshot


def _profile_digest(profile: Mapping[str, object]) -> str:
    return sha256(json.dumps(profile, sort_keys=True, separators=(",", ":"),
                             allow_nan=False).encode("utf-8")).hexdigest()


class _FunctionCollector(ast.NodeVisitor):
    def __init__(self, path: str) -> None:
        self.path = path
        self.scopes: list[str] = []
        self.functions: list[tuple[ast.FunctionDef | ast.AsyncFunctionDef, str]] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scopes.append(node.name)
        for child in node.body:
            self.visit(child)
        self.scopes.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        qualified = ".".join((*self.scopes, node.name))
        identity = f"def::{self.path}::{qualified}@{node.lineno}:{node.col_offset}"
        self.functions.append((node, identity))
        self.scopes.append(node.name)
        for child in node.body:
            self.visit(child)
        self.scopes.pop()

    visit_AsyncFunctionDef = visit_FunctionDef


def extract_python_token_blocks(
    parsed: ParsedSnapshot,
    sources: Mapping[str, str],
    *,
    snapshot_id: str,
    profile: Mapping[str, object],
) -> TokenEvidence:
    """Pure adapter extraction. Profile shape is also checked by evaluator."""
    if not isinstance(snapshot_id, str) or not snapshot_id:
        raise ValueError("source identity required")
    required = {"profile_id", "schema_version", "min_block_tokens",
                "normalize_identifiers", "normalize_literals", "excluded_prefixes"}
    if (not isinstance(profile, Mapping) or set(profile) != required
            or profile["schema_version"] != "0.1"
            or type(profile["min_block_tokens"]) is not int
            or profile["min_block_tokens"] < 2
            or type(profile["normalize_identifiers"]) is not bool
            or type(profile["normalize_literals"]) is not bool
            or not isinstance(profile["excluded_prefixes"], list)
            or any(not isinstance(s, str) or not s or not s.endswith("/")
                   for s in profile["excluded_prefixes"])):
        raise ValueError("invalid token extraction profile")
    blocks: list[TokenBlock] = []
    skipped: list[tuple[str, str]] = []
    for entry in parsed.files:
        path = entry.path
        if path not in sources or entry.tree is None:
            raise ValueError("missing selected parsed Python source")
        if any(path.startswith(prefix) for prefix in profile["excluded_prefixes"]):
            skipped.append((path, "profile_excluded_path"))
            continue
        collector = _FunctionCollector(path)
        collector.visit(entry.tree)
        stream = tokenize.generate_tokens(io.StringIO(sources[path]).readline)
        toks = [
            t for t in stream
            if t.type not in (
                tokenize.ENCODING, tokenize.ENDMARKER, tokenize.INDENT,
                tokenize.DEDENT, tokenize.NEWLINE, tokenize.NL,
                tokenize.COMMENT,
            )
        ]
        for node, identity in collector.functions:
            if any(isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                   for child in node.body for x in ast.walk(child)
                   if x is not child):
                skipped.append((identity, "nested_scope_overlap_not_evaluated"))
                continue
            if not node.body:
                skipped.append((identity, "empty_function_body"))
                continue
            first, last = node.body[0], node.body[-1]
            start = (first.lineno, first.col_offset)
            stop = (last.end_lineno or last.lineno,
                    last.end_col_offset or last.col_offset)
            selected = [t for t in toks if t.start >= start and t.end <= stop]
            normalized = []
            for t in selected:
                if t.type == token.NAME and profile["normalize_identifiers"] and not keyword.iskeyword(t.string):
                    value = "<NAME>"
                elif t.type == token.NUMBER and profile["normalize_literals"]:
                    value = "<NUMBER>"
                elif t.type == token.STRING and profile["normalize_literals"]:
                    value = "<STRING>"
                else:
                    value = t.string
                normalized.append((t.type, value))
            if len(normalized) < profile["min_block_tokens"]:
                skipped.append((identity, "below_minimum_tokens"))
                continue
            digest = sha256(json.dumps(normalized, ensure_ascii=False,
                                       separators=(",", ":")).encode("utf-8")).hexdigest()
            blocks.append(TokenBlock(
                identity, path, first.lineno, stop[0], len(normalized), digest,
            ))
    return TokenEvidence(
        snapshot_id=snapshot_id,
        profile_fingerprint=_profile_digest(profile),
        analyzed_paths=tuple(sorted(f.path for f in parsed.files)),
        unprocessed=tuple(sorted(parsed.unprocessed)),
        blocks=tuple(sorted(blocks, key=lambda b: b.node_id)),
        skipped=tuple(sorted(skipped)),
    )
