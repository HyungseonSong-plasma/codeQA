"""Source-scoped, non-certifying Naming Glossary Governance v0.2 tests."""
from __future__ import annotations

from copy import deepcopy
from datetime import date
import unittest

from codeqa.core.naming_glossary_governance_v02 import (
    GlossaryGovernance, GlossaryGovernanceError,
)

TODAY = date(2026, 10, 24)


def example():
    return {
        "schema_version": "0.2-draft",
        "review_status": "AWAITING_HUMAN_REVIEW",
        "terms": [
            {"canonical": "plasma", "aliases": ["discharge"],
             "owner": "domain-reviewer", "expires_on": "2027-10-24",
             "allowed_roles": ["physics"]},
            {"canonical": "time_ms", "aliases": [],
             "owner": "domain-reviewer", "expires_on": "2027-10-24",
             "allowed_roles": ["runtime"]},
        ],
        "scopes": [
            {"prefix": "src", "language": "python", "category": "function",
             "role": "runtime"},
            {"prefix": "src/codeqa/physics", "language": "python",
             "category": "function", "role": "physics"},
        ],
    }


class GlossaryGovernanceTests(unittest.TestCase):
    def test_scoped_positive_is_only_candidate(self):
        p = GlossaryGovernance.from_mapping(example())
        c = p.candidate(
            path="src/codeqa/physics/electron.py", identifier="plasma_density",
            language="python", category="function", as_of=TODAY)
        self.assertEqual(c.status, "ROLE_NAME_MATCH_CANDIDATE")
        self.assertFalse(c.semantic_proven)
        self.assertEqual(c.declared_role, "physics")

    def test_longest_prefix_and_discrepancy(self):
        p = GlossaryGovernance.from_mapping(example())
        c = p.candidate(
            path="src/codeqa/other.py", identifier="plasma_density",
            language="python", category="function", as_of=TODAY)
        self.assertEqual(c.status, "ROLE_NAME_REVIEW_CANDIDATE")
        self.assertEqual(c.declared_role, "runtime")

    def test_alias_is_explicit_only(self):
        p = GlossaryGovernance.from_mapping(example())
        one = p.candidate(path="src/codeqa/physics/x.py",
            identifier="discharge_probe", language="python",
            category="function", as_of=TODAY)
        two = p.candidate(path="src/codeqa/physics/x.py",
            identifier="electron_probe", language="python",
            category="function", as_of=TODAY)
        self.assertEqual(one.status, "ROLE_NAME_MATCH_CANDIDATE")
        self.assertEqual(two.status, "NOT_EVALUATED")

    def test_external_override_is_never_renamed(self):
        p = GlossaryGovernance.from_mapping(example())
        c = p.candidate(path="src/codeqa/physics/x.py",
            identifier="plasma_callback", language="python",
            category="function", as_of=TODAY, external_contract=True)
        self.assertEqual(c.status, "NOT_EVALUATED")

    def test_expired_term_is_not_accepted(self):
        d = example()
        d["terms"][0]["expires_on"] = "2026-01-01"
        c = GlossaryGovernance.from_mapping(d).candidate(
            path="src/codeqa/physics/x.py", identifier="plasma_density",
            language="python", category="function", as_of=TODAY)
        self.assertEqual(c.status, "NOT_EVALUATED")

    def test_conflicting_alias_and_circular_alias_rejected(self):
        d = example()
        d["terms"][1]["aliases"] = ["discharge"]
        with self.assertRaises(GlossaryGovernanceError):
            GlossaryGovernance.from_mapping(d)
        d = example()
        d["terms"][0]["aliases"] = ["plasma"]
        with self.assertRaises(GlossaryGovernanceError):
            GlossaryGovernance.from_mapping(d)

    def test_same_scope_conflict_rejected(self):
        d = example()
        d["scopes"].append(deepcopy(d["scopes"][1]))
        d["scopes"][2]["role"] = "runtime"
        with self.assertRaises(GlossaryGovernanceError):
            GlossaryGovernance.from_mapping(d)

    def test_unicode_or_unsafe_scope_rejected_without_rewrite(self):
        for bad in ("../src", "src//x", "src/électron", "src/../test"):
            d = example()
            d["scopes"][1]["prefix"] = bad
            with self.subTest(bad=bad), self.assertRaises(GlossaryGovernanceError):
                GlossaryGovernance.from_mapping(d)
        d = example()
        d["terms"][0]["canonical"] = "рlasma"
        with self.assertRaises(GlossaryGovernanceError):
            GlossaryGovernance.from_mapping(d)

    def test_unapproved_status_cannot_be_forged_as_accepted(self):
        d = example()
        d["review_status"] = "APPROVED"
        with self.assertRaises(GlossaryGovernanceError):
            GlossaryGovernance.from_mapping(d)

    def test_unit_suffix_is_lexical_only_not_semantic_conversion(self):
        p = GlossaryGovernance.from_mapping(example())
        c = p.candidate(path="src/timing.py", identifier="time_ms",
            language="python", category="function", as_of=TODAY)
        self.assertEqual(c.status, "NOT_EVALUATED")
        self.assertFalse(c.semantic_proven)


if __name__ == "__main__":
    unittest.main()
