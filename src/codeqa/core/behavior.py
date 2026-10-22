"""Versioned, language-neutral responsibility/behavior *syntax* evidence.

A known imported API call is a source observation, not proof of execution,
side effects or ownership. Evaluations of those observations are triage only.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class BehaviorObservation:
    source_node_id: str
    path: str
    line: int
    column: int
    expression: str
    declared_module: str
    declared_symbol: str
    behavior_kind: str
    evidence_id: str
    assurance: str = "DECLARED_API_CALL_SYNTAX_ONLY"

    def to_document(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class BehaviorPlacement:
    source_node_id: str
    path: str
    directory_role: str
    behavior_kind: str
    status: str  # ROLE_CONFLICT_REVIEW | ROLE_COMPATIBLE_OBSERVATION
    evidence_id: str
    reason: str

    def to_document(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ResponsibilityBehaviorReport:
    snapshot_id: str
    policy_id: str
    scanned_call_sites: int
    observations: tuple[BehaviorObservation, ...]
    placements: tuple[BehaviorPlacement, ...]
    excluded_by_reason: tuple[tuple[str, int], ...]
    unassessed_dimensions: tuple[str, ...] = (
        "runtime_execution", "transitive_calls", "dynamic_dispatch",
        "complete_function_responsibility", "scientific_domain_semantics",
    )
    status: str = "NOT_EVALUATED"

    def to_document(self) -> dict[str, Any]:
        def normalize(value: Any) -> Any:
            if isinstance(value, dict):
                return {k: normalize(v) for k, v in value.items()}
            if isinstance(value, (list, tuple)):
                return [normalize(v) for v in value]
            return value
        return normalize(asdict(self))

    def summary_document(self) -> dict[str, Any]:
        from collections import Counter
        return {
            "status": self.status,
            "policy_id": self.policy_id,
            "snapshot_id": self.snapshot_id,
            "scanned_call_sites": self.scanned_call_sites,
            "observed_api_call_sites": len(self.observations),
            "placements_by_status": dict(sorted(
                Counter(p.status for p in self.placements).items()
            )),
            "excluded_by_reason": dict(self.excluded_by_reason),
            "unassessed_dimensions": list(self.unassessed_dimensions),
            "meaning": "SYNTAX_BASED_TRIAGE_NOT_BEHAVIOR_CERTIFICATION",
        }
