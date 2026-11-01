"""Fail-closed positive/negative tests for source-only B8 import binding candidates."""
from __future__ import annotations

import ast
from hashlib import sha256
import json
import unittest

from codeqa.evaluation.architecture.import_binding_usage import (
    ImportBindingUsageError, _load_syntax_context, census_b8_import_binding_uses,
)


def seal(obj, key):
    obj[key] = sha256(json.dumps({k: v for k, v in obj.items() if k != key},
                                 sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def inputs(count=2, text=None):
    src = "src/demo/pipeline/main.py"
    targets = ["src/demo/core/a.py", "src/demo/adapters/b.py"][:count]
    raw = (text or "from demo.core.a import Alpha\nfrom demo.adapters.b import Beta\nx = Alpha()\n").encode()
    hashes = {p: sha256(p.encode()).hexdigest() for p in targets}
    imports = [
        node for node in ast.walk(ast.parse(raw))
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    if count:
        hashes[src] = sha256(raw).hexdigest()
    edges = [{"source_path": src, "target_path": target,
              "import_witnesses": [{"source_path": src, "target_path": target,
                                    "source_sha256": hashes[src], "line": i + 1,
                                     "expression": (
                                         "import " + target.removeprefix("src/")
                                         .removesuffix(".py").replace("/", ".")
                                         if isinstance(imports[i], ast.Import)
                                         else ast.unparse(imports[i])
                                     ), "execution": "top_level"}]}
             for i, target in enumerate(targets)]
    resp = {"schema_version": "0.1", "source_identity": {"snapshot_sha": "a" * 40},
            "observed_cross_role_pairs": count, "edges": edges, "decision": "NOT_EVALUATED"}
    seal(resp, "responsibility_id")
    sel = {"schema_version": "0.1", "source_identity": {"snapshot_sha": "a" * 40,
            "responsibility_id": resp["responsibility_id"]},
           "pairs": [[src, target] for target in targets],
           "observed_cross_role_pairs": count, "source_sha256": hashes,
           "decision": "NOT_EVALUATED"}
    seal(sel, "selection_id")
    return sel, resp, {src: raw} if count else {}


class ImportBindingUsageTests(unittest.TestCase):
    def test_name_load_and_no_load_distinct_but_not_semantic(self):
        s, r, b = inputs()
        report = census_b8_import_binding_uses(s, r, b)
        self.assertEqual((report["static_pairs"], report["pairs_with_name_load_candidates"],
                          report["pairs_without_name_load_candidates"]), (2, 1, 1))
        by_target = {edge["target_path"]: edge for edge in report["records"]}
        self.assertEqual(by_target["src/demo/core/a.py"]["candidate_bindings"][0]["name"], "Alpha")
        self.assertEqual(by_target["src/demo/core/a.py"]["candidate_bindings"][0]["load_witnesses"],
                         [{"line": 3, "column": 4}])
        self.assertEqual(by_target["src/demo/adapters/b.py"]["candidate_bindings"][0]["status"],
                         "NO_NAME_LOAD_IN_SOURCE")
        self.assertEqual(report["decision"], "NOT_EVALUATED")
        self.assertEqual(report["import_execution"], "NOT_EVALUATED")

    def test_healthy_zero_pair_control(self):
        s, r, b = inputs(0)
        report = census_b8_import_binding_uses(s, r, b)
        self.assertEqual(report["static_pairs"], 0)
        self.assertEqual(report["records"], [])
        self.assertEqual(report["decision"], "NOT_EVALUATED")

    def test_reject_changed_or_extra_source(self):
        s, r, b = inputs()
        with self.assertRaises(ImportBindingUsageError):
            census_b8_import_binding_uses(s, r, {**b, "src/other.py": b""})
        with self.assertRaises(ImportBindingUsageError):
            census_b8_import_binding_uses(s, r, {next(iter(b)): b"import os\n"})

    def test_reject_resealed_forged_witness_line(self):
        s, r, b = inputs()
        r["edges"][0]["import_witnesses"][0]["line"] = 99
        seal(r, "responsibility_id")
        s["source_identity"]["responsibility_id"] = r["responsibility_id"]
        seal(s, "selection_id")
        with self.assertRaises(ImportBindingUsageError):
            census_b8_import_binding_uses(s, r, b)

    def test_reject_resealed_forged_witness_hash(self):
        s, r, b = inputs()
        r["edges"][0]["import_witnesses"][0]["source_sha256"] = "0" * 64
        seal(r, "responsibility_id")
        s["source_identity"]["responsibility_id"] = r["responsibility_id"]
        seal(s, "selection_id")
        with self.assertRaises(ImportBindingUsageError):
            census_b8_import_binding_uses(s, r, b)

    def test_multiple_aliases_are_not_assigned_to_target(self):
        s, r, b = inputs(1, "from demo.core.a import Alpha, Beta\nx = Beta\n")
        report = census_b8_import_binding_uses(s, r, b)
        self.assertEqual([c["name"] for c in report["records"][0]["candidate_bindings"]],
                         ["Alpha", "Beta"])
        self.assertEqual(report["records"][0]["binding_target_attribution"],
                         "LINE_COLOCATED_UNVERIFIED")
        self.assertTrue(report["records"][0]["has_name_load_candidate"])

    def test_multi_alias_import_does_not_count_unrelated_alias(self):
        s, r, b = inputs(
            1,
            "import demo.core.a as core, demo.adapters.b as adapters\n"
            "x = adapters\n",
        )
        report = census_b8_import_binding_uses(s, r, b)
        bindings = report["records"][0]["candidate_bindings"]
        self.assertEqual([c["name"] for c in bindings], ["core"])
        self.assertEqual(bindings[0]["lexical_load_count"], 0)
        self.assertEqual(report["pairs_with_name_load_candidates"], 0)
        self.assertEqual(report["decision"], "NOT_EVALUATED")

    def test_reject_resealed_import_target_mismatch(self):
        # A syntactically real import must not be attached to another module.
        s, r, b = inputs(
            1, "from demo.adapters.b import Alpha\nx = Alpha\n",
        )
        with self.assertRaises(ImportBindingUsageError):
            census_b8_import_binding_uses(s, r, b)

    def test_reject_resealed_wrong_import_expression_or_execution(self):
        for field, wrong in (
            ("expression", "import demo.core.a"),
            ("execution", "conditional_or_deferred"),
        ):
            with self.subTest(field=field):
                s, r, b = inputs(1)
                r["edges"][0]["import_witnesses"][0][field] = wrong
                seal(r, "responsibility_id")
                s["source_identity"]["responsibility_id"] = r["responsibility_id"]
                seal(s, "selection_id")
                with self.assertRaises(ImportBindingUsageError):
                    census_b8_import_binding_uses(s, r, b)

    def test_shadowing_does_not_upgrade_binding_resolution(self):
        s, r, b = inputs(1, "from demo.core.a import Alpha\nAlpha = 3\nx = Alpha\n")
        report = census_b8_import_binding_uses(s, r, b)
        self.assertTrue(report["records"][0]["has_name_load_candidate"])
        self.assertEqual(report["records"][0]["binding_target_attribution"],
                         "LINE_COLOCATED_UNVERIFIED")

    def test_ast_context_separates_annotations_calls_attributes_and_guards(self):
        source = (
            "from demo.core.a import Alpha\n"
            "def evaluate(value: Alpha) -> Alpha:\n"
            "    if enabled:\n"
            "        return Alpha()\n"
            "    Alpha.attribute\n"
            "    return Alpha\n"
        )
        s, r, b = inputs(1, source)
        report = census_b8_import_binding_uses(s, r, b)
        row = report["records"][0]
        self.assertEqual(row["syntax_context_counts"], {
            "ANNOTATION_SYNTAX": 2,
            "CALL_TARGET_SYNTAX": 1,
            "ATTRIBUTE_ACCESS_SYNTAX": 1,
            "OTHER_LOAD_SYNTAX": 1,
        })
        self.assertEqual(row["conditional_load_candidates"], 1)
        self.assertEqual(row["candidate_bindings"][0]["lexical_load_count"], 5)
        self.assertEqual(report["syntax_context_counts"], row["syntax_context_counts"])
        self.assertEqual(report["semantic_ownership"], "NOT_EVALUATED")
        self.assertEqual(report["public_api_compatibility"], "NOT_EVALUATED")

    def test_guarded_loop_exception_match_and_with_loads_are_not_unconditional(self):
        # The loop iterable and finally suite are not conditionally reached
        # merely because their parent statements have guarded branches.
        # Syntax context is review evidence, never resolved import identity.
        source = (
            "from demo.core.a import Alpha\n"
            "for item in Alpha():\n"
            "    Alpha.run()\n"
            "try:\n"
            "    maybe_fail()\n"
            "except ValueError:\n"
            "    Alpha()\n"
            "finally:\n"
            "    Alpha()\n"
            "match state:\n"
            "    case 1 if Alpha.ready:\n"
            "        Alpha.run()\n"
            "with manager():\n"
            "    Alpha()\n"
            "Alpha()\n"
        )
        s, r, b = inputs(1, source)
        report = census_b8_import_binding_uses(s, r, b)
        row = report["records"][0]
        binding = row["candidate_bindings"][0]
        self.assertEqual(binding["lexical_load_count"], 8)
        self.assertEqual(binding["syntax_context_counts"], {
            "ANNOTATION_SYNTAX": 0,
            "CALL_TARGET_SYNTAX": 7,
            "ATTRIBUTE_ACCESS_SYNTAX": 1,
            "OTHER_LOAD_SYNTAX": 0,
        })
        self.assertEqual(binding["conditional_load_candidates"], 5)
        self.assertEqual(row["conditional_load_candidates"], 5)
        self.assertEqual(report["conditional_load_candidates"], 5)
        # Guarded status is attached to the correct source lines, not merely
        # a matching aggregate. Iterable evaluation and finally are controls.
        tree = ast.parse(source)
        parents = {
            id(child): (node, field)
            for node in ast.walk(tree)
            for field, value in ast.iter_fields(node)
            for child in (value if isinstance(value, list) else [value])
            if isinstance(child, ast.AST)
        }
        guarded = {
            node.lineno: _load_syntax_context(node, parents)[1]
            for node in ast.walk(tree)
            if isinstance(node, ast.Name) and node.id == "Alpha"
            and isinstance(node.ctx, ast.Load)
        }
        self.assertEqual(guarded, {
            2: False, 3: True, 7: True, 9: False,
            11: True, 12: True, 14: True, 15: False,
        })
        self.assertEqual(report["decision"], "NOT_EVALUATED")
        self.assertEqual(report["semantic_ownership"], "NOT_EVALUATED")

    def test_method_call_is_call_syntax_not_attribute_only(self):
        s, r, b = inputs(1, "from demo.core.a import Alpha\nAlpha.run()\n")
        report = census_b8_import_binding_uses(s, r, b)
        counts = report["records"][0]["syntax_context_counts"]
        self.assertEqual(counts["CALL_TARGET_SYNTAX"], 1)
        self.assertEqual(counts["ATTRIBUTE_ACCESS_SYNTAX"], 0)

    def test_callee_spine_excludes_subscript_index_and_nested_call_argument(self):
        # An enclosing Call.func does not make *every* descendant Name a callee.
        source = (
            "from demo.core.a import Alpha, Beta\n"
            "Alpha[Beta]()\n"
            "factory(Alpha).method()\n"
            "Alpha.run()\n"
        )
        s, r, b = inputs(1, source)
        report = census_b8_import_binding_uses(s, r, b)
        bindings = {c["name"]: c for c in report["records"][0]["candidate_bindings"]}
        self.assertEqual(bindings["Alpha"]["syntax_context_counts"], {
            "ANNOTATION_SYNTAX": 0,
            "CALL_TARGET_SYNTAX": 2,
            "ATTRIBUTE_ACCESS_SYNTAX": 0,
            "OTHER_LOAD_SYNTAX": 1,
        })
        self.assertEqual(bindings["Beta"]["syntax_context_counts"], {
            "ANNOTATION_SYNTAX": 0,
            "CALL_TARGET_SYNTAX": 0,
            "ATTRIBUTE_ACCESS_SYNTAX": 0,
            "OTHER_LOAD_SYNTAX": 1,
        })
        self.assertEqual(report["syntax_context_counts"]["CALL_TARGET_SYNTAX"], 2)
        self.assertEqual(report["decision"], "NOT_EVALUATED")

    def test_subscript_receiver_remains_attribute_syntax(self):
        s, r, b = inputs(1, "from demo.core.a import Alpha\nAlpha[0].value\n")
        report = census_b8_import_binding_uses(s, r, b)
        counts = report["records"][0]["syntax_context_counts"]
        self.assertEqual(counts["ATTRIBUTE_ACCESS_SYNTAX"], 1)
        self.assertEqual(counts["CALL_TARGET_SYNTAX"], 0)

    def test_star_import_and_zero_pair_contexts_do_not_force_question(self):
        s, r, b = inputs(1, "from demo.core.a import *\n")
        report = census_b8_import_binding_uses(s, r, b)
        self.assertEqual(sum(report["syntax_context_counts"].values()), 0)
        self.assertEqual(report["records"][0]["candidate_bindings"][0]["status"],
                         "STAR_IMPORT_UNRESOLVED")
        self.assertEqual(report["decision"], "NOT_EVALUATED")
        s, r, b = inputs(0)
        self.assertEqual(census_b8_import_binding_uses(s, r, b)[
            "syntax_context_counts"]["CALL_TARGET_SYNTAX"], 0)

    def test_reject_stale_selection_identity(self):
        s, r, b = inputs()
        s["source_identity"]["snapshot_sha"] = "b" * 40
        seal(s, "selection_id")
        with self.assertRaises(ImportBindingUsageError):
            census_b8_import_binding_uses(s, r, b)


if __name__ == "__main__":
    unittest.main()
