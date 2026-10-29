"""B8 runtime pair selection: authentic source, full denominator, zero-pair control."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import unittest

from codeqa.evaluation.architecture.runtime_pair_selection import (
    RuntimePairSelectionError, select_b8_runtime_pairs,
)


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def fixture(with_edge=True):
    head = "a" * 40
    paths = ("src/demo/pipeline/a.py", "src/demo/core/b.py")
    files = [{"path": p, "read_state": "READ", "source_sha256": sha256(p.encode()).hexdigest()}
             for p in paths]
    inventory = {"schema_version": "0.1",
                 "source_identity": {"repository_commit_sha": head},
                 "files": files}
    inventory["inventory_id"] = digest(inventory)
    edges = [{
        "source_path": paths[0], "target_path": paths[1],
        "source_role": "pipeline", "target_role": "core",
        "import_witnesses": [{
            "source_path": paths[0], "target_path": paths[1],
            "source_sha256": files[0]["source_sha256"], "line": 3,
        }],
    }] if with_edge else []
    responsibility = {
        "schema_version": "0.1",
        "source_identity": {"snapshot_sha": head, "inventory_id": inventory["inventory_id"]},
        "observed_cross_role_pairs": len(edges), "edges": edges,
        "decision": "NOT_EVALUATED", "test_behavior_coverage": "NOT_EVALUATED",
    }
    responsibility["responsibility_id"] = digest(responsibility)
    return inventory, responsibility


def reseal(report, key):
    report[key] = digest({k: v for k, v in report.items() if k != key})


class B8RuntimeSelectionTests(unittest.TestCase):
    def test_one_pair_uses_both_exact_inventory_hashes(self):
        inv, resp = fixture()
        result = select_b8_runtime_pairs(inv, resp)
        self.assertEqual(result["observed_cross_role_pairs"], 1)
        self.assertEqual(len(result["source_sha256"]), 2)
        self.assertEqual(result["pairs"][0], [
            "src/demo/pipeline/a.py", "src/demo/core/b.py"
        ])
        self.assertEqual(result["decision"], "NOT_EVALUATED")
        self.assertEqual(result["static_import_edge_traversal"], "NOT_EVALUATED")
        self.assertEqual(result["selection_id"], digest({
            k: v for k, v in result.items() if k != "selection_id"
        }))

    def test_zero_pairs_valid_without_forced_question(self):
        inv, resp = fixture(with_edge=False)
        result = select_b8_runtime_pairs(inv, resp)
        self.assertEqual(result["pairs"], [])
        self.assertEqual(result["source_sha256"], {})
        self.assertEqual(result["decision"], "NOT_EVALUATED")

    def test_reject_forged_source_hash_even_if_responsibility_resealed(self):
        inv, resp = fixture()
        resp["edges"][0]["import_witnesses"][0]["source_sha256"] = "0" * 64
        reseal(resp, "responsibility_id")
        with self.assertRaises(RuntimePairSelectionError):
            select_b8_runtime_pairs(inv, resp)

    def test_reject_duplicate_pair_even_if_denominator_resealed(self):
        inv, resp = fixture()
        resp["edges"].append(deepcopy(resp["edges"][0]))
        resp["observed_cross_role_pairs"] = 2
        reseal(resp, "responsibility_id")
        with self.assertRaises(RuntimePairSelectionError):
            select_b8_runtime_pairs(inv, resp)

    def test_reject_mixed_head_and_missing_source(self):
        inv, resp = fixture()
        resp["source_identity"]["snapshot_sha"] = "b" * 40
        reseal(resp, "responsibility_id")
        with self.assertRaises(RuntimePairSelectionError):
            select_b8_runtime_pairs(inv, resp)
        inv, resp = fixture()
        inv["files"].pop()
        reseal(inv, "inventory_id")
        resp["source_identity"]["inventory_id"] = inv["inventory_id"]
        reseal(resp, "responsibility_id")
        with self.assertRaises(RuntimePairSelectionError):
            select_b8_runtime_pairs(inv, resp)


if __name__ == "__main__":
    unittest.main()
