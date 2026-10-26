"""Bounded field evidence and fail-closed counterexamples for Issue #91."""
from __future__ import annotations

from dataclasses import fields, is_dataclass
from hashlib import sha256
from pathlib import Path
import unittest

from codeqa.core.naming_field_classification_v03 import (
    FieldClassificationError, classify_pinned_class_annotation,
)
from codeqa.core.naming_glossary import GlossaryTerm
from codeqa.infrastructure.git import GitReader

ROOT = Path(__file__).resolve().parents[1]
HISTORICAL = "dfd94bb25d52642bb2e46766b1ebe074c2f82803"
DIGEST = "09b89f5f492f6d449257e1c6baa4bc1ea98dedd17e93b9f13ced1c62fbcd9d2c"


class FieldClassificationV03Tests(unittest.TestCase):
    def check(self, body: str, expected: str, annotation: str = "x:") -> None:
        source = body.encode("utf-8")
        line = next(i for i, x in enumerate(body.splitlines(), 1)
                    if x.strip().startswith(annotation))
        observed = classify_pinned_class_annotation(
            source, expected_sha256=sha256(source).hexdigest(),
            owner="C", name="x", line=line)
        self.assertEqual(observed.classification, expected)
        self.assertEqual(observed.runtime_field_verification, "NOT_EVALUATED")
        self.assertEqual(observed.naming_policy_applicability, "NOT_EVALUATED")
        self.assertFalse(observed.rename_authorized)

    def test_historical_canonical_source_and_separate_runtime_witness(self):
        source = GitReader(ROOT).read_file(
            HISTORICAL, "src/codeqa/core/naming_glossary.py")
        r = classify_pinned_class_annotation(
            source, expected_sha256=DIGEST,
            owner="GlossaryTerm", name="canonical", line=34)
        self.assertEqual(r.classification, "FIELD_CANDIDATE")
        self.assertEqual(r.annotation_site, "DIRECT_CLASS_ANNASSIGN")
        self.assertEqual(r.runtime_field_verification, "NOT_EVALUATED")
        self.assertFalse(r.rename_authorized)
        # Runtime evidence is deliberately SEPARATE from the static certificate.
        self.assertTrue(is_dataclass(GlossaryTerm))
        self.assertIn("canonical", [f.name for f in fields(GlossaryTerm)])

    def test_bare_class_annotation_is_not_proven_instance_field(self):
        self.check("class C:\n    x: str\n", "CLASS_ANNOTATION_ONLY")

    def test_direct_simple_field_is_candidate_not_semantic_pass(self):
        self.check("from dataclasses import dataclass\n@dataclass(frozen=True, slots=True)\n"
                   "class C:\n    x: str\n", "FIELD_CANDIDATE")

    def test_import_proven_classvar_initvar_kw_only_are_pseudofields(self):
        specimens = [
            ("from typing import ClassVar\n", "ClassVar[int]"),
            ("import typing as t\n", "t.ClassVar[int]"),
            ("from dataclasses import InitVar\n", "InitVar[int]"),
            ("import dataclasses as dc\n", "dc.InitVar[int]"),
            ("from dataclasses import KW_ONLY\n", "KW_ONLY"),
        ]
        for imports, annotation in specimens:
            with self.subTest(annotation=annotation):
                self.check("from dataclasses import dataclass\n" + imports +
                           "@dataclass\nclass C:\n    x: " + annotation + "\n",
                           "PSEUDO_FIELD_EXCLUDED")

    def test_unresolved_special_annotation_never_assumed_real_or_pseudo(self):
        for annotation in ("ClassVar[int]", "InitVar[int]", "KW_ONLY",
                           "Final[int]", "'ClassVar[int]'"):
            with self.subTest(annotation=annotation):
                self.check("from dataclasses import dataclass\n@dataclass\n"
                           "class C:\n    x: " + annotation + "\n", "REVIEW_REQUIRED")

    def test_final_is_not_wrongly_equated_to_classvar(self):
        self.check("from dataclasses import dataclass\nfrom typing import Final\n"
                   "@dataclass\nclass C:\n    x: Final[int]\n", "REVIEW_REQUIRED")

    def test_unshadowed_stdlib_aliases_are_syntactic_candidates(self):
        for source in ("from dataclasses import dataclass as dc\n@dc\n"
                       "class C:\n    x: str\n",
                       "import dataclasses as dc\n@dc.dataclass\n"
                       "class C:\n    x: str\n"):
            with self.subTest(source=source[:35]):
                self.check(source, "FIELD_CANDIDATE")

    def test_decorator_spelling_rebinding_composition_and_late_import(self):
        for src in ("@dataclass\nclass C:\n    x: str\n",
                    "@dataclass\nclass C:\n    x: str\nfrom dataclasses import dataclass\n",
                    "from dataclasses import dataclass\n"
                    "dataclass = lambda x: x\n@dataclass\nclass C:\n    x: str\n",
                    "from dataclasses import dataclass\n"
                    "@other\n@dataclass\nclass C:\n    x: str\n",
                    "from dataclasses import dataclass\n"
                    "@dataclass(unsafe=foo)\nclass C:\n    x: str\n",
                    "from dataclasses import dataclass\n"
                    "from anything import *\n@dataclass\nclass C:\n    x: str\n"):
            with self.subTest(src=src[:50]):
                self.check(src, "REVIEW_REQUIRED")

    def test_bases_metaclasses_and_dynamic_class_body_force_review(self):
        for context in ("class C(Base):", "class C(metaclass=M):"):
            self.check("from dataclasses import dataclass\n@dataclass\n" +
                       context + "\n    x: str\n", "REVIEW_REQUIRED")
        for tail in ("    x = 'shadow'\n", "    x: int\n",
                     "    def x(self): pass\n", "    __annotations__ = {}\n",
                     "    exec('x=1')\n", "    if True:\n        y: int\n"):
            with self.subTest(tail=tail):
                self.check("from dataclasses import dataclass\n@dataclass\n"
                           "class C:\n    x: str\n" + tail, "REVIEW_REQUIRED")

    def test_typing_marker_shadowing_disables_pseudo_field_certification(self):
        self.check("from dataclasses import dataclass\nfrom typing import ClassVar\n"
                   "@dataclass\nclass C:\n    ClassVar = str\n    x: ClassVar[int]\n",
                   "REVIEW_REQUIRED")

    def test_parenthesized_name_has_simple_zero(self):
        self.check("from dataclasses import dataclass\n@dataclass\n"
                   "class C:\n    (x): int\n", "REVIEW_REQUIRED", "(x)")

    def test_default_factories_and_descriptors_need_separate_evidence(self):
        for value in ("field(default_factory=list)",
                      "property(lambda self: 1)", "factory()"):
            with self.subTest(value=value):
                self.check("from dataclasses import dataclass, field\n@dataclass\n"
                           "class C:\n    x: int = " + value + "\n", "REVIEW_REQUIRED")

    def test_stale_source_or_wrong_line_owner_raises(self):
        source = b"class C:\n    x: str\n"
        for digest, owner, line in (
            ("0" * 64, "C", 2),
            (sha256(source).hexdigest(), "Unknown", 2),
            (sha256(source).hexdigest(), "C", 3),
        ):
            with self.subTest(owner=owner, line=line):
                with self.assertRaises(FieldClassificationError):
                    classify_pinned_class_annotation(
                        source, expected_sha256=digest,
                        owner=owner, name="x", line=line)


if __name__ == "__main__":
    unittest.main()
