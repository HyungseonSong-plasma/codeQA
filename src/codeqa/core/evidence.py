"""Language-neutral source evidence and cross-report relationship references.

This companion index does not change CCG v0.1 or promote syntactic import
correspondence to proven runtime symbol identity.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class EvidenceFact:
    evidence_id: str
    path: str
    line: int
    column: int
    kind: str
    expression: str


@dataclass(frozen=True, slots=True)
class EvidenceRelation:
    layer: str  # module | symbol | function | definition | inheritance
    source: str
    target: str | None
    target_hint: str | None
    resolution: str
    evidence_id: str | None  # null if multiple facts share one source location


@dataclass(frozen=True, slots=True)
class EvidenceIndex:
    snapshot_id: str
    facts: tuple[EvidenceFact, ...]
    relations: tuple[EvidenceRelation, ...]

    def to_document(self) -> dict[str, Any]:
        return asdict(self)
