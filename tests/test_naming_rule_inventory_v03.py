"""Machine-verifiable source-only closure gate for #91."""
from __future__ import annotations
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import unittest

from codeqa.core.naming_rule_inventory_v03 import (
    RuleInventoryError, classify_exact_rule_inventory, validate_exact_rule_inventory,
)
from codeqa.core.naming_review_worklist_v03 import build_review_worklist
from codeqa.infrastructure.git import GitReader
from codeqa.pipeline.naming_rule_inventory_v03 import evaluate_pinned_rule_inventory


ROOT = Path(__file__).resolve().parents[1]
PROPOSAL = ROOT / "fixtures/naming-governance/codeqa-ast-review-v03-proposal.json"
HUMAN = ROOT / "fixtures/naming-governance/codeqa-batch1-contract-evidence-v03.json"
CHARTER = ROOT / "fixtures/naming-governance/codeqa-rule-acceptance-v03.json"


class DeterministicRuleInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proposal = json.loads(PROPOSAL.read_text(encoding="utf-8"))
        cls.human = json.loads(HUMAN.read_text(encoding="utf-8"))
        cls.charter = json.loads(CHARTER.read_text(encoding="utf-8"))
        source = cls.proposal["source"]
        cls.source = GitReader(ROOT).read_file(source["commit"], source["path"])
        cls.packet = evaluate_pinned_rule_inventory(ROOT, cls.proposal)

    def test_scope_charter_is_not_semantic_naming_acceptance(self):
        c = self.charter
        self.assertEqual(c["schema_version"], "0.3-source-only-acceptance")
        self.assertEqual(c["issue"], 91)
        for key in ("repository", "commit", "path", "git_blob_sha", "sha256"):
            self.assertEqual(c["source"][key], self.proposal["source"][key])
        self.assertEqual(c["source"]["sha256"], self.proposal["source"]["sha256"])
        self.assertEqual(c["required_total"], 50)
        self.assertEqual(c["required_unknown"], 0)
        self.assertFalse(c["automatic_rename_authorized"])
        self.assertTrue(c["successor_issue_required_for_deferred_semantics"])

    def test_all_50_legacy_sites_have_source_rule_results(self):
        rows = self.packet["rows"]
        expected = build_review_worklist(self.proposal)["rows"]
        self.assertEqual(self.packet["closure_gate"], "PASS")
        self.assertEqual((self.packet["total_sites"], self.packet["classified_sites"],
                          self.packet["unknown_sites"]), (50, 50, 0))
        self.assertEqual([r["site_id"] for r in rows], [r["site_id"] for r in expected])
        self.assertEqual([sum(r["group"] == g for r in rows) for g in (
            "original_candidates", "omitted_observation_candidates",
            "negative_control_candidates")], [26, 17, 7])
        counts = Counter(r["source_evidence"] for r in rows)
        self.assertEqual(counts["DATACLASS_FIELD_CANDIDATE"], 7)
        self.assertEqual(counts["NEGATIVE_CONTROL_RENAME_EXCLUDED"], 7)
        self.assertEqual(counts["DECORATOR_SYNTAX_ONLY"], 3)
        self.assertEqual(counts["FUTURE_DIRECTIVE_SYNTAX"], 1)
        self.assertEqual(sum(counts.values()), 50)
        print("NAMING_RULE_INVENTORY total=50 classified=50 unknown=0 "
              "field_candidates=7 negative_controls=7 "
              "semantics=NOT_EVALUATED rename_authorized=false")

    def test_canonical_is_structural_candidate_not_human_approval(self):
        row = self.packet["rows"][14]
        self.assertEqual(row["site_id"], "n91-09e35a4a541b5eac7a96d235")
        self.assertEqual(row["source_evidence"], "DATACLASS_FIELD_CANDIDATE")
        self.assertEqual(row["field_static_classification"], "FIELD_CANDIDATE")
        self.assertEqual(self.human["cases"][1]["human_decision"], "UNRESOLVED")
        self.assertTrue(self.packet["human_review_not_required_for_bounded_AST_axis"])
        self.assertEqual(self.packet["semantic_glossary"], "NOT_ADOPTED")

    def test_negative_control_is_not_semantic_failure(self):
        cases = [r for r in self.packet["rows"]
                 if r["group"] == "negative_control_candidates"]
        self.assertEqual(len(cases), 7)
        self.assertTrue(all(r["source_evidence"] ==
                            "NEGATIVE_CONTROL_RENAME_EXCLUDED" for r in cases))
        self.assertTrue(all(r["naming_semantics"] == "NOT_EVALUATED"
                            and not r["rename_authorized"] for r in cases))

    def test_determinism_and_git_provenance(self):
        self.assertEqual(
            self.packet, classify_exact_rule_inventory(self.proposal,
                                                        source=self.source))
        self.assertEqual(
            self.packet, validate_exact_rule_inventory(
                self.proposal, source=self.source, submitted=deepcopy(self.packet)))

    def test_mutated_pinned_bytes_and_wrong_site_fail_closed(self):
        modified = self.source.replace(b"canonical: str", b"canonical: int", 1)
        self.assertNotEqual(modified, self.source)
        with self.assertRaises(RuleInventoryError):
            classify_exact_rule_inventory(self.proposal, source=modified)
        forged = deepcopy(self.proposal)
        forged["original_candidates"][14]["name"] = "invented_name"
        result = classify_exact_rule_inventory(forged, source=self.source)
        self.assertEqual(result["closure_gate"], "BLOCKED_UNKNOWN")
        self.assertGreater(result["unknown_sites"], 0)

    def test_forged_pass_and_missing_reordered_evidence_rejected(self):
        alterations = [
            lambda d: d["rows"].pop(),
            lambda d: d["rows"].reverse(),
            lambda d: d["rows"][14].update(source_evidence="FIELD_CONFIRMED"),
            lambda d: d["rows"][14].update(source_evidence="PASS"),
            lambda d: d["rows"][14].update(rename_authorized=True),
            lambda d: d.update(closure_gate="PASS", unknown_sites=1),
            lambda d: d.update(semantic_glossary="ADOPTED"),
            lambda d: d.update(policy_applicability="PASS"),
            lambda d: d.update(rename_authorized=True),
            lambda d: d.update(human_signature_verified=True),
            lambda d: d["source"].update(sha256="0" * 64),
        ]
        for i, mutation in enumerate(alterations):
            with self.subTest(i=i):
                edited = deepcopy(self.packet)
                mutation(edited)
                with self.assertRaises(RuleInventoryError):
                    validate_exact_rule_inventory(
                        self.proposal, source=self.source, submitted=edited)

    def test_all_semantic_authority_is_always_excluded(self):
        self.assertEqual(self.packet["external_dynamic_api_safety"], "OUT_OF_SCOPE")
        self.assertEqual(self.packet["policy_applicability"], "NOT_EVALUATED")
        self.assertFalse(self.packet["rename_authorized"])
        for row in self.packet["rows"]:
            self.assertEqual(row["naming_semantics"], "NOT_EVALUATED")
            self.assertEqual(row["runtime_binding_graph"], "NOT_EVALUATED")
            self.assertEqual(row["external_compatibility"], "NOT_EVALUATED")
            self.assertFalse(row["rename_authorized"])


if __name__ == "__main__":
    unittest.main()
