"""Adversarial #91 opt-in Naming policy precedence tests, not human approvals."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import date
from hashlib import sha256
import json
import unittest

from codeqa.core.naming_policy_precedence_v03 import (
    NamingPrecedenceError, NamingPrecedencePolicy,
)

REPO = "HyungseonSong-plasma/codeQA"
REV = "git:" + REPO + "@" + "a" * 40
CATALOG = "c" * 64
PROFILE = "d" * 64
SOURCE = "def plasma_density():\n    return 1\n"
SOURCES = {"src/codeqa/physics/electron.py": SOURCE}
TODAY = date(2026, 10, 25)


def sample():
    return {
        "schema_version": "0.3-draft",
        "policy_id": "codeqa-naming-v0.3-draft",
        "review_status": "AWAITING_HUMAN_REVIEW",
        "catalog_sha256": CATALOG,
        "profile_sha256": PROFILE,
        "rules": [
            {"rule_id": "catalog-baseline", "level": "catalog",
             "action": "REVIEW_REQUIRED", "selector": {}},
            {"rule_id": "language-python", "level": "language",
             "action": "CHECK_CANDIDATE", "selector": {"language": "python"}},
            {"rule_id": "repository-codeqa", "level": "repository",
             "action": "REVIEW_REQUIRED",
             "selector": {"language": "python", "repository": REPO}},
            {"rule_id": "physics-functions", "level": "path_symbol",
             "action": "CHECK_CANDIDATE",
             "selector": {"language": "python", "repository": REPO,
                          "path_prefix": "src/codeqa/physics", "symbol_kind": "function"}},
            {"rule_id": "physics-narrower", "level": "path_symbol",
             "action": "REVIEW_REQUIRED",
             "selector": {"language": "python", "repository": REPO,
                          "path_prefix": "src/codeqa/physics/experimental",
                          "symbol_kind": "function"}},
            {"rule_id": "exception-reviewed", "level": "exception",
             "action": "EXCLUDE_CANDIDATE",
             "selector": {"language": "python", "repository": REPO,
                          "path": "src/codeqa/physics/electron.py",
                          "symbol_kind": "function", "symbol": "plasma_density"},
             "owner": "human-domain-reviewer", "reason": "external alias requires review",
             "expires_on": "2027-01-01"},
        ],
    }


def args(policy, **changes):
    values = {
        "revision": REV, "repository": REPO, "sources": SOURCES,
        "path": "src/codeqa/physics/electron.py",
        "language": "python", "symbol_kind": "function",
        "symbol": "plasma_density", "as_of": TODAY,
        "catalog_sha256": CATALOG, "profile_sha256": PROFILE,
        "expected_policy_sha256": policy.policy_sha256,
        "expected_source_sha256": sha256(SOURCES["src/codeqa/physics/electron.py"].encode()).hexdigest(),
    }
    values.update(changes)
    return values


class NamingPolicyPrecedenceTests(unittest.TestCase):
    def test_all_five_levels_and_review_only_exception(self):
        p = NamingPrecedencePolicy.from_mapping(sample())
        r = p.resolve(**args(p))
        self.assertEqual(r.status, "EXCLUDE_CANDIDATE")
        self.assertEqual(r.selected_level, "exception")
        self.assertEqual(r.selected_rule_id, "exception-reviewed")
        self.assertEqual(r.matched_rule_ids, (
            "catalog-baseline", "language-python", "repository-codeqa",
            "physics-functions", "exception-reviewed",
        ))
        self.assertEqual(r.source_sha256, sha256(SOURCE.encode()).hexdigest())
        self.assertTrue(r.human_review_required)
        self.assertFalse(r.semantic_proven)

    def test_longest_segment_prefix_and_no_nearby_prefix_match(self):
        p = NamingPrecedencePolicy.from_mapping(sample())
        new = dict(SOURCES, **{
            "src/codeqa/physics/experimental/field.py": "def density(): pass\n",
            "src/codeqa/physics_extra/field.py": "def density(): pass\n",
        })
        a = p.resolve(**args(p, sources=new,
            path="src/codeqa/physics/experimental/field.py", symbol="density",
            expected_source_sha256=sha256(new["src/codeqa/physics/experimental/field.py"].encode()).hexdigest()))
        self.assertEqual(a.status, "REVIEW_REQUIRED")
        self.assertEqual(a.selected_rule_id, "physics-narrower")
        b = p.resolve(**args(p, sources=new,
            path="src/codeqa/physics_extra/field.py", symbol="density",
            expected_source_sha256=sha256(new["src/codeqa/physics_extra/field.py"].encode()).hexdigest()))
        self.assertEqual(b.status, "NOT_EVALUATED")
        self.assertIsNone(b.selected_rule_id)

    def test_exact_exception_never_matches_another_symbol(self):
        p = NamingPrecedencePolicy.from_mapping(sample())
        source = SOURCE + "def other_function(): pass\n"
        sources = {"src/codeqa/physics/electron.py": source}
        r = p.resolve(**args(
            p, symbol="other_function", sources=sources,
            expected_source_sha256=sha256(source.encode()).hexdigest(),
        ))
        self.assertEqual(r.status, "CHECK_CANDIDATE")
        self.assertEqual(r.selected_level, "path_symbol")

    def test_unknown_language_repository_or_symbol_kind_is_not_evaluated(self):
        p = NamingPrecedencePolicy.from_mapping(sample())
        for change in (
            {"language": "rust"}, {"symbol_kind": "class"},
        ):
            with self.subTest(change=change):
                r = p.resolve(**args(p, **change))
                self.assertEqual(r.status, "NOT_EVALUATED")
                self.assertFalse(r.semantic_proven)
        other = "another/owner"
        r = p.resolve(**args(p, repository=other,
                             revision="git:" + other + "@" + "a" * 40))
        self.assertEqual(r.status, "NOT_EVALUATED")

    def test_expired_exception_fails_instead_of_falling_back_to_check(self):
        p = NamingPrecedencePolicy.from_mapping(sample())
        with self.assertRaisesRegex(NamingPrecedenceError, "expired"):
            p.resolve(**args(p, as_of=date(2027, 1, 2)))

    def test_catalog_profile_policy_revision_and_source_drift_fail(self):
        p = NamingPrecedencePolicy.from_mapping(sample())
        for change in (
            {"catalog_sha256": "a" * 64},
            {"profile_sha256": "a" * 64},
            {"expected_policy_sha256": "a" * 64},
            {"expected_source_sha256": "a" * 64},
            {"revision": "git:other/repo@" + "a" * 40},
            {"revision": "main"},
            {"sources": {}},
            {"sources": {"src/codeqa/physics/electron.py": 1}},
        ):
            with self.subTest(change=change), self.assertRaises(NamingPrecedenceError):
                p.resolve(**args(p, **change))

    def test_changed_source_bytes_fail_until_independently_reattested(self):
        p = NamingPrecedencePolicy.from_mapping(sample())
        new = {"src/codeqa/physics/electron.py": SOURCE + "\n# changed\n"}
        before = p.resolve(**args(p))
        with self.assertRaisesRegex(NamingPrecedenceError, "stale source"):
            p.resolve(**args(p, sources=new))
        after = p.resolve(**args(
            p, sources=new, expected_source_sha256=sha256(new[
                "src/codeqa/physics/electron.py"].encode()).hexdigest(),
        ))
        self.assertNotEqual(before.source_sha256, after.source_sha256)
        self.assertTrue(after.human_review_required)
        self.assertFalse(after.semantic_proven)

    def test_duplicate_equal_precedence_and_duplicate_id_fail(self):
        for duplicate in (
            deepcopy(sample()["rules"][3]),
            dict(sample()["rules"][3], rule_id="another-duplicate",
                 action="EXCLUDE_CANDIDATE"),
        ):
            raw = sample()
            raw["rules"].append(duplicate)
            with self.assertRaises(NamingPrecedenceError):
                NamingPrecedencePolicy.from_mapping(raw)

    def test_exception_outside_selected_path_or_symbol_scope_rejected(self):
        for change in (
            {"path": "src/codeqa/other.py"},
            {"symbol_kind": "class"},
            {"repository": "another/repo"},
        ):
            raw = sample()
            raw["rules"][-1]["selector"].update(change)
            with self.subTest(change=change), self.assertRaisesRegex(
                    NamingPrecedenceError, "explicit path/symbol scope"):
                NamingPrecedencePolicy.from_mapping(raw)

    def test_policy_fingerprint_and_trace_are_deterministic(self):
        p = NamingPrecedencePolicy.from_mapping(sample())
        q = NamingPrecedencePolicy.from_mapping(deepcopy(sample()))
        self.assertEqual(p.policy_sha256, q.policy_sha256)
        self.assertEqual(p.resolve(**args(p)), q.resolve(**args(q)))

    def test_reject_approved_policy_or_pass_and_malformed_selector(self):
        for change in ("APPROVED", "ACCEPTED"):
            raw = sample()
            raw["review_status"] = change
            with self.assertRaises(NamingPrecedenceError):
                NamingPrecedencePolicy.from_mapping(raw)
        for action in ("PASS", "ALLOW", "SAFE_TO_RENAME"):
            raw = sample()
            raw["rules"][3]["action"] = action
            with self.assertRaises(NamingPrecedenceError):
                NamingPrecedencePolicy.from_mapping(raw)
        raw = sample()
        raw["rules"][3]["selector"]["path_prefix"] = "src/../unsafe"
        with self.assertRaises(NamingPrecedenceError):
            NamingPrecedencePolicy.from_mapping(raw)
        raw = sample()
        raw["rules"][0]["selector"]["unknown"] = "untrusted"
        with self.assertRaises(NamingPrecedenceError):
            NamingPrecedencePolicy.from_mapping(raw)

    def test_conflicting_override_expiry_and_owner_required(self):
        for value in ("2026-02-30", "2026-1-01", "", None):
            raw = sample()
            raw["rules"][-1]["expires_on"] = value
            with self.subTest(value=value), self.assertRaises(NamingPrecedenceError):
                NamingPrecedencePolicy.from_mapping(raw)
        raw = sample()
        raw["rules"][-1]["owner"] = ""
        with self.assertRaises(NamingPrecedenceError):
            NamingPrecedencePolicy.from_mapping(raw)

    def test_private_ascii_identifiers_supported_but_unicode_rejected(self):
        raw = sample()
        raw["rules"][-1]["selector"]["symbol"] = "__init__"
        p = NamingPrecedencePolicy.from_mapping(raw)
        source = SOURCE + "def __init__(): pass\n"
        sources = {"src/codeqa/physics/electron.py": source}
        self.assertEqual(p.resolve(**args(
            p, symbol="__init__", sources=sources,
            expected_source_sha256=sha256(source.encode()).hexdigest(),
        )).status, "EXCLUDE_CANDIDATE")
        with self.assertRaises(NamingPrecedenceError):
            p.resolve(**args(p, symbol="рlasma_density"))

    def test_absent_or_prefix_only_symbol_never_becomes_policy_candidate(self):
        p = NamingPrecedencePolicy.from_mapping(sample())
        for name in ("never_declared", "plasma"):
            with self.subTest(name=name):
                r = p.resolve(**args(p, symbol=name))
                self.assertEqual(r.status, "NOT_EVALUATED")
                self.assertEqual(r.reason, "symbol not lexically observed in selected source")
                self.assertTrue(r.human_review_required)
                self.assertFalse(r.semantic_proven)

    def test_comment_only_lexical_hit_does_not_prove_declaration(self):
        p = NamingPrecedencePolicy.from_mapping(sample())
        source = "# comment_only\n"
        sources = {"src/codeqa/physics/electron.py": source}
        r = p.resolve(**args(
            p, symbol="comment_only", sources=sources,
            expected_source_sha256=sha256(source.encode()).hexdigest(),
        ))
        self.assertEqual(r.status, "CHECK_CANDIDATE")
        self.assertFalse(r.semantic_proven)
        self.assertTrue(r.human_review_required)

    def test_lexical_only_not_policy_gate_or_source_mutation(self):
        p = NamingPrecedencePolicy.from_mapping(sample())
        original = deepcopy(SOURCES)
        result = p.resolve(**args(p))
        self.assertEqual(SOURCES, original)
        self.assertNotIn(result.status, {"PASS", "ALLOW", "SAFE_TO_RENAME"})
        self.assertTrue(result.human_review_required)


if __name__ == "__main__":
    unittest.main()
