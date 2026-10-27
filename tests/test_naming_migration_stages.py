"""Negative controls for #94's stage-to-rollback draft (never a safe-rename Gate)."""
from __future__ import annotations

from dataclasses import replace
import unittest

from codeqa.evaluation.naming_migration_review import (
    BOUNDARIES, MigrationPlanError, MigrationReviewPacket,
)
from codeqa.evaluation.naming_migration_stages import (
    prepare_staged_migration_draft,
)


def packet() -> MigrationReviewPacket:
    return MigrationReviewPacket(
        schema_version="0.1-draft",
        baseline_revision="git:owner/repo@" + "a" * 40,
        candidate_revision="git:owner/repo@" + "b" * 40,
        profile_fingerprint="c" * 64,
        proposal_verdict="UNVERIFIED_PROPOSAL",
        selected_before_paths=("src/a.py",),
        selected_after_paths=("src/a.py",),
        compatibility_window="DRAFT: no production window approved",
        staged_steps=("prepare candidate", "trial candidate"),
        rollback_steps=("restore exact prior artifact",),
        boundary_checkpoints=tuple((b, "NOT_EVALUATED") for b in BOUNDARIES),
        unknowns=("source_proposal_binding_not_evaluated",),
    )


class StageDraftTests(unittest.TestCase):
    def make(self, **overrides):
        params = dict(
            entry_gates={
                "prepare candidate": "REVIEW_REQUIRED",
                "trial candidate": "NOT_EVALUATED",
            },
            stage_rollbacks={
                "prepare candidate": "restore exact prior artifact",
                "trial candidate": "restore exact prior artifact",
            },
            rollback_evidence={
                "prepare candidate": "NOT_EVALUATED",
                "trial candidate": "NOT_EVALUATED",
            },
        )
        params.update(overrides)
        return prepare_staged_migration_draft(packet(), **params)

    def test_exact_per_stage_draft_never_grants_approval(self):
        draft = self.make()
        self.assertEqual(len(draft.stages), 2)
        self.assertEqual(draft.status, "HUMAN_REVIEW_REQUIRED")
        self.assertFalse(draft.mutation_performed)
        self.assertEqual(set(draft.missing_external_boundaries), set(BOUNDARIES))
        self.assertIn("independent_stage_approval_missing", draft.unknowns)
        self.assertIn("source_proposal_binding_not_evaluated", draft.unknowns)
        self.assertEqual(len(draft.to_document()["stages"]), 2)

    def test_missing_stage_rollback_rejected(self):
        with self.assertRaises(MigrationPlanError):
            self.make(stage_rollbacks={"prepare candidate": "restore exact prior artifact"})

    def test_unlisted_rollback_action_rejected(self):
        bad = {
            "prepare candidate": "wipe production database",
            "trial candidate": "restore exact prior artifact",
        }
        with self.assertRaises(MigrationPlanError):
            self.make(stage_rollbacks=bad)

    def test_missing_stage_entry_gate_rejected(self):
        with self.assertRaises(MigrationPlanError):
            self.make(entry_gates={"prepare candidate": "REVIEW_REQUIRED"})

    def test_self_approved_stage_cannot_pass(self):
        for bad in ("APPROVED", "PASS", "ALLOW"):
            with self.subTest(bad=bad), self.assertRaises(MigrationPlanError):
                self.make(entry_gates={
                    "prepare candidate": bad,
                    "trial candidate": "NOT_EVALUATED",
                })

    def test_forged_rollback_evidence_cannot_pass(self):
        with self.assertRaises(MigrationPlanError):
            self.make(rollback_evidence={
                "prepare candidate": "VERIFIED",
                "trial candidate": "NOT_EVALUATED",
            })

    def test_duplicate_stage_names_cannot_hide_mapping(self):
        with self.assertRaises(MigrationPlanError):
            prepare_staged_migration_draft(
                replace(packet(), staged_steps=("trial candidate", "trial candidate")),
                entry_gates={"trial candidate": "NOT_EVALUATED"},
                stage_rollbacks={"trial candidate": "restore exact prior artifact"},
                rollback_evidence={"trial candidate": "NOT_EVALUATED"},
            )

    def test_forged_packet_approval_or_mutation_rejected(self):
        for forged in (
            replace(packet(), status="APPROVED"),
            replace(packet(), mutation_performed=True),
        ):
            with self.subTest(forged=forged.status), self.assertRaises(MigrationPlanError):
                prepare_staged_migration_draft(
                    forged,
                    entry_gates={s: "NOT_EVALUATED" for s in forged.staged_steps},
                    stage_rollbacks={s: "restore exact prior artifact" for s in forged.staged_steps},
                    rollback_evidence={s: "NOT_EVALUATED" for s in forged.staged_steps},
                )

    def test_missing_or_promoted_boundary_rejected(self):
        for boundaries in (
            tuple((b, "PASS") for b in BOUNDARIES),
            (("public_api", "NOT_EVALUATED"),),
        ):
            p = replace(packet(), boundary_checkpoints=boundaries)
            with self.subTest(boundaries=boundaries), self.assertRaises(MigrationPlanError):
                prepare_staged_migration_draft(
                    p,
                    entry_gates={s: "NOT_EVALUATED" for s in p.staged_steps},
                    stage_rollbacks={s: "restore exact prior artifact" for s in p.staged_steps},
                    rollback_evidence={s: "NOT_EVALUATED" for s in p.staged_steps},
                )


if __name__ == "__main__":
    unittest.main()
