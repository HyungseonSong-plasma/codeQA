"""Issue #144: pinned direct-import syntax and independent external caller gate."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json
import unittest

from codeqa.core.naming_import_scope_gate_v04 import (
    ImportScopeEvidenceError, audit_pinned_import_scope,
    classify_direct_import,
)
from codeqa.infrastructure.git import GitReader

ROOT = Path(__file__).resolve().parents[1]
CHARTER = ROOT / "fixtures/naming-governance/codeqa-import-scope-witness-v04.json"


class BoundedImportScopeGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.charter = json.loads(CHARTER.read_text(encoding="utf-8"))
        cls.reader = GitReader(ROOT)
        paths = [cls.charter["declaration"]["path"]] + [
            c["path"] for c in cls.charter["consumers"]]
        cls.sources = {p: cls.reader.read_file(cls.charter["source_commit"], p)
                       for p in paths}
        cls.result = audit_pinned_import_scope(cls.charter, sources=cls.sources)

    def test_real_internal_imports_bound_to_pinned_class_field_candidate(self):
        x = self.result
        self.assertEqual(x["selected_file_count"], 3)
        self.assertEqual(x["direct_import_witnesses"], 2)
        self.assertEqual([c["import_line"] for c in x["consumers"]], [12, 8])
        self.assertEqual(x["declaration_field_status"], "FIELD_CANDIDATE")
        self.assertEqual(x["source_role_scope"], "SOURCE_SHAPE_ADMISSIBLE_ONLY")
        self.assertTrue(all(c["status"] == "DIRECT_IMPORT_SYNTAX_WITNESSED"
                            for c in x["consumers"]))
        print("NAMING_IMPORT_SCOPE_GATE source_files=3 direct_imports=2 "
              "field=FIELD_CANDIDATE external=UNKNOWN "
              "semantic=UNKNOWN policy=NOT_ADOPTED rename=false")

    def test_external_and_semantic_authority_remains_blocked(self):
        x = self.result
        self.assertEqual(x["external_client_evidence"], "NOT_SUPPLIED")
        self.assertEqual(x["external_api_compatibility"], "UNKNOWN")
        self.assertEqual(x["reexport_graph"], "NOT_EVALUATED")
        self.assertEqual(x["transitive_binding_graph"], "NOT_EVALUATED")
        self.assertEqual(x["owner_approval"], "NOT_ADOPTED")
        self.assertEqual(x["glossary_policy"], "NOT_ADOPTED")
        self.assertEqual(x["semantic_policy_gate"], "UNKNOWN")
        self.assertFalse(x["rename_authorized"])
        for c in x["consumers"]:
            self.assertFalse(c["rename_authorized"])
            self.assertEqual(c["runtime_binding_identity"], "NOT_EVALUATED")
            self.assertEqual(c["external_consumer_compatibility"], "NOT_EVALUATED")

    def test_alias_wildcard_relative_conditional_and_reexport_do_not_pass(self):
        examples = (
            "from codeqa.core.complexity import ControlFlowObservation as Alias\n"
            "value = Alias\n",
            "from codeqa.core.complexity import *\n"
            "ControlFlowObservation\n",
            "from .complexity import ControlFlowObservation\n"
            "value = ControlFlowObservation\n",
            "if True:\n"
            "    from codeqa.core.complexity import ControlFlowObservation\n"
            "value = ControlFlowObservation\n",
            "from codeqa.core.complexity import ControlFlowObservation\n"
            "from other import ControlFlowObservation\nvalue = ControlFlowObservation\n",
            "from codeqa.core.complexity import ControlFlowObservation\n"
            "ControlFlowObservation = lambda: 0\n",
            "from codeqa.core.complexity import ControlFlowObservation\n"
            "exec('ControlFlowObservation = 1')\n"
            "value = ControlFlowObservation\n",
            "from codeqa.core.complexity import ControlFlowObservation\n"
            "from anything import *\nvalue = ControlFlowObservation\n",
        )
        for src in examples:
            with self.subTest(src=src[:52]):
                x = classify_direct_import(
                    src.encode(), path="src/codeqa/consumer.py",
                    symbol="ControlFlowObservation",
                    module="codeqa.core.complexity")
                self.assertEqual(x["status"], "UNKNOWN")
                self.assertFalse(x["rename_authorized"])

    def test_direct_synthetic_import_is_syntax_only(self):
        src = ("from codeqa.core.complexity import ControlFlowObservation\n"
               "item = ControlFlowObservation\n").encode()
        x = classify_direct_import(src, path="src/codeqa/consumer.py",
                                   symbol="ControlFlowObservation",
                                   module="codeqa.core.complexity")
        self.assertEqual(x["status"], "DIRECT_IMPORT_SYNTAX_WITNESSED")
        self.assertEqual(x["import_line"], 1)
        self.assertEqual(x["reexport_graph"], "NOT_EVALUATED")
        self.assertEqual(x["external_consumer_compatibility"], "NOT_EVALUATED")

    def test_missing_source_use_or_import_does_not_pass(self):
        for src in ("from codeqa.core.complexity import ControlFlowObservation\n",
                    "value = ControlFlowObservation\n", "x = 'ControlFlowObservation'\n",
                    "# from codeqa.core.complexity import ControlFlowObservation\n"):
            with self.subTest(source=src):
                x = classify_direct_import(src.encode(),
                    path="src/codeqa/consumer.py", symbol="ControlFlowObservation",
                    module="codeqa.core.complexity")
                self.assertEqual(x["status"], "UNKNOWN")

    def test_modified_blob_or_omitted_consumer_fails_closed(self):
        sources = dict(self.sources)
        target = self.charter["consumers"][0]["path"]
        sources[target] = sources[target].replace(
            b"ControlFlowObservation", b"ChangedObservation", 1)
        with self.assertRaises(ImportScopeEvidenceError):
            audit_pinned_import_scope(self.charter, sources=sources)
        sources = dict(self.sources)
        sources.pop(target)
        with self.assertRaises(ImportScopeEvidenceError):
            audit_pinned_import_scope(self.charter, sources=sources)

    def test_order_and_pinned_file_identity_cannot_drift(self):
        for change in (
            lambda p: p["consumers"].reverse(),
            lambda p: p["consumers"][0].update(import_line=20),
            lambda p: p["declaration"].update(line=11),
            lambda p: p["declaration"].update(blob_sha="0"*40),
            lambda p: p.update(source_commit="0"*40),
            lambda p: p.update(source_tree_sha="0"*40),
            lambda p: p["consumers"].append(deepcopy(p["consumers"][0])),
        ):
            modified = deepcopy(self.charter)
            change(modified)
            with self.assertRaises(ImportScopeEvidenceError):
                audit_pinned_import_scope(modified, sources=self.sources)

    def test_adoption_and_claimed_external_compatibility_fail_closed(self):
        for alteration in (
            lambda p: p.update(owner_approval="APPROVED"),
            lambda p: p.update(glossary_policy="ADOPTED"),
            lambda p: p.update(rename_authorized=True),
            lambda p: p.update(external_client_evidence="COMPATIBLE"),
            lambda p: p.update(semantic_pass=True),
        ):
            changed = deepcopy(self.charter)
            alteration(changed)
            with self.assertRaises(ImportScopeEvidenceError):
                audit_pinned_import_scope(changed, sources=self.sources)


if __name__ == "__main__":
    unittest.main()
