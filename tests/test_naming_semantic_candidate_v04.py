"""Adversarial rule-based semantic candidate gating for #144, not policy adoption."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import unittest

from codeqa.core.naming_semantic_candidate_v04 import (
    SemanticCandidateError, SemanticCandidateRules,
)

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "fixtures/naming-governance/codeqa-semantic-candidate-v04.json"


def draft():
    return json.loads(POLICY.read_text(encoding="utf-8"))


def selected(name="time_step", kind="function", *, owner="", path="src/codeqa/core/m.py"):
    src = f"def {name}():\n    pass\n".encode()
    return dict(source=src, expected_sha256=sha256(src).hexdigest(),
                path=path, name=name, kind=kind, line=1, owner=owner)


class SemanticCandidateV04Tests(unittest.TestCase):
    def test_unscoped_owner_proposal_fails_closed(self):
        x = SemanticCandidateRules(draft()).assess(**selected())
        self.assertEqual((x.status, x.reason), ("UNKNOWN", "NO_EXPLICIT_ROLE_SCOPE"))
        self.assertFalse(x.semantic_proven)
        self.assertFalse(x.rename_authorized)

    def test_explicit_scope_only_yields_lexical_candidate(self):
        x = draft()
        x["scopes"] = [{"path_prefix": "src/codeqa/core", "language": "python",
                        "kind": "function", "role": "runtime"}]
        r = SemanticCandidateRules(x)
        one = r.assess(**selected())
        self.assertEqual((one.status, one.rule_id, one.owner_role),
                         ("LEXICAL_RULE_MATCH_CANDIDATE", "time_step", "runtime"))
        self.assertFalse(one.semantic_proven)
        self.assertFalse(one.rename_authorized)
        self.assertEqual(r.assess(**selected(name="timestep")).rule_id, "time_step")

    def test_scope_boundary_and_role_mismatch_unknown(self):
        x = draft()
        x["scopes"] = [{"path_prefix": "src/codeqa/core", "language": "python",
                        "kind": "function", "role": "physics"}]
        p = SemanticCandidateRules(x)
        self.assertEqual(p.assess(**selected()).reason, "DECLARED_ROLE_NOT_APPLICABLE")
        self.assertEqual(p.assess(**selected(path="src/codeqa/core2/m.py")).reason,
                         "NO_EXPLICIT_ROLE_SCOPE")

    def test_negative_controls_are_excluded_not_meaning_equivalence(self):
        x = draft()
        x["scopes"] = [{"path_prefix": "src", "language": "python",
                        "kind": "function", "role": "runtime"}]
        p = SemanticCandidateRules(x)
        o = p.assess(**selected(name="timestamp"))
        self.assertEqual((o.status, o.reason),
                         ("EXCLUDED", "EXPLICIT_NEGATIVE_INFERENCE_CONTROL"))
        self.assertFalse(o.semantic_proven)
        self.assertEqual(p.assess(**selected(name="time_stamp")).status, "EXCLUDED")
        self.assertEqual(p.assess(**selected(name="process_dt")).status, "UNKNOWN")

    def test_comment_string_and_mismatched_ast_never_count(self):
        x = draft()
        x["scopes"] = [{"path_prefix": "src", "language": "python",
                        "kind": "function", "role": "runtime"}]
        p = SemanticCandidateRules(x)
        raw = b"# time_step\nquoted = 'time_step'\ndef unrelated():\n    pass\n"
        params = selected()
        params.update(source=raw, expected_sha256=sha256(raw).hexdigest())
        self.assertEqual(p.assess(**params).reason, "NO_EXACT_AST_DECLARATION")
        params["name"] = "unrelated"
        params["line"] = 3
        self.assertEqual(p.assess(**params).reason, "NO_DECLARED_EXACT_TOKEN_RULE")

    def test_competing_terms_and_inferred_synonyms_are_unknown(self):
        x = draft()
        x["scopes"] = [{"path_prefix": "src", "language": "python",
                        "kind": "function", "role": "runtime"}]
        p = SemanticCandidateRules(x)
        self.assertEqual(p.assess(**selected(name="time_step_node_id")).reason,
                         "MULTIPLE_MATCHED_TERM_ROLES")
        self.assertEqual(p.assess(**selected(name="dt")).status, "EXCLUDED")
        self.assertEqual(p.assess(**selected(name="clock")).status, "UNKNOWN")

    def test_external_or_unparseable_or_digest_drift(self):
        x = draft()
        x["scopes"] = [{"path_prefix": "src", "language": "python",
                        "kind": "function", "role": "runtime"}]
        p = SemanticCandidateRules(x)
        self.assertEqual(p.assess(**selected(), external_contract=True).status, "UNKNOWN")
        args = selected()
        args["expected_sha256"] = "0" * 64
        with self.assertRaises(SemanticCandidateError):
            p.assess(**args)
        args = selected()
        args["source"] = b"def incomplete("
        args["expected_sha256"] = sha256(args["source"]).hexdigest()
        with self.assertRaises(SemanticCandidateError):
            p.assess(**args)

    def test_shadowed_and_duplicate_rules_rejected(self):
        x = draft()
        x["terms"][1]["aliases"].append("timestep")
        with self.assertRaises(SemanticCandidateError):
            SemanticCandidateRules(x)
        x = draft()
        x["excluded_inferences"].append("time_step")
        with self.assertRaises(SemanticCandidateError):
            SemanticCandidateRules(x)
        x = draft()
        x["scopes"] = [dict(path_prefix="src", language="python",
                            kind="function", role="runtime")]*2
        with self.assertRaises(SemanticCandidateError):
            SemanticCandidateRules(x)

    def test_no_policy_adoption_or_untrusted_token(self):
        x = draft()
        x["adoption_status"] = "APPROVED"
        with self.assertRaises(SemanticCandidateError):
            SemanticCandidateRules(x)
        x = draft()
        x["terms"][0]["aliases"].append("tɪmestep")
        with self.assertRaises(SemanticCandidateError):
            SemanticCandidateRules(x)
        x = draft()
        x["terms"][0]["meaning_status"] = "PROVEN"
        with self.assertRaises(SemanticCandidateError):
            SemanticCandidateRules(x)

    def test_method_parameter_and_field_scopes_are_distinct(self):
        x = draft()
        x["scopes"] = [
            {"path_prefix": "src", "language": "python",
             "kind": "method", "role": "data"},
            {"path_prefix": "src", "language": "python",
             "kind": "parameter", "role": "data"},
            {"path_prefix": "src", "language": "python",
             "kind": "field", "role": "data"},
        ]
        rules = SemanticCandidateRules(x)
        method = b"class Model:\n    def node_id(self):\n        pass\n"
        kw = dict(source=method, expected_sha256=sha256(method).hexdigest(),
                  path="src/model.py", name="node_id", kind="method", line=2,
                  owner="Model")
        self.assertEqual(rules.assess(**kw).status, "LEXICAL_RULE_MATCH_CANDIDATE")
        kw["kind"] = "function"
        self.assertEqual(rules.assess(**kw).status, "UNKNOWN")
        fn = b"def process(node_id: int):\n    pass\n"
        kw = dict(source=fn, expected_sha256=sha256(fn).hexdigest(),
                  path="src/model.py", name="node_id", kind="parameter", line=1,
                  owner="process")
        self.assertEqual(rules.assess(**kw).status, "LEXICAL_RULE_MATCH_CANDIDATE")
        for code, expected in (
            (b"class Model:\n    node_id: int\n", "UNKNOWN"),
            (b"from dataclasses import dataclass\n@dataclass\nclass Model:\n    node_id: int\n",
             "LEXICAL_RULE_MATCH_CANDIDATE"),
        ):
            line = 4 if b"dataclass" in code else 2
            kw = dict(source=code, expected_sha256=sha256(code).hexdigest(),
                      path="src/model.py", name="node_id", kind="field", line=line,
                      owner="Model")
            self.assertEqual(rules.assess(**kw).status, expected)

    def test_proposed_owner_terms_and_exclusions_not_adopted(self):
        owner = json.loads((ROOT / "fixtures/naming-governance/"
                            "codeqa-owner-policy-direction-v03-proposal.json")
                           .read_text(encoding="utf-8"))
        proposal = draft()
        self.assertEqual(owner["adoption_status"], "NOT_ADOPTED")
        self.assertEqual(proposal["adoption_status"], "NOT_ADOPTED")
        self.assertEqual(proposal["scopes"], [])
        original = {t["canonical"]: t for t in owner["terms"]}
        for term in proposal["terms"]:
            expected = original[term["canonical"]]
            self.assertEqual(term["aliases"], expected["explicit_noncanonical_aliases"])
            self.assertEqual(term["meaning_status"], "PENDING_DOMAIN_EVIDENCE")
            self.assertTrue(set(expected["excluded_inferred_synonyms"]).issubset(
                proposal["excluded_inferences"]))

    def test_actual_historical_source_does_not_gain_semantic_authority(self):
        from codeqa.infrastructure.git import GitReader
        source = GitReader(ROOT).read_file(
            "dfd94bb25d52642bb2e46766b1ebe074c2f82803",
            "src/codeqa/core/naming_glossary.py")
        self.assertEqual(sha256(source).hexdigest(),
                         "09b89f5f492f6d449257e1c6baa4bc1ea98dedd17e93b9f13ced1c62fbcd9d2c")
        rules = SemanticCandidateRules(draft())
        result = rules.assess(
            source=source, expected_sha256=sha256(source).hexdigest(),
            path="src/codeqa/core/naming_glossary.py",
            name="canonical", kind="field", line=34, owner="GlossaryTerm")
        self.assertEqual(result.status, "UNKNOWN")
        self.assertEqual(result.reason, "NO_EXPLICIT_ROLE_SCOPE")
        self.assertFalse(result.rename_authorized)
        self.assertFalse(result.semantic_proven)

    def test_source_role_site_and_scope_precedence(self):
        x = draft()
        x["scopes"] = [
            {"path_prefix": "src", "language": "python",
             "kind": "function", "role": "physics"},
            {"path_prefix": "src/codeqa/core", "language": "python",
             "kind": "function", "role": "runtime"},
        ]
        p = SemanticCandidateRules(x)
        self.assertEqual(p.assess(**selected()).status, "LEXICAL_RULE_MATCH_CANDIDATE")
        self.assertEqual(p.assess(**selected(path="src/other/m.py")).status, "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
