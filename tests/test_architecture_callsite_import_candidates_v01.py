"""Source-bound import/callsite lexical candidates, with adversarial controls."""
from __future__ import annotations

from hashlib import sha256
import unittest

from codeqa.evaluation.architecture.callsite_context import (
    CallsiteContextError, census_b8_callsite_context,
)
from test_architecture_callsite_context_v01 import fixture, seal


def sample(raw: bytes, *, line: int):
    selection, correlation, sources = fixture()
    source = next(iter(sources))
    selection["source_sha256"][source] = sha256(raw).hexdigest()
    seal(selection, "selection_id")
    correlation["selection_id"] = selection["selection_id"]
    correlation["edges"][0]["call_witnesses"][0]["caller_line"] = line
    seal(correlation, "correlation_id")
    return census_b8_callsite_context(selection, correlation, {source: raw})


def candidate(report):
    return report["edges"][0]["sampled_call_witnesses"][0]


class ImportCalleeCandidateTests(unittest.TestCase):
    def test_direct_from_import_call_is_lexical_candidate(self):
        selection, correlation, sources = fixture()
        report = census_b8_callsite_context(selection, correlation, sources)
        witness = candidate(report)
        self.assertEqual(witness["target_import_alias_call_status"],
                         "LEXICAL_ALIAS_CALL_CANDIDATE")
        self.assertEqual(witness["target_import_alias_call_candidates"], [{
            "callee_expression": "work.execute",
            "root_name": "work",
            "call_line": 4,
            "call_column": 15,
            "target_import_lines": [1],
        }])
        self.assertEqual(report["sampled_import_alias_call_candidate_witnesses"], 1)
        self.assertEqual(witness["target_import_alias_parameter_shadowing_warnings"], [])
        self.assertEqual(report["sampled_alias_parameter_shadowing_warning_witnesses"], 0)
        self.assertEqual(report["intentional_orchestration"], "NOT_EVALUATED")

    def test_local_receiver_call_does_not_claim_direct_import_alias(self):
        raw = (b"from demo.core import work\n"
               b"class Runner:\n"
               b"    def execute(self):\n"
               b"        worker = work.Builder()\n"
               b"        return worker.execute()\n")
        witness = candidate(sample(raw, line=5))
        self.assertEqual(witness["ast_call_expression_candidates"], 1)
        self.assertEqual(witness["target_import_alias_call_candidates"], [])
        self.assertEqual(witness["target_import_alias_call_status"],
                         "NO_DIRECT_ALIAS_CALL_CANDIDATE")
        self.assertEqual(witness["unmatched_indirect_receiver_call_candidates"], [{
            "callee_expression": "worker.execute",
            "root_name": "worker",
            "receiver_kind": "NAMED_RECEIVER",
            "call_line": 5,
            "call_column": 15,
        }])

    def test_self_attribute_receiver_is_syntax_only(self):
        raw = (b"from demo.core import work\n"
               b"def execute(self):\n"
               b"    return self.graph.to_document()\n")
        report = sample(raw, line=3)
        witness = candidate(report)
        self.assertEqual(witness["target_import_alias_call_candidates"], [])
        self.assertEqual(report[
            "sampled_no_direct_alias_with_indirect_receiver_candidate"], 1)
        self.assertEqual(witness["unmatched_indirect_receiver_call_candidates"][0][
            "receiver_kind"], "SELF_ATTRIBUTE_RECEIVER")
        self.assertEqual(report["semantic_ownership"], "NOT_EVALUATED")

    def test_computed_receiver_is_not_runtime_provenance(self):
        raw = (b"from demo.core import work\n"
               b"def execute():\n"
               b"    return get_reader().execute()\n")
        witness = candidate(sample(raw, line=3))
        self.assertEqual(witness["unmatched_indirect_receiver_call_candidates"][0][
            "receiver_kind"], "COMPUTED_RECEIVER")

    def test_plain_name_call_has_no_indirect_receiver_candidate(self):
        raw = (b"from demo.core import work\n"
               b"def execute():\n"
               b"    return len((1, 2))\n")
        report = sample(raw, line=3)
        witness = candidate(report)
        self.assertEqual(witness["unmatched_indirect_receiver_call_candidates"], [])
        self.assertEqual(report[
            "sampled_no_direct_alias_with_indirect_receiver_candidate"], 0)

    def test_shadowed_alias_remains_candidate_not_binding_proof(self):
        raw = (b"from demo.core import work\n"
               b"def execute(work):\n"
               b"    return work.execute()\n")
        report = sample(raw, line=3)
        self.assertEqual(candidate(report)["target_import_alias_call_status"],
                         "LEXICAL_ALIAS_CALL_CANDIDATE")
        self.assertEqual(report["semantic_ownership"], "NOT_EVALUATED")
        self.assertEqual(candidate(report)["target_import_alias_parameter_shadowing_warnings"],
                         ["work"])
        self.assertEqual(report["sampled_alias_parameter_shadowing_warning_witnesses"], 1)
        self.assertIn("shadowing", " ".join(report["limitations"]))

    def test_outer_function_parameter_warns_for_nested_closure(self):
        raw = (b"from demo.core import work\n"
               b"def outer(work):\n"
               b"    def inner():\n"
               b"        return work.execute()\n"
               b"    return inner\n")
        witness = candidate(sample(raw, line=4))
        self.assertEqual(witness["target_import_alias_parameter_shadowing_warnings"],
                         ["work"])
        self.assertEqual(witness["target_import_alias_call_status"],
                         "LEXICAL_ALIAS_CALL_CANDIDATE")

    def test_keyword_only_parameter_warns(self):
        raw = (b"from demo.core import work\n"
               b"def execute(*, work):\n"
               b"    return work.execute()\n")
        witness = candidate(sample(raw, line=3))
        self.assertEqual(witness["target_import_alias_parameter_shadowing_warnings"],
                         ["work"])

    def test_vararg_parameter_warns(self):
        raw = (b"from demo.core import work\n"
               b"def execute(*work):\n"
               b"    return work.execute()\n")
        witness = candidate(sample(raw, line=3))
        self.assertEqual(witness["target_import_alias_parameter_shadowing_warnings"],
                         ["work"])

    def test_unrelated_parameter_does_not_warn(self):
        raw = (b"from demo.core import work\n"
               b"def execute(other):\n"
               b"    return work.execute()\n")
        report = sample(raw, line=3)
        self.assertEqual(candidate(report)[
            "target_import_alias_parameter_shadowing_warnings"], [])
        self.assertEqual(report["sampled_alias_parameter_shadowing_warning_witnesses"], 0)

    def test_unrelated_import_with_same_spelling_does_not_match_target(self):
        raw = (b"from demo.other import work\n"
               b"def execute():\n"
               b"    return work.execute()\n")
        report = sample(raw, line=3)
        self.assertEqual(candidate(report)["target_import_alias_call_candidates"], [])
        self.assertEqual(report["sampled_import_alias_call_candidate_witnesses"], 0)

    def test_relative_from_import_is_source_resolved(self):
        raw = (b"from ..core import work\n"
               b"def execute():\n"
               b"    return work.execute()\n")
        self.assertEqual(candidate(sample(raw, line=3))[
            "target_import_alias_call_candidates"][0]["target_import_lines"], [1])

    def test_absolute_module_alias_is_candidate(self):
        raw = (b"import demo.core.work as service\n"
               b"def execute():\n"
               b"    return service.execute()\n")
        self.assertEqual(candidate(sample(raw, line=3))[
            "target_import_alias_call_candidates"][0]["root_name"], "service")

    def test_nested_calls_are_bounded_candidates_not_runtime_attribution(self):
        raw = (b"from demo.core import work\n"
               b"def execute():\n"
               b"    return work.execute(work.prepare())\n")
        report = sample(raw, line=3)
        witness = candidate(report)
        self.assertEqual(witness["ast_call_expression_candidates"], 2)
        self.assertEqual(len(witness["target_import_alias_call_candidates"]), 2)
        self.assertEqual(report["sampled_import_alias_call_candidate_witnesses"], 1)
        self.assertEqual(report["public_api_compatibility"], "NOT_EVALUATED")

    def test_overdeep_relative_import_does_not_match(self):
        raw = (b"from ...core import work\n"
               b"def execute():\n"
               b"    return work.execute()\n")
        self.assertEqual(candidate(sample(raw, line=3))[
            "target_import_alias_call_candidates"], [])

    def test_zero_call_sample_never_invents_a_candidate(self):
        selection, correlation, sources = fixture(with_call=False)
        report = census_b8_callsite_context(selection, correlation, sources)
        self.assertEqual(report["sampled_import_alias_call_candidate_witnesses"], 0)
        self.assertEqual(report["sampled_without_direct_import_alias_call_candidate"], 0)
        self.assertEqual(report["sampled_alias_parameter_shadowing_warning_witnesses"], 0)
        self.assertEqual(report["sampled_no_direct_alias_with_indirect_receiver_candidate"], 0)
        self.assertEqual(report["decision"], "NOT_EVALUATED")

    def test_source_hash_tamper_fails_closed(self):
        selection, correlation, sources = fixture()
        source = next(iter(sources))
        with self.assertRaises(CallsiteContextError):
            census_b8_callsite_context(selection, correlation,
                                       {source: b"from demo.core import work\n"})


if __name__ == "__main__":
    unittest.main()
