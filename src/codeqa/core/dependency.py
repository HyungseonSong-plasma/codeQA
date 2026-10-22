"""Language-independent observations about static source dependency relations.

Separate from the CCG v0.1 exchange schema and mechanical QA verdicts.
These records represent static correspondence inside the supplied snapshot;
they do not claim import execution, runtime dispatch or exhaustive impact.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class StaticDependency:
    source_path: str
    target_path: str
    line: int
    expression: str
    execution: str  # top_level | conditional_or_deferred


@dataclass(frozen=True, slots=True)
class UnknownDependency:
    source_path: str
    line: int
    expression: str
    reason: str  # outside_snapshot | ambiguous | invalid_relative | dynamic_import


@dataclass(frozen=True, slots=True)
class DependencyGraph:
    snapshot_id: str
    analyzed_paths: tuple[str, ...]
    unprocessed_paths: tuple[str, ...]
    edges: tuple[StaticDependency, ...]
    unknown: tuple[UnknownDependency, ...]

    def to_document(self) -> dict[str, Any]:
        return asdict(self)
