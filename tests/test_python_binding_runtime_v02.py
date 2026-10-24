"""#70 synthetic Python binding evidence without external SDK certification."""
from __future__ import annotations

from typing import override
import unittest

from codeqa.evaluation.python_binding_runtime_v02 import (
    BindingEvidenceError, inspect_callback, inspect_override,
)


class Base:
    def hook(self, value, *, mode="normal"):
        return value


class Compatible(Base):
    @override
    def hook(self, value, *, mode="normal"):
        return value


class MissingRequired(Base):
    def hook(self, value, added_required):
        return value


class WrongKeyword(Base):
    def hook(self, value):
        return value


class Orphan(Base):
    @override
    def missing(self, value):
        return value


class MixinOne:
    def step(self, value):
        return value


class MixinTwo:
    def step(self, value, *, extra):
        return value


class Ordered(MixinOne, MixinTwo):
    def step(self, value):
        return value


SHAPES = (((object(), 1), {"mode": "normal"}),)


class BindingRuntimeEvidenceTests(unittest.TestCase):
    def test_compatible_call_shape_is_not_typechecker_verified(self):
        evidence = inspect_override(Compatible, "hook", call_shapes=SHAPES)
        self.assertEqual(evidence.status, "SIGNATURE_SHAPE_CANDIDATE")
        self.assertEqual(evidence.sdk_status, "NOT_EVALUATED")
        self.assertEqual(evidence.typechecker_status, "NOT_EVALUATED")
        self.assertEqual(evidence.framework_runtime_status, "NOT_EVALUATED")
        self.assertTrue(evidence.override_marker_is_intent_only)

    def test_extra_required_argument_breaks_substitution(self):
        evidence = inspect_override(
            MissingRequired, "hook", call_shapes=(((object(), 1), {}),))
        self.assertEqual(evidence.status, "INCOMPATIBLE_SIGNATURE")

    def test_missing_keyword_breaks_contract(self):
        evidence = inspect_override(WrongKeyword, "hook", call_shapes=SHAPES)
        self.assertEqual(evidence.status, "INCOMPATIBLE_SIGNATURE")

    def test_override_decorator_is_only_intent_without_ancestor(self):
        evidence = inspect_override(
            Orphan, "missing", call_shapes=(((object(), 1), {}),))
        self.assertEqual(evidence.status, "UNRESOLVED")
        self.assertIsNone(evidence.owner)

    def test_exact_python_mro_is_not_arbitrary_base_guessing(self):
        evidence = inspect_override(
            Ordered, "step", call_shapes=(((object(), 1), {}),))
        self.assertEqual(evidence.status, "SIGNATURE_SHAPE_CANDIDATE")
        self.assertIn("MixinOne", evidence.owner)

    def test_callback_is_distinct_from_inheritance(self):
        def required(event, *, key):
            return event
        def wrong(event):
            return event
        evidence = inspect_callback(
            required, wrong, name="on_event",
            call_shapes=(((object(),), {"key": "x"}),))
        self.assertEqual(evidence.kind, "callback")
        self.assertEqual(evidence.status, "INCOMPATIBLE_SIGNATURE")

    def test_invalid_contract_sample_is_not_compatibility_evidence(self):
        with self.assertRaises(BindingEvidenceError):
            inspect_override(Compatible, "hook",
                             call_shapes=(((object(),), {"nonsense": 1}),))

    def test_no_call_shapes_is_unresolved_not_success(self):
        evidence = inspect_override(Compatible, "hook", call_shapes=())
        self.assertEqual(evidence.status, "UNRESOLVED")


if __name__ == "__main__":
    unittest.main()
