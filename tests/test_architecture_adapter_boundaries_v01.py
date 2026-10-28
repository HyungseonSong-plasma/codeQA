"""B6 generic adapter boundary tests: no filename-based split heuristics."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import unittest

from codeqa.core.dependency import DependencyGraph, StaticDependency
from codeqa.evaluation.architecture.inventory import analyze_architecture_inventory
from codeqa.evaluation.architecture.metrics import analyze_architecture_metrics
from codeqa.evaluation.architecture.adapter_boundaries import (
    AdapterBoundaryError, assess_adapter_boundaries,
)
from codeqa.evaluation.dependency_metrics import DependencyMetricsProfile

SHA = "a" * 40
SCOPE = "src/forest/adapters"
POLICY = {
    "policy_id": "forest.roles.v0.1", "scope": "src/forest",
    "roles": {
        "adapters": {"responsibility": "adapters", "forbidden_imports": []},
        "core": {"responsibility": "core", "forbidden_imports": []},
    },
    "exceptions": [],
}
SOURCES = {f"{SCOPE}/{name}.py": "x = 1\n" for name in ("a", "b", "c", "utility")}
PROFILE = DependencyMetricsProfile.from_mapping({
    "profile_id": "forest.static.v0.1", "schema_version": "0.1",
    "max_out_degree_review": 8, "max_cycle_nodes_review": 1,
})


def declaration():
    return {
        "schema_version": "0.1", "adapter_scope": SCOPE,
        "families": [
            {"family": "violet", "module_paths": [f"{SCOPE}/a.py"],
             "capability_status": "SUPPORTED", "parser_provenance": "VERIFIED"},
            {"family": "amber", "module_paths": [f"{SCOPE}/b.py", f"{SCOPE}/c.py"],
             "capability_status": "PARTIAL", "parser_provenance": "NOT_EVALUATED"},
        ],
        "shared_paths": [f"{SCOPE}/utility.py"],
        "external_consumers": "NOT_EVALUATED",
        "distribution_compatibility": "NOT_EVALUATED",
    }


def reports(edges=()):
    inventory = analyze_architecture_inventory(SHA, SOURCES, SOURCES, POLICY)
    graph = DependencyGraph(SHA, tuple(sorted(SOURCES)), (), tuple(edges), ())
    metrics = analyze_architecture_metrics(inventory, graph, POLICY, PROFILE)
    return inventory, metrics


def edge(source, target):
    return StaticDependency(
        f"{SCOPE}/{source}.py", f"{SCOPE}/{target}.py", 1,
        f"import forest.adapters.{target}", "top_level",
    )


class AdapterBoundaryTests(unittest.TestCase):
    def test_healthy_baseline_no_forced_split(self):
        inv, metrics = reports()
        report = assess_adapter_boundaries(inv, metrics, declaration())
        self.assertEqual(report["architecture_signals"], [])
        self.assertEqual([c["layout"] for c in report["candidates"]], ["KEEP"])
        self.assertEqual(report["decision"], "NOT_EVALUATED")
        self.assertEqual(report["coverage"]["unverified_family_parsers"], ["amber"])

    def test_witnessed_cross_family_pressure_is_only_a_question(self):
        inv, metrics = reports((edge("a", "b"), edge("a", "c")))
        report = assess_adapter_boundaries(inv, metrics, declaration())
        self.assertEqual(report["static_pairs"]["CROSS_FAMILY"], 2)
        self.assertEqual(report["architecture_signals"][0]["measurement"]["denominator"], 2)
        self.assertEqual([c["layout"] for c in report["candidates"]],
                         ["KEEP", "GROUP_BY_DECLARED_LANGUAGE_FAMILY"])
        self.assertEqual(report["candidates"][1]["decision"], "NOT_EVALUATED")
        self.assertEqual(len(report["architecture_signals"][0]["source_witnesses"]), 2)

    def test_renamed_isomorphic_family_labels_do_not_change_pressure(self):
        inv, metrics = reports((edge("a", "b"), edge("a", "c")))
        first = assess_adapter_boundaries(inv, metrics, declaration())
        renamed = declaration()
        renamed["families"][0]["family"] = "quartz"
        renamed["families"][1]["family"] = "moss"
        second = assess_adapter_boundaries(inv, metrics, renamed)
        self.assertEqual(first["static_pairs"], second["static_pairs"])
        self.assertEqual(len(first["architecture_signals"]),
                         len(second["architecture_signals"]))

    def test_shared_utility_imports_do_not_force_split(self):
        inv, metrics = reports((edge("a", "utility"), edge("b", "utility")))
        result = assess_adapter_boundaries(inv, metrics, declaration())
        self.assertEqual(result["static_pairs"]["SHARED_UTILITY"], 2)
        self.assertEqual(result["architecture_signals"], [])
        self.assertEqual(len(result["candidates"]), 1)

    def test_sibling_distribution_requires_independent_compatibility(self):
        inv, metrics = reports((edge("a", "b"), edge("a", "c")))
        baseline = assess_adapter_boundaries(inv, metrics, declaration())
        self.assertNotIn("SIBLING_DISTRIBUTION",
                         [c["layout"] for c in baseline["candidates"]])
        trusted = declaration()
        trusted["external_consumers"] = "VERIFIED"
        trusted["distribution_compatibility"] = "VERIFIED"
        # A declared verification is still not a permission to migrate.
        result = assess_adapter_boundaries(inv, metrics, trusted)
        self.assertIn("SIBLING_DISTRIBUTION",
                      [c["layout"] for c in result["candidates"]])
        self.assertEqual(result["decision"], "NOT_EVALUATED")

    def test_unclassified_and_missing_parser_are_explicit(self):
        inv, metrics = reports()
        declared = declaration()
        declared["shared_paths"] = []
        result = assess_adapter_boundaries(inv, metrics, declared)
        self.assertEqual(result["coverage"]["unclassified_paths"],
                         [f"{SCOPE}/utility.py"])
        self.assertIn("UNCLASSIFIED_ADAPTER_SOURCES", result["unknowns"])
        self.assertIn("PARSER_PROVENANCE_NOT_EVALUATED", result["unknowns"])

    def test_rejects_forged_identity_and_duplicate_ownership(self):
        inv, metrics = reports()
        bad = deepcopy(metrics)
        bad["snapshot_sha"] = "b" * 40
        with self.assertRaises(AdapterBoundaryError):
            assess_adapter_boundaries(inv, bad, declaration())
        declared = declaration()
        declared["shared_paths"].append(f"{SCOPE}/a.py")
        with self.assertRaises(AdapterBoundaryError):
            assess_adapter_boundaries(inv, metrics, declared)

    def test_determinism_immutable_inputs_and_digest(self):
        inv, metrics = reports((edge("a", "b"), edge("a", "c")))
        declared = declaration()
        before = deepcopy((inv, metrics, declared))
        report = assess_adapter_boundaries(inv, metrics, declared)
        self.assertEqual(report, assess_adapter_boundaries(inv, metrics, declared))
        self.assertEqual(before, (inv, metrics, declared))
        expected = sha256(json.dumps(
            {k: v for k, v in report.items() if k != "boundary_id"},
            sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest()
        self.assertEqual(report["boundary_id"], expected)


    def test_schema_and_missing_dynamic_macro_abi_evidence(self):
        from pathlib import Path
        from jsonschema import Draft202012Validator
        inv, metrics = reports((edge("a", "b"), edge("a", "c")))
        report = assess_adapter_boundaries(inv, metrics, declaration())
        for unknown in (
            "DYNAMIC_PLUGIN_LOADING_NOT_EVALUATED",
            "RUST_MACRO_TRAIT_SEMANTICS_NOT_EVALUATED",
            "CPP_MACRO_HEADER_ABI_NOT_EVALUATED",
            "EXTERNAL_CONSUMERS_NOT_EVALUATED",
            "DISTRIBUTION_COMPATIBILITY_NOT_EVALUATED",
        ):
            self.assertIn(unknown, report["unknowns"])
        schema = json.loads((Path(__file__).resolve().parents[1] /
            "contracts/qa/architecture-adapter-boundaries-v0.1.schema.json").read_text())
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(report)

    def test_forged_source_witness_rejected_even_if_metrics_digest_updated(self):
        inv, metrics = reports((edge("a", "b"), edge("a", "c")))
        bad = deepcopy(metrics)
        bad["resolved_pairs"][0]["witnesses"][0]["source_sha256"] = "0" * 64
        bad["metrics_id"] = sha256(json.dumps(
            {k: v for k, v in bad.items() if k != "metrics_id"},
            sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest()
        with self.assertRaises(AdapterBoundaryError):
            assess_adapter_boundaries(inv, bad, declaration())


if __name__ == "__main__":
    unittest.main()
