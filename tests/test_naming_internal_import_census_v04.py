"""Issue #144: pinned internal import/reexport syntax evidence; external #147 deferred."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from codeqa.core.naming_internal_import_graph_v04 import (
    InternalImportGraphError, classify_static_import_chains,
    module_for_path, resolve_from, scan_module_imports,
)
from codeqa.pipeline.naming_internal_import_census_v04 import (
    InternalImportCensusError, audit_pinned_internal_imports,
)

ROOT = Path(__file__).resolve().parents[1]
CHARTER = ROOT / "fixtures/naming-governance/codeqa-internal-graph-charter-v04.json"


def _scan(path: str, code: str) -> dict:
    return scan_module_imports(code.encode("utf-8"), path=path)


class InternalImportCensusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.charter = json.loads(CHARTER.read_text(encoding="utf-8"))
        cls.actual = audit_pinned_internal_imports(ROOT, cls.charter)

    def test_all_100_real_tracked_source_files_have_sha_and_ast(self):
        x = self.actual
        self.assertEqual(x["selected_source_files"], 100)
        self.assertEqual(x["ast_parsed_files"], 100)
        self.assertEqual(x["total_import_statements"], 618)
        self.assertEqual(len(x["target_graph"]["target_from_import_edges"]), 2)
        self.assertEqual(x["target_graph"]["syntax_candidate_edges"], 2)
        self.assertEqual(x["target_graph"]["unresolved_target_edges"], 0)
        self.assertEqual(len(x["source_file_evidence"]), 100)
        self.assertEqual(len({r["path"] for r in x["source_file_evidence"]}), 100)
        self.assertTrue(all(r["ast_parse"] == "PASS" and
                            len(r["git_blob_sha"]) == 40 and
                            len(r["source_sha256"]) == 64
                            for r in x["source_file_evidence"]))
        self.assertEqual(x["root_field_role"],
                         "STDLIB_DATACLASS_FIELD_CANDIDATE")
        print("NAMING_INTERNAL_IMPORT_CENSUS "
              f"files={x['selected_source_files']} "
              f"import_statements={x['total_import_statements']} "
              f"target_edges={len(x['target_graph']['target_from_import_edges'])} "
              f"static_candidates={x['target_graph']['syntax_candidate_edges']} "
              f"uncertain_edges={x['target_graph']['unresolved_target_edges']} "
              f"external=DEFERRED_ISSUE_147 policy=NOT_ADOPTED")

    def test_two_historic_real_direct_source_clients_are_preserved(self):
        x = self.actual["target_graph"]
        self.assertIn("codeqa.core.complexity",
                      x["source_syntax_chain_modules"])
        assert_paths = {
            ("src/codeqa/adapters/python_complexity.py", 12),
            ("src/codeqa/evaluation/complexity.py", 8),
        }
        observed = {(e["path"], e["line"])
                    for e in x["target_from_import_edges"]
                    if e["source_module"] == "codeqa.core.complexity" and
                    e["syntax"] == "TOP_LEVEL_FROM" and
                    e["provenance"] == "DIRECT_OR_CHAINED_IMPORT_SYNTAX_CANDIDATE"}
        self.assertTrue(assert_paths.issubset(observed))
        self.assertTrue(all(e["runtime_binding_verified"] is False
                            and e["semantic_approval"] is False
                            and e["rename_authorized"] is False
                            for e in x["target_from_import_edges"]))

    def test_transitive_reexport_is_only_source_syntax_candidate(self):
        a = _scan("src/codeqa/core/complexity.py",
                  "class ControlFlowObservation: pass\n")
        b = _scan("src/codeqa/core/bridge.py",
                  "from codeqa.core.complexity import ControlFlowObservation\n"
                  "__all__ = ['ControlFlowObservation']\n")
        c = _scan("src/codeqa/evaluation/client.py",
                  "from codeqa.core.bridge import ControlFlowObservation\n"
                  "entry = ControlFlowObservation\n")
        graph = classify_static_import_chains({
            x["module"]: x for x in (a,b,c)})
        self.assertEqual(graph["syntax_candidate_edges"], 2)
        self.assertIn("codeqa.core.bridge", graph["source_syntax_chain_modules"])
        self.assertIn("codeqa.evaluation.client", graph["source_syntax_chain_modules"])
        self.assertEqual(graph["graph_completeness"], "NOT_EVALUATED")
        self.assertEqual(graph["runtime_symbol_identity"], "NOT_EVALUATED")

    def test_relative_internal_import_resolution_and_bad_depth(self):
        self.assertEqual(resolve_from("complexity", path="src/codeqa/core/bridge.py",
                                      level=1), "codeqa.core.complexity")
        self.assertEqual(resolve_from("complexity", path="src/codeqa/core/bridge.py",
                                      level=2), "codeqa.complexity")
        self.assertIsNone(resolve_from("complexity", path="src/codeqa/core/bridge.py",
                                       level=4))
        self.assertEqual(module_for_path("src/codeqa/core/__init__.py"), "codeqa.core")
        with self.assertRaises(InternalImportGraphError):
            module_for_path("src/codeqa/../bad.py")

    def test_alias_rebinding_dynamic_star_and_conditional_imports_stay_unknown(self):
        root = _scan("src/codeqa/core/complexity.py",
                     "class ControlFlowObservation: pass\n")
        suspicious = [
            "from codeqa.core.complexity import ControlFlowObservation as C\n",
            "from codeqa.core.complexity import ControlFlowObservation\n"
            "ControlFlowObservation = object\n",
            "def f():\n"
            "    from codeqa.core.complexity import ControlFlowObservation\n",
            "if True:\n"
            "    from codeqa.core.complexity import ControlFlowObservation\n",
            "from codeqa.core.complexity import ControlFlowObservation\n"
            "from thirdparty import *\n",
            "from codeqa.core.complexity import ControlFlowObservation\n"
            "exec('ControlFlowObservation = None')\n",
            "from codeqa.core.complexity import ControlFlowObservation\n"
            "def __getattr__(name): return 0\n",
        ]
        for s in suspicious:
            with self.subTest(s=s[:40]):
                candidate = _scan("src/codeqa/core/client.py", s)
                graph = classify_static_import_chains({
                    root["module"]: root, candidate["module"]: candidate})
                self.assertEqual(graph["syntax_candidate_edges"], 0)
                self.assertEqual(graph["runtime_symbol_identity"], "NOT_EVALUATED")

    def test_competing_same_symbol_module_bindings_block_provenance(self):
        root = _scan("src/codeqa/core/complexity.py",
                     "class ControlFlowObservation: pass\n")
        specimens = [
            "from codeqa.core.complexity import ControlFlowObservation\n"
            "from another import ControlFlowObservation\n",
            "from another import ControlFlowObservation\n"
            "from codeqa.core.complexity import ControlFlowObservation\n",
            "from codeqa.core.complexity import ControlFlowObservation\n"
            "from codeqa.core.complexity import ControlFlowObservation\n",
            "from codeqa.core.complexity import ControlFlowObservation\n"
            "import other as ControlFlowObservation\n",
            "from codeqa.core.complexity import ControlFlowObservation\n"
            "(ControlFlowObservation, ignore) = (None, 0)\n",
            "from codeqa.core.complexity import ControlFlowObservation\n"
            "del ControlFlowObservation\n",
            "from codeqa.core.complexity import ControlFlowObservation\n"
            "for ControlFlowObservation in range(2): pass\n",
            "from codeqa.core.complexity import ControlFlowObservation\n"
            "if flag:\n    ControlFlowObservation = None\n",
            "from codeqa.core.complexity import ControlFlowObservation\n"
            "if (ControlFlowObservation := object()): pass\n",
            "from codeqa.core.complexity import ControlFlowObservation\n"
            "def f():\n    global ControlFlowObservation\n"
            "    ControlFlowObservation = None\n",
        ]
        for code in specimens:
            with self.subTest(code=code[:65]):
                client = _scan("src/codeqa/core/client.py", code)
                graph = classify_static_import_chains({
                    entry["module"]: entry for entry in (root, client)})
                self.assertEqual(graph["syntax_candidate_edges"], 0)
                self.assertNotIn("codeqa.core.client",
                                 graph["source_syntax_chain_modules"])
                self.assertEqual(graph["runtime_symbol_identity"], "NOT_EVALUATED")

    def test_nested_local_shadow_does_not_rebind_module_level(self):
        root = _scan("src/codeqa/core/complexity.py",
                     "class ControlFlowObservation: pass\n")
        client = _scan("src/codeqa/core/client.py",
                       "from codeqa.core.complexity import ControlFlowObservation\n"
                       "def use():\n"
                       "    ControlFlowObservation = 'local'\n"
                       "    return ControlFlowObservation\n")
        graph = classify_static_import_chains({
            entry["module"]: entry for entry in (root, client)})
        self.assertEqual(graph["syntax_candidate_edges"], 1)
        self.assertEqual(graph["runtime_symbol_identity"], "NOT_EVALUATED")

    def test_cycles_and_non_provenance_chains_are_not_silently_proven(self):
        root = _scan("src/codeqa/core/complexity.py",
                     "class ControlFlowObservation: pass\n")
        first = _scan("src/codeqa/core/a.py",
                      "from codeqa.core.b import ControlFlowObservation\n")
        second = _scan("src/codeqa/core/b.py",
                       "from codeqa.core.a import ControlFlowObservation\n")
        graph = classify_static_import_chains({i["module"]:i
                                              for i in (root,first,second)})
        self.assertEqual(graph["syntax_candidate_edges"], 0)
        self.assertEqual(graph["unresolved_target_edges"], 2)

    def test_reexport_and_external_compatibility_are_never_certified(self):
        x = self.actual
        graph = x["target_graph"]
        self.assertEqual(x["internal_import_scope"],
                         "SELECTED_ROOT_SYMBOL_SOURCE_SYNTAX_ONLY")
        self.assertEqual(x["whole_repository_binding_graph"], "NOT_EVALUATED")
        self.assertEqual(x["dynamic_import_resolution"], "NOT_EVALUATED")
        self.assertEqual(x["external_caller_evidence"], "DEFERRED_NO_EVIDENCE")
        self.assertEqual(x["external_deferred_issue"], 147)
        self.assertEqual(x["external_compatibility"], "UNKNOWN")
        self.assertEqual(x["glossary_policy"], "NOT_ADOPTED")
        self.assertEqual(x["owner_semantic_approval"], "NOT_ADOPTED")
        self.assertEqual(x["semantic_fp_fn"], "NOT_EVALUATED")
        self.assertEqual(graph["external_caller_compatibility"], "UNKNOWN")
        self.assertFalse(x["rename_authorized"])
        self.assertFalse(graph["rename_authorized"])

    def test_forged_scope_or_source_denominator_is_rejected(self):
        edits = [
            lambda c: c.update(source_commit="0"*40),
            lambda c: c.update(source_tree_sha="0"*40),
            lambda c: c.update(selected_python_file_count=99),
            lambda c: c.update(root_module="codeqa.core"),
            lambda c: c.update(glossary_adoption="ADOPTED"),
            lambda c: c.update(rename_authorized=True),
            lambda c: c.update(external_callers="VERIFIED"),
            lambda c: c.update(external_deferred_issue=0),
            lambda c: c["known_direct_clients"].pop(),
            lambda c: c["known_direct_clients"][0].update(line=13),
        ]
        for i, edit in enumerate(edits):
            with self.subTest(i=i):
                charter = deepcopy(self.charter)
                edit(charter)
                with self.assertRaises(InternalImportCensusError):
                    audit_pinned_internal_imports(ROOT, charter)

    def test_invalid_source_is_never_assumed_to_have_no_imports(self):
        with self.assertRaises(InternalImportGraphError):
            scan_module_imports(b"def incomplete(",
                                path="src/codeqa/core/bad.py")


if __name__ == "__main__":
    unittest.main()
