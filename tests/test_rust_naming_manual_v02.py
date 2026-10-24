"""Manual Rust naming evidence: classification must never imply a parser PASS."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from codeqa.evaluation.rust_naming_manual_v02 import (
    RustManualEvidenceError, assess_manual_rust_naming,
)

ROOT = Path(__file__).resolve().parents[1]


def specimen():
    profile = json.loads(
        (ROOT / "profiles/rust-naming-manual-v0.2-draft.json").read_text())
    manifest = json.loads(
        (ROOT / "fixtures/rust-naming/manual-witness-v0.2-draft.json").read_text())
    source = (ROOT / "fixtures/rust-naming/synthetic.rs.txt").read_text()
    return profile, manifest, source


class RustManualWitnessTests(unittest.TestCase):
    def test_pinned_synthetic_witnesses_never_claim_compiler(self):
        profile, manifest, source = specimen()
        report = assess_manual_rust_naming(profile, manifest, source)
        self.assertEqual(len(report.observations), 15)
        self.assertEqual(report.parser_status, "NOT_EVALUATED")
        self.assertEqual(report.compiler_status, "NOT_EVALUATED")
        self.assertEqual(report.trait_resolution_status, "NOT_EVALUATED")
        self.assertEqual(report.source_revision_status, "NOT_EVALUATED")
        self.assertFalse(report.runtime_approved)
        self.assertEqual(sum(x.status == "STYLE_MATCH_CANDIDATE"
                             for x in report.observations), 8)
        self.assertEqual(sum(x.status == "STYLE_REVIEW_CANDIDATE"
                             for x in report.observations), 1)
        self.assertEqual(sum(x.status == "NOT_EVALUATED"
                             for x in report.observations), 6)

    def test_trait_required_method_precedence_is_unknown_not_style_failure(self):
        p, m, s = specimen()
        r = assess_manual_rust_naming(p, m, s)
        trait_methods = [x for x in r.observations if x.name == "processInput"]
        self.assertEqual(len(trait_methods), 2)
        self.assertTrue(all(x.status == "NOT_EVALUATED" for x in trait_methods))
        named = next(x for x in r.observations if x.name == "BadHelper")
        self.assertEqual(named.status, "STYLE_REVIEW_CANDIDATE")

    def test_external_reexport_macro_raw_identifiers_are_unresolved(self):
        p, m, s = specimen()
        r = assess_manual_rust_naming(p, m, s)
        for name in ("generate_item", "ExternalThing", "r#type", "GeneratedItem"):
            with self.subTest(name=name):
                self.assertEqual(next(x for x in r.observations if x.name == name).status,
                                 "NOT_EVALUATED")

    def test_forged_digest_drift_fails_closed(self):
        p, m, s = specimen()
        with self.assertRaises(RustManualEvidenceError):
            assess_manual_rust_naming(p, m, s + " ")
        m["source_sha256"] = "0" * 64
        with self.assertRaises(RustManualEvidenceError):
            assess_manual_rust_naming(p, m, s)

    def test_forged_parser_or_compiler_status_is_rejected(self):
        p, m, s = specimen()
        for obj, key in ((p, "parser_status"), (p, "compiler_status"),
                         (m, "trait_resolution_status")):
            x, y = deepcopy(p), deepcopy(m)
            (x if obj is p else y)[key] = "VERIFIED"
            with self.assertRaises(RustManualEvidenceError):
                assess_manual_rust_naming(x, y, s)

    def test_false_line_and_duplicate_witness_rejected(self):
        p, m, s = specimen()
        m["witnesses"][0]["line"] = 4
        with self.assertRaises(RustManualEvidenceError):
            assess_manual_rust_naming(p, m, s)
        p, m, s = specimen()
        m["witnesses"].append(deepcopy(m["witnesses"][0]))
        with self.assertRaises(RustManualEvidenceError):
            assess_manual_rust_naming(p, m, s)

    def test_unicode_and_unsupported_category_never_prove_style(self):
        p, m, s = specimen()
        m["witnesses"][0]["name"] = "RuntіmeApi"
        with self.assertRaises(RustManualEvidenceError):
            assess_manual_rust_naming(p, m, s)
        p, m, s = specimen()
        m["witnesses"][0]["kind"] = "unknown_syntax"
        result = assess_manual_rust_naming(p, m, s)
        self.assertEqual(result.observations[0].status, "NOT_EVALUATED")


if __name__ == "__main__":
    unittest.main()
