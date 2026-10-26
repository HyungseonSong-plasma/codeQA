"""Test that changing __init__ declarations is review-only."""
import unittest
from codeqa.evaluation.domain_inventory import compare_domain_inventories

def record(sha, exported):
    return {
        "schema_version": "0.1", "snapshot_id": sha,
        "source_scope": "CODEQA_PRODUCT_PYTHON",
        "domain_policy_sha256": "a"*64, "role_policy_sha256": "b"*64,
        "interpretation": "STATIC_SOURCE_WITNESSES_NOT_RUNTIME_COHESION_OR_COMPATIBILITY_PROOF",
        "status": "NOT_EVALUATED", "inventory": [],
        "observed_import_sites": 0, "classified_intra_import_sites": 0,
        "classified_cross_import_sites": 0, "import_witnesses": [],
        "init_import_candidates": exported,
    }

class ImportDeltaTests(unittest.TestCase):
    def test_removed_candidate_is_not_api_compatibility_pass(self):
        candidate = {"path": "src/codeqa/core/__init__.py", "from": ".graph",
                     "name": "Graph", "asname": None}
        result = compare_domain_inventories(
            record("1"*40, [candidate]), record("2"*40, []), analyzer_sha="3"*40,
        )
        self.assertEqual(result["status"], "NOT_EVALUATED")
        self.assertEqual(result["init_import_change_review"]["status"], "REVIEW_REQUIRED")
