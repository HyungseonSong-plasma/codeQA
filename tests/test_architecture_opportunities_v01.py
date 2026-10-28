"""B3 regression tests: question emergence must follow structural witnesses."""
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
from codeqa.evaluation.architecture.metrics import analyze_architecture_metrics
from codeqa.evaluation.architecture.opportunities import (
    ArchitectureOpportunityError, discover_architecture_opportunities,
)
from codeqa.evaluation.dependency_metrics import DependencyMetricsProfile
from codeqa.adapters.python_dependencies import extract_python_dependencies
from codeqa.infrastructure.git import GitReader


ROOT = Path(__file__).resolve().parents[1]
SHA = "a" * 40
POLICY = {
    "policy_id": "orchard.roles.v0.1",
    "scope": "src/orchard",
    "roles": {
        "earth": {"responsibility": "data", "forbidden_imports": ["sky"]},
        "sky": {"responsibility": "display", "forbidden_imports": []},
        "rain": {"responsibility": "shared service", "forbidden_imports": []},
    },
    "exceptions": [],
}
PROFILE = DependencyMetricsProfile.from_mapping({
    "profile_id": "orchard.static.v0.1", "schema_version": "0.1",
    "max_out_degree_review": 8, "max_cycle_nodes_review": 1,
})
SOURCES = {
    "src/orchard/earth/model.py": "class Model: pass\n",
    "src/orchard/sky/view.py": "from orchard.earth.model import Model\n",
    "src/orchard/sky/helper.py": "from orchard.sky.view import view\n",
    "src/orchard/rain/flow.py": "from orchard.earth.model import Model\n",
    "src/orchard/rain/config.py": "value = 1\n",
}
def edge(source: str, target: str, line: int = 1) -> StaticDependency:
    return StaticDependency(
        "src/orchard/" + source + ".py", "src/orchard/" + target + ".py",
        line, "import orchard." + target.replace("/", "."), "top_level",
    )


def make_report(*, sources=None, policy=None, edges=(), unknown=(), analyzed=None):
    sources = SOURCES if sources is None else sources
    policy = POLICY if policy is None else policy
    inventory = analyze_architecture_inventory(SHA, sources, sources, policy)
    paths = tuple(sorted(sources)) if analyzed is None else tuple(sorted(analyzed))
    graph = DependencyGraph(SHA, paths, (), tuple(edges), tuple(unknown))
    metrics = analyze_architecture_metrics(inventory, graph, policy, PROFILE)
    return inventory, metrics


class ArchitectureOpportunitiesTests(unittest.TestCase):
    def evaluate(self, **kwargs):
        return discover_architecture_opportunities(*make_report(**kwargs))

    def test_healthy_no_signal_is_not_architecture_pass(self):
        report = self.evaluate()
        self.assertEqual(report["architecture_signals"], [])
        self.assertEqual(report["question_opportunities"], [])
        self.assertEqual(report["observation"], "NO_SIGNALS_OBSERVED")
        self.assertNotEqual(report["evidence_status"], "PASS")
        self.assertIn("EXTERNAL_CONSUMERS_NOT_EVALUATED", report["unknowns"])

    def test_cycle_produces_traceable_signal_and_keep_alternative(self):
        report = self.evaluate(edges=(
            edge("sky/view", "sky/helper"),
            edge("sky/helper", "sky/view"),
        ))
        self.assertEqual(len(report["architecture_signals"]), 1)
        signal = report["architecture_signals"][0]
        self.assertEqual(signal["family"], "STATIC_IMPORT_CYCLE")
        self.assertEqual(len(signal["source_witnesses"]), 2)
        self.assertTrue(all(w["source_sha256"] == sha256(
            SOURCES[w["source_path"]].encode()).hexdigest()
            for w in signal["source_witnesses"]))
        opportunity = report["question_opportunities"][0]
        self.assertEqual(opportunity["originating_signal_ids"], [signal["signal_id"]])
        self.assertIn("KEEP", opportunity["alternatives"])
        self.assertEqual(opportunity["decision"], "NOT_EVALUATED")
        self.assertTrue(opportunity["benign_counterhypothesis"])

    def test_declared_violation_has_real_import_site(self):
        report = self.evaluate(edges=(edge("earth/model", "sky/view"),))
        self.assertEqual(
            [s["family"] for s in report["architecture_signals"]],
            ["DECLARED_BOUNDARY_CONFLICT"],
        )
        self.assertEqual(report["architecture_signals"][0]["measurement"]["denominator"], 1)

    def test_cross_boundary_concentration_requires_multiple_targets(self):
        many = (
            edge("sky/view", "earth/model"),
            edge("sky/helper", "earth/model"),
            edge("sky/view", "rain/flow"),
            edge("sky/view", "sky/helper"),
        )
        report = self.evaluate(edges=many)
        signals = [s for s in report["architecture_signals"]
                   if s["family"] == "CROSS_BOUNDARY_CONCENTRATION"]
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]["measurement"], {
            "numerator": 3, "denominator": 4, "ratio": 0.75,
        })
        self.assertEqual(len(signals[0]["source_witnesses"]), 3)

    def test_deliberate_shared_utility_is_not_flagged_by_name_or_fan_in(self):
        report = self.evaluate(edges=(
            edge("sky/view", "rain/flow"),
            edge("earth/model", "rain/flow"),
            edge("sky/helper", "rain/flow"),
        ))
        self.assertEqual(report["question_opportunities"], [])

    def test_same_names_without_relationships_and_unlike_names_with_cycle(self):
        sources = {p.replace("orchard", "naming"): value for p, value in SOURCES.items()}
        policy = deepcopy(POLICY)
        policy["scope"] = "src/naming"
        report = self.evaluate(sources=sources, policy=policy)
        self.assertEqual(report["question_opportunities"], [])
        report2 = self.evaluate(edges=(
            edge("earth/model", "rain/flow"), edge("rain/flow", "earth/model"),
        ))
        self.assertEqual(report2["architecture_signals"][0]["family"], "STATIC_IMPORT_CYCLE")

    def test_renamed_isomorphic_graph_keeps_signal_families_and_ratios(self):
        graph = (
            edge("sky/view", "sky/helper"), edge("sky/helper", "sky/view"),
            edge("sky/view", "earth/model"), edge("sky/helper", "earth/model"),
            edge("sky/view", "rain/flow"),
        )
        original = self.evaluate(edges=graph)
        renamed = {p.replace("orchard", "woodland"): value for p, value in SOURCES.items()}
        policy = deepcopy(POLICY)
        policy["scope"] = "src/woodland"
        converted = tuple(StaticDependency(
            e.source_path.replace("orchard", "woodland"),
            e.target_path.replace("orchard", "woodland"),
            e.line, e.expression.replace("orchard", "woodland"), e.execution,
        ) for e in graph)
        after = self.evaluate(sources=renamed, policy=policy, edges=converted)
        self.assertEqual(
            [(s["family"], s["measurement"]["ratio"])
             for s in original["architecture_signals"]],
            [(s["family"], s["measurement"]["ratio"])
             for s in after["architecture_signals"]],
        )

    def test_unknown_dynamic_and_partial_source_do_not_become_pass(self):
        unknown = (UnknownDependency("src/orchard/sky/view.py", 3,
                                     "__import__(name)", "dynamic_import"),)
        report = self.evaluate(unknown=unknown, analyzed=("src/orchard/sky/view.py",))
        self.assertEqual(report["observation"], "NO_SIGNALS_OBSERVED")
        self.assertEqual(report["evidence_status"], "INCOMPLETE")
        self.assertIn("dynamic_import", report["unknowns"])

    def test_identity_and_witness_tampering_fail_closed(self):
        inv, metrics = make_report(edges=(edge("sky/view", "earth/model"),))
        bad = deepcopy(metrics)
        bad["resolved_pairs"][0]["witnesses"][0]["source_sha256"] = "0" * 64
        bad["metrics_id"] = sha256(json.dumps({
            k: v for k, v in bad.items() if k != "metrics_id"
        }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        with self.assertRaises(ArchitectureOpportunityError):
            discover_architecture_opportunities(inv, bad)
        bad = deepcopy(inv)
        bad["source_identity"]["repository_commit_sha"] = "b" * 40
        with self.assertRaises(ArchitectureOpportunityError):
            discover_architecture_opportunities(bad, metrics)
        with self.assertRaises(ArchitectureOpportunityError):
            discover_architecture_opportunities(inv, metrics, min_cross_role_pairs=0)

    def test_schema_and_report_integrity(self):
        schema = json.loads(
            (ROOT / "contracts/qa/architecture-opportunities-v0.1.schema.json").read_text()
        )
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        report = self.evaluate(edges=(edge("earth/model", "sky/view"),))
        validator.validate(report)
        bad = deepcopy(report)
        bad["question_opportunities"][0]["decision"] = "PREFER"
        self.assertTrue(list(validator.iter_errors(bad)))

    def test_real_codeqa_source_is_not_preseeded_with_questions(self):
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
        graph = extract_python_dependencies(sources, snapshot_id=sha,
                                            analyzed_paths=tuple(paths))
        metrics = analyze_architecture_metrics(inv, graph, policy, PROFILE)
        result = discover_architecture_opportunities(inv, metrics)
        self.assertEqual(result["snapshot_sha"], sha)
        self.assertEqual(result["metrics_id"], metrics["metrics_id"])
        self.assertEqual(
            {s["signal_id"] for s in result["architecture_signals"]},
            {sid for o in result["question_opportunities"]
             for sid in o["originating_signal_ids"]},
        )
        self.assertNotEqual(result["evidence_status"], "PASS")
        self.assertTrue(all(o["decision"] == "NOT_EVALUATED"
                            for o in result["question_opportunities"]))
        self.assertTrue(all(o["source_witnesses"] for o in result["question_opportunities"]))


if __name__ == "__main__":
    unittest.main()
