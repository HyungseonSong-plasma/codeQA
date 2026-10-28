"""Architecture QA B2: source-backed static graph metrics, never semantic PASS."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import unittest

from jsonschema import Draft202012Validator

from codeqa.core.dependency import DependencyGraph, StaticDependency, UnknownDependency
from codeqa.evaluation.architecture.inventory import analyze_architecture_inventory
from codeqa.evaluation.architecture.metrics import (
    ArchitectureMetricsError, analyze_architecture_metrics,
)
from codeqa.evaluation.dependency_metrics import DependencyMetricsProfile
from codeqa.adapters.python_dependencies import extract_python_dependencies
from codeqa.infrastructure.git import GitReader


ROOT = Path(__file__).resolve().parents[1]
SHA = "a" * 40
POLICY = {
    "policy_id": "garden.roles.v0.1",
    "scope": "src/garden",
    "roles": {
        "soil": {"responsibility": "facts", "forbidden_imports": ["leaf"]},
        "leaf": {"responsibility": "views", "forbidden_imports": []},
        "water": {"responsibility": "shared service", "forbidden_imports": []},
    },
    "exceptions": [],
}
PROFILE = DependencyMetricsProfile.from_mapping({
    "profile_id": "garden.static.v0.1", "schema_version": "0.1",
    "max_out_degree_review": 8, "max_cycle_nodes_review": 1,
})
SOURCES = {
    "src/garden/soil/__init__.py": "",
    "src/garden/soil/model.py": "class Model: pass\n",
    "src/garden/leaf/__init__.py": "",
    "src/garden/leaf/view.py": (
        "from garden.soil.model import Model\n"
        "from garden.leaf.helper import helper\n"
    ),
    "src/garden/leaf/helper.py": "from garden.leaf.view import view\n",
    "src/garden/water/__init__.py": "",
    "src/garden/water/flow.py": "from garden.soil.model import Model\n",
}
EDGES = (
    StaticDependency("src/garden/leaf/view.py", "src/garden/soil/model.py", 1,
                     "from garden.soil.model import Model", "top_level"),
    StaticDependency("src/garden/leaf/view.py", "src/garden/leaf/helper.py", 2,
                     "from garden.leaf.helper import helper", "top_level"),
    StaticDependency("src/garden/leaf/helper.py", "src/garden/leaf/view.py", 1,
                     "from garden.leaf.view import view", "top_level"),
    StaticDependency("src/garden/water/flow.py", "src/garden/soil/model.py", 1,
                     "from garden.soil.model import Model", "top_level"),
)


def case(*, sources=None, policy=None, edges=None, unknown=(), unprocessed=(),
         excluded=(), tracked_extra=(), analyzed=None):
    sources = SOURCES if sources is None else sources
    policy = POLICY if policy is None else policy
    inventory = analyze_architecture_inventory(
        SHA, [*sources, *tracked_extra], sources, policy,
        excluded_paths=excluded,
    )
    analyzed = tuple(sorted(set(sources) - set(unprocessed))) if analyzed is None else analyzed
    graph = DependencyGraph(SHA, analyzed, tuple(unprocessed),
                            EDGES if edges is None else edges, tuple(unknown))
    return inventory, graph, policy


class ArchitectureMetricsTests(unittest.TestCase):
    def evaluate(self, **kwargs):
        return analyze_architecture_metrics(*case(**kwargs), PROFILE)

    def test_deterministic_metrics_with_line_and_source_hash_witness(self):
        inventory, graph, policy = case()
        left = analyze_architecture_metrics(inventory, graph, policy, PROFILE)
        shuffled = DependencyGraph(SHA, tuple(reversed(graph.analyzed_paths)), (),
                                   tuple(reversed(graph.edges)), ())
        right = analyze_architecture_metrics(inventory, shuffled, policy, PROFILE)
        self.assertEqual(left, right)
        self.assertEqual(left["denominators"]["within_declared_pairs"], 2)
        self.assertEqual(left["denominators"]["cross_declared_pairs"], 2)
        self.assertEqual(left["denominators"]["resolved_distinct_pairs"], 4)
        self.assertEqual(left["denominators"]["cross_share_of_declared_pairs"], 0.5)
        leaf = next(g for g in left["groups"] if g["role"] == "leaf")
        self.assertEqual(leaf["analyzed_modules"], 3)
        self.assertEqual(leaf["possible_within_directed_pairs"], 6)
        self.assertAlmostEqual(leaf["within_density_proxy"], 1 / 3)
        self.assertEqual(leaf["cross_out_pairs"], 1)
        self.assertEqual(len(left["cycles"]), 1)
        self.assertEqual(len(left["cycles"][0]["edge_witnesses"]), 2)
        witness = left["cross_boundary_witnesses"][0]
        self.assertEqual(witness["line"], 1)
        self.assertEqual(witness["source_sha256"],
                         sha256(SOURCES[witness["source_path"]].encode()).hexdigest())
        self.assertEqual(witness["evidence_class"], "GRAPH_PROVIDED_STATIC_IMPORT")
        soil = next(g for g in left["groups"] if g["role"] == "soil")
        self.assertEqual(soil["reverse_import_impact"]["potential_dependents"], 3)
        self.assertEqual(left["status"], "EVIDENCE_ONLY")
        self.assertNotIn("questions", left)
        self.assertNotEqual(left["status"], "PASS")

    def test_versioned_output_schema_and_negative_unknown_contract(self):
        schema = json.loads(
            (ROOT / "contracts/qa/architecture-metrics-v0.1.schema.json").read_text()
        )
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        report = self.evaluate()
        validator.validate(report)
        forged = deepcopy(report)
        forged["coverage"]["external_consumers"] = "PASS"
        self.assertTrue(list(validator.iter_errors(forged)))
        forged = deepcopy(report)
        forged["groups"][0]["within_density_proxy"] = 2.0
        self.assertTrue(list(validator.iter_errors(forged)))
        forged = deepcopy(report)
        forged["resolved_pairs"][0]["witnesses"][0]["source_sha256"] = "not-a-hash"
        self.assertTrue(list(validator.iter_errors(forged)))

    def test_zero_denominator_is_null_not_perfect_cohesion(self):
        selected = {
            "src/garden/soil/one.py": "",
            "src/garden/leaf/one.py": "",
            "src/garden/water/one.py": "",
        }
        result = self.evaluate(sources=selected, edges=())
        self.assertEqual(result["denominators"]["resolved_distinct_pairs"], 0)
        self.assertIsNone(result["denominators"]["within_share_of_declared_pairs"])
        self.assertTrue(all(g["within_density_proxy"] is None
                            for g in result["groups"]))
        self.assertTrue(all(g["reverse_import_impact"]["potential_dependents"] == 0
                            for g in result["groups"]))
        self.assertEqual(result["status"], "EVIDENCE_ONLY")

    def test_unknown_dynamic_and_incomplete_resolver_are_not_clean(self):
        u = UnknownDependency("src/garden/leaf/view.py", 3,
                              "__import__(module)", "dynamic_import")
        report = self.evaluate(unknown=(u,), unprocessed=("src/garden/water/flow.py",),
                               edges=EDGES[:3])
        self.assertEqual(report["status"], "INCOMPLETE")
        self.assertEqual(report["coverage"]["unknown_by_reason"]["dynamic_import"], 1)
        self.assertEqual(report["coverage"]["python_unprocessed"], 1)
        self.assertEqual(report["coverage"]["external_consumers"], "NOT_EVALUATED")

        inventory, graph, policy = case(analyzed=("src/garden/soil/model.py",),
                                       edges=())
        incomplete = analyze_architecture_metrics(inventory, graph, policy, PROFILE)
        self.assertEqual(incomplete["status"], "INCOMPLETE")
        self.assertEqual(len(incomplete["coverage"]["python_missing_from_graph"]), 6)

    def test_forbidden_direction_and_deceptive_name_do_not_certify_alignment(self):
        edge = StaticDependency("src/garden/soil/model.py", "src/garden/leaf/view.py",
                                2, "import garden.leaf.view", "top_level")
        result = self.evaluate(edges=(*EDGES, edge))
        self.assertEqual(result["status"], "VIOLATION")
        self.assertTrue(any(f["code"] == "FORBIDDEN_ROLE_DEPENDENCY"
                            for f in result["declared_role_findings"]))
        self.assertEqual(result["evidence_class"], "PROXY_INFERENCE")

    def test_vendor_exclusions_and_unknown_language_coverage(self):
        result = self.evaluate(
            tracked_extra=("vendor/thirdparty.py", "src/garden/soil/solver.rs"),
            excluded=("vendor/thirdparty.py", "src/garden/soil/solver.rs"),
        )
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertEqual(result["coverage"]["unknown_by_reason"]["UNREAD_TRACKED_SOURCE"], 2)
        self.assertEqual(result["coverage"]["unknown_by_reason"]
                         ["NON_PYTHON_PARSER_NOT_EVALUATED"], 1)

    def test_isomorphic_renamed_repository_keeps_normalized_metrics(self):
        renamed = {path.replace("garden", "forest"): src.replace("garden", "forest")
                   for path, src in SOURCES.items()}
        policy = deepcopy(POLICY)
        policy["scope"] = "src/forest"
        edges = tuple(StaticDependency(
            e.source_path.replace("garden", "forest"),
            e.target_path.replace("garden", "forest"),
            e.line, e.expression.replace("garden", "forest"), e.execution,
        ) for e in EDGES)
        result = self.evaluate(sources=renamed, policy=policy, edges=edges)
        baseline = self.evaluate()
        self.assertEqual(result["denominators"], baseline["denominators"])
        self.assertEqual(
            [(g["role"], g["within_density_proxy"], g["cross_out_density_proxy"])
             for g in result["groups"]],
            [(g["role"], g["within_density_proxy"], g["cross_out_density_proxy"])
             for g in baseline["groups"]],
        )

    def test_identity_and_forged_edges_fail_closed(self):
        inventory, graph, policy = case()
        bad = deepcopy(inventory)
        bad["source_identity"]["repository_commit_sha"] = "b" * 40
        with self.assertRaises(ArchitectureMetricsError):
            analyze_architecture_metrics(bad, graph, policy, PROFILE)
        bad = deepcopy(inventory)
        bad["source_identity"]["role_policy_sha256"] = "f" * 64
        with self.assertRaises(ArchitectureMetricsError):
            analyze_architecture_metrics(bad, graph, policy, PROFILE)
        bad = deepcopy(inventory)
        bad["coverage"]["tracked_total"] = 1
        with self.assertRaises(ArchitectureMetricsError):
            analyze_architecture_metrics(bad, graph, policy, PROFILE)
        bad = deepcopy(inventory)
        bad["files"][0]["declared_role"] = "soil"
        with self.assertRaises(ArchitectureMetricsError):
            analyze_architecture_metrics(bad, graph, policy, PROFILE)
        self_import = StaticDependency(
            "src/garden/leaf/view.py", "src/garden/leaf/view.py", 1,
            "import garden.leaf.view", "top_level",
        )
        with self.assertRaises(ArchitectureMetricsError):
            self.evaluate(edges=(*EDGES, self_import))
        forged = StaticDependency("src/garden/leaf/view.py", "outside.py", 99,
                                  "import nonexistent", "top_level")
        with self.assertRaises(ArchitectureMetricsError):
            self.evaluate(edges=(*EDGES, forged))
        bad = DependencyGraph(SHA, ("src/garden/soil/model.py",), (), EDGES, ())
        with self.assertRaises(ArchitectureMetricsError):
            analyze_architecture_metrics(inventory, bad, policy, PROFILE)

    def test_real_codeqa_source_scope_is_source_bounded(self):
        reader = GitReader(ROOT)
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
        paths = sorted(p for p in reader.tracked_paths()
                       if p.startswith("src/codeqa/") and p.endswith(".py"))
        sources = {p: reader.read_file(sha, p).decode("utf-8") for p in paths}
        policy = json.loads(
            (ROOT / "profiles/semantic-directory-roles-v0.1.json").read_text()
        )
        inv = analyze_architecture_inventory(sha, paths, sources, policy)
        graph = extract_python_dependencies(
            sources, snapshot_id=sha, analyzed_paths=tuple(paths),
        )
        result = analyze_architecture_metrics(inv, graph, policy, PROFILE)
        self.assertEqual(result["snapshot_sha"], sha)
        self.assertEqual(result["coverage"]["python_analyzed"], len(paths))
        self.assertEqual(result["coverage"]["python_missing_from_graph"], [])
        self.assertGreater(len(result["groups"]), 1)
        self.assertTrue(result["resolved_pairs"])
        self.assertTrue(all(w["source_sha256"] for p in result["resolved_pairs"]
                            for w in p["witnesses"]))
        self.assertNotIn(result["status"], ("PASS", "ALIGNED"))


if __name__ == "__main__":
    unittest.main()
