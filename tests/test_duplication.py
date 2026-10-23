"""#38: token-grounded duplicate function block review and negative controls."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator

from codeqa.adapters.python_duplication import extract_python_token_blocks
from codeqa.adapters.python_snapshot import parse_python_snapshot
from codeqa.evaluation.duplication import (
    DuplicationProfile, DuplicationProfileError, evaluate_duplication,
)
from codeqa.infrastructure.resources import ResourceRegistry
from codeqa.pipeline.python import analyze_python


ROOT = Path(__file__).resolve().parents[1]
BODY = "    n = x + 2\n    y = n * 4\n    return y + 1\n"


class DuplicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reg = ResourceRegistry(ROOT)
        cls.base = reg.load_json("duplication_profile")
        cls.schema = reg.load_json("duplication_report_schema")
        cls.ccg = reg.load_json("ccg_schema")
        cls.mechanical = reg.load_json("mechanical_profile")
        Draft202012Validator.check_schema(cls.schema)

    def review(self, sources, settings=None):
        config = self.base if settings is None else settings
        parsed = parse_python_snapshot(sources)
        evidence = extract_python_token_blocks(
            parsed, sources, snapshot_id="pinned-source-A", profile=config,
        )
        profile = DuplicationProfile.from_mapping(config)
        result = evaluate_duplication(evidence, profile)
        Draft202012Validator(self.schema).validate(result.to_document())
        return evidence, result

    def test_exact_function_body_duplicates_have_source_witness(self):
        sources = {
            "pkg/a.py": "def alpha(x):\n" + BODY,
            "other/a.py": "def beta(x):\n" + BODY,
            "pkg/b.py": "def different(x):\n    return x * 9\n",
        }
        evidence, report = self.review(sources)
        self.assertEqual(report.status, "OBSERVED_DUPLICATION")
        self.assertEqual(len(report.groups), 1)
        group = report.groups[0]
        self.assertEqual({b.path for b in group.blocks}, {"pkg/a.py", "other/a.py"})
        self.assertTrue(all(b.start_line == 2 and b.end_line == 4 for b in group.blocks))
        self.assertEqual(report.duplicate_excess_tokens, group.token_count_per_block)
        self.assertAlmostEqual(
            report.observed_duplicate_fraction,
            report.duplicate_excess_tokens / report.evaluated_tokens,
        )
        self.assertEqual(report.profile_fingerprint, evidence.profile_fingerprint)

    def test_identifier_and_literal_normalization_are_profile_owned(self):
        a = {"a.py": "def a(x):\n    value = x + 2\n    return value * 3\n",
             "b.py": "def b(y):\n    output = y + 7\n    return output * 8\n"}
        _, raw = self.review(a)
        self.assertEqual(raw.status, "NO_DUPLICATES_OBSERVED")
        normalized = deepcopy(self.base)
        normalized["normalize_identifiers"] = True
        normalized["normalize_literals"] = True
        _, result = self.review(a, normalized)
        self.assertEqual(result.status, "OBSERVED_DUPLICATION")
        self.assertEqual(len(result.groups), 1)
        self.assertNotEqual(raw.profile_fingerprint, result.profile_fingerprint)

    def test_generated_and_vendor_content_explicitly_excluded(self):
        sources = {
            "src/a.py": "def a(x):\n" + BODY,
            "vendor/copy.py": "def b(x):\n" + BODY,
            "generated/copy.py": "def c(x):\n" + BODY,
        }
        evidence, result = self.review(sources)
        self.assertEqual(result.status, "NO_DUPLICATES_OBSERVED")
        self.assertEqual(result.eligible_blocks, 1)
        self.assertIn(("vendor/copy.py", "profile_excluded_path"), evidence.skipped)
        self.assertEqual(result.not_evaluated, ("excluded_or_unmeasured_function_blocks",))

    def test_trivial_boilerplate_does_not_meet_minimum(self):
        evidence, result = self.review({
            "a.py": "def f(): return 1\n",
            "b.py": "def g(): return 1\n",
        })
        self.assertEqual(result.status, "NOT_EVALUATED")
        self.assertIsNone(result.observed_duplicate_fraction)
        self.assertEqual(result.evaluated_tokens, 0)
        self.assertEqual(len(evidence.skipped), 2)

    def test_nested_scopes_are_not_double_counted(self):
        sources = {"nested.py": (
            "def outer(x):\n"
            "    def inner(y):\n"
            "        z = y + 2\n"
            "        return z * 4\n"
            "    return inner(x)\n"
        )}
        evidence, result = self.review(sources)
        self.assertEqual(len(evidence.blocks), 1)
        self.assertIn(("def::nested.py::outer@1:0",
                       "nested_scope_overlap_not_evaluated"), evidence.skipped)
        self.assertEqual(result.status, "NO_DUPLICATES_OBSERVED")

    def test_parse_errors_and_unsupported_extensions_preserve_partial_coverage(self):
        _, report = self.review({
            "okay.py": "def f(x):\n" + BODY,
            "broken.py": "def (",
            "foreign.rs": "fn main() {}",
        })
        self.assertEqual(report.coverage_status, "partial")
        self.assertEqual(dict(report.unprocessed), {
            "broken.py": "syntax_error", "foreign.rs": "unsupported_extension",
        })
        self.assertIn("unprocessed_selected_files", report.not_evaluated)
        self.assertNotEqual(report.interpretation, "P6_PASS")

    def test_input_order_and_pipeline_are_unchanged(self):
        sources = {
            "z/a.py": "def foo(x):\n" + BODY,
            "a/a.py": "def bar(x):\n" + BODY,
        }
        self.assertEqual(self.review(sources)[1].to_document(),
                         self.review(dict(reversed(list(sources.items()))))[1].to_document())
        old = analyze_python(sources, snapshot_id="pinned-source-A",
                             ccg_schema=self.ccg, mechanical_profile=self.mechanical)
        self.assertNotIn("duplication", old.to_document())

    def test_profile_drift_and_corrupted_witness_fail_closed(self):
        evidence, _ = self.review({"a.py": "def a(x):\n" + BODY})
        other = deepcopy(self.base)
        other["normalize_identifiers"] = True
        with self.assertRaises(DuplicationProfileError):
            evaluate_duplication(evidence, DuplicationProfile.from_mapping(other))
        for broken in (
            replace(evidence.blocks[0], path="not_analyzed.py"),
            replace(evidence.blocks[0], token_count=1),
        ):
            with self.subTest(block=broken), self.assertRaises(DuplicationProfileError):
                evaluate_duplication(replace(evidence, blocks=(broken,)),
                                     DuplicationProfile.from_mapping(self.base))
        for patch in (
            {"min_block_tokens": 1},
            {"excluded_prefixes": ["../vendor/"]},
            {"normalize_literals": "yes"},
            {"schema_version": "0.2"},
        ):
            with self.subTest(patch=patch), self.assertRaises(DuplicationProfileError):
                DuplicationProfile.from_mapping({**self.base, **patch})


if __name__ == "__main__":
    unittest.main()
