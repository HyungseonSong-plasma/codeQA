"""Static cross-file declaration candidates, not runtime call resolution.

Immutable observations express an unambiguous plain function declaration
reached via explicit import syntax. They neither change CCG edge resolutions
nor establish what object actually runs (monkey-patching is not modeled).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class SymbolCallCandidate:
    source_path: str
    source_node_id: str
    call_line: int
    call_column: int
    call_expression: str
    import_binding: str
    import_kind: str
    imported_module: str
    target_path: str
    target_node_id: str
    evidence_id: str
    assurance: str = "STATIC_DECLARATION_CANDIDATE_NOT_RUNTIME_TARGET"

    def to_document(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SymbolCallReport:
    snapshot_id: str
    scanned_call_sites: int
    candidates: tuple[SymbolCallCandidate, ...]
    excluded_by_reason: tuple[tuple[str, int], ...]
    assurance: str = "STATIC_DECLARATIONS_ONLY"

    def to_document(self) -> dict[str, Any]:
        return asdict(self)
