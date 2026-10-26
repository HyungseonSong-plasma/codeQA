"""Non-mutating rename impact evidence tests (#76)."""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import json
import unittest

from jsonschema import Draft202012Validator

from codeqa.evaluation.naming_rename_impact_v02 import (
    RenameImpactError, SymbolWitness, ReferenceWitness, assess_rename_impact,
)

REV = "git:owner/repo@" + "a" * 40
SOURCE = "def OldName(): pass\nOldName()\ndef OldNameSuffix(): pass\n"
SOURCES = {"src/sample.py": SOURCE}
DIGEST = sha256(SOURCE.encode()).hexdigest()


class RenameImpactTests(unittest.TestCase):
    def make_symbol(self, **kwargs):
        base = SymbolWitness(
            path="src/sample.py", name="OldName", kind="function",
            line=1, source_sha256=DIGEST, boundary="internal",
            binding_verified=True,
        )
        return replace(base, **kwargs)

    def assess(self, **kwargs):
        args = dict(
            revision=REV, sources=SOURCES, symbol=self.make_symbol(),
            proposed_name="new_name", references=(),
            source_selection_complete=True, policy_id="repo-naming-v0.2",
        )
        args.update(kwargs)
        return assess_rename_impact(**args)

    def test_verified_lexical_evidence_still_cannot_certify_rename(self):
        ref = ReferenceWitness("src/sample.py", 2, DIGEST, "verified_lexical", "OldName")
        report = self.assess(references=(ref,))
        self.assertEqual(report.lexical_reference_count, 1)
        self.assertEqual(report.verdict, "UNVERIFIED_PROPOSAL")
        self.assertFalse(report.mutation_performed)
        self.assertEqual(report.migration_plan, "HUMAN_REVIEW_REQUIRED")

    def test_boundaries_force_separate_contract_review(self):
        for boundary in ("public_api", "external_sdk", "override", "dto_inbound",
                         "dto_outbound", "db_physical", "rust_trait",
                         "cpp_virtual_abi", "moose_reserved_dsl"):
            with self.subTest(boundary=boundary):
                report = self.assess(symbol=self.make_symbol(
                    boundary=boundary, binding_verified=True,
                    contract_revision="sdk@pinned123"))
                self.assertEqual(report.verdict, "BLOCKED_CONTRACT_REVIEW")
                self.assertIn("external_or_persisted_contract:" + boundary,
                              report.blockers)

    def test_unverified_or_dynamic_evidence_is_not_safety_proof(self):
        report = self.assess(symbol=self.make_symbol(
            boundary="dynamic_call", binding_verified=False),
            source_selection_complete=False,
            references=(ReferenceWitness(
                "src/sample.py", 2, DIGEST, "unresolved_dynamic", "OldName"),))
        self.assertIn("incomplete_source_selection", report.unknowns)
        self.assertIn("unresolved_symbol_boundary:dynamic_call", report.unknowns)
        self.assertIn("unresolved_reference:unresolved_dynamic", report.unknowns)

    def test_missing_contract_provenance_is_visible(self):
        report = self.assess(symbol=self.make_symbol(
            boundary="db_physical", binding_verified=False))
        self.assertIn("unverified_boundary_contract", report.unknowns)
        self.assertEqual(report.verdict, "BLOCKED_CONTRACT_REVIEW")

    def test_forged_revision_source_and_locations_rejected(self):
        with self.assertRaises(RenameImpactError):
            self.assess(revision="main")
        with self.assertRaises(RenameImpactError):
            self.assess(symbol=self.make_symbol(source_sha256="0" * 64))
        with self.assertRaises(RenameImpactError):
            self.assess(symbol=self.make_symbol(line=42))
        with self.assertRaises(RenameImpactError):
            self.assess(symbol=self.make_symbol(path="../escape.py"))

    def test_immutable_revision_repository_dot_segments_rejected(self):
        for repository in ("../repo", "./repo", "owner/..", "owner/."):
            with self.subTest(repository=repository):
                with self.assertRaisesRegex(RenameImpactError, "immutable Git revision"):
                    self.assess(revision="git:" + repository + "@" + "a" * 40)

    def test_python_keyword_is_not_a_declaration_symbol(self):
        source = "def Actual(): pass\n"
        digest = sha256(source.encode()).hexdigest()
        witness = self.make_symbol(name="def", source_sha256=digest)
        with self.assertRaisesRegex(RenameImpactError, "Python source identifier"):
            self.assess(sources={"src/sample.py": source}, symbol=witness)

    def test_substring_reference_is_not_a_valid_token(self):
        ref = ReferenceWitness(
            "src/sample.py", 3, DIGEST, "verified_lexical", "OldName")
        with self.assertRaisesRegex(RenameImpactError, "lexical token"):
            self.assess(references=(ref,))

    def test_duplicate_or_forged_references_fail_closed(self):
        ref = ReferenceWitness(
            "src/sample.py", 2, DIGEST, "verified_lexical", "OldName")
        with self.assertRaisesRegex(RenameImpactError, "duplicate"):
            self.assess(references=(ref, ref))
        with self.assertRaisesRegex(RenameImpactError, "target mismatch"):
            self.assess(references=(replace(ref, target_name="other"),))

    def test_proposal_report_validates_separate_versioned_schema(self):
        root = Path(__file__).resolve().parents[1]
        schema = json.loads((root / "contracts/qa/naming-rename-impact-v0.2-draft.schema.json").read_text())
        Draft202012Validator.check_schema(schema)
        report = self.assess(symbol=self.make_symbol(boundary="public_api"))
        Draft202012Validator(schema).validate(report.to_document())
        self.assertFalse(report.to_document()["mutation_performed"])

    def test_invalid_python_target_identifier_is_not_a_migration_candidate(self):
        for bad in ("class", "with space", "bad-name", "qualified.name",
                    "bad/name", "line\nbreak", "9leading"):
            with self.subTest(bad=repr(bad)):
                with self.assertRaisesRegex(RenameImpactError, "Python rename target"):
                    self.assess(proposed_name=bad)

    def test_unicode_python_identifier_remains_unverified_proposal(self):
        report = self.assess(proposed_name="Δposition")
        self.assertEqual(report.verdict, "UNVERIFIED_PROPOSAL")
        self.assertEqual(report.migration_plan, "HUMAN_REVIEW_REQUIRED")

    def test_python_comment_or_string_is_not_a_declaration_witness(self):
        for text in ('# OldName\ndef real(): pass\n',
                     'label = "OldName"\n'):
            with self.subTest(text=text):
                sources = {"src/sample.py": text}
                witness = self.make_symbol(
                    line=1, source_sha256=sha256(text.encode()).hexdigest())
                with self.assertRaisesRegex(RenameImpactError, "declaration lexical"):
                    self.assess(sources=sources, symbol=witness)

    def test_python_comment_or_string_is_not_a_reference_witness(self):
        for suffix in ('# OldName\n', 'label = "OldName"\n'):
            with self.subTest(suffix=suffix):
                text = SOURCE + suffix
                digest = sha256(text.encode()).hexdigest()
                symbol = self.make_symbol(source_sha256=digest)
                ref = ReferenceWitness(
                    "src/sample.py", 4, digest, "verified_lexical", "OldName")
                with self.assertRaisesRegex(RenameImpactError, "reference lexical token"):
                    self.assess(sources={"src/sample.py": text},
                                symbol=symbol, references=(ref,))

    def test_syntax_invalid_python_cannot_certify_lexical_declaration(self):
        text = "def OldName(:\n    pass\n"
        witness = self.make_symbol(source_sha256=sha256(text.encode()).hexdigest())
        with self.assertRaisesRegex(RenameImpactError, "declaration lexical"):
            self.assess(sources={"src/sample.py": text}, symbol=witness)

    def test_parseable_stub_python_name_remains_proposal_only(self):
        text = "def OldName() -> None: ...\n"
        witness = self.make_symbol(
            path="src/sample.pyi", source_sha256=sha256(text.encode()).hexdigest())
        result = self.assess(sources={"src/sample.pyi": text}, symbol=witness)
        self.assertEqual(result.verdict, "UNVERIFIED_PROPOSAL")
        self.assertEqual(result.migration_plan, "HUMAN_REVIEW_REQUIRED")

    def test_invalid_policy_and_identity_rejected(self):
        with self.assertRaises(RenameImpactError):
            self.assess(policy_id="../not-pinned")
        with self.assertRaises(RenameImpactError):
            self.assess(proposed_name="OldName")
        with self.assertRaises(RenameImpactError):
            self.assess(symbol=self.make_symbol(boundary="invented"))


if __name__ == "__main__":
    unittest.main()
