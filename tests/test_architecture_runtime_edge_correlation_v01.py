"""Source-bound B8 static-to-runtime join, with no false import/ownership PASS."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import unittest

from codeqa.evaluation.architecture.runtime_edge_correlation import (
    RuntimeEdgeCorrelationError, correlate_b8_runtime_pairs,
)


def digest(obj):
    return sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def seal(obj, key):
    obj[key] = digest({k: v for k, v in obj.items() if k != key})


def inputs(count=2):
    head = "a" * 40
    src = "src/demo/pipeline/main.py"
    targets = ("src/demo/core/a.py", "src/demo/adapters/b.py")[:count]
    paths = [src, *targets] if count else []
    hashes = {p: sha256(p.encode()).hexdigest() for p in paths}
    edges = []
    for target in targets:
        edges.append({
            "source_path": src, "target_path": target,
            "source_role": "pipeline", "target_role": target.split("/")[2],
            "declared_policy_direction": "DECLARED_ALLOWED",
            "import_witnesses": [{
                "source_path": src, "target_path": target,
                "source_sha256": hashes[src], "line": 7,
            }],
        })
    resp = {
        "schema_version": "0.1",
        "source_identity": {"snapshot_sha": head, "inventory_id": "inv"},
        "observed_cross_role_pairs": count,
        "edges": edges,
        "decision": "NOT_EVALUATED",
        "semantic_ownership": "NOT_EVALUATED",
    }
    seal(resp, "responsibility_id")
    sel = {
        "schema_version": "0.1",
        "source_identity": {
            "snapshot_sha": head, "inventory_id": "inv",
            "responsibility_id": resp["responsibility_id"],
        },
        "pairs": [[src, t] for t in targets],
        "observed_cross_role_pairs": count,
        "source_sha256": hashes,
        "static_import_edge_traversal": "NOT_EVALUATED",
        "decision": "NOT_EVALUATED",
    }
    seal(sel, "selection_id")
    obs = None
    if count:
        obs = {
            "schema_version": "0.1",
            "source_identity": {"snapshot_sha_claim": head, "source_sha256": hashes},
            "observed_pairs": [{
                "source_path": src, "target_path": target,
                "observed_direct_python_calls": 3 if i == 0 else 0,
                "call_witnesses": ([{"test_id": "test_one", "caller_line": 15,
                                    "callee_first_line": 2}] if i == 0 else []),
                "witnesses_truncated": i == 0,
            } for i, target in enumerate(targets)],
            "executed_tests": [{"test_id": "test_one", "outcome": "PASSED"}],
            "tests_run": 1,
            "suite_was_successful": True,
            "evidence_class": "LOCAL_PYTHON_FRAME_CALL_UNATTESTED",
            "static_import_edge_traversal": "NOT_EVALUATED",
            "decision": "NOT_EVALUATED",
        }
        seal(obs, "observation_id")
    return sel, resp, obs


class B8RuntimeCorrelationTests(unittest.TestCase):
    def test_complete_join_keeps_unobserved_edges_and_unknowns(self):
        sel, resp, obs = inputs()
        report = correlate_b8_runtime_pairs(sel, resp, obs)
        self.assertEqual((report["static_pairs"], report["direct_call_observed_pairs"],
                          report["not_observed_in_sample_pairs"], report["direct_python_calls"]),
                         (2, 1, 1, 3))
        self.assertEqual(report["by_target_role"]["core"]["direct_calls"], 3)
        self.assertEqual(report["by_target_role"]["adapters"]["direct_calls"], 0)
        self.assertEqual({r["runtime_observation"] for r in report["edges"]},
                         {"OBSERVED_DIRECT_PYTHON_CALL", "NOT_OBSERVED_IN_SAMPLE"})
        self.assertEqual(report["static_import_edge_traversal"], "NOT_EVALUATED")
        self.assertEqual(report["semantic_ownership"], "NOT_EVALUATED")
        self.assertEqual(report["correlation_id"], digest({
            k: v for k, v in report.items() if k != "correlation_id"
        }))

    def test_healthy_zero_pair_control_has_no_forced_problem(self):
        sel, resp, obs = inputs(0)
        report = correlate_b8_runtime_pairs(sel, resp, obs)
        self.assertEqual(report["edges"], [])
        self.assertEqual(report["static_pairs"], 0)
        self.assertEqual(report["by_target_role"], {})
        self.assertEqual(report["decision"], "NOT_EVALUATED")

    def test_reject_missing_or_unexpected_runtime_observation(self):
        sel, resp, obs = inputs()
        with self.assertRaises(RuntimeEdgeCorrelationError):
            correlate_b8_runtime_pairs(sel, resp, None)
        zero, zresp, _ = inputs(0)
        with self.assertRaises(RuntimeEdgeCorrelationError):
            correlate_b8_runtime_pairs(zero, zresp, obs)

    def test_reject_forged_or_stale_source_and_denominator(self):
        sel, resp, obs = inputs()
        changed = deepcopy(obs)
        changed["source_identity"]["snapshot_sha_claim"] = "b" * 40
        seal(changed, "observation_id")
        with self.assertRaises(RuntimeEdgeCorrelationError):
            correlate_b8_runtime_pairs(sel, resp, changed)
        changed = deepcopy(obs)
        changed["observed_pairs"].pop()
        seal(changed, "observation_id")
        with self.assertRaises(RuntimeEdgeCorrelationError):
            correlate_b8_runtime_pairs(sel, resp, changed)
        changed = deepcopy(resp)
        changed["edges"][0]["import_witnesses"][0]["source_sha256"] = "0" * 64
        seal(changed, "responsibility_id")
        with self.assertRaises(RuntimeEdgeCorrelationError):
            correlate_b8_runtime_pairs(sel, changed, obs)

    def test_reject_invalid_call_witness_and_outcome_even_if_resealed(self):
        sel, resp, obs = inputs()
        for key, value in (("test_id", "unrelated"), ("caller_line", 0)):
            changed = deepcopy(obs)
            changed["observed_pairs"][0]["call_witnesses"][0][key] = value
            seal(changed, "observation_id")
            with self.subTest(key=key), self.assertRaises(RuntimeEdgeCorrelationError):
                correlate_b8_runtime_pairs(sel, resp, changed)
        changed = deepcopy(obs)
        changed["executed_tests"][0]["outcome"] = "FAILED"
        changed["suite_was_successful"] = False
        seal(changed, "observation_id")
        with self.assertRaises(RuntimeEdgeCorrelationError):
            correlate_b8_runtime_pairs(sel, resp, changed)

    def test_reject_wrong_call_count_and_duplicate_pairs(self):
        sel, resp, obs = inputs()
        changed = deepcopy(obs)
        changed["observed_pairs"][0]["observed_direct_python_calls"] = 0
        seal(changed, "observation_id")
        with self.assertRaises(RuntimeEdgeCorrelationError):
            correlate_b8_runtime_pairs(sel, resp, changed)
        changed = deepcopy(obs)
        changed["observed_pairs"][1] = deepcopy(changed["observed_pairs"][0])
        seal(changed, "observation_id")
        with self.assertRaises(RuntimeEdgeCorrelationError):
            correlate_b8_runtime_pairs(sel, resp, changed)


if __name__ == "__main__":
    unittest.main()
