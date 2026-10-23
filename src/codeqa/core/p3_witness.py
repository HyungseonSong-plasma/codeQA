"""Immutable, language-neutral source-backed function-call witnesses for P3 review."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class P3CallWitness:
    node_id: str
    owner: str
    path: str
    line: int
    expression: str
    callee_spelling: str
    syntax_sha256: str


@dataclass(frozen=True, slots=True)
class P3CallEvidence:
    producer: str
    source_sha256: tuple[tuple[str, str], ...]
    analyzed_paths: tuple[str, ...]
    unprocessed: tuple[tuple[str, str], ...]
    calls: tuple[tuple[str, tuple[P3CallWitness, ...]], ...]
