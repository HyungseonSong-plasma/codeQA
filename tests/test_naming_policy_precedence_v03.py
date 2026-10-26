"""Adversarial #91 opt-in Naming policy precedence tests, not human approvals."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, replace
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
        self.assertEqual(r.observation, "LEXICAL_ONLY")
        self.assertEqual(asdict(r)["observation"], "LEXICAL_ONLY")
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

    def test_python_keyword_is_not_a_naming_candidate(self):
        p = NamingPrecedencePolicy.from_mapping(sample())
        with self.assertRaisesRegex(NamingPrecedenceError, "Python keyword"):
            p.resolve(**args(p, symbol="def"))

    def test_nonportable_source_selector_paths_rejected(self):
        p = NamingPrecedencePolicy.from_mapping(sample())
        for bad in ("src/codeqa/physics/unsafe:stream.py",
                    "src/codeqa/physics/trailing./file.py",
                    "src/codeqa/physics/name /file.py"):
            with self.subTest(path=bad):
                with self.assertRaisesRegex(NamingPrecedenceError, "source path"):
                    p.resolve(**args(p, path=bad))
        raw = sample()
        raw["rules"][3]["selector"]["path_prefix"] = "src/codeqa/physics:stream"
        with self.assertRaisesRegex(NamingPrecedenceError, "source path"):
            NamingPrecedencePolicy.from_mapping(raw)

    def test_absent_or_prefix_only_symbol_never_becomes_policy_candidate(self):
        p = NamingPrecedencePolicy.from_mapping(sample())
        for name in ("never_declared", "plasma"):
            with self.subTest(name=name):
                r = p.resolve(**args(p, symbol=name))
                self.assertEqual(r.status, "NOT_EVALUATED")
                self.assertEqual(r.reason, "symbol not lexically observed in selected source")
                self.assertEqual(r.observation, "NOT_OBSERVED")
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
        self.assertEqual(r.observation, "LEXICAL_ONLY")
        self.assertFalse(r.semantic_proven)
        self.assertTrue(r.human_review_required)

    def test_string_only_and_missing_scope_remain_lexical_only(self):
        p = NamingPrecedencePolicy.from_mapping(sample())
        source = 'note = "comment_only"\n'
        r = p.resolve(**args(
            p, symbol="comment_only", sources={"src/codeqa/physics/electron.py": source},
            expected_source_sha256=sha256(source.encode()).hexdigest(),
        ))
        self.assertEqual(r.status, "CHECK_CANDIDATE")
        self.assertEqual(asdict(r)["observation"], "LEXICAL_ONLY")
        self.assertFalse(r.semantic_proven)
        # A lexical hit outside the explicitly allowed symbol kind is not a
        # policy selection, but the token is still only a lexical observation.
        no_scope = p.resolve(**args(p, symbol_kind="parameter"))
        self.assertEqual(no_scope.status, "NOT_EVALUATED")
        self.assertEqual(no_scope.observation, "LEXICAL_ONLY")
        self.assertTrue(no_scope.human_review_required)

    def test_lexical_only_not_policy_gate_or_source_mutation(self):
        p = NamingPrecedencePolicy.from_mapping(sample())
        original = deepcopy(SOURCES)
        result = p.resolve(**args(p))
        self.assertEqual(SOURCES, original)
        self.assertNotIn(result.status, {"PASS", "ALLOW", "SAFE_TO_RENAME"})
        self.assertTrue(result.human_review_required)


class NamingASTReviewOwnerDecisionTests(unittest.TestCase):
    """Pinned structural evidence; deliberately no human inventory signature."""

    @classmethod
    def setUpClass(cls):
        from pathlib import Path
        from codeqa.infrastructure.git import GitReader
        from codeqa.core.naming_declaration_evidence_v03 import observe_pinned_python
        cls.root = Path(__file__).resolve().parents[1]
        cls.fixture = json.loads((cls.root / "fixtures/naming-governance/"
            "codeqa-python-inventory-review-candidates-v02.json").read_text(encoding="utf-8"))
        cls.proposal = json.loads((cls.root / "fixtures/naming-governance/"
            "codeqa-owner-policy-direction-v03-proposal.json").read_text(encoding="utf-8"))
        cls.source = GitReader(cls.root).read_file(
            cls.fixture["source_commit"], cls.fixture["source_path"])
        cls.review = observe_pinned_python(
            cls.source, expected_sha256=cls.fixture["source_sha256"])

    def test_all_26_are_observations_but_three_decorators_are_not_identifiers(self):
        outcomes = [self.review.classify_candidate(c)
                    for c in self.fixture["candidates"]]
        self.assertEqual(len(outcomes), 26)
        self.assertEqual(outcomes.count("AST_OBSERVED"), 23)
        self.assertEqual(outcomes.count("SYNTAX_ONLY"), 3)
        self.assertNotIn("NOT_EVALUATED", outcomes)
        self.assertFalse(self.review.semantic_proven)
        self.assertTrue(self.review.human_review_required)
        self.assertEqual(self.review.review_status, "PENDING_FINAL_ADJUDICATION")
        self.assertEqual({(d.callee, d.line) for d in self.review.decorators},
                         {("dataclass", 32), ("dataclass", 39), ("classmethod", 46)})

    def test_parameter_and_local_scope_do_not_conflate_homonyms(self):
        sites = {(d.name, d.kind, d.line, d.owner) for d in self.review.declarations}
        for key in (("name", "parameter", 19, "tokenize_identifier"),
                    ("cls", "parameter", 47, "NamingGlossaryProfile.from_mapping"),
                    ("value", "parameter", 47, "NamingGlossaryProfile.from_mapping"),
                    ("self", "parameter", 100, "NamingGlossaryProfile.fingerprint"),
                    ("terms", "local_binding", 64, "NamingGlossaryProfile.from_mapping"),
                    ("terms", "declared_field", 44, "NamingGlossaryProfile"),
                    ("segment", "loop_binding", 23, "tokenize_identifier"),
                    ("k", "loop_binding", 89, "NamingGlossaryProfile.from_mapping"),
                    ("value", "local_binding", 101, "NamingGlossaryProfile.fingerprint")):
            with self.subTest(site=key):
                self.assertIn(key, sites)
        self.assertFalse(next(d for d in self.review.declarations
            if d.name == "terms" and d.line == 64).eligible_kind)
        self.assertTrue(next(d for d in self.review.declarations
            if d.name == "terms" and d.line == 44).eligible_kind)

    def test_all_17_grok_omission_candidates_are_scope_specific_ast_sites(self):
        # AI candidate omissions are AST observations, not algorithmic FN
        # unless the extractor's declared coverage includes their kinds.
        sites = {(d.name, d.kind, d.line, d.owner): d
                 for d in self.review.declarations}
        owner = "NamingGlossaryProfile.from_mapping"
        expected = [
            ("name", "parameter", 19, "tokenize_identifier"),
            ("cls", "parameter", 47, owner),
            ("value", "parameter", 47, owner),
            ("self", "parameter", 100, "NamingGlossaryProfile.fingerprint"),
            ("prefixes", "local_binding", 54, owner),
            ("values", "local_binding", 61, owner),
            ("terms", "local_binding", 64, owner),
            ("ownership", "local_binding", 65, owner),
            ("allowed", "local_binding", 66, owner),
            ("keys", "local_binding", 94, owner),
            ("value", "local_binding", 101, "NamingGlossaryProfile.fingerprint"),
            ("segment", "loop_binding", 23, "tokenize_identifier"),
            ("matched", "local_binding", 25, "tokenize_identifier"),
            ("item", "loop_binding", 67, owner),
            ("phrase", "loop_binding", 82, owner),
            ("k", "loop_binding", 89, owner),
            ("key", "local_binding", 90, owner),
        ]
        self.assertEqual(len(expected), 17)
        for key in expected:
            with self.subTest(site=key):
                self.assertIn(key, sites)
                if key[1] in {"local_binding", "loop_binding"}:
                    self.assertFalse(sites[key].eligible_kind)
        future = next(d for d in self.review.declarations
                      if d.name == "annotations" and d.line == 2)
        self.assertEqual(future.kind, "import_binding")
        self.assertFalse(future.eligible_kind)
        self.assertFalse(next(d for d in self.review.declarations
            if d.name == "TOKEN" and d.line == 16).eligible_kind)

    def test_no_lexical_comment_string_attribute_or_decorator_promotion(self):
        from codeqa.core.naming_declaration_evidence_v03 import observe_pinned_python
        source = b'# phantom\nmessage = "phantom"\nclass C:\n    @factory(enabled=True)\n    def f(self):\n        self.phantom = 1\n'
        review = observe_pinned_python(source, expected_sha256=sha256(source).hexdigest())
        for name, kind, line, owner in (
            ("phantom", "function", 1, ""),
            ("phantom", "declared_field", 6, "C"),
            ("factory(enabled=True)", "method", 4, "C"),
            ("f", "method", 5, ""),
        ):
            self.assertEqual(review.classify_candidate(
                {"name": name, "kind": kind, "line": line, "owner": owner}),
                "NOT_EVALUATED")
        self.assertEqual(review.classify_candidate(
            {"name": "factory(enabled=True)", "kind": "decorator", "line": 4,
             "owner": "f"}), "SYNTAX_ONLY")
        self.assertEqual(review.classify_candidate(
            {"name": "f", "kind": "method", "line": 5, "owner": "C"}),
            "AST_OBSERVED")

    def test_decorator_expression_literal_whitespace_cannot_be_erased(self):
        from codeqa.core.naming_declaration_evidence_v03 import observe_pinned_python
        source = b'@tag(label="a b")\ndef f(): pass\n'
        review = observe_pinned_python(source, expected_sha256=sha256(source).hexdigest())
        for expression, expected in (('tag(label="a b")', "SYNTAX_ONLY"),
                                     ('tag(label="ab")', "NOT_EVALUATED"),
                                     ('tag(label="a  b")', "NOT_EVALUATED"),
                                     ("tag(label=", "NOT_EVALUATED")):
            with self.subTest(expression=expression):
                self.assertEqual(review.classify_candidate({
                    "name": expression, "kind": "decorator", "line": 1, "owner": "f",
                }), expected)

    def test_stale_unparseable_and_malformed_evidence_fail_closed(self):
        from codeqa.core.naming_declaration_evidence_v03 import (
            DeclarationEvidenceError, observe_pinned_python)
        with self.assertRaises(DeclarationEvidenceError):
            observe_pinned_python(self.source + b"\n# drift",
                expected_sha256=self.fixture["source_sha256"])
        with self.assertRaises(DeclarationEvidenceError):
            observe_pinned_python(b"def x(: pass", expected_sha256=sha256(b"def x(: pass").hexdigest())
        with self.assertRaises(DeclarationEvidenceError):
            self.review.classify_candidate({"name": "x"})
        with self.assertRaises(DeclarationEvidenceError):
            observe_pinned_python(self.source, expected_sha256="0"*64)

    def test_owner_policy_is_proposal_only_and_opt_in(self):
        p = self.proposal
        self.assertEqual(p["review_status"], "PENDING_FINAL_ADJUDICATION")
        self.assertEqual(p["adoption_status"], "NOT_ADOPTED")
        self.assertEqual(p["owner_decision_url"].split("#")[-1], "issuecomment-6413057026")
        self.assertEqual([(t["canonical"], t["explicit_noncanonical_aliases"])
                          for t in p["terms"]],
                         [("time_step", ["timestep"]), ("node_id", ["nodeid"])])
        self.assertEqual(p["applicability"]["language"], "python")
        self.assertEqual(p["applicability"]["mode"], "EXPLICIT_OPT_IN_ONLY")
        self.assertEqual(p["applicability"]["path_scopes"], [])
        self.assertEqual(p["governance"]["review_interval_days"], 180)
        self.assertIsNone(p["governance"]["adoption_date"])
        self.assertIsNone(p["declaration_ground_truth"]["inventory_human_signature"])
        self.assertFalse(p["safety"]["automatic_rename_authorized"])
        self.assertFalse(p["safety"]["pr_merge_authorized"])
        self.assertFalse(p["safety"]["issue_closure_authorized"])
        self.assertIn("timestamp", p["terms"][0]["excluded_inferred_synonyms"])
        self.assertFalse(p["safety"]["check_candidate_is_pass"])


if __name__ == "__main__":
    unittest.main()
