"""Owner-approved Naming v0.5: exact-scope opt-in and fail-closed regression."""
from __future__ import annotations

from copy import deepcopy
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import unittest

from codeqa.core.naming_official_adoption_v05 import NamingAdoptionError
from codeqa.core.naming_official_policy_v05 import (
    evaluate_official_naming_v05,
)
from codeqa.infrastructure.git import GitReader
from codeqa.infrastructure.resources import ResourceRegistry
from codeqa.pipeline.naming_official_policy_v05 import (
    evaluate_pinned_official_naming_v05,
)

ROOT = Path(__file__).resolve().parents[1]
PROPOSAL = ROOT / "profiles/codeqa-python-naming-scoped-v0.5-proposal.json"
ADOPTED = ROOT / "profiles/codeqa-python-naming-scoped-v0.5.json"
PIN = "1fca848833167829752b4fda8632ef06aa77dd49"
SITE = dict(path="src/codeqa/core/complexity.py",
            owner="ControlFlowObservation", name="node_id",
            kind="field", line=10)
TODAY = date(2026, 10, 26)


class OfficialNamingV05Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proposal = json.loads(PROPOSAL.read_text(encoding="utf-8"))
        cls.policy = json.loads(ADOPTED.read_text(encoding="utf-8"))
        cls.source = GitReader(ROOT).read_file(
            PIN, SITE["path"])

    def evaluate(self, policy=None, proposal=None, source=None,
                 as_of=TODAY, **changes):
        site = {**SITE, **changes}
        return evaluate_official_naming_v05(
            self.policy if policy is None else policy,
            proposal=self.proposal if proposal is None else proposal,
            source=self.source if source is None else source,
            as_of=as_of, **site)

    def test_exact_adopted_lexical_site_via_independent_git_pin(self):
        o = evaluate_pinned_official_naming_v05(
            ROOT, self.policy, self.proposal, as_of=TODAY, **SITE)
        self.assertEqual(o.status, "SCOPED_LEXICAL_CONFORMANT")
        self.assertEqual(o.reason, "EXACT_SOURCE_FIELD_SPELLING_OBSERVED")
        self.assertEqual(o.source_commit, PIN)
        self.assertEqual(o.policy_scope, "EXACT_DECLARATION_LEXICAL_ONLY")
        self.assertEqual(o.declaration, "ControlFlowObservation.node_id")
        self.assertEqual(o.source_line, 10)
        self.assertEqual(o, self.evaluate())
        self.assertFalse(o.semantic_meaning_verified)
        self.assertFalse(o.runtime_binding_verified)
        self.assertFalse(o.rename_authorized)
        self.assertEqual(o.external_compatibility, "UNKNOWN")
        print("NAMING_V05_ADOPTED scope=ControlFlowObservation.node_id "
              "source=PINNED owner_decision=APPROVED "
              "result=SCOPED_LEXICAL_CONFORMANT "
              "semantic_pass=false rename=false")

    def test_explicit_resource_optin_preserves_frozen_v01(self):
        registry = ResourceRegistry(ROOT)
        self.assertEqual(
            registry.load_json("codeqa_python_naming_scoped_v05_policy"),
            self.policy)
        self.assertEqual(
            registry.load_json("python_naming_glossary_profile")["schema_version"],
            "0.1")
        self.assertEqual(self.policy["status"], "ADOPTED_SCOPED_LEXICAL_ONLY")
        self.assertEqual(self.policy["owner_decision"],
                         "PROJECT_OWNER_EXPLICIT_APPROVAL_2026-10-26")
        self.assertEqual(self.policy["terms"][0]["path_scopes"], [])
        self.assertFalse(self.policy["automatic_rename_authorized"])
        self.assertFalse(self.policy["semantic_glossary_pass"])

    def test_scope_is_exact_not_other_fields_or_owners(self):
        for change in (
            {"name": "nodeid"}, {"name": "time_step"}, {"owner": "Other"},
            {"kind": "parameter"}, {"line": 11},
            {"path": "src/codeqa/core/p3_witness.py"},
        ):
            with self.subTest(**change):
                o = self.evaluate(**change)
                self.assertEqual(o.status, "NOT_APPLICABLE")
                self.assertEqual(o.reason, "DECLARATION_OUTSIDE_EXACT_SCOPE")
                self.assertFalse(o.rename_authorized)

    def test_review_cadence_and_effective_date_are_exact(self):
        self.assertEqual(self.policy["adoption_date"], "2026-10-26")
        self.assertEqual(self.policy["next_review_date"], "2027-04-24")
        self.assertEqual(self.evaluate(as_of=date(2026,10,25)).reason,
                         "POLICY_NOT_YET_EFFECTIVE")
        self.assertEqual(self.evaluate(as_of=date(2027,4,24)).status,
                         "SCOPED_LEXICAL_CONFORMANT")
        due = self.evaluate(as_of=date(2027,4,25))
        self.assertEqual(due.status, "REVIEW_REQUIRED")
        self.assertEqual(due.reason, "OWNER_REVIEW_OVERDUE")
        self.assertFalse(due.rename_authorized)

    def test_reject_forged_broadening_and_semantic_pass(self):
        changes = (
            lambda p: p["declaration_scope"].update(owner="Everything"),
            lambda p: p["declaration_scope"].update(line=11),
            lambda p: p["terms"][1].update(path_scopes=["src/codeqa"]),
            lambda p: p["terms"][0].update(path_scopes=["src/codeqa"]),
            lambda p: p["terms"][1].update(noncanonical_spelling="node"),
            lambda p: p["terms"][1].update(meaning="PROVEN"),
            lambda p: p.update(semantic_glossary_pass=True),
            lambda p: p.update(automatic_rename_authorized=True),
            lambda p: p.update(default_v01_unchanged=False),
            lambda p: p.update(external_clients="COMPATIBLE"),
            lambda p: p.update(exceptions=[{"reason":"free"}]),
            lambda p: p.update(signed_by="claimed-human"),
        )
        for i, change in enumerate(changes):
            with self.subTest(i=i):
                invalid = deepcopy(self.policy)
                change(invalid)
                with self.assertRaises(NamingAdoptionError):
                    self.evaluate(policy=invalid)

    def test_reject_forged_owner_decision_or_date(self):
        for key, value in (
            ("owner_decision", "UNREVIEWED"),
            ("status", "ADOPTED_ALL"),
            ("adoption_date", "2026-10-25"),
            ("next_review_date", "2027-05-01"),
            ("review_interval_days", 365),
        ):
            with self.subTest(key=key):
                bad = deepcopy(self.policy)
                bad[key] = value
                with self.assertRaises(NamingAdoptionError):
                    self.evaluate(policy=bad)

    def test_proposal_itself_is_not_adopted_and_is_unchanged(self):
        self.assertEqual(self.proposal["status"], "PENDING_FINAL_OWNER_APPROVAL")
        self.assertEqual(self.proposal["owner_decision"],
                         "EXPLICIT_SEPARATE_APPROVAL_REQUIRED")
        self.assertIsNone(self.proposal["adoption_date"])
        self.assertIsNone(self.proposal["next_review_date"])
        with self.assertRaises(NamingAdoptionError):
            self.evaluate(policy=self.proposal)
        q = deepcopy(self.proposal)
        q["declaration_scope"]["owner_role_approval"] = "APPROVED"
        with self.assertRaises(NamingAdoptionError):
            self.evaluate(proposal=q)

    def test_historical_source_drift_fails_even_if_declared_name_unchanged(self):
        raw = self.source.replace(b"node_id: str", b"node_id: int", 1)
        self.assertNotEqual(raw, self.source)
        with self.assertRaises(NamingAdoptionError):
            self.evaluate(source=raw)
        bad = deepcopy(self.proposal)
        bad["source_witness"]["git_blob_sha"] = "0"*40
        with self.assertRaises(NamingAdoptionError):
            evaluate_pinned_official_naming_v05(
                ROOT, self.policy, bad, as_of=TODAY, **SITE)

    def test_policy_fingerprint_is_deterministic(self):
        a = self.evaluate()
        b = self.evaluate(policy=deepcopy(self.policy))
        self.assertEqual(a.policy_sha256, b.policy_sha256)
        self.assertEqual(len(a.policy_sha256), 64)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
