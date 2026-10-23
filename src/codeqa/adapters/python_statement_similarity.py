"""Extract direct function-body complex statement AST similarities; no execution."""
from __future__ import annotations

import ast
from copy import deepcopy
from hashlib import sha256
import io
import token
import tokenize
from collections.abc import Mapping
from typing import Any

from codeqa.core.statement_similarity import (
    StatementPatternEvidence, StatementPatternProfile, StatementWitness,
)
from .python_snapshot import ParsedSnapshot


_KIND = {
    ast.If: "if", ast.For: "for", ast.AsyncFor: "for",
    ast.While: "while", ast.Try: "try", ast.With: "with",
    ast.AsyncWith: "with", ast.Match: "match",
}


class _NormalizedSyntax(ast.NodeTransformer):
    def __init__(self, profile: StatementPatternProfile) -> None:
        self.profile = profile

    def visit_Name(self, node: ast.Name) -> ast.AST:
        if self.profile.normalize_identifiers:
            return ast.copy_location(ast.Name(id="_IDENT", ctx=node.ctx),node)
        return node

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        if not self.profile.normalize_literals:
            return node
        value = node.value
        if type(value) is str:
            normalized = "_STRING"
        elif type(value) is float:
            normalized = 0.0
        elif type(value) is int:
            normalized = 0
        elif type(value) is complex:
            normalized = 0j
        elif type(value) is bytes:
            normalized = b"_BYTES"
        else:
            normalized = value
        return ast.copy_location(ast.Constant(value=normalized),node)


def _count_tokens(text: str) -> int:
    tokens = tokenize.generate_tokens(io.StringIO(text).readline)
    return sum(1 for item in tokens if item.type not in (
        token.ENDMARKER, tokenize.INDENT, tokenize.DEDENT,
        tokenize.NL, tokenize.NEWLINE, tokenize.COMMENT,
    ))


class _Collector(ast.NodeVisitor):
    def __init__(self, path: str, text: str, digest: str,
                 profile: StatementPatternProfile) -> None:
        self.path = path
        self.text = text
        self.digest = digest
        self.profile = profile
        self.scope: list[str] = []
        self.witnesses: list[StatementWitness] = []
        self.skipped: list[tuple[str, str]] = []

    def visit_ClassDef(self,node:ast.ClassDef)->None:
        self.scope.append(node.name)
        for statement in node.body:
            self.visit(statement)
        self.scope.pop()

    def visit_FunctionDef(self,node:ast.FunctionDef|ast.AsyncFunctionDef)->None:
        qualified = ".".join((*self.scope,node.name))
        owner = f"def::{self.path}::{qualified}@{node.lineno}:{node.col_offset}"
        for stmt in node.body:
            kind = next((label for typ,label in _KIND.items() if isinstance(stmt,typ)),None)
            if kind in self.profile.statement_kinds:
                original = ast.get_source_segment(self.text,stmt)
                if original is None:
                    self.skipped.append((owner, "missing_statement_text"))
                    continue
                count = _count_tokens(original)
                if count < self.profile.min_statement_tokens:
                    self.skipped.append((owner, "below_minimum_statement_tokens"))
                    continue
                normalized = _NormalizedSyntax(self.profile).visit(deepcopy(stmt))
                syntax = ast.dump(normalized,include_attributes=False)
                digest = sha256(syntax.encode("utf-8")).hexdigest()
                self.witnesses.append(StatementWitness(
                    owner_id=owner,path=self.path,line=stmt.lineno,
                    end_line=stmt.end_lineno or stmt.lineno,
                    statement_kind=kind,token_count=count,
                    source_sha256=self.digest,normalized_syntax_sha256=digest,
                ))
        self.scope.append(node.name)
        for statement in node.body:
            self.visit(statement)
        self.scope.pop()

    visit_AsyncFunctionDef=visit_FunctionDef


def extract_python_statement_patterns(
    parsed: ParsedSnapshot,
    sources: Mapping[str,str],
    *,
    snapshot_id: str,
    profile: Mapping[str,Any],
) -> StatementPatternEvidence:
    """Source-only adapter; direct function statements, no substatement mining."""
    cfg = StatementPatternProfile.from_mapping(profile)
    if not isinstance(snapshot_id,str) or not snapshot_id:
        raise ValueError("caller must provide source snapshot identity")
    if not isinstance(sources,Mapping) or set(sources) != (
        set(parsed.analyzed_paths)|{p for p,_ in parsed.unprocessed}):
        raise ValueError("selected source mapping differs from parse inventory")
    if any(not isinstance(s,str) or not isinstance(p,str) or not p
           or p.startswith("/") or "\\" in p or ".." in p.split("/")
           for p,s in sources.items()):
        raise ValueError("invalid or unsafe selected source mapping")
    observations: list[StatementWitness] = []
    skipped: list[tuple[str,str]] = []
    for item in parsed.files:
        if item.tree is None:
            raise ValueError("selected parsed input lacks AST")
        content = sources[item.path]
        digest = sha256(content.encode("utf-8")).hexdigest()
        if digest != item.digest:
            raise ValueError("AST cache/source hash mismatch")
        if any(item.path.startswith(p) for p in cfg.excluded_prefixes):
            skipped.append((item.path, "profile_excluded_path"))
            continue
        visitor = _Collector(item.path,content,digest,cfg)
        visitor.visit(item.tree)
        observations.extend(visitor.witnesses)
        skipped.extend(visitor.skipped)
    return StatementPatternEvidence(
        snapshot_id=snapshot_id,profile_fingerprint=cfg.fingerprint(),
        analyzed_paths=tuple(sorted(parsed.analyzed_paths)),
        unprocessed=tuple(sorted(parsed.unprocessed)),
        source_hashes=tuple(sorted(
            (path,sha256(content.encode("utf-8")).hexdigest())
            for path,content in sources.items()
        )),
        skipped=tuple(sorted(skipped)),
        witnesses=tuple(sorted(observations,key=lambda x: (
            x.path,x.owner_id,x.line,x.normalized_syntax_sha256
        ))),
    )
