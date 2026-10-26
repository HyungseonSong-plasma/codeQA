"""#144: pinned full-source path denominator and no inferred semantic owners."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import unittest

from codeqa.core.naming_scope_discovery_v04 import (
    ScopeDiscoveryError, scan_explicit_spellings,
)
from codeqa.pipeline.naming_scope_discovery_v04 import (
    ScopeEvidenceError, discover_pinned_semantic_scope,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "fixtures/naming-governance/codeqa-source-scope-manifest-v04.json"
POLICY = ROOT / "fixtures/naming-governance/codeqa-semantic-candidate-v04.json"
TARGETS = ("time_step", "timestep", "node_id", "nodeid")


class PinnedScopeDiscoveryV04Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.packet = discover_pinned_semantic_scope(ROOT, cls.manifest)

    def test_complete_immutable_python_source_denominator(self):
        p = self.packet
        self.assertEqual(p["source_commit"],
                         "667a5f17f9890c5588d4f1c8ae079aba241501f3")
        self.assertEqual(p["source_tree_sha"],
                         "e9a78ccc3a5ccf75f6ee4818289549f39f526d2d")
        self.assertEqual(p["selected_source_file_count"], 95)
        self.assertEqual(p["files_scanned"], 95)
        self.assertEqual(p["ast_parsed_file_count"], 95)
        self.assertEqual(len(p["file_evidence"]), 95)
        self.assertEqual(p["source_observation_gate"], "PASS")
        self.assertEqual(p["semantic_policy_gate"], "UNKNOWN")
        self.assertEqual([f["path"] for f in p["file_evidence"]],
                         sorted(f["path"] for f in self.manifest["files"]))
        self.assertTrue(all(f["ast_parse"] == "PASS" for f in p["file_evidence"]))
        print("NAMING_SCOPE_DISCOVERY "
              f"selected_paths={p['selected_source_file_count']} "
              f"ast_scanned={p['ast_parsed_file_count']} "
              f"target_ast_sites={p['exact_ast_spelling_count']} "
              f"declaration_sites={p['structural_declaration_candidate_count']} "
              f"semantic_policy_gate={p['semantic_policy_gate']} "
              f"role_scopes_approved=0")

    def test_exact_ast_sites_never_induce_approved_owners(self):
        p = self.packet
        self.assertEqual(
            p["exact_ast_spelling_count"],
            len(p["lexical_site_evidence"]))
        self.assertEqual(
            p["structural_declaration_candidate_count"],
            len(p["proposed_path_role_scopes"]))
        self.assertEqual(p["policy_adoption"], "NOT_ADOPTED")
        self.assertEqual(p["semantic_meaning"], "NOT_EVALUATED")
        self.assertEqual(p["source_reference_completeness"], "NOT_EVALUATED")
        self.assertEqual(p["external_api_compatibility"], "NOT_EVALUATED")
        self.assertFalse(p["automatic_rename_authorized"])
        for row in p["lexical_site_evidence"]:
            self.assertIn(row["name"], TARGETS)
            self.assertFalse(row["semantic_proven"])
            self.assertFalse(row["approved_path_scope"])
            self.assertFalse(row["rename_authorized"])
            self.assertEqual(row["role_evidence"], "NOT_EVALUATED")
        for row in p["proposed_path_role_scopes"]:
            self.assertEqual(row["role"], "UNKNOWN")
            self.assertFalse(row["approved_scope"])

    def test_candidate_policy_does_not_gain_guessed_path_scopes(self):
        fixture = json.loads(POLICY.read_text(encoding="utf-8"))
        self.assertEqual(fixture["adoption_status"], "NOT_ADOPTED")
        self.assertEqual(fixture["scopes"], [])
        observed = [
            x["canonical"] for x in fixture["terms"]
        ]
        self.assertEqual(observed, ["time_step", "node_id"])
        self.assertEqual(tuple(self.manifest["target_spellings"]), TARGETS)
        self.assertEqual(self.manifest["applied_role_scopes"], [])

    def test_missing_or_swapped_pinned_path_fails_closed(self):
        altered = deepcopy(self.manifest)
        altered["files"].pop()
        with self.assertRaisesRegex(ScopeEvidenceError, "denominator"):
            discover_pinned_semantic_scope(ROOT, altered)
        altered = deepcopy(self.manifest)
        altered["files"][0]["git_blob_sha"] = "0" * 40
        with self.assertRaises(ScopeEvidenceError):
            discover_pinned_semantic_scope(ROOT, altered)
        altered = deepcopy(self.manifest)
        altered["files"].append(deepcopy(altered["files"][0]))
        with self.assertRaises(ScopeEvidenceError):
            discover_pinned_semantic_scope(ROOT, altered)

    def test_wrong_source_revision_role_or_target_fails_closed(self):
        for change in (
            lambda a: a.update(source_commit="0" * 40),
            lambda a: a.update(source_tree_sha="0" * 40),
            lambda a: a.update(observed_semantics="PASS"),
            lambda a: a.update(automatic_rename_authorized=True),
            lambda a: a.update(applied_role_scopes=[{"path_prefix": "src"}]),
            lambda a: a.update(target_spellings=["node_id"]),
            lambda a: a.update(coverage_claim="COMPLETE_BINDING_GRAPH"),
        ):
            with self.subTest(change=str(change)):
                data = deepcopy(self.manifest)
                change(data)
                with self.assertRaises(ScopeEvidenceError):
                    discover_pinned_semantic_scope(ROOT, data)

    def test_ast_synthetic_sites_keep_distinct_kinds_and_owners(self):
        text = (
            "def time_step(node_id: int):\n"
            "    return node_id\n"
            "class C:\n"
            "    node_id: int\n"
            "    def timestep(self, nodeid):\n"
            "        return self.node_id\n"
            "alias = 'time_step'\n"
        )
        rows = scan_explicit_spellings(
            text.encode(), path="src/codeqa/example.py", targets=TARGETS)
        kinds = {(r["name"], r["line"], r["owner"], r["source_kind"])
                 for r in rows}
        self.assertIn(("time_step", 1, "", "function"), kinds)
        self.assertIn(("node_id", 1, "time_step", "parameter"), kinds)
        self.assertIn(("node_id", 4, "C", "class_annotation"), kinds)
        self.assertIn(("timestep", 5, "C", "method"), kinds)
        self.assertIn(("nodeid", 5, "C.timestep", "parameter"), kinds)
        self.assertIn(("node_id", 6, "C.timestep", "attribute_unresolved"), kinds)
        self.assertFalse(any(r["source_kind"] == "field" for r in rows))
        self.assertEqual({r["source_sha256"] for r in rows},
                         {sha256(text.encode()).hexdigest()})
        self.assertTrue(all(r["role_evidence"] == "NOT_EVALUATED" for r in rows))

    def test_no_comment_or_string_only_identifiers_as_declarations(self):
        text = b"# node_id\nlabel = 'time_step'\ntext = 'nodeid'\n"
        self.assertEqual(
            scan_explicit_spellings(text, path="src/codeqa/example.py",
                                    targets=TARGETS), ())

    def test_unsafe_lexical_targets_or_broken_ast_rejected(self):
        for target in ("nöde_id", "NodeID", "a__b", "../node_id"):
            with self.subTest(target=target):
                with self.assertRaises(ScopeDiscoveryError):
                    scan_explicit_spellings(
                        b"node_id = 1\n", path="src/codeqa/example.py",
                        targets=(target,))
        with self.assertRaises(ScopeDiscoveryError):
            scan_explicit_spellings(
                b"def incomplete(", path="src/codeqa/example.py",
                targets=TARGETS)
        with self.assertRaises(ScopeDiscoveryError):
            scan_explicit_spellings(
                b"node_id = 1\n", path="src/codeqa/../escape.py",
                targets=TARGETS)


if __name__ == "__main__":
    unittest.main()
