"""Exact-source domain comparison negative controls."""
import unittest
from codeqa.evaluation.domain_inventory import compare_domain_inventories, DomainInventoryError

def report(sha):
    return {
        "schema_version": "0.1", "source_scope": "CODEQA_PRODUCT_PYTHON",
        "domain_policy_sha256": "a"*64, "role_policy_sha256": "b"*64,
        "interpretation": "STATIC_SOURCE_WITNESSES_NOT_RUNTIME_COHESION_OR_COMPATIBILITY_PROOF",
        "snapshot_id": sha, "status": "NOT_EVALUATED",
        "inventory": [{"path": "src/codeqa/core/a.py", "sha256": "c"*64}],
        "observed_import_sites": 0, "classified_intra_import_sites": 0,
        "classified_cross_import_sites": 0, "import_witnesses": [],
    }

class DomainComparisonTests(unittest.TestCase):
    def test_no_quality_pass(self):
        result = compare_domain_inventories(report("1"*40), report("2"*40), analyzer_sha="3"*40)
        self.assertEqual(result["status"], "NOT_EVALUATED")
        self.assertEqual(result["metrics"]["source_files"]["delta"], 0)

    def test_forged_import_count_rejected(self):
        before, after = report("1"*40), report("2"*40)
        after["observed_import_sites"] = 1
        with self.assertRaisesRegex(DomainInventoryError, "metric contradicts"):
            compare_domain_inventories(before, after, analyzer_sha="3"*40)

    def test_missing_import_witnesses_rejected(self):
        before, after = report("1"*40), report("2"*40)
        del before["import_witnesses"]
        with self.assertRaisesRegex(DomainInventoryError, "missing source-backed"):
            compare_domain_inventories(before, after, analyzer_sha="3"*40)

    def test_foreign_source_import_witness_rejected(self):
        before, after = report("1"*40), report("2"*40)
        after["import_witnesses"] = [{
            "source": "src/foreign.py", "target": "src/codeqa/core/a.py",
            "line": 1, "classification": "CROSS_DOMAIN",
        }]
        after["observed_import_sites"] = 1
        after["classified_cross_import_sites"] = 1
        with self.assertRaisesRegex(DomainInventoryError, "invalid source-backed"):
            compare_domain_inventories(before, after, analyzer_sha="3"*40)

    def test_mismatched_policy_rejected(self):
        before, after = report("1"*40), report("2"*40)
        after["role_policy_sha256"] = "d"*64
        with self.assertRaises(DomainInventoryError):
            compare_domain_inventories(before, after, analyzer_sha="3"*40)
