"""Opt-in, non-mutating stage-to-rollback obligations for Naming #94.

This is a draft checklist. Neither staged evidence nor this packet can approve
a rename, attest third-party compatibility, or authorize repository changes.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping

from codeqa.evaluation.naming_migration_review import (
    BOUNDARIES, MigrationPlanError, MigrationReviewPacket,
)

_UNVERIFIED = frozenset({"NOT_EVALUATED", "REVIEW_REQUIRED"})


@dataclass(frozen=True, slots=True)
class MigrationStage:
    step: str
    entry_gate: str
    rollback_action: str
    rollback_evidence: str


@dataclass(frozen=True, slots=True)
class StagedMigrationDraft:
    schema_version: str
    baseline_revision: str
    candidate_revision: str
    compatibility_window: str
    stages: tuple[MigrationStage, ...]
    missing_external_boundaries: tuple[str, ...]
    unknowns: tuple[str, ...]
    status: str = "HUMAN_REVIEW_REQUIRED"
    mutation_performed: bool = False

    def to_document(self) -> dict:
        raw = asdict(self)
        raw["stages"] = [asdict(stage) for stage in self.stages]
        raw["missing_external_boundaries"] = list(self.missing_external_boundaries)
        raw["unknowns"] = list(self.unknowns)
        return raw


def prepare_staged_migration_draft(
    packet: MigrationReviewPacket,
    *,
    entry_gates: Mapping[str, str],
    stage_rollbacks: Mapping[str, str],
    rollback_evidence: Mapping[str, str],
) -> StagedMigrationDraft:
    """Require stage-specific rollback obligations without promoting approval."""
    if (not isinstance(packet, MigrationReviewPacket)
            or packet.status != "HUMAN_REVIEW_REQUIRED"
            or packet.mutation_performed is not False
            or packet.schema_version != "0.1-draft"):
        raise MigrationPlanError("only unapproved non-mutating migration packet accepted")

    stages = packet.staged_steps
    if (not stages or any(not isinstance(step, str) or not step.strip() for step in stages)
            or len(set(stages)) != len(stages)
            or not packet.rollback_steps
            or not isinstance(packet.compatibility_window, str)
            or not packet.compatibility_window.strip()):
        raise MigrationPlanError("unique named stages, compatibility window and rollback required")

    mappings = (entry_gates, stage_rollbacks, rollback_evidence)
    if any(not isinstance(mapping, Mapping) or set(mapping) != set(stages)
           for mapping in mappings):
        raise MigrationPlanError("each stage needs an exact entry/rollback/evidence mapping")

    boundary_statuses = dict(packet.boundary_checkpoints)
    if (len(packet.boundary_checkpoints) != len(BOUNDARIES)
            or set(boundary_statuses) != set(BOUNDARIES)
            or set(boundary_statuses.values()) - _UNVERIFIED):
        raise MigrationPlanError("unsupported or promoted external boundary")

    output: list[MigrationStage] = []
    for step in stages:
        entry, action, evidence = (
            entry_gates[step], stage_rollbacks[step], rollback_evidence[step]
        )
        if (entry not in _UNVERIFIED or evidence not in _UNVERIFIED
                or not isinstance(action, str) or not action.strip()
                or action not in packet.rollback_steps):
            raise MigrationPlanError("stage gate or rollback is unreviewed or unbound")
        output.append(MigrationStage(step, entry, action, evidence))

    return StagedMigrationDraft(
        schema_version="0.1-opt-in-draft",
        baseline_revision=packet.baseline_revision,
        candidate_revision=packet.candidate_revision,
        compatibility_window=packet.compatibility_window,
        stages=tuple(output),
        missing_external_boundaries=tuple(sorted(boundary_statuses)),
        unknowns=tuple(sorted(set(packet.unknowns) | {
            "stage_rollback_executability_not_attested",
            "compatibility_window_not_approved",
            "independent_stage_approval_missing",
            "source_proposal_provenance_is_caller_supplied",
        })),
    )
