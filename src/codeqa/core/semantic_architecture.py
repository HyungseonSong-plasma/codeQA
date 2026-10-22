"""Immutable, language-neutral semantic architecture projection v0.1.

An ontology relation is explicitly marked as a POLICY_DECLARATION, a
SOURCE_OBSERVATION, or a CCG observation. None proves runtime dispatch or
domain behavior. This is a companion to CCG 0.1, not an extension of it.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


ENTITY_KINDS = frozenset({
    "DirectoryRole", "Responsibility", "SourceFile", "CodeEntity",
    "DependencyObservation", "Evidence", "Constraint",
})
RELATION_KINDS = frozenset({
    "owns_responsibility", "contains", "belongs_to_role", "defines",
    "calls", "imports", "prohibited_dependency", "observed_in",
    "observed_target", "supported_by", "constrains_source", "constrains_target",
})
ASSURANCES = frozenset({
    "POLICY_DECLARATION", "PATH_OBSERVATION", "CCG_OBSERVATION",
    "CCG_RESOLVED_LOCAL", "STATIC_MODULE_PATH", "SOURCE_WITNESS",
})


@dataclass(frozen=True, slots=True)
class SemanticEntity:
    id: str
    kind: str
    label: str


@dataclass(frozen=True, slots=True)
class SemanticRelation:
    source: str
    kind: str
    target: str
    assurance: str
    evidence_id: str | None = None


@dataclass(frozen=True, slots=True)
class SemanticAssessment:
    status: str  # VIOLATION | REVIEW_REQUIRED | NOT_EVALUATED
    code: str
    source: str
    target: str | None
    reason: str
    evidence_id: str | None = None


@dataclass(frozen=True, slots=True)
class SemanticArchitecture:
    schema_version: str
    snapshot_id: str
    policy_id: str
    entities: tuple[SemanticEntity, ...]
    relations: tuple[SemanticRelation, ...]
    assessments: tuple[SemanticAssessment, ...]
    unassessed_dimensions: tuple[str, ...]
    status: str

    def to_document(self) -> dict[str, Any]:
        """Produce schema-valid JSON values, including lists instead of tuples."""
        def normalize(value: Any) -> Any:
            if isinstance(value, dict):
                return {key: normalize(item) for key, item in value.items()}
            if isinstance(value, (tuple, list)):
                return [normalize(item) for item in value]
            return value
        return normalize(asdict(self))

    def summary_document(self) -> dict[str, Any]:
        from collections import Counter
        return {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "snapshot_id": self.snapshot_id,
            "status": self.status,
            "entity_kinds": dict(sorted(Counter(e.kind for e in self.entities).items())),
            "relation_kinds": dict(sorted(Counter(e.kind for e in self.relations).items())),
            "assessment_codes": dict(sorted(Counter(e.code for e in self.assessments).items())),
            "unassessed_dimensions": list(self.unassessed_dimensions),
        }
