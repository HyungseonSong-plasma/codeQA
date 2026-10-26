"""#91: additive field evidence cannot upgrade a legacy Naming observation."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from codeqa.core.naming_field_evidence_v03 import (
    FieldEvidenceError, build_shadow_field_evidence, validate_shadow_field_evidence,
)
from codeqa.core.naming_review_worklist_v03 import build_review_worklist
from codeqa.infrastructure.git import GitReader
from codeqa.pipeline.naming_field_evidence_v03 import project_pinned_field_evidence


ROOT = Path(__file__).resolve().parents[1]
PROPOSAL = ROOT / "fixtures/naming-governance/codeqa-ast-review-v03-proposal.json"
REVIEW = ROOT / "fixtures/naming-governance/codeqa-batch1-contract-evidence-v03.json"


class ShadowFieldEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.proposal = json.loads(PROPOSAL.read_text(encoding="utf-8"))
        cls.review = json.loads(REVIEW.read_text(encoding="utf-8"))
        source = cls.proposal["source"]
        cls.source = GitReader(ROOT).read_file(source["commit"], source["path"])
        cls.packet = project_pinned_field_evidence(ROOT, cls.proposal)

    def test_seven_legacy_fields_all_remain_separate_candidates(self) -> None:
        packet = self.packet
        self.assertEqual(packet["schema_version"], "0.3-shadow-field-evidence")
        self.assertEqual(packet["migration_mode"], "ADDITIVE_SHADOW_ONLY")
        self.assertEqual(packet["legacy_worklist_sites"], 50)
        self.assertEqual(packet["projected_field_sites"], 7)
        self.assertEqual([row["symbol"]["name"] for row in packet["fields"]], [
            "canonical", "aliases", "kinds", "schema_version",
            "profile_id", "include_prefixes", "terms",
        ])
        self.assertTrue(all(row["static_classification"] == "FIELD_CANDIDATE"
                            for row in packet["fields"]))
        self.assertEqual(packet["policy_adoption"], "NOT_ADOPTED")
        self.assertEqual(packet["human_approval"], "NOT_EVALUATED")
        self.assertEqual(packet["runtime_field_verification"], "NOT_EVALUATED")
        self.assertFalse(packet["automatic_rename_authorized"])
        self.assertFalse(packet["issue_close_authorized"])
        print("NAMING_FIELD_SHADOW_EVIDENCE "
              "legacy_worklist_sites=50 projected_fields=7 candidates=7 "
              "human_approval=NOT_EVALUATED rename_authorized=false")

    def test_all_existing_worklist_site_ids_unchanged(self) -> None:
        original = build_review_worklist(self.proposal)
        expected = [
            r["site_id"] for r in original["rows"]
            if r["group"] == "original_candidates"
            and r["symbol"]["kind"] == "declared_field"
        ]
        self.assertEqual([r["site_id"] for r in self.packet["fields"]], expected)
        self.assertEqual(len(original["rows"]), 50)
        self.assertEqual(len({r["site_id"] for r in original["rows"]}), 50)
        self.assertTrue(all(r["decision"] is None for r in original["rows"]))
        # Shadow evidence cannot modify or sign original proposal/worksheet.
        self.assertTrue(all(r.get("human_adjudication") is None
                            for r in self.proposal["original_candidates"]))

    def test_canonical_follows_source_not_the_human_review_verdict(self) -> None:
        row = next(r for r in self.packet["fields"]
                   if r["symbol"]["name"] == "canonical")
        self.assertEqual(row["symbol"], {
            "name": "canonical", "kind": "declared_field",
            "line": 34, "owner": "GlossaryTerm",
        })
        self.assertEqual(row["site_id"], "n91-09e35a4a541b5eac7a96d235")
        self.assertEqual(row["ast_site"], "DIRECT_CLASS_ANNASSIGN")
        self.assertEqual(row["static_classification"], "FIELD_CANDIDATE")
        self.assertEqual(row["human_decision"],
                         "NOT_IMPORTED_FROM_REVIEW_LEDGER")
        actual_human = next(
            c for c in self.review["cases"] if c["index"] == 15)
        self.assertEqual(actual_human["human_decision"], "UNRESOLVED")

    def test_pinned_source_bytes_and_live_adapter_agree(self) -> None:
        expected = build_shadow_field_evidence(self.proposal, source=self.source)
        self.assertEqual(expected, self.packet)
        self.assertEqual(
            validate_shadow_field_evidence(self.proposal, source=self.source,
                                           submitted=deepcopy(self.packet)),
            self.packet,
        )

    def test_reject_mutated_historical_source_even_with_same_site_spelling(self) -> None:
        altered = self.source.replace(b"canonical: str", b"canonical: int", 1)
        self.assertNotEqual(altered, self.source)
        with self.assertRaises(FieldEvidenceError):
            build_shadow_field_evidence(self.proposal, source=altered)

    def test_reject_missing_reordered_or_forged_sites(self) -> None:
        changes = [
            lambda p: p["fields"].pop(),
            lambda p: p["fields"].reverse(),
            lambda p: p["fields"].append(deepcopy(p["fields"][0])),
            lambda p: p["fields"][0].update(site_id="n91-fake"),
            lambda p: p["fields"][0]["symbol"].update(owner="Forged"),
            lambda p: p["fields"][0].update(static_classification="FIELD_CONFIRMED"),
            lambda p: p["fields"][0].update(static_classification="PASS"),
            lambda p: p["fields"][0].update(reason_codes=["fake"]),
            lambda p: p["fields"][0].update(human_decision="OBSERVATION_CONFIRMED"),
            lambda p: p["fields"][0].update(runtime_field_verification="VERIFIED"),
            lambda p: p.update(projected_field_sites=6),
            lambda p: p.update(proposal_sha256="0" * 64),
            lambda p: p["source"].update(git_blob_sha="a" * 40),
        ]
        for i, change in enumerate(changes):
            with self.subTest(i=i):
                forged = deepcopy(self.packet)
                change(forged)
                with self.assertRaises(FieldEvidenceError):
                    validate_shadow_field_evidence(
                        self.proposal, source=self.source, submitted=forged)

    def test_reject_authorizing_fields_and_policy_promotion(self) -> None:
        alterations = [
            lambda p: p.update(policy_adoption="ADOPTED"),
            lambda p: p.update(human_approval="APPROVED"),
            lambda p: p.update(automatic_rename_authorized=True),
            lambda p: p.update(issue_close_authorized=True),
            lambda p: p.update(migration_mode="REPLACE_LEGACY"),
            lambda p: p.update(official_naming_pass=True),
            lambda p: p["fields"][0].update(automatic_rename_authorized=True),
            lambda p: p["fields"][0].update(unsafe_approval="ACCEPT"),
        ]
        for i, change in enumerate(alterations):
            with self.subTest(i=i):
                changed = deepcopy(self.packet)
                change(changed)
                with self.assertRaises(FieldEvidenceError):
                    validate_shadow_field_evidence(
                        self.proposal, source=self.source, submitted=changed)

    def test_reject_proposal_drift_and_missing_evidence(self) -> None:
        changed = deepcopy(self.proposal)
        changed["original_candidates"][14]["name"] = "invented_field"
        with self.assertRaises(FieldEvidenceError):
            build_shadow_field_evidence(changed, source=self.source)
        changed = deepcopy(self.proposal)
        changed["source"]["git_blob_sha"] = "0" * 40
        with self.assertRaises(FieldEvidenceError):
            build_shadow_field_evidence(changed, source=self.source)
        with self.assertRaises(FieldEvidenceError):
            build_shadow_field_evidence(self.proposal, source=b"")

    def test_no_runtime_or_rename_authority_from_any_projection(self) -> None:
        packet = self.packet
        for field in packet["fields"]:
            with self.subTest(site=field["site_id"]):
                self.assertEqual(field["runtime_field_verification"],
                                 "NOT_EVALUATED")
                self.assertEqual(field["naming_policy_applicability"],
                                 "NOT_EVALUATED")
                self.assertFalse(field["automatic_rename_authorized"])


if __name__ == "__main__":
    unittest.main()
