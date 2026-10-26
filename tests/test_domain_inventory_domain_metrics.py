"""Per-domain counts retain ambiguous static evidence instead of quality claims."""
import json
from pathlib import Path
import unittest

from codeqa.core.dependency import DependencyGraph, StaticDependency, UnknownDependency
from codeqa.evaluation.domain_inventory import (
    DomainInventoryError, analyze_domain_inventory,
)

ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / "profiles/domain-grouping-v0.1.json").read_text())
ROLES = json.loads((ROOT / "profiles/semantic-directory-roles-v0.1.json").read_text())


class DomainMetricTests(unittest.TestCase):
    def setUp(self):
        self.sources = {
            "src/codeqa/evaluation/mechanical.py": "from codeqa.core.naming import Rule\n",
            "src/codeqa/core/naming.py": "class Rule: pass\n",
            "src/codeqa/evaluation/naming.py": "from codeqa.core.naming import Rule\n",
            "src/codeqa/core/graph.py": "x = 1\n",
            "src/codeqa/adapters/__init__.py": "",
            "src/codeqa/pipeline/__init__.py": "",
            "src/codeqa/governance/__init__.py": "",
            "src/codeqa/infrastructure/__init__.py": "",
        }
        self.edges = (
            StaticDependency(
                "src/codeqa/evaluation/mechanical.py", "src/codeqa/core/naming.py",
                1, "from codeqa.core.naming import Rule", "top_level",
            ),
            StaticDependency(
                "src/codeqa/evaluation/naming.py", "src/codeqa/core/naming.py",
                1, "from codeqa.core.naming import Rule", "top_level",
            ),
            StaticDependency(
                "src/codeqa/core/graph.py", "src/codeqa/core/naming.py",
                1, "from codeqa.core.naming import Rule", "top_level",
            ),
        )

    def graph(self, unknown=()):
        return DependencyGraph(
            snapshot_id="git:synthetic",
            analyzed_paths=tuple(sorted(self.sources)),
            unprocessed_paths=(),
            edges=self.edges,
            unknown=unknown,
        )

    def test_per_domain_static_and_unknown_counts(self):
        unknown = (
            UnknownDependency(
                "src/codeqa/core/graph.py", 2, "__import__(name)", "dynamic_import"
            ),
        )
        result = analyze_domain_inventory(self.sources, self.graph(unknown), POLICY, ROLES)
        metrics = result["domain_metrics"]
        self.assertEqual(metrics["mechanical"]["cross_outgoing_import_sites"], 1)
        self.assertEqual(metrics["naming"]["cross_incoming_import_sites"], 1)
        self.assertEqual(metrics["naming"]["intra_import_sites"], 1)
        self.assertEqual(metrics["UNCLASSIFIED"]["domain_unknown_outgoing_import_sites"], 1)
        self.assertEqual(metrics["UNCLASSIFIED"]["unknown_import_sites"], 1)
        self.assertEqual(metrics["naming"]["potential_reverse_dependents_max"], 3)
        self.assertEqual(result["status"], "NOT_EVALUATED")
        self.assertNotIn("PASS", {result["status"]})

    def test_unknown_witness_cannot_claim_out_of_scope_source(self):
        forged = (
            UnknownDependency("src/other/foreign.py", 1, "import x", "dynamic_import"),
        )
        with self.assertRaisesRegex(DomainInventoryError, "unknown import witness"):
            analyze_domain_inventory(self.sources, self.graph(forged), POLICY, ROLES)


if __name__ == "__main__":
    unittest.main()
