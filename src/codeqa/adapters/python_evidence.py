"""Build shared stable evidence references from an already parsed snapshot."""
from __future__ import annotations

import ast
from collections import defaultdict
from hashlib import sha256
import json

from codeqa.core import Graph, DependencyGraph
from codeqa.core.evidence import EvidenceFact, EvidenceIndex, EvidenceRelation
from .python_snapshot import ParsedSnapshot


def _facts(parsed: ParsedSnapshot) -> tuple[EvidenceFact, ...]:
    observed: list[EvidenceFact] = []
    for item in parsed.files:
        assert item.tree is not None
        for node in ast.walk(item.tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                kind, expression = "import", ast.unparse(node)
            elif isinstance(node, ast.Call):
                kind, expression = "call", ast.unparse(node.func)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                kind, expression = "definition", node.name
            else:
                continue
            body = json.dumps(
                (item.path, node.lineno, node.col_offset, kind, expression),
                separators=(",", ":"), ensure_ascii=False,
            )
            observed.append(EvidenceFact(
                evidence_id="py:" + sha256(body.encode("utf-8")).hexdigest(),
                path=item.path, line=node.lineno, column=node.col_offset,
                kind=kind, expression=expression,
            ))
    return tuple(sorted(observed, key=lambda f: (
        f.path, f.line, f.column, f.kind, f.expression,
    )))


def build_python_evidence(
    parsed: ParsedSnapshot, *, graph: Graph, dependencies: DependencyGraph,
) -> EvidenceIndex:
    """Link module/symbol/call views only through unambiguous syntax witnesses.

    CCG v0.1 can omit columns; two statements on one source line must not
    be assigned a guessed witness. Their evidence_id remains null.
    """
    if graph.snapshot.id != dependencies.snapshot_id:
        raise ValueError("evidence views must share an immutable snapshot ID")
    facts = _facts(parsed)
    by_location: dict[tuple[str, int, str], set[str]] = defaultdict(set)
    for fact in facts:
        by_location[(fact.path, fact.line, fact.kind)].add(fact.evidence_id)

    def witness(path: str, line: int, kind: str) -> str | None:
        candidates = by_location.get((path, line, kind), set())
        return next(iter(candidates)) if len(candidates) == 1 else None

    relations: list[EvidenceRelation] = []
    for edge in graph.edges:
        if edge.kind not in ("defines", "calls", "imports", "inherits"):
            continue
        loc = edge.location
        if loc is None:
            ref = None
        else:
            kind = "definition" if edge.kind == "defines" else (
                "call" if edge.kind == "calls" else "import"
                if edge.kind == "imports" else "inheritance"
            )
            ref = witness(loc.path, loc.start_line, kind)
        layer = {
            "defines": "definition", "calls": "function",
            "imports": "symbol", "inherits": "inheritance",
        }[edge.kind]
        relations.append(EvidenceRelation(
            layer=layer, source=edge.source, target=edge.target,
            target_hint=edge.target_hint,
            resolution="ccg_" + edge.resolution,
            evidence_id=ref,
        ))

    for edge in dependencies.edges:
        relations.append(EvidenceRelation(
            layer="module", source=edge.source_path, target=edge.target_path,
            target_hint=None, resolution="static_module_path",
            evidence_id=witness(edge.source_path, edge.line, "import"),
        ))
    for unknown in dependencies.unknown:
        relations.append(EvidenceRelation(
            layer="module", source=unknown.source_path, target=None,
            target_hint=unknown.expression,
            resolution="unknown_" + unknown.reason,
            evidence_id=witness(unknown.source_path, unknown.line, "import")
            if unknown.reason != "dynamic_import" else
            witness(unknown.source_path, unknown.line, "call"),
        ))
    return EvidenceIndex(
        snapshot_id=graph.snapshot.id,
        facts=facts,
        relations=tuple(sorted(relations, key=lambda v: (
            v.layer, v.source, v.target or "", v.target_hint or "",
            v.resolution, v.evidence_id or "",
        ))),
    )
