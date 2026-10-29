"""Fail-closed positive/negative tests for source-only B8 import binding candidates."""
from __future__ import annotations

from hashlib import sha256
import json
import unittest

from codeqa.evaluation.architecture.import_binding_usage import (
    ImportBindingUsageError, census_b8_import_binding_uses,
)


def seal(obj, key):
    obj[key] = sha256(json.dumps({k: v for k, v in obj.items() if k != key},
                                 sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def inputs(count=2, text=None):
    src = "src/demo/pipeline/main.py"
    targets = ["src/demo/core/a.py", "src/demo/adapters/b.py"][:count]
    raw = (text or "from codeqa.core import Alpha\nfrom codeqa.adapters import Beta\nx = Alpha()\n").encode()
    hashes = {p: sha256(p.encode()).hexdigest() for p in targets}
    if count:
        hashes[src] = sha256(raw).hexdigest()
    edges = [{"source_path": src, "target_path": target,
              "import_witnesses": [{"source_path": src, "target_path": target,
                                    "source_sha256": hashes[src], "line": i + 1}]}
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
        s, r, b = inputs(1, "from codeqa.core import Alpha, Beta\nx = Beta\n")
        report = census_b8_import_binding_uses(s, r, b)
        self.assertEqual([c["name"] for c in report["records"][0]["candidate_bindings"]],
                         ["Alpha", "Beta"])
        self.assertEqual(report["records"][0]["binding_target_attribution"],
                         "LINE_COLOCATED_UNVERIFIED")
        self.assertTrue(report["records"][0]["has_name_load_candidate"])

    def test_shadowing_does_not_upgrade_binding_resolution(self):
        s, r, b = inputs(1, "from codeqa.core import Alpha\nAlpha = 3\nx = Alpha\n")
        report = census_b8_import_binding_uses(s, r, b)
        self.assertTrue(report["records"][0]["has_name_load_candidate"])
        self.assertEqual(report["records"][0]["binding_target_attribution"],
                         "LINE_COLOCATED_UNVERIFIED")

    def test_reject_stale_selection_identity(self):
        s, r, b = inputs()
        s["source_identity"]["snapshot_sha"] = "b" * 40
        seal(s, "selection_id")
        with self.assertRaises(ImportBindingUsageError):
            census_b8_import_binding_uses(s, r, b)


if __name__ == "__main__":
    unittest.main()
