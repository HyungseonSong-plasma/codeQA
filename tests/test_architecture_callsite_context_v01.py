"""Exact-source positive, negative and no-call callsite-context regressions."""
from __future__ import annotations

from hashlib import sha256
import json
import unittest

from codeqa.evaluation.architecture.callsite_context import (
    CallsiteContextError, census_b8_callsite_context,
)


def seal(obj, key):
    obj[key] = sha256(json.dumps({k: v for k, v in obj.items() if k != key},
                                 sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def fixture(*, with_call=True):
    source = "src/demo/pipeline/run.py"
    target = "src/demo/core/work.py"
    raw = ("from demo.core import work\n"
           "class Runner:\n"
           "    def execute(self):\n"
           "        return work.execute()\n").encode()
    hashes = {source: sha256(raw).hexdigest(), target: "b" * 64}
    identity = {"snapshot_sha": "a" * 40, "responsibility_id": "c" * 64}
    selection = {"schema_version": "0.1", "source_identity": identity,
                 "pairs": [[source, target]], "source_sha256": hashes,
                 "observed_cross_role_pairs": 1, "decision": "NOT_EVALUATED"}
    seal(selection, "selection_id")
    calls = 2 if with_call else 0
    witnesses = [{"test_id": "suite.test", "caller_line": 4,
                  "callee_first_line": 1}] if with_call else []
    correlation = {
        "schema_version": "0.1", "source_identity": identity,
        "selection_id": selection["selection_id"], "static_pairs": 1,
        "direct_call_observed_pairs": int(with_call),
        "not_observed_in_sample_pairs": int(not with_call),
        "direct_python_calls": calls,
        "edges": [{"source_path": source, "target_path": target,
                   "source_role": "pipeline", "target_role": "core",
                   "declared_policy_direction": "DECLARED_ALLOWED",
                   "direct_python_calls": calls, "call_witnesses": witnesses,
                   "witnesses_truncated": with_call,
                   "static_import_edge_traversal": "NOT_EVALUATED",
                   "semantic_ownership": "NOT_EVALUATED"}],
        "static_import_edge_traversal": "NOT_EVALUATED",
        "semantic_ownership": "NOT_EVALUATED",
        "public_api_compatibility": "NOT_EVALUATED",
        "decision": "NOT_EVALUATED",
    }
    seal(correlation, "correlation_id")
    return selection, correlation, {source: raw}


class CallsiteContextTests(unittest.TestCase):
    def test_function_span_annotated_without_semantic_verdict(self):
        s, c, b = fixture()
        report = census_b8_callsite_context(s, c, b)
        self.assertEqual(report["static_pairs"], 1)
        self.assertEqual(report["direct_call_observed_pairs"], 1)
        self.assertEqual(report["direct_python_calls"], 2)
        self.assertEqual(report["sampled_call_witnesses"], 1)
        self.assertEqual(report["sampled_function_body_witnesses"], 1)
        witness = report["edges"][0]["sampled_call_witnesses"][0]
        self.assertEqual(witness["lexical_context"], "FUNCTION_BODY")
        self.assertEqual(witness["function_qualname"], "Runner.execute")
        self.assertEqual(witness["function_line"], 3)
        self.assertEqual(report["intentional_orchestration"], "NOT_EVALUATED")
        self.assertEqual(report["decision"], "NOT_EVALUATED")
        self.assertEqual(report, census_b8_callsite_context(s, c, b))

    def test_no_call_is_not_dead_edge(self):
        s, c, b = fixture(with_call=False)
        report = census_b8_callsite_context(s, c, b)
        self.assertEqual(report["not_observed_in_sample_pairs"], 1)
        self.assertEqual(report["edges"][0]["sampled_call_witnesses"], [])
        self.assertEqual(report["semantic_ownership"], "NOT_EVALUATED")

    def test_reject_modified_source_or_extra_source(self):
        s, c, b = fixture()
        with self.assertRaises(CallsiteContextError):
            census_b8_callsite_context(s, c, {next(iter(b)): b"changed\n"})
        with self.assertRaises(CallsiteContextError):
            census_b8_callsite_context(s, c, {**b, "src/other.py": b""})

    def test_reject_resealed_out_of_range_caller_line(self):
        s, c, b = fixture()
        c["edges"][0]["call_witnesses"][0]["caller_line"] = 1000
        seal(c, "correlation_id")
        with self.assertRaises(CallsiteContextError):
            census_b8_callsite_context(s, c, b)

    def test_reject_resealed_wrong_pair_or_count(self):
        s, c, b = fixture()
        c["edges"][0]["target_path"] = "src/demo/core/other.py"
        seal(c, "correlation_id")
        with self.assertRaises(CallsiteContextError):
            census_b8_callsite_context(s, c, b)
        s, c, b = fixture()
        c["direct_python_calls"] = 3
        seal(c, "correlation_id")
        with self.assertRaises(CallsiteContextError):
            census_b8_callsite_context(s, c, b)

    def test_zero_pair_control(self):
        s, c, _ = fixture(with_call=False)
        s["pairs"] = []
        s["source_sha256"] = {}
        s["observed_cross_role_pairs"] = 0
        seal(s, "selection_id")
        c["selection_id"] = s["selection_id"]
        c["edges"] = []
        c["static_pairs"] = 0
        c["not_observed_in_sample_pairs"] = 0
        seal(c, "correlation_id")
        report = census_b8_callsite_context(s, c, {})
        self.assertEqual(report["edges"], [])
        self.assertEqual(report["decision"], "NOT_EVALUATED")

    def test_module_level_call_is_not_function(self):
        s, c, b = fixture()
        src = next(iter(b))
        raw = b"from demo.core import work\nwork.execute()\n"
        s["source_sha256"][src] = sha256(raw).hexdigest()
        seal(s, "selection_id")
        c["selection_id"] = s["selection_id"]
        c["edges"][0]["call_witnesses"][0]["caller_line"] = 2
        seal(c, "correlation_id")
        report = census_b8_callsite_context(s, c, {src: raw})
        self.assertEqual(report["sampled_function_body_witnesses"], 0)
        self.assertEqual(report["edges"][0]["sampled_call_witnesses"][0]["lexical_context"],
                         "MODULE_OR_CLASS_BODY")


if __name__ == "__main__":
    unittest.main()
