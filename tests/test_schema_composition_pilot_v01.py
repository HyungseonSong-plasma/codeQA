"""Issue #282: bounded in-memory composition pilot; no public contract migration.

The experiment uses the two existing architecture schemas as immutable
goldens. It deliberately does not publish a generator or change their $ids.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
METRICS = "contracts/qa/architecture-metrics-v0.1.schema.json"
INVENTORY = "contracts/qa/architecture-inventory-v0.1.schema.json"
FRAGMENTS = {
    "sha256": (("$defs", "sha256"),),
    "limitations": (("properties", "limitations"),),
}


def _at(document: dict, path: tuple[str, ...]) -> dict:
    result = document
    for part in path:
        result = result[part]
    return result


def _replace(document: dict, path: tuple[str, ...], value: dict) -> None:
    target = document
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = deepcopy(value)


def _reconstruct(item, fragments: dict[str, dict]):
    if isinstance(item, dict):
        if "$fragment" in item:
            if set(item) != {"$fragment"}:
                raise ValueError("fragment marker must be the whole object")
            name = item["$fragment"]
            if name not in fragments:
                raise ValueError("unknown reusable fragment")
            value = fragments[name]
            if not isinstance(value, dict) or "$fragment" in value:
                raise ValueError("nested or invalid fragment")
            return deepcopy(value)
        return {key: _reconstruct(value, fragments)
                for key, value in item.items()}
    if isinstance(item, list):
        return [_reconstruct(value, fragments) for value in item]
    return item


def _prepare_pair(metrics: dict, inventory: dict):
    """Extract only exact semantic-structure matches; refuse name-only matches."""
    candidates = (metrics, inventory)
    shared: dict[str, dict] = {}
    templates = [deepcopy(metrics), deepcopy(inventory)]
    locations = {
        "sha256": ("$defs", "sha256"),
        "limitations": ("properties", "limitations"),
    }
    for name, path in locations.items():
        values = [_at(source, path) for source in candidates]
        if values[0] != values[1]:
            raise ValueError("same name with different validation semantics")
        shared[name] = deepcopy(values[0])
        for template in templates:
            _replace(template, path, {"$fragment": name})
    return templates, shared


class SchemaCompositionPilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baselines = [
            json.loads((ROOT / name).read_text(encoding="utf-8"))
            for name in (METRICS, INVENTORY)
        ]

    def test_two_schema_round_trip_is_exact_and_standalone(self):
        templates, primitives = _prepare_pair(*self.baselines)
        for baseline, template in zip(self.baselines, templates):
            rebuilt = _reconstruct(template, primitives)
            self.assertEqual(rebuilt, baseline)
            Draft202012Validator.check_schema(rebuilt)
            # Existing local references are retained exactly, not rewritten
            # to URLs requiring network or shared-document resolvers.
            text = json.dumps(rebuilt, sort_keys=True)
            self.assertNotIn('"$fragment"', text)
            self.assertNotIn('"$ref": "http', text)
            self.assertNotIn('"$ref": "../', text)
            self.assertEqual(rebuilt["$id"], baseline["$id"])

    def test_positive_and_negative_sha256_semantics_match(self):
        templates, primitives = _prepare_pair(*self.baselines)
        for baseline, template in zip(self.baselines, templates):
            rebuilt = _reconstruct(template, primitives)
            old = Draft202012Validator(_at(baseline, ("$defs", "sha256")))
            new = Draft202012Validator(_at(rebuilt, ("$defs", "sha256")))
            for value in ("0" * 64, "a" * 64, "0" * 63, "g" * 64, "", 0, None):
                with self.subTest(schema=baseline.get("title"), value=value):
                    self.assertEqual(old.is_valid(value), new.is_valid(value))
            self.assertTrue(new.is_valid("a" * 64))
            self.assertFalse(new.is_valid("g" * 64))

    def test_divergent_semantics_refuse_extraction(self):
        bad = deepcopy(self.baselines[1])
        bad["$defs"]["sha256"]["maxLength"] = 64
        with self.assertRaisesRegex(ValueError, "different validation semantics"):
            _prepare_pair(self.baselines[0], bad)
        bad = deepcopy(self.baselines[1])
        bad["properties"]["limitations"]["minItems"] = 0
        with self.assertRaisesRegex(ValueError, "different validation semantics"):
            _prepare_pair(self.baselines[0], bad)

    def test_unknown_or_mixed_fragment_fails_closed(self):
        for template in (
            {"$fragment": "unknown"},
            {"$fragment": "sha256", "type": "number"},
        ):
            with self.subTest(template=template):
                with self.assertRaises(ValueError):
                    _reconstruct(template, {"sha256": {"type": "string"}})
        with self.assertRaisesRegex(ValueError, "nested or invalid"):
            _reconstruct(
                {"$fragment": "sha256"},
                {"sha256": {"$fragment": "recursive"}},
            )

    def test_composition_does_not_change_baseline_bytes(self):
        # The pilot's candidate output is held only in memory; it has no
        # authority to overwrite the normative files or package registry.
        templates, shared = _prepare_pair(*self.baselines)
        assert all(_reconstruct(t, shared) == b
                   for t, b in zip(templates, self.baselines))
        for path in (METRICS, INVENTORY):
            data = (ROOT / path).read_bytes()
            self.assertTrue(data.endswith(b"\n"))
            self.assertNotIn(b'"$fragment"', data)


if __name__ == "__main__":
    unittest.main()
