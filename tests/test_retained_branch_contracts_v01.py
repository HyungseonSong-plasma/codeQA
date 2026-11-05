"""Retained branches: orphan contracts and Samuel E2E remain non-operative."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator

from codeqa.governance.samuel_native_pr_e2e import NativePrE2EError, qualify

ROOT = Path(__file__).resolve().parents[1]


class LegacyBranchAdmissionTests(unittest.TestCase):
    def test_formal_implementation_contract_is_valid_schema_not_gate_authority(self):
        document = json.loads(
            (ROOT / "contracts/qa/formal-implementation-binding-v0.1.schema.json").read_text()
        )
        Draft202012Validator.check_schema(document)
        self.assertEqual(document["$id"],
                         "urn:codeqa:formal:implementation-binding:v0.1")

    def test_samuel_native_pr_policy_is_disabled_by_default(self):
        policy = json.loads(
            (ROOT / "profiles/samuel-native-pr-create-e2e-v1.json").read_text()
        )
        self.assertIs(policy["enabled"], False)
        with self.assertRaises(NativePrE2EError):
            qualify(policy, {}, {})


if __name__ == "__main__":
    unittest.main()
