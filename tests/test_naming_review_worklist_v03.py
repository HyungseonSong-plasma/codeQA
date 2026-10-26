"""Regression and adversarial controls for #91 human review claim boundaries."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from codeqa.core.naming_review_worklist_v03 import (
    NamingReviewWorklistError, assess_review_worklist, build_review_worklist,
)


class NamingReviewWorklistV03Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        path = (Path(__file__).resolve().parents[1]
                / "fixtures/naming-governance/codeqa-ast-review-v03-proposal.json")
        cls.proposal = json.loads(path.read_text(encoding="utf-8"))

    def setUp(self) -> None:
        self.worklist = build_review_worklist(self.proposal)

    def _fill(self, row: dict) -> None:
        row["decision"] = ("NEGATIVE_CONFIRMED" if row["group"] ==
                           "negative_control_candidates" else "OBSERVATION_CONFIRMED")
        row["reviewer_login"] = "reviewer-example"
        # Deliberately only a syntactically plausible URL: NEVER an authenticated review.
        row["review_comment_url"] = (
            "https://github.com/HyungseonSong-plasma/codeQA/issues/91"
            "#issuecomment-123456789"
        )
        row["rationale"] = "Example claim; independent review still required"

    def test_50_sites_from_pinned_unsigned_candidate_packet(self):
        self.assertEqual(len(self.worklist["rows"]), 50)
        self.assertEqual(
            [sum(row["group"] == group for row in self.worklist["rows"])
             for group in ("original_candidates", "omitted_observation_candidates",
                           "negative_control_candidates")],
            [26, 17, 7],
        )
        self.assertEqual(len({r["site_id"] for r in self.worklist["rows"]}), 50)
        self.assertEqual(self.worklist["source"]["sha256"],
                         "09b89f5f492f6d449257e1c6baa4bc1ea98dedd17e93b9f13ced1c62fbcd9d2c")
        self.assertEqual(self.worklist["rows"][12]["observation"], "SYNTAX_ONLY")
        self.assertEqual(self.worklist["rows"][23]["symbol"]["name"], "classmethod")
        self.assertEqual(self.worklist["rows"][26]["group"],
                         "omitted_observation_candidates")
        self.assertEqual(self.worklist["rows"][43]["group"],
                         "negative_control_candidates")
        self.assertFalse(self.worklist["human_signature_verified"])
        self.assertFalse(self.worklist["policy_adopted"])
        self.assertFalse(self.worklist["automatic_rename_authorized"])

    def test_empty_packet_is_not_evaluated_and_never_auto_approved(self):
        result = assess_review_worklist(self.proposal, self.worklist)
        self.assertEqual((result.total, result.claimed_decisions, result.unresolved,
                          result.remaining_without_decision), (50, 0, 50, 50))
        self.assertEqual(result.status, "NOT_EVALUATED")
        self.assertFalse(result.automatic_rename_authorized)

    def test_even_50_self_declared_reviews_are_not_authenticated(self):
        for row in self.worklist["rows"]:
            self._fill(row)
        assessment = assess_review_worklist(self.proposal, self.worklist)
        self.assertEqual(assessment.claimed_decisions, 50)
        self.assertEqual(assessment.unresolved, 0)
        self.assertEqual(assessment.independent_human_authentication, "NOT_EVALUATED")
        self.assertEqual(assessment.official_glossary_adoption, "NOT_EVALUATED")
        self.assertEqual(assessment.status, "NOT_EVALUATED")
        self.assertFalse(assessment.automatic_rename_authorized)

    def test_partial_and_unresolved_claims(self):
        self._fill(self.worklist["rows"][0])
        self._fill(self.worklist["rows"][26])
        self.worklist["rows"][26]["decision"] = "UNRESOLVED"
        a = assess_review_worklist(self.proposal, self.worklist)
        self.assertEqual((a.claimed_decisions, a.unresolved, a.remaining_without_decision),
                         (2, 49, 48))

    def test_reject_forged_source_policy_and_safety_status(self):
        mutations = [
            ("source", lambda w: w["source"].update({"commit": "a"*40})),
            ("hash", lambda w: w.update({"proposal_sha256": "f"*64})),
            ("status", lambda w: w.update({"status": "APPROVED"})),
            ("auth", lambda w: w.update({"human_signature_verified": True})),
            ("policy", lambda w: w.update({"policy_adopted": True})),
            ("rename", lambda w: w.update({"automatic_rename_authorized": True})),
            ("extra", lambda w: w.update({"unsupported_pass": True})),
        ]
        for label, change in mutations:
            with self.subTest(label=label):
                packet = deepcopy(self.worklist)
                change(packet)
                with self.assertRaises(NamingReviewWorklistError):
                    assess_review_worklist(self.proposal, packet)

    def test_reject_missing_reordered_duplicated_or_forged_sites(self):
        changes = [
            lambda w: w["rows"].pop(),
            lambda w: w["rows"].append(deepcopy(w["rows"][0])),
            lambda w: w["rows"].reverse(),
            lambda w: w["rows"][0].update({"site_id": "n91-forged"}),
            lambda w: w["rows"][0]["symbol"].update({"name": "counterfeit"}),
            lambda w: w["rows"][0].update({"ordinal": 2}),
            lambda w: w["rows"][0].update({"source_sha256": "0"*64}),
            lambda w: w["rows"][0].update({"approved": True}),
        ]
        for i, change in enumerate(changes):
            with self.subTest(i=i):
                packet = deepcopy(self.worklist)
                change(packet)
                with self.assertRaises(NamingReviewWorklistError):
                    assess_review_worklist(self.proposal, packet)

    def test_reject_partial_claim_forged_pass_and_untrusted_link(self):
        changes = [
            lambda r: r.update({"decision": "OBSERVATION_CONFIRMED"}),
            lambda r: (self._fill(r), r.update({"decision": "PASS"})),
            lambda r: (self._fill(r), r.update({"reviewer_login": "Grok AI"})),
            lambda r: (self._fill(r), r.update({"review_comment_url": "https://evil.example/x"})),
            lambda r: (self._fill(r), r.update({"review_comment_url":
                "https://github.com/HyungseonSong-plasma/codeQA/issues/92#issuecomment-99"})),
            lambda r: (self._fill(r), r.update({"rationale": " "})),
            lambda r: (self._fill(r), r.update({"decision": "NEGATIVE_CONFIRMED"})),
        ]
        for i, change in enumerate(changes):
            with self.subTest(i=i):
                packet = deepcopy(self.worklist)
                change(packet["rows"][0])
                with self.assertRaises(NamingReviewWorklistError):
                    assess_review_worklist(self.proposal, packet)

    def test_reject_forged_or_incomplete_proposal(self):
        changes = [
            lambda p: p["original_candidates"].pop(),
            lambda p: p["omitted_observation_candidates"].pop(),
            lambda p: p["negative_control_candidates"].pop(),
            lambda p: p.update({"review_status": "APPROVED"}),
            lambda p: p["original_candidates"][0].update({"human_adjudication": "ACCEPT"}),
            lambda p: p["omitted_observation_candidates"][0].update(
                {"extractor_false_negative": True}),
            lambda p: p["negative_control_candidates"][0].update(
                {"human_review_outcome": "ACCEPT"}),
        ]
        for i, change in enumerate(changes):
            with self.subTest(i=i):
                proposal = deepcopy(self.proposal)
                change(proposal)
                with self.assertRaises(NamingReviewWorklistError):
                    build_review_worklist(proposal)

    def test_worklist_does_not_mutate_proposal(self):
        before = deepcopy(self.proposal)
        packet = build_review_worklist(self.proposal)
        packet["source"]["commit"] = "0"*40
        self.assertEqual(self.proposal, before)


if __name__ == "__main__":
    unittest.main()
