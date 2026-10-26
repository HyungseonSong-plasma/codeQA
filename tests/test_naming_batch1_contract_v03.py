"""#91: evidence-strengthening tests, not human or Naming policy approval.

All source references are syntactic candidates, NEVER a complete binding graph.
Runtime observations prove the current version's behavior, not external adoption.
"""
from __future__ import annotations

import ast
from copy import deepcopy
from dataclasses import FrozenInstanceError, asdict, fields
from hashlib import sha1, sha256
import inspect
import json
import os
from pathlib import Path
import unittest

from codeqa.core.naming_glossary import (
    GlossaryTerm, NamingGlossaryError, NamingGlossaryProfile, tokenize_identifier,
)
from codeqa.core.naming_review_worklist_v03 import (
    NamingReviewWorklistError, assess_review_worklist, build_review_worklist,
)
from codeqa.infrastructure.git import GitReader
from codeqa.pipeline.naming_snapshot_coverage_v03 import scan_pinned_git


ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "fixtures/naming-governance/codeqa-batch1-contract-evidence-v03.json"
PROPOSAL = ROOT / "fixtures/naming-governance/codeqa-ast-review-v03-proposal.json"


def _sample() -> dict:
    return {
        "schema_version": "0.1",
        "profile_id": "codeqa.naming.glossary.v0.1",
        "include_prefixes": ["src/"],
        "terms": [
            {"canonical": "time_step", "aliases": ["timestep"],
             "kinds": ["function", "parameter"]},
            {"canonical": "node_id", "aliases": ["nodeid"],
             "kinds": ["method", "field"]},
        ],
    }


class Batch1CompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = json.loads(PACKET.read_text(encoding="utf-8"))
        cls.proposal = json.loads(PROPOSAL.read_text(encoding="utf-8"))

    def test_exact_unsigned_human_claims_and_site_ids(self):
        packet = self.packet
        self.assertEqual(packet["schema_version"], "0.3-unsigned-batch1-contract-evidence")
        self.assertEqual(packet["issue"], 91)
        self.assertEqual(packet["human_comment"]["observed_github_author"],
                         "HyungseonSong-plasma")
        self.assertEqual(packet["human_comment"]["url"],
                         "https://github.com/HyungseonSong-plasma/codeQA/issues/91"
                         "#issuecomment-6414512106")
        self.assertFalse(packet["human_comment"]["github_identity_independently_authenticated_by_packet"])
        self.assertFalse(packet["human_comment"]["substantive_independent_human_review_completed"])
        self.assertEqual(packet["human_policy_adoption"], "NOT_ADOPTED")
        self.assertFalse(packet["automatic_rename_authorized"])
        self.assertFalse(packet["issue_close_authorized"])
        self.assertEqual(packet["external_consumer_coverage"], "OUT_OF_SCOPE")
        rows = build_review_worklist(self.proposal)["rows"]
        self.assertEqual([x["index"] for x in packet["cases"]], [11, 15, 25])
        for c in packet["cases"]:
            with self.subTest(i=c["index"]):
                row = rows[c["index"] - 1]
                self.assertEqual(c["site_id"], row["site_id"])
                self.assertEqual(
                    (c["name"], c["kind"], c["line"], c["owner"]),
                    (row["symbol"]["name"], row["symbol"]["kind"],
                     row["symbol"]["line"], row["symbol"]["owner"]),
                )
                self.assertEqual(c["human_decision"], {
                    11: "OBSERVATION_CONFIRMED",
                    15: "UNRESOLVED",
                    25: "OBSERVATION_CONFIRMED",
                }[c["index"]])
                self.assertEqual(c["decision_source_comment_url"],
                                 packet["human_amendment"]["amendment_comment_url"])
                self.assertEqual(c["ast_observation"], "AST_OBSERVED")
                self.assertTrue(c["known_reference_candidates"])
                self.assertTrue(c["remaining_unknown"])
        self.assertEqual(packet["source"]["sha256"], self.proposal["source"]["sha256"])
        self.assertEqual(packet["source"]["git_blob_sha"],
                         self.proposal["source"]["git_blob_sha"])
        self.assertEqual(packet["source"]["revision"], self.proposal["source"]["commit"])

    def test_review_scope_exclusions_cannot_upgrade_human_or_policy_decisions(self):
        packet = self.packet
        scope = packet["review_scope"]
        self.assertEqual(scope["decision_axis"], "PINNED_SOURCE_AST_OBSERVATION_ONLY")
        self.assertEqual(scope["authorized_limited_review"],
                         "SOURCE_DECLARATION_EXISTENCE_KIND_LINE_OWNER")
        self.assertEqual(
            {x["domain"] for x in scope["excluded_domains"]},
            {"EXTERNAL_CONSUMER_COMPATIBILITY",
             "DYNAMIC_AND_TRANSITIVE_BINDING_RESOLUTION",
             "API_RENAME_OR_CHANGE_IMPACT"},
        )
        self.assertEqual(len(scope["excluded_domains"]), 3)
        for excluded in scope["excluded_domains"]:
            self.assertEqual(excluded["status"], "OUT_OF_SCOPE")
            self.assertTrue(excluded["not_proven"])
        self.assertEqual(packet["external_consumer_coverage"], "OUT_OF_SCOPE")
        self.assertEqual(packet["dynamic_reference_coverage"], "OUT_OF_SCOPE")
        self.assertEqual(packet["api_change_impact_coverage"], "OUT_OF_SCOPE")
        self.assertEqual(scope["policy_applicability"], "NOT_EVALUATED")
        self.assertEqual(scope["semantic_equivalence"], "NOT_EVALUATED")
        self.assertEqual(scope["external_impact_safety"], "NOT_EVALUATED")
        self.assertTrue(scope["human_re_adjudication_pending"])
        self.assertTrue(scope["scope_does_not_satisfy_uncovered_issue_acceptance"])
        self.assertTrue(scope["out_of_scope_must_not_be_interpreted_as_pass"])
        self.assertEqual(packet["human_policy_adoption"], "NOT_ADOPTED")
        self.assertFalse(packet["automatic_rename_authorized"])
        self.assertFalse(packet["issue_close_authorized"])
        self.assertEqual([x["human_decision"] for x in packet["cases"]],
                         ["OBSERVATION_CONFIRMED", "UNRESOLVED",
                          "OBSERVATION_CONFIRMED"])


    def test_observed_amendment_is_source_scoped_not_a_policy_approval(self):
        """Project-owner issue comments are attributed evidence, not a final policy."""
        packet = self.packet
        change = packet["human_amendment"]
        self.assertEqual(change["source_type"],
                         "GITHUB_ISSUE_COMMENT_OBSERVED_NOT_CRYPTOGRAPHICALLY_SIGNED")
        self.assertEqual(change["observed_github_author"], "HyungseonSong-plasma")
        self.assertEqual(change["original_comment_url"], packet["human_comment"]["url"])
        self.assertEqual(change["amendment_comment_url"],
                         "https://github.com/HyungseonSong-plasma/codeQA/issues/91"
                         "#issuecomment-6415147582")
        self.assertEqual(change["decision_axis"], "PINNED_SOURCE_AST_OBSERVATION_ONLY")
        self.assertEqual(change["counts"], {
            "observation_confirmed": 4,
            "observation_rejected": 0,
            "unresolved": 1,
            "not_adjudicated": 45,
        })
        self.assertFalse(change["independent_human_signature_verified"])
        self.assertEqual(change["official_glossary_adoption"], "NOT_ADOPTED")
        self.assertEqual(change["semantic_policy_applicability"], "NOT_EVALUATED")
        self.assertFalse(change["automatic_rename_authorized"])
        self.assertFalse(change["issue_close_authorized"])
        self.assertEqual(packet["human_policy_adoption"], "NOT_ADOPTED")
        self.assertFalse(packet["automatic_rename_authorized"])
        self.assertFalse(packet["issue_close_authorized"])

        worklist = build_review_worklist(self.proposal)
        observed = change["observations"]
        self.assertEqual([d["index"] for d in observed], [1, 11, 13, 15, 25])
        for decision in observed:
            with self.subTest(index=decision["index"]):
                row = worklist["rows"][decision["index"] - 1]
                self.assertEqual(row["site_id"], decision["site_id"])
                self.assertEqual(row["group"], "original_candidates")
                self.assertIn(decision["review_comment_url"], (
                    change["original_comment_url"], change["amendment_comment_url"]))
                row.update(decision=decision["decision"],
                           reviewer_login=change["observed_github_author"],
                           review_comment_url=decision["review_comment_url"],
                           rationale=decision["rationale"])
        result = assess_review_worklist(self.proposal, worklist)
        self.assertEqual((result.total, result.claimed_decisions,
                          result.unresolved, result.remaining_without_decision),
                         (50, 5, 46, 45))
        self.assertEqual(result.status, "NOT_EVALUATED")
        self.assertEqual(result.independent_human_authentication, "NOT_EVALUATED")
        self.assertFalse(result.automatic_rename_authorized)

        for invalid in ("PASS", "OUT_OF_SCOPE", "NEGATIVE_CONFIRMED"):
            with self.subTest(invalid=invalid):
                changed = deepcopy(worklist)
                changed["rows"][14]["decision"] = invalid
                with self.assertRaises(NamingReviewWorklistError):
                    assess_review_worklist(self.proposal, changed)
        changed = deepcopy(worklist)
        changed["policy_adopted"] = True
        with self.assertRaises(NamingReviewWorklistError):
            assess_review_worklist(self.proposal, changed)

    def test_out_of_scope_is_not_a_human_observation_verdict(self):
        worklist = build_review_worklist(self.proposal)
        row = worklist["rows"][10]
        row.update({
            "decision": "OUT_OF_SCOPE",
            "reviewer_login": "HyungseonSong-plasma",
            "review_comment_url":
                "https://github.com/HyungseonSong-plasma/codeQA/issues/91"
                "#issuecomment-6414512106",
            "rationale": "External API and dynamic refs excluded from review",
        })
        with self.assertRaises(NamingReviewWorklistError):
            assess_review_worklist(self.proposal, worklist)

    def test_historical_git_bytes_blob_and_ast_declarations(self):
        witness = self.packet["source"]
        body = GitReader(ROOT).read_file(witness["revision"], witness["path"])
        self.assertEqual(sha256(body).hexdigest(), witness["sha256"])
        self.assertEqual(
            sha1(b"blob " + str(len(body)).encode() + b"\0" + body).hexdigest(),
            witness["git_blob_sha"],
        )
        tree = ast.parse(body.decode("utf-8"))
        token = next(n for n in tree.body
                     if isinstance(n, ast.FunctionDef) and n.name == "tokenize_identifier")
        term = next(n for n in tree.body
                    if isinstance(n, ast.ClassDef) and n.name == "GlossaryTerm")
        profile = next(n for n in tree.body
                       if isinstance(n, ast.ClassDef) and n.name == "NamingGlossaryProfile")
        field = next(n for n in term.body if isinstance(n, ast.AnnAssign)
                     and isinstance(n.target, ast.Name) and n.target.id == "canonical")
        method = next(n for n in profile.body if isinstance(n, ast.FunctionDef)
                      and n.name == "from_mapping")
        self.assertEqual((token.lineno, field.lineno, method.lineno), (19, 34, 47))
        self.assertEqual([a.arg for a in method.args.args], ["cls", "value"])
        self.assertTrue(any(isinstance(d, ast.Name) and d.id == "classmethod"
                            for d in method.decorator_list))
        self.assertEqual(self.packet["source"]["path"], "src/codeqa/core/naming_glossary.py")

    def test_tokenizer_runtime_edge_cases(self):
        samples = {
            "time_step": ("time", "step"),
            "nodeid": ("nodeid",),
            "readNodeID": ("read", "node", "id"),
            "ABC123": ("abc", "123"),
            "some__name": ("some", "name"),
            "": (),
            "alpha-beta": (),
            "μs": (),
        }
        for value, expected in samples.items():
            with self.subTest(value=value):
                self.assertEqual(tokenize_identifier(value), expected)
        for bad in (None, 3, [], object()):
            with self.subTest(bad=type(bad).__name__):
                with self.assertRaises(NamingGlossaryError):
                    tokenize_identifier(bad)

    def test_dataclass_field_constructor_serialization_frozen(self):
        self.assertEqual([f.name for f in fields(GlossaryTerm)],
                         ["canonical", "aliases", "kinds"])
        self.assertEqual(list(inspect.signature(GlossaryTerm).parameters),
                         ["canonical", "aliases", "kinds"])
        term = GlossaryTerm(canonical="time_step", aliases=("timestep",),
                            kinds=("parameter",))
        self.assertEqual(term.canonical, "time_step")
        self.assertEqual(asdict(term), {
            "canonical": "time_step", "aliases": ("timestep",),
            "kinds": ("parameter",),
        })
        with self.assertRaises(FrozenInstanceError):
            term.canonical = "different"
        with self.assertRaises(TypeError):
            GlossaryTerm(canonical="time_step", aliases=("timestep",),
                         kinds=("parameter",), extra="forbidden")

    def test_from_mapping_valid_contract_and_repeatability(self):
        self.assertIsInstance(
            NamingGlossaryProfile.__dict__["from_mapping"], classmethod)
        value = _sample()
        before = deepcopy(value)
        profile = NamingGlossaryProfile.from_mapping(value)
        self.assertIsInstance(profile, NamingGlossaryProfile)
        self.assertEqual(value, before)
        self.assertEqual(profile.schema_version, "0.1")
        self.assertEqual(tuple(t.canonical for t in profile.terms),
                         ("node_id", "time_step"))
        self.assertEqual(profile.include_prefixes, ("src/",))
        fingerprint = profile.fingerprint()
        self.assertEqual(len(fingerprint), 64)
        self.assertEqual(fingerprint, NamingGlossaryProfile.from_mapping(
            deepcopy(value)).fingerprint())
        self.assertEqual(asdict(profile)["terms"][0]["canonical"], "node_id")
        self.assertIn("canonical", asdict(profile)["terms"][0])

    def test_from_mapping_invalid_inputs_and_conflicting_aliases(self):
        changes = [
            lambda x: x.update({"unknown": 1}),
            lambda x: x.pop("terms"),
            lambda x: x.update({"schema_version": "0.2"}),
            lambda x: x.update({"profile_id": "wrong"}),
            lambda x: x.update({"include_prefixes": ["../outside/"]}),
            lambda x: x.update({"terms": []}),
            lambda x: x["terms"][0].update({"canonical": "TimeStep"}),
            lambda x: x["terms"][0].update({"aliases": ["timestep", "timestep"]}),
            lambda x: x["terms"][0].update({"kinds": ["invalid"]}),
            lambda x: x["terms"].append({
                "canonical": "another", "aliases": ["timestep"],
                "kinds": ["function"],
            }),
        ]
        for n, change in enumerate(changes):
            with self.subTest(n=n):
                packet = _sample()
                change(packet)
                with self.assertRaises(NamingGlossaryError):
                    NamingGlossaryProfile.from_mapping(packet)

    def test_reference_claim_is_not_a_full_binding_graph(self):
        self.assertEqual(
            self.packet["source_reference_classification"],
            "PINNED_AST_SYNTAX_CANDIDATES_NOT_RESOLVED_BINDING_GRAPH",
        )
        self.assertEqual(self.packet["runtime_contract_classification"],
                         "CURRENT_IMPLEMENTATION_BEHAVIOR_ONLY")
        # Syntactic same spelling may denote a different class or local object.
        fake = ast.parse(
            "class Other:\n"
            "    def from_mapping(self): pass\n"
            "x = Other()\n"
            "x.from_mapping()\n"
        )
        self.assertTrue(any(isinstance(n, ast.Attribute)
                            and n.attr == "from_mapping" for n in ast.walk(fake)))
        self.assertFalse(any(isinstance(n, ast.Name)
                             and n.id == "NamingGlossaryProfile" for n in ast.walk(fake)))

    def test_pinned_head_reference_candidates_in_full_selected_src(self):
        rev = os.environ.get("CODEQA_NAMING_PINNED_REV")
        if rev is None:
            self.skipTest("full pinned tree reference check requires exact CI SHA")
        repo = scan_pinned_git(ROOT, revision=rev)
        hashes = dict(repo.source_digests)
        reader = GitReader(ROOT)
        evaluator = "src/codeqa/evaluation/naming_glossary.py"
        self.assertIn(evaluator, hashes)
        body = reader.read_file(rev, evaluator)
        self.assertEqual(sha256(body).hexdigest(), hashes[evaluator])
        tree = ast.parse(body.decode("utf-8"))
        imports = [(node.lineno, alias.name)
                   for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
                   and node.module == "codeqa.core.naming_glossary"
                   for alias in node.names]
        self.assertIn((8, "tokenize_identifier"), imports)
        direct_calls = {n.lineno for n in ast.walk(tree)
                        if isinstance(n, ast.Call)
                        and isinstance(n.func, ast.Name)
                        and n.func.id == "tokenize_identifier"}
        self.assertTrue({71, 82}.issubset(direct_calls))
        field_reads = {n.lineno for n in ast.walk(tree)
                       if isinstance(n, ast.Attribute)
                       and n.attr == "canonical" and isinstance(n.ctx, ast.Load)}
        self.assertTrue({70, 73}.issubset(field_reads))
        tests_path = "tests/test_naming_glossary.py"
        tests_raw = reader.read_file(rev, tests_path)
        test_ast = ast.parse(tests_raw.decode("utf-8"))
        observed_test_calls = {n.lineno for n in ast.walk(test_ast)
                               if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                               and n.func.attr == "from_mapping"
                               and isinstance(n.func.value, ast.Name)
                               and n.func.value.id == "NamingGlossaryProfile"}
        self.assertIn(25, observed_test_calls)
        print(
            "NAMING_BATCH1_PINNED_REFERENCES",
            "revision=" + rev,
            "src_files=" + str(repo.examined_files),
            "tokenize_identifier_call_candidates=" + repr(sorted(direct_calls)),
            "canonical_attribute_candidates=" + repr(sorted(field_reads)),
            "profile_factory_test_call_candidates=" + repr(sorted(observed_test_calls)),
            "binding_and_external_consumers=NOT_EVALUATED",
        )


if __name__ == "__main__":
    unittest.main()
