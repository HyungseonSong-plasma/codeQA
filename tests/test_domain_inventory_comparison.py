"""Exact-source domain comparison negative controls."""
import unittest
from codeqa.evaluation.domain_inventory import compare_domain_inventories, DomainInventoryError

def report(sha):
    return {
        "schema_version": "0.1", "source_scope": "CODEQA_PRODUCT_PYTHON",
        "domain_policy_sha256": "a"*64, "role_policy_sha256": "b"*64,
        "interpretation": "STATIC_SOURCE_WITNESSES_NOT_RUNTIME_COHESION_OR_COMPATIBILITY_PROOF",
        "snapshot_id": sha, "status": "NOT_EVALUATED",
        "inventory": [
            {"path": "src/codeqa/core/a.py", "sha256": "c"*64, "domain": "mechanical"},
            {"path": "src/codeqa/core/b.py", "sha256": "d"*64, "domain": "naming"},
        ],
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


    def _one_edge(self, classification="CROSS_DOMAIN", *, source_domain="mechanical",
                  target_domain="naming"):
        before, after = report("1"*40), report("2"*40)
        after["import_witnesses"] = [{
            "source": "src/codeqa/core/a.py",
            "target": "src/codeqa/core/b.py",
            "line": 1, "expression": "import b", "execution": "top_level",
            "source_domain": source_domain, "target_domain": target_domain,
            "classification": classification,
        }]
        after["observed_import_sites"] = 1
        after["classified_intra_import_sites"] = int(classification == "INTRA_DOMAIN")
        after["classified_cross_import_sites"] = int(classification == "CROSS_DOMAIN")
        return before, after

    def test_source_domain_witness_consistency_positive(self):
        before, after = self._one_edge()
        result = compare_domain_inventories(before, after, analyzer_sha="3"*40)
        self.assertEqual(result["metrics"]["classified_cross_import_sites"]["after"], 1)
        self.assertEqual(result["status"], "NOT_EVALUATED")

    def test_forged_cross_domain_edge_as_intra_rejected(self):
        before, after = self._one_edge("INTRA_DOMAIN")
        with self.assertRaisesRegex(DomainInventoryError, "contradicts source domain"):
            compare_domain_inventories(before, after, analyzer_sha="3"*40)

    def test_forged_endpoint_domain_label_rejected(self):
        before, after = self._one_edge(target_domain="mechanical")
        with self.assertRaisesRegex(DomainInventoryError, "contradicts source domain"):
            compare_domain_inventories(before, after, analyzer_sha="3"*40)

    def test_ambiguous_source_cannot_claim_cross_domain(self):
        before, after = self._one_edge()
        after["inventory"][0]["domain"] = "AMBIGUOUS"
        with self.assertRaisesRegex(DomainInventoryError, "contradicts source domain"):
            compare_domain_inventories(before, after, analyzer_sha="3"*40)

    def test_missing_inventory_domain_is_not_a_comparable_witness(self):
        before, after = self._one_edge()
        del before["inventory"][0]["domain"]
        with self.assertRaisesRegex(DomainInventoryError, "source domain classification"):
            compare_domain_inventories(before, after, analyzer_sha="3"*40)

    def test_unselected_public_init_import_cannot_forge_breakage(self):
        before, after = report("1"*40), report("2"*40)
        before["init_import_candidates"] = [{
            "path": "src/codeqa/core/__init__.py", "from": ".legacy",
            "name": "Legacy", "asname": None,
        }]
        after["init_import_candidates"] = []
        with self.assertRaisesRegex(DomainInventoryError, "__init__ import witness"):
            compare_domain_inventories(before, after, analyzer_sha="3"*40)

    def test_selected_init_import_candidate_removal_requires_review(self):
        before, after = report("1"*40), report("2"*40)
        for item in (before, after):
            item["inventory"].append({
                "path": "src/codeqa/core/__init__.py",
                "sha256": "e"*64, "domain": "UNCLASSIFIED",
            })
        before["init_import_candidates"] = [{
            "path": "src/codeqa/core/__init__.py", "from": ".legacy",
            "name": "Legacy", "asname": None,
        }]
        after["init_import_candidates"] = []
        result = compare_domain_inventories(before, after, analyzer_sha="3"*40)
        self.assertEqual(result["init_import_change_review"]["status"], "REVIEW_REQUIRED")
        self.assertEqual(result["status"], "NOT_EVALUATED")

    def test_mismatched_policy_rejected(self):
        before, after = report("1"*40), report("2"*40)
        after["role_policy_sha256"] = "d"*64
        with self.assertRaises(DomainInventoryError):
            compare_domain_inventories(before, after, analyzer_sha="3"*40)
