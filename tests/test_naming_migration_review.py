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


    def test_proposal_source_and_policy_fingerprints_remain_unattested(self):
        packet = self.make()
        self.assertIn("proposal_source_manifest_binding_not_evaluated", packet.unknowns)
        self.assertIn("proposal_policy_fingerprint_not_attested", packet.unknowns)
        self.assertEqual(packet.status, "HUMAN_REVIEW_REQUIRED")

    def test_extra_selected_source_not_covered_by_proposal_is_explicit_unknown(self):
        before = {"src/a.py": SOURCE1, "src/extra.py": "x = 1\\n"}
        digests = {path: sha256(data.encode()).hexdigest() for path, data in before.items()}
        packet = self.make(before_sources=before, before_sha256=digests)
        self.assertIn("proposal_source_selection_differs", packet.unknowns)
        self.assertFalse(packet.mutation_performed)

    def test_string_claim_of_complete_selection_is_not_a_boolean(self):
        with self.assertRaises(MigrationPlanError):
            self.make(source_selection_complete="false")



    def test_forged_proposal_name_rejected_against_exact_baseline(self):
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
        with self.assertRaisesRegex(MigrationPlanError, "old identifier absent"):
            self.make(proposal=replace(proposal, old_name="ForgedMissingName"))

    def test_identical_file_move_does_not_prove_symbol_rename(self):
        after = {"src/moved.py": SOURCE1}
        packet = self.make(
            after_sources=after,
            after_sha256={"src/moved.py": sha256(SOURCE1.encode()).hexdigest()},
            path_renames={"src/a.py": "src/moved.py"},
        )
        self.assertIn("byte_identical_file_move_not_symbol_rename", packet.unknowns)
        self.assertIn("proposed_identifier_not_lexically_observed_in_candidate",
                      packet.unknowns)
        self.assertEqual(packet.status, "HUMAN_REVIEW_REQUIRED")

    def test_old_identifier_still_observed_after_change_is_unknown(self):
        after = {"src/a.py": SOURCE1 + SOURCE2}
        packet = self.make(
            after_sources=after,
            after_sha256={"src/a.py": sha256(after["src/a.py"].encode()).hexdigest()},
        )
        self.assertIn("old_identifier_still_lexically_observed_in_candidate",
                      packet.unknowns)
        self.assertIn("lexical_presence_not_source_binding_proof", packet.unknowns)

    def test_comment_and_string_only_old_identifier_is_rejected(self):
        source = SOURCE1 + '# GhostName\nlabel = "GhostName"\n'
        old = {"src/a.py": source}
        proposal = assess_rename_impact(
            revision=BEFORE, sources=old,
            symbol=SymbolWitness(
                "src/a.py", "OldName", "function", 1,
                sha256(source.encode()).hexdigest(), "internal", True,
            ),
            proposed_name="new_name", references=(),
            source_selection_complete=True, policy_id="repo-naming-v0.2",
        )
        with self.assertRaisesRegex(MigrationPlanError, "old identifier absent"):
            self.make(
                before_sources=old,
                before_sha256={"src/a.py": sha256(source.encode()).hexdigest()},
                proposal=replace(proposal, old_name="GhostName"),
            )

    def test_incomplete_python_token_stream_cannot_certify_old_name(self):
        malformed = SOURCE1 + "'''unterminated"
        old = {"src/a.py": malformed}
        # The proposal remains from a distinct, valid source; a revision
        # string alone cannot authenticate its source-manifest binding.
        valid = {"src/a.py": SOURCE1}
        proposal = assess_rename_impact(
            revision=BEFORE, sources=valid,
            symbol=SymbolWitness(
                "src/a.py", "OldName", "function", 1,
                sha256(SOURCE1.encode()).hexdigest(), "internal", True,
            ),
            proposed_name="new_name", references=(),
            source_selection_complete=True, policy_id="repo-naming-v0.2",
        )
        with self.assertRaisesRegex(MigrationPlanError, "old identifier absent"):
            self.make(
                before_sources=old,
                before_sha256={"src/a.py": sha256(malformed.encode()).hexdigest()},
                proposal=proposal,
            )

    def test_candidate_name_only_in_string_or_comment_remains_unknown(self):
        after = 'def unrelated(): return "new_name"\n# new_name\n'
        packet = self.make(
            after_sources={"src/a.py": after},
            after_sha256={"src/a.py": sha256(after.encode()).hexdigest()},
        )
        self.assertIn("proposed_identifier_not_lexically_observed_in_candidate",
                      packet.unknowns)
        self.assertEqual(packet.status, "HUMAN_REVIEW_REQUIRED")

    def test_reference_name_token_is_not_mistaken_for_semantic_binding(self):
        after = "alias = new_name\n"
        packet = self.make(
            after_sources={"src/a.py": after},
            after_sha256={"src/a.py": sha256(after.encode()).hexdigest()},
        )
        self.assertNotIn("proposed_identifier_not_lexically_observed_in_candidate",
                         packet.unknowns)
        self.assertIn("lexical_presence_not_source_binding_proof", packet.unknowns)

    def test_non_python_embedded_substring_is_not_exact_identifier(self):
        before = {
            "src/a.py": "def unrelated(): return 1\\n",
            "src/native.cpp": "void PrefixOldNameSuffix();\\n",
        }
        with self.assertRaisesRegex(MigrationPlanError, "old identifier absent"):
            self.make(
                before_sources=before,
                before_sha256={p: sha256(v.encode()).hexdigest()
                               for p, v in before.items()},
            )

    def test_non_python_source_is_explicitly_lexical_only(self):
        before = {"src/a.py": SOURCE1, "src/native.cpp": "void OldName();\n"}
        after = {"src/a.py": SOURCE2, "src/native.cpp": "void new_name();\n"}
        packet = self.make(
            before_sources=before, after_sources=after,
            before_sha256={p: sha256(v.encode()).hexdigest() for p, v in before.items()},
            after_sha256={p: sha256(v.encode()).hexdigest() for p, v in after.items()},
        )
        self.assertIn("non_python_lexical_presence_only", packet.unknowns)
        self.assertEqual(packet.status, "HUMAN_REVIEW_REQUIRED")

    def test_missing_proposed_name_in_candidate_is_not_approval(self):
        after = {"src/a.py": "def unrelated(): return 0\\n"}
        packet = self.make(
            after_sources=after,
            after_sha256={"src/a.py": sha256(after["src/a.py"].encode()).hexdigest()},
        )
        self.assertIn("proposed_identifier_not_lexically_observed_in_candidate",
                      packet.unknowns)
        self.assertFalse(packet.mutation_performed)


if __name__ == "__main__":
    unittest.main()
