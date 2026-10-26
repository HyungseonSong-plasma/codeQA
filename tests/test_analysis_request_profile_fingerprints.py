"""Request response profile identities are deterministic, not signatures."""
from hashlib import sha256
import json
from pathlib import Path
import unittest

from codeqa.infrastructure.resources import ResourceRegistry
from codeqa.pipeline.analysis_request import AnalysisRequest, analyze_python_request

ROOT = Path(__file__).resolve().parents[1]


class RequestProfileFingerprintTests(unittest.TestCase):
    def test_actual_registered_profiles_have_exact_hash_witnesses(self):
        resources = ResourceRegistry(ROOT)
        ccg = resources.load_json("ccg_schema")
        mechanical = resources.load_json("mechanical_profile")
        req = AnalysisRequest(
            sources={"sample.py": "def f():\n    return 1\n"},
            snapshot_id="git:source-only-fixture",
            ccg_schema=ccg,
            mechanical_profile=mechanical,
        )
        result = analyze_python_request(req)
        recorded = result.summary_document()["profile_fingerprints"]
        for name, resource in (("ccg_schema", ccg), ("mechanical_profile", mechanical)):
            expected = sha256(json.dumps(resource, sort_keys=True).encode()).hexdigest()
            self.assertEqual(recorded[name], expected)
        self.assertEqual(result.companion_states["naming"], "NOT_REQUESTED")
        self.assertEqual(result.companion_states["formal"], "NOT_REQUESTED")


if __name__ == "__main__":
    unittest.main()
