"""No fabricated human approval or safe rename from lexical evidence (#94)."""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import unittest

from codeqa.evaluation.naming_migration_review import (
    BOUNDARIES, MigrationPlanError, prepare_migration_review_packet,
)
from codeqa.evaluation.naming_rename_impact_v02 import (
    SymbolWitness, assess_rename_impact,
)


BEFORE = "git:owner/repo@" + "a" * 40
AFTER = "git:owner/repo@" + "b" * 40
SOURCE1 = "def OldName(): return 1\n"
SOURCE2 = "def new_name(): return 1\n"


class MigrationReviewTests(unittest.TestCase):
    def make(self, **changes):
        old = {"src/a.py": SOURCE1}
        new = {"src/a.py": SOURCE2}
        proposal = assess_rename_impact(
            revision=BEFORE, sources=old,
            symbol=SymbolWitness(
                "src/a.py", "OldName", "function", 1,
                sha256(SOURCE1.encode()).hexdigest(), "internal", True,
            ),
            proposed_name="new_name", references=(),
            source_selection_complete=True, policy_id="repo-naming-v0.2",
        )
        params = dict(
            baseline_revision=BEFORE, candidate_revision=AFTER,
            before_sources=old, after_sources=new,
            before_sha256={"src/a.py": sha256(SOURCE1.encode()).hexdigest()},
            after_sha256={"src/a.py": sha256(SOURCE2.encode()).hexdigest()},
            profile_fingerprint="c" * 64, proposal=proposal,
            path_renames={}, source_selection_complete=True,
            compatibility_window="2026-Q4: two supported API versions",
            staged_steps=("shadow deploy", "independent compatibility review"),
            rollback_steps=("restore previous artifact SHA",),
            boundary_checkpoints={name: "NOT_EVALUATED" for name in BOUNDARIES},
        )
        params.update(changes)
        return prepare_migration_review_packet(**params)

    def test_real_source_packet_is_always_human_review_required(self):
        report = self.make()
        self.assertEqual(report.status, "HUMAN_REVIEW_REQUIRED")
        self.assertFalse(report.mutation_performed)
        self.assertIn("independent_human_migration_approval_missing", report.unknowns)
        self.assertIn("unverified_contract:db_physical", report.unknowns)

    def test_forged_source_hash_rejected(self):
        with self.assertRaises(MigrationPlanError):
            self.make(after_sha256={"src/a.py": "0" * 64})

    def test_same_revision_or_cross_repository_rejected(self):
        for after in (BEFORE, "git:other/repo@" + "b" * 40):
            with self.subTest(after=after), self.assertRaises(MigrationPlanError):
                self.make(candidate_revision=after)

    def test_forged_human_approval_rejected(self):
        checks = {name: "NOT_EVALUATED" for name in BOUNDARIES}
        checks["public_api"] = "APPROVED"
        with self.assertRaises(MigrationPlanError):
            self.make(boundary_checkpoints=checks)

    def test_missing_rollback_rejected(self):
        with self.assertRaises(MigrationPlanError):
            self.make(rollback_steps=())

    def test_incomplete_selection_is_explicit_unknown(self):
        report = self.make(source_selection_complete=False)
        self.assertIn("incomplete_source_selection", report.unknowns)

    def test_changed_population_is_not_silently_comparable(self):
        report = self.make(after_sources={"src/b.py": SOURCE2},
                           after_sha256={"src/b.py": sha256(SOURCE2.encode()).hexdigest()})
        self.assertIn("selected_source_path_coverage_drift", report.unknowns)

    def test_unchanged_source_bytes_do_not_certify_rename(self):
        report = self.make(
            after_sources={"src/a.py": SOURCE1},
            after_sha256={"src/a.py": sha256(SOURCE1.encode()).hexdigest()},
        )
        self.assertIn("unchanged_source_bytes_do_not_prove_rename", report.unknowns)
        self.assertEqual(report.status, "HUMAN_REVIEW_REQUIRED")

    def test_incomplete_contract_checkpoint_inventory_rejected(self):
        with self.assertRaises(MigrationPlanError):
            self.make(boundary_checkpoints={"public_api": "NOT_EVALUATED"})

    def test_invalid_or_ambiguous_file_rename_rejected(self):
        with self.assertRaises(MigrationPlanError):
            self.make(path_renames={"src/a.py": "src/a.py"})

    def test_invalid_unverified_proposal_rejected(self):
        report = self.make()
        old = {"src/a.py": SOURCE1}
        proposal = assess_rename_impact(
            revision=BEFORE, sources=old,
            symbol=SymbolWitness(
                "src/a.py", "OldName", "function", 1,
                sha256(SOURCE1.encode()).hexdigest(), "internal", True,
            ),
            proposed_name="new_name", references=(),
            source_selection_complete=True, policy_id="repo-naming-v0.2",
        )
        with self.assertRaises(MigrationPlanError):
            self.make(proposal=replace(proposal, migration_plan="AUTO_APPROVED"))


if __name__ == "__main__":
    unittest.main()
