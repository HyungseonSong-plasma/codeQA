"""Official Naming v0.5 adoption proposal: source attestation, not approval."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import unittest

from codeqa.core.naming_official_adoption_v05 import (
    NamingAdoptionError, assess_official_naming_adoption_proposal,
)
from codeqa.infrastructure.git import GitReader
from codeqa.pipeline.naming_official_adoption_v05 import (
    verify_pinned_naming_adoption_proposal,
)

ROOT = Path(__file__).resolve().parents[1]
PROFILE = (ROOT / "profiles/codeqa-python-naming-scoped-v0.5-proposal.json")


class OfficialNamingV05ProposalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = json.loads(PROFILE.read_text(encoding="utf-8"))
        cls.source = GitReader(ROOT).read_file(
            cls.policy["source_witness"]["commit"],
            cls.policy["source_witness"]["path"],
        )
        cls.result = verify_pinned_naming_adoption_proposal(ROOT, cls.policy)

    def test_exact_source_and_owner_decision_ready_only(self):
        result = self.result
        self.assertEqual(result["verified_source_sites"], 1)
        self.assertEqual(result["source_classification"], "FIELD_CANDIDATE")
        self.assertEqual(
            result["readiness"], "SOURCE_EVIDENCE_READY_OWNER_DECISION_REQUIRED")
        self.assertEqual(result["source_sha256"], sha256(self.source).hexdigest())
        self.assertEqual(len(result["approved_policy_principles"]), 4)
        self.assertFalse(result["official_policy_adopted"])
        self.assertFalse(result["domain_meaning_verified"])
        self.assertFalse(result["automatic_rename_authorized"])
        self.assertEqual(result["external_compatibility"], "UNKNOWN")
        print("NAMING_OFFICIAL_ADOPTION proposal=v0.5 exact_ast_sites=1 "
              "source=VERIFIED owner_decision=REQUIRED adopted=false "
              "rename=false external=UNKNOWN")

    def test_policy_principles_are_not_extrapolated_into_semantics(self):
        self.assertEqual(self.policy["review_interval_days"], 180)
        self.assertIsNone(self.policy["adoption_date"])
        self.assertIsNone(self.policy["next_review_date"])
        self.assertEqual(self.policy["status"], "PENDING_FINAL_OWNER_APPROVAL")
        self.assertEqual(self.policy["terms"][0]["path_scopes"], [])
        self.assertEqual(self.policy["terms"][1]["path_scopes"],
                         ["src/codeqa/core/complexity.py"])
        self.assertEqual(self.result["time_step_source_scope"], "NOT_ADOPTED")
        self.assertEqual(self.result["node_id_alias_semantics"],
                         "NO_EQUIVALENCE_INFERRED")
        self.assertEqual(self.policy["exceptions"], [])
        self.assertEqual(self.policy["external_reference_issue"], 147)
        self.assertTrue(self.result["default_v01_unchanged"])

    def test_determinism_and_independent_git_provenance(self):
        expected = assess_official_naming_adoption_proposal(
            self.policy, source=self.source)
        self.assertEqual(self.result, expected)
        self.assertEqual(verify_pinned_naming_adoption_proposal(
            ROOT, deepcopy(self.policy)), expected)

    def test_source_change_or_ast_absence_fails_closed(self):
        altered = self.source.replace(b"node_id: str", b"node_id: int", 1)
        self.assertNotEqual(altered, self.source)
        with self.assertRaises(NamingAdoptionError):
            assess_official_naming_adoption_proposal(self.policy, source=altered)
        with self.assertRaises(NamingAdoptionError):
            assess_official_naming_adoption_proposal(
                self.policy, source=b"# node_id\nnode_id = 'str'\n")

    def test_mutated_git_source_attestations_fail_closed(self):
        for key, value in (
            ("commit", "0"*40), ("tree_sha", "0"*40),
            ("git_blob_sha", "0"*40),
            ("path", "src/codeqa/other.py"),
        ):
            with self.subTest(key=key):
                p = deepcopy(self.policy)
                p["source_witness"][key] = value
                with self.assertRaises(NamingAdoptionError):
                    verify_pinned_naming_adoption_proposal(ROOT, p)

    def test_fake_adoption_decision_and_rename_authority_rejected(self):
        mutations = (
            lambda p: p.update(status="ADOPTED"),
            lambda p: p.update(owner_decision="APPROVED"),
            lambda p: p.update(adoption_date="2026-10-26"),
            lambda p: p.update(next_review_date="2027-04-24"),
            lambda p: p.update(semantic_glossary_pass=True),
            lambda p: p.update(automatic_rename_authorized=True),
            lambda p: p.update(default_v01_unchanged=False),
            lambda p: p.update(signed_by="project-owner"),
            lambda p: p.update(review_interval_days=0),
        )
        for i, f in enumerate(mutations):
            with self.subTest(i=i):
                p = deepcopy(self.policy)
                f(p)
                with self.assertRaises(NamingAdoptionError):
                    assess_official_naming_adoption_proposal(p, source=self.source)

    def test_broad_scopes_and_false_synonym_equivalence_rejected(self):
        mods = (
            lambda p: p["terms"][0].update(path_scopes=["src/codeqa"]),
            lambda p: p["terms"][1].update(path_scopes=["src/codeqa"]),
            lambda p: p["terms"][1].update(noncanonical_spelling="node"),
            lambda p: p["terms"][0].update(meaning="VERIFIED"),
            lambda p: p["declaration_scope"].update(path="src/codeqa"),
            lambda p: p["declaration_scope"].update(owner="OtherClass"),
            lambda p: p["declaration_scope"].update(role_candidate="CERTIFIED"),
            lambda p: p["declaration_scope"].update(line=11),
            lambda p: p["declaration_scope"].update(owner_role_approval="APPROVED"),
        )
        for i, change in enumerate(mods):
            with self.subTest(i=i):
                p = deepcopy(self.policy)
                change(p)
                with self.assertRaises(NamingAdoptionError):
                    assess_official_naming_adoption_proposal(p, source=self.source)

    def test_no_unowned_or_expiring_implicit_exceptions(self):
        for exceptions in (
            [{"reason": "legacy"}],
            [{"owner": "codeqa", "expires_on": "2027-01-01"}],
        ):
            with self.subTest(exceptions=exceptions):
                p = deepcopy(self.policy)
                p["exceptions"] = exceptions
                with self.assertRaises(NamingAdoptionError):
                    assess_official_naming_adoption_proposal(p, source=self.source)


if __name__ == "__main__":
    unittest.main()
