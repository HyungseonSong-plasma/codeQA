"""#144: thirteen pinned node_id source shapes, not a semantic policy PASS."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from pathlib import Path
import json
import unittest

from codeqa.core.naming_node_id_role_evidence_v04 import (
    NodeRoleEvidenceError, _shape, assess_pinned_node_role,
)
from codeqa.infrastructure.git import GitReader
from codeqa.pipeline.naming_scope_discovery_v04 import (
    discover_pinned_semantic_scope,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "fixtures/naming-governance/codeqa-source-scope-manifest-v04.json"
WITNESS = ROOT / "fixtures/naming-governance/codeqa-node-id-role-witness-v04.json"
POLICY = ROOT / "fixtures/naming-governance/codeqa-semantic-candidate-v04.json"


class PinnedNodeIdRoleEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.discovered = discover_pinned_semantic_scope(ROOT, cls.manifest)
        cls.fixture = json.loads(WITNESS.read_text(encoding="utf-8"))
        cls.reader = GitReader(ROOT)
        cls.sources = {
            path: cls.reader.read_file(cls.fixture["source_commit"], path)
            for path in {s["path"] for s in cls.fixture["sites"]}
        }
        cls.result = assess_pinned_node_role(cls.discovered, sources=cls.sources,
                                             fixture=cls.fixture)

    def test_all_thirteen_are_exact_witnessed_and_semantic_unapproved(self):
        a = self.result
        self.assertEqual(a["source_python_file_count"], 95)
        self.assertEqual(a["sites_checked"], 13)
        self.assertEqual((a["generator_patterns"], a["string_parameters"],
                          a["dataclass_field_candidates"]), (2, 2, 9))
        self.assertEqual(a["source_role_candidate"],
                         "internal_declaration_node_identity_candidate")
        self.assertEqual(a["semantic_status"], "NOT_EVALUATED")
        self.assertEqual(a["external_compatibility"], "NOT_EVALUATED")
        self.assertFalse(a["rename_authorized"])
        self.assertEqual(a["approved_scopes"], [])
        self.assertEqual(Counter(s["syntax_kind"] for s in a["sites"]), {
            "class_annotation": 9, "parameter": 2, "local_binding": 2,
        })
        self.assertTrue(all(s["meaning_approved"] is False and
                            s["path_scope_approved"] is False and
                            s["rename_authorized"] is False and
                            s["runtime_value_semantics"] == "NOT_EVALUATED"
                            for s in a["sites"]))
        print("NAMING_NODE_ID_ROLE_EVIDENCE "
              "sites=13 generator=2 parameter=2 dataclass_field_candidates=9 "
              "semantics=NOT_EVALUATED approved_scopes=0 rename=false")

    def test_checked_in_glossary_and_scope_remain_not_adopted(self):
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        self.assertEqual(policy["adoption_status"], "NOT_ADOPTED")
        self.assertEqual(policy["scopes"], [])
        self.assertEqual(self.fixture["approved_scopes"], [])
        self.assertEqual(self.fixture["semantic_policy"], "NOT_ADOPTED")
        self.assertFalse(self.fixture["rename_authorized"])

    def test_real_generator_shape_requires_exact_def_identifier(self):
        cases = [s for s in self.fixture["sites"]
                 if s["syntax_kind"] == "local_binding"]
        self.assertEqual(len(cases), 2)
        for s in cases:
            with self.subTest(path=s["path"], line=s["line"]):
                self.assertEqual(_shape(self.sources[s["path"]], s),
                                 "DECLARATION_ID_FSTRING_GENERATOR")
        good = (b"class _Calls:\n    def f(self, node):\n"
                b"        name = 'x'\n        node_id = f\"def::{self.path}::{name}@{node.lineno}:{node.col_offset}\"\n")
        row = {"path": "src/codeqa/temp.py", "line": 4, "owner": "_Calls.f",
               "name": "node_id", "syntax_kind": "local_binding"}
        self.assertEqual(_shape(good, row), "DECLARATION_ID_FSTRING_GENERATOR")
        with self.assertRaises(NodeRoleEvidenceError):
            _shape(good.replace(b"def::", b"tmp::"), row)
        with self.assertRaises(NodeRoleEvidenceError):
            _shape(good.replace(b"node_id = f", b"node_id = 1 + f"), row)

    def test_dataclass_annotation_must_be_string_and_stdlib_proven(self):
        good = (b"from dataclasses import dataclass\n@dataclass\n"
                b"class Witness:\n    node_id: str\n")
        row = {"path": "src/codeqa/witness.py", "line": 4, "owner": "Witness",
               "name": "node_id", "syntax_kind": "class_annotation"}
        self.assertEqual(_shape(good, row),
                         "STDLIB_DATACLASS_STRING_FIELD_CANDIDATE")
        with self.assertRaises(NodeRoleEvidenceError):
            _shape(good.replace(b"node_id: str", b"node_id: int"), row)
        with self.assertRaises(NodeRoleEvidenceError):
            _shape(b"class Witness:\n    node_id: str\n",
                   {**row, "line": 2})
        with self.assertRaises(NodeRoleEvidenceError):
            _shape(good.replace(b"@dataclass\n", b"@other\n"), row)

    def test_parameter_typed_string_not_untyped_or_wrong_owner(self):
        text = b"def f(node_id: str):\n    return node_id\n"
        site = {"path": "src/codeqa/temp.py", "line": 1, "owner": "f",
                "name": "node_id", "syntax_kind": "parameter"}
        self.assertEqual(_shape(text, site), "STRING_ANNOTATED_PARAMETER")
        with self.assertRaises(NodeRoleEvidenceError):
            _shape(text.replace(b"node_id: str", b"node_id: int"), site)
        with self.assertRaises(NodeRoleEvidenceError):
            _shape(text, {**site, "owner": "wrong"})

    def test_record_deletion_order_forgery_or_approval_fails(self):
        mutations = [
            lambda d: d["sites"].pop(),
            lambda d: d["sites"].reverse(),
            lambda d: d["sites"][0].update(role_candidate="domain_truth"),
            lambda d: d["sites"][0].update(evidence_rule="PASS"),
            lambda d: d["sites"][0].update(approved_scope=True),
            lambda d: d.update(approved_scopes=[{"path": "src/codeqa"}]),
            lambda d: d.update(semantic_policy="ADOPTED"),
            lambda d: d.update(rename_authorized=True),
            lambda d: d.update(source_commit="0" * 40),
            lambda d: d.update(source_tree_sha="0" * 40),
        ]
        for i, change in enumerate(mutations):
            with self.subTest(i=i):
                forged = deepcopy(self.fixture)
                change(forged)
                with self.assertRaises(NodeRoleEvidenceError):
                    assess_pinned_node_role(
                        self.discovered, sources=self.sources, fixture=forged)

    def test_source_or_snapshot_drift_blocks_role_evidence(self):
        sources = dict(self.sources)
        sources["src/codeqa/core/complexity.py"] = (
            sources["src/codeqa/core/complexity.py"].replace(
                b"node_id: str", b"node_id: int", 1))
        with self.assertRaises(NodeRoleEvidenceError):
            assess_pinned_node_role(self.discovered, sources=sources,
                                    fixture=self.fixture)
        corrupted = deepcopy(self.discovered)
        corrupted["proposed_path_role_scopes"][0]["lexical_owner"] = "Forged"
        with self.assertRaises(NodeRoleEvidenceError):
            assess_pinned_node_role(corrupted, sources=self.sources,
                                    fixture=self.fixture)


if __name__ == "__main__":
    unittest.main()
