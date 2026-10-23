"""Portable adapter capability contract: positive and adversarial examples."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator

from codeqa.adapters.capability import AdapterCapabilityError, validate_adapter_capability
from codeqa.infrastructure.resources import ResourceRegistry


ROOT = Path(__file__).resolve().parents[1]


class AdapterCapabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        registry = ResourceRegistry(ROOT)
        cls.schema = registry.load_json("adapter_capability_schema")
        cls.python = registry.load_json("python_adapter_capability")
        Draft202012Validator.check_schema(cls.schema)

    def test_version_and_grounded_python_profile(self):
        doc = validate_adapter_capability(self.python, self.schema)
        self.assertEqual(doc["adapter"]["language"], "python")
        self.assertEqual(doc["output"]["graph_contract"], "CCG:0.1")
        self.assertEqual(doc["input"]["acquisition"], "caller_supplied")
        self.assertEqual(doc["input"]["selection"], "caller_supplied_paths_only")
        names = {feature["name"]: feature["status"] for feature in doc["features"]}
        self.assertEqual(names["decorator_expressions"], "NOT_EVALUATED")
        self.assertEqual(names["local_lexical_calls"], "PARTIAL")
        self.assertEqual(names["relative_import_alias_syntax"], "SUPPORTED")
        self.assertEqual(names["dynamic_runtime_dispatch"], "NOT_EVALUATED")

    def test_invalid_schema_version_and_missing_identity_fail(self):
        for mutation in ("version", "adapter", "parser", "language"):
            with self.subTest(mutation=mutation):
                doc = deepcopy(self.python)
                if mutation == "version":
                    doc["schema_version"] = "1.0"
                elif mutation == "adapter":
                    del doc["adapter"]["id"]
                elif mutation == "parser":
                    del doc["adapter"]["parser"]
                else:
                    doc["adapter"]["language"] = ""
                with self.assertRaises(AdapterCapabilityError):
                    validate_adapter_capability(doc, self.schema)

    def test_unsupported_feature_claims_and_coverage_states_fail_closed(self):
        for mutation in ("feature_status", "coverage", "graph_version", "extra", "no_limit"):
            with self.subTest(mutation=mutation):
                doc = deepcopy(self.python)
                if mutation == "feature_status":
                    doc["features"][0]["status"] = "PASS"
                elif mutation == "coverage":
                    doc["output"]["coverage_statuses"] = ["complete"]
                elif mutation == "graph_version":
                    doc["output"]["graph_contract"] = "CCG:2.0"
                elif mutation == "extra":
                    doc["quality_verdict"] = "PASS"
                else:
                    doc["limitations"] = []
                with self.assertRaises(AdapterCapabilityError):
                    validate_adapter_capability(doc, self.schema)

    def test_duplicate_names_and_config_conflict_are_invalid(self):
        for mutation in ("duplicate_feature", "overlapping_config", "executes_source"):
            with self.subTest(mutation=mutation):
                doc = deepcopy(self.python)
                if mutation == "duplicate_feature":
                    doc["features"].append(dict(doc["features"][0], evidence="different wording"))
                elif mutation == "overlapping_config":
                    doc["input"]["configuration"]["supported"].append(
                        doc["input"]["configuration"]["unsupported"][0]
                    )
                else:
                    doc["adapter"]["parser"]["execution"] = "executes_target"
                with self.assertRaises(AdapterCapabilityError):
                    validate_adapter_capability(doc, self.schema)

    def test_documentation_does_not_promise_source_execution_or_full_resolution(self):
        text = (ROOT / "docs/contracts/language-adapter-0.1.md").read_text(encoding="utf-8")
        self.assertIn("NOT_EVALUATED", text)
        self.assertIn("CCG v0.1", text)
        self.assertIn("caller", text.lower())


if __name__ == "__main__":
    unittest.main()
