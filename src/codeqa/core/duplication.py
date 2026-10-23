"""Language-neutral, immutable source-backed token-block evidence for P6 review."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class TokenBlock:
    node_id: str
    path: str
    start_line: int
    end_line: int
    token_count: int
    fingerprint: str
    producer: str = "python-token-block-v0.1"


@dataclass(frozen=True, slots=True)
class TokenEvidence:
    snapshot_id: str
    profile_fingerprint: str
    analyzed_paths: tuple[str, ...]
    unprocessed: tuple[tuple[str, str], ...]
    blocks: tuple[TokenBlock, ...]
    skipped: tuple[tuple[str, str], ...]
    interpretation: str = "SYNTAX_TOKENS_NOT_BEHAVIOR"

    def to_document(self) -> dict[str, Any]:
        return asdict(self)
