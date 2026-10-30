"""B4 evidence-triggered virtual scenario tests, including renamed-isomorphic graphs."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import unittest

from jsonschema import Draft202012Validator

from codeqa.core.dependency import DependencyGraph, StaticDependency
from codeqa.adapters.python_dependencies import extract_python_dependencies
from codeqa.evaluation.architecture.inventory import analyze_architecture_inventory
from codeqa.evaluation.architecture.metrics import analyze_architecture_metrics
from codeqa.evaluation.architecture.opportunities import discover_architecture_opportunities
from codeqa.evaluation.architecture.scenarios import (
    ArchitectureScenarioError, generate_virtual_layout_scenarios,
)
from codeqa.evaluation.dependency_metrics import DependencyMetricsProfile
from codeqa.infrastructure.git import GitReader


ROOT = Path(__file__).resolve().parents[1]
SHA = "a" * 40
POLICY = {
    "policy_id": "orchard.roles.v0.1",
    "scope": "src/orchard",
    "roles": {
        "earth": {"responsibility": "data", "forbidden_imports": ["sky"]},
        "sky": {"responsibility": "display", "forbidden_imports": []},
        "rain": {"responsibility": "shared", "forbidden_imports": []},
    },
    "exceptions": [],
}
PROFILE = DependencyMetricsProfile.from_mapping({
    "profile_id": "orchard.static.v0.1", "schema_version": "0.1",
    "max_out_degree_review": 8, "max_cycle_nodes_review": 1,
})
SOURCES = {
    "src/orchard/earth/model.py": "class Model: pass\n",
    "src/orchard/earth/other.py": "class Other: pass\n",
    "src/orchard/earth/helper.py": "class Helper: pass\n",
    "src/orchard/earth/extra.py": "class Extra: pass\n",
    "src/orchard/sky/view.py": "from orchard.earth.model import Model\n",
    "src/orchard/sky/other.py": "x = 1\n",
    "src/orchard/rain/flow.py": "x = 1\n",
}
def edge(src, dst):
    return StaticDependency(
        "src/orchard/" + src + ".py", "src/orchard/" + dst + ".py",
        1, "from orchard." + dst.replace("/", ".") + " import something", "top_level",
    )

CONCENTRATED = (
    edge("sky/view", "earth/model"),
    edge("sky/view", "earth/other"),
    edge("sky/view", "rain/flow"),
)
UNFAVORABLE = CONCENTRATED + (
    edge("earth/other", "earth/model"),
    edge("earth/helper", "earth/model"),
    edge("earth/extra", "earth/model"),
)


def reports(*, sources=None, policy=None, edges=(), unknown=()):
    sources = SOURCES if sources is None else sources
    policy = POLICY if policy is None else policy
    inventory = analyze_architecture_inventory(SHA, sources, sources, policy)
    graph = DependencyGraph(SHA, tuple(sorted(sources)), (), tuple(edges), tuple(unknown))
    metrics = analyze_architecture_metrics(inventory, graph, policy, PROFILE)
    opportunities = discover_architecture_opportunities(inventory, metrics)
    return inventory, metrics, opportunities, policy


def compare(*, sources=None, policy=None, edges=(), unknown=(),
            candidate_mappings=None):
    return generate_virtual_layout_scenarios(
        *reports(sources=sources, policy=policy, edges=edges, unknown=unknown),
        candidate_mappings=candidate_mappings,
    )


class ArchitectureScenarioTests(unittest.TestCase):
    def test_healthy_source_has_only_keep_and_zero_candidates(self):
        result = compare()
        self.assertEqual(result["candidates"], [])
        self.assertEqual(result["rejected"], [])
        self.assertEqual(result["baseline"]["resolved_pairs"], 0)
        self.assertEqual(result["decision"], "NOT_EVALUATED")
        self.assertNotEqual(result["evidence_status"], "PASS")

    def test_favorable_role_proxy_change_does_not_claim_edge_improvement(self):
        result = compare(edges=CONCENTRATED)
        self.assertEqual(len(result["candidates"]), 1)
        candidate = result["candidates"][0]
        self.assertEqual(candidate["path_mapping"][0]["from"], "src/orchard/sky/view.py")
        self.assertEqual(candidate["path_mapping"][0]["to"], "src/orchard/earth/view.py")
        self.assertEqual(candidate["measured_proxy_delta"]["cross_declared_pairs"], -2)
        self.assertEqual(candidate["measured_proxy_delta"]["within_declared_pairs"], 2)
        self.assertEqual(candidate["measured_proxy_delta"]["resolved_static_pairs"], 0)
        self.assertEqual(candidate["measured_proxy_delta"]["static_cycles"], 0)
        self.assertEqual(len(candidate["rewrite_candidates"]), 3)
        self.assertTrue(all(w["rewrite_status"] == "NOT_EVALUATED"
                            for w in candidate["rewrite_candidates"]))
        self.assertEqual(candidate["decision"], "NOT_EVALUATED")
        self.assertIn("PUBLIC_IMPORT_COMPATIBILITY_NOT_EVALUATED", candidate["unknowns"])
        self.assertEqual(candidate["evidence_class"], "PROJECTED_PATH_ROLE_PROXY_ONLY")

    def test_unfavorable_move_is_measured_without_hiding_cost(self):
        _, _, opportunities, _ = reports(edges=UNFAVORABLE)
        qid = opportunities["question_opportunities"][0]["opportunity_id"]
        result = compare(edges=UNFAVORABLE, candidate_mappings={
            qid: {"src/orchard/earth/model.py": "src/orchard/rain/model.py"},
        })
        self.assertEqual(len(result["candidates"]), 1)
        candidate = result["candidates"][0]
        self.assertEqual(candidate["measured_proxy_delta"]["cross_declared_pairs"], 3)
        self.assertEqual(candidate["measured_proxy_delta"]["resolved_static_pairs"], 0)
        self.assertEqual(candidate["measured_proxy_delta"]["moved_files"], 1)

    def test_noop_and_collision_are_rejected(self):
        _, _, opportunities, _ = reports(edges=CONCENTRATED)
        qid = opportunities["question_opportunities"][0]["opportunity_id"]
        self.assertEqual(compare(edges=CONCENTRATED, candidate_mappings={
            qid: {"src/orchard/sky/view.py": "src/orchard/sky/view.py"}
        })["rejected"][0]["reason"], "NO_OP_MAPPING")
        collision = compare(edges=CONCENTRATED, candidate_mappings={
            qid: {"src/orchard/sky/view.py": "src/orchard/earth/model.py"}
        })
        self.assertEqual(collision["rejected"][0]["reason"], "TARGET_COLLISION")
        self.assertEqual(collision["rejected"][0]["collision_witnesses"], [{
            "source_path": "src/orchard/sky/view.py",
            "proposed_target_path": "src/orchard/earth/model.py",
            "source_sha256": sha256(SOURCES["src/orchard/sky/view.py"].encode()).hexdigest(),
            "collision_kind": "OCCUPIED_TARGET",
            "occupied_target_sha256":
                sha256(SOURCES["src/orchard/earth/model.py"].encode()).hexdigest(),
        }])
        schema = json.loads(
            (ROOT / "contracts/qa/architecture-scenarios-v0.1.schema.json").read_text()
        )
        Draft202012Validator(schema).validate(collision)
        tampered = deepcopy(collision)
        del tampered["rejected"][0]["collision_witnesses"]
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(tampered)))

    def test_duplicate_target_collision_has_all_source_witnesses(self):
        _, _, opportunities, _ = reports(edges=CONCENTRATED)
        qid = opportunities["question_opportunities"][0]["opportunity_id"]
        report = compare(edges=CONCENTRATED, candidate_mappings={qid: {
            "src/orchard/sky/view.py": "src/orchard/rain/new.py",
            "src/orchard/earth/model.py": "src/orchard/rain/new.py",
        }})
        rejected = report["rejected"][0]
        self.assertEqual(rejected["reason"], "TARGET_COLLISION")
        self.assertEqual(len(rejected["collision_witnesses"]), 2)
        self.assertEqual({w["source_path"] for w in rejected["collision_witnesses"]},
                         {"src/orchard/sky/view.py", "src/orchard/earth/model.py"})
        self.assertTrue(all(w["collision_kind"] == "DUPLICATE_DESTINATION"
                            and len(w["conflicting_sources"]) == 1
                            and w["proposed_target_path"] == "src/orchard/rain/new.py"
                            for w in rejected["collision_witnesses"]))
        schema = json.loads(
            (ROOT / "contracts/qa/architecture-scenarios-v0.1.schema.json").read_text()
        )
        Draft202012Validator(schema).validate(report)

    def test_invalid_paths_frozen_root_unclassified_and_chained_moves(self):
        _, _, opportunities, _ = reports(edges=CONCENTRATED)
        qid = opportunities["question_opportunities"][0]["opportunity_id"]
        for mapping, expected in (
            ({"src/orchard/sky/view.py": "../escape.py"}, "INVALID_PATH"),
            ({"src/orchard/sky/view.py": "src/orchard/missing/view.py"},
             "FROZEN_ROOT_OR_UNDECLARED_TARGET"),
            ({"src/orchard/sky/view.py": "src/orchard/rain/new.py",
              "src/orchard/earth/other.py": "src/orchard/rain/new.py"},
             "TARGET_COLLISION"),
            ({"src/orchard/sky/view.py": "src/orchard/earth/other.py",
              "src/orchard/earth/other.py": "src/orchard/sky/view.py"},
             "CYCLIC_OR_CHAINED_MAPPING"),
        ):
            with self.subTest(expected=expected):
                report = compare(edges=CONCENTRATED, candidate_mappings={qid: mapping})
                self.assertEqual(report["rejected"][0]["reason"], expected)

    def test_occupied_primary_kept_and_distinct_witnessed_source_compared(self):
        # The highest-pressure source cannot move to its exact target path.
        # A second, independently witnessed source can still be compared.
        sources = {
            **SOURCES,
            "src/orchard/earth/view.py": "value = 1\n",
            "src/orchard/sky/presenter.py":
                "from orchard.earth.model import Model\n"
                "from orchard.earth.other import Other\n",
        }
        edges = CONCENTRATED + (
            edge("sky/presenter", "earth/model"),
            StaticDependency(
                "src/orchard/sky/presenter.py",
                "src/orchard/earth/other.py", 2,
                "from orchard.earth.other import Other", "top_level",
            ),
        )
        inv, metrics, opp, policy = reports(sources=sources, edges=edges)
        result = generate_virtual_layout_scenarios(inv, metrics, opp, policy)
        self.assertTrue(any(
            r["reason"] == "TARGET_COLLISION" and any(
                w["source_path"] == "src/orchard/sky/view.py"
                and w["proposed_target_path"] == "src/orchard/earth/view.py"
                and w["collision_kind"] == "OCCUPIED_TARGET"
                for w in r["collision_witnesses"]
            ) for r in result["rejected"]))
        self.assertEqual(len(result["candidates"]), 1)
        mapping = result["candidates"][0]["path_mapping"]
        self.assertEqual([(m["from"], m["to"]) for m in mapping], [
            ("src/orchard/sky/presenter.py", "src/orchard/earth/presenter.py"),
        ])
        self.assertEqual(result["candidates"][0]["decision"], "NOT_EVALUATED")
        from codeqa.evaluation.architecture.migration import assess_architecture_migration
        from codeqa.evaluation.architecture.assessment import assemble_architecture_advisory
        migration = assess_architecture_migration(inv, result, sources)
        advisory = assemble_architecture_advisory(inv, metrics, opp, result, migration)
        self.assertEqual(len(advisory["scenario_assessments"]), 1)
        self.assertEqual(
            advisory["scenario_assessments"][0]["decision_evidence"]["decision"],
            "INSUFFICIENT_EVIDENCE",
        )
        self.assertEqual(advisory["scenario_assessments"][0]["denominators"][
            "resolved_pairs"], len(metrics["resolved_pairs"]))

    def test_collision_does_not_rename_or_force_weak_alternative(self):
        sources = {
            **SOURCES,
            "src/orchard/earth/view.py": "value = 1\n",
            "src/orchard/sky/presenter.py":
                "from orchard.earth.model import Model\n",
        }
        edges = CONCENTRATED + (edge("sky/presenter", "earth/model"),)
        result = compare(sources=sources, edges=edges)
        self.assertEqual(result["candidates"], [])
        self.assertEqual(result["rejected"][0]["reason"], "TARGET_COLLISION")
        self.assertEqual(result["rejected"][0]["collision_witnesses"][0][
            "proposed_target_path"], "src/orchard/earth/view.py")

    def test_known_new_forbidden_boundary_blocks_candidate(self):
        _, _, opportunities, _ = reports(edges=CONCENTRATED)
        qid = opportunities["question_opportunities"][0]["opportunity_id"]
        report = compare(edges=CONCENTRATED, candidate_mappings={
            qid: {"src/orchard/sky/view.py": "src/orchard/earth/view.py"},
        })
        self.assertEqual(len(report["candidates"]), 1)
        # A new role policy can introduce a forbidden import; the same source
        # evidence must be re-derived under the new policy rather than edited.
        policy = deepcopy(POLICY)
        policy["roles"]["earth"]["forbidden_imports"] = ["rain", "sky"]
        inv, metrics, opp, _ = reports(policy=policy, edges=CONCENTRATED)
        changed = generate_virtual_layout_scenarios(inv, metrics, opp, policy)
        self.assertEqual(changed["candidates"], [])
        self.assertEqual(changed["rejected"][0]["reason"],
                         "NEW_DECLARED_BOUNDARY_VIOLATION")

    def test_cycle_only_does_not_invent_path_fix(self):
        result = compare(edges=(edge("sky/view", "sky/other"),
                                edge("sky/other", "sky/view")))
        self.assertEqual(result["candidates"], [])
        self.assertEqual(result["rejected"][0]["reason"],
                         "PATH_MOVE_CANNOT_REMOVE_STATIC_CYCLE")
        self.assertEqual(result["baseline"]["static_cycles"], 1)

    def test_renamed_isomorphic_sources_have_same_metric_delta(self):
        original = compare(edges=CONCENTRATED)
        sources = {p.replace("orchard", "woodland"): v for p, v in SOURCES.items()}
        policy = deepcopy(POLICY)
        policy["scope"] = "src/woodland"
        converted = tuple(StaticDependency(
            e.source_path.replace("orchard", "woodland"),
            e.target_path.replace("orchard", "woodland"), e.line,
            e.expression.replace("orchard", "woodland"), e.execution,
        ) for e in CONCENTRATED)
        after = compare(sources=sources, policy=policy, edges=converted)
        self.assertEqual(
            original["candidates"][0]["measured_proxy_delta"],
            after["candidates"][0]["measured_proxy_delta"],
        )

    def test_indistinguishable_role_proxies_do_not_create_a_preference(self):
        sources = {**SOURCES, "src/orchard/rain/other.py": "x = 1\n"}
        edges = CONCENTRATED + (edge("sky/view", "rain/other"),)
        _, _, opportunities, _ = reports(sources=sources, edges=edges)
        qid = opportunities["question_opportunities"][0]["opportunity_id"]
        source = "src/orchard/sky/view.py"
        first = compare(sources=sources, edges=edges, candidate_mappings={
            qid: {source: "src/orchard/earth/view.py"},
        })["candidates"][0]
        second = compare(sources=sources, edges=edges, candidate_mappings={
            qid: {source: "src/orchard/rain/view.py"},
        })["candidates"][0]
        self.assertEqual(first["measured_proxy_delta"], second["measured_proxy_delta"])
        self.assertNotEqual(first["path_mapping"], second["path_mapping"])
        self.assertEqual(first["decision"], second["decision"])
        self.assertEqual(first["decision"], "NOT_EVALUATED")

    def test_partial_dynamic_and_unclassified_evidence_fail_closed(self):
        from codeqa.core.dependency import UnknownDependency
        unknown = (UnknownDependency("src/orchard/sky/view.py", 4,
                                     "__import__(name)", "dynamic_import"),)
        result = compare(edges=CONCENTRATED, unknown=unknown)
        self.assertEqual(result["evidence_status"], "INCOMPLETE")
        self.assertIn("dynamic_import", result["candidates"][0]["unknowns"])
        sources = {**SOURCES, "src/orchard/unknown.py": "x = 1\n"}
        _, _, opportunities, _ = reports(sources=sources, edges=CONCENTRATED)
        qid = opportunities["question_opportunities"][0]["opportunity_id"]
        bad = compare(sources=sources, edges=CONCENTRATED, candidate_mappings={
            qid: {"src/orchard/unknown.py": "src/orchard/earth/unknown.py"},
        })
        self.assertEqual(bad["rejected"][0]["reason"], "UNCLASSIFIED_OR_UNREAD_SOURCE")
        _, _, base_opportunities, _ = reports(edges=CONCENTRATED)
        base_qid = base_opportunities["question_opportunities"][0]["opportunity_id"]
        unrelated = compare(edges=CONCENTRATED, candidate_mappings={
            base_qid: {"src/orchard/earth/helper.py": "src/orchard/rain/helper.py"},
        })
        self.assertEqual(unrelated["rejected"][0]["reason"],
                         "MAPPING_SOURCE_NOT_IN_ORIGINATING_SIGNAL")

    def test_mismatched_identity_or_untriggered_mapping_fails_closed(self):
        inv, metrics, opp, policy = reports(edges=CONCENTRATED)
        bad = deepcopy(opp)
        bad["question_opportunities"][0]["originating_signal_ids"] = ["0" * 64]
        with self.assertRaises(ArchitectureScenarioError):
            generate_virtual_layout_scenarios(inv, metrics, bad, policy)
        bad = deepcopy(policy)
        bad["scope"] = "src/other"
        with self.assertRaises(ArchitectureScenarioError):
            generate_virtual_layout_scenarios(inv, metrics, opp, bad)
        with self.assertRaises(ArchitectureScenarioError):
            generate_virtual_layout_scenarios(inv, metrics, opp, policy,
                candidate_mappings={"not-an-opportunity": {}})

    def test_determinism_schema_and_no_source_mutation(self):
        inv, metrics, opp, policy = reports(edges=CONCENTRATED)
        before = deepcopy((inv, metrics, opp, policy))
        result = generate_virtual_layout_scenarios(inv, metrics, opp, policy)
        self.assertEqual(result, generate_virtual_layout_scenarios(inv, metrics, opp, policy))
        self.assertEqual((inv, metrics, opp, policy), before)
        self.assertEqual(result["scenarios_id"], sha256(json.dumps(
            {k: v for k, v in result.items() if k != "scenarios_id"},
            sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest())
        schema = json.loads(
            (ROOT / "contracts/qa/architecture-scenarios-v0.1.schema.json").read_text()
        )
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(result)
        forged = deepcopy(result)
        forged["candidates"][0]["decision"] = "PREFER"
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(forged)))

    def test_real_codeqa_snapshot_does_not_force_named_scenarios(self):
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
        inventory = analyze_architecture_inventory(sha, paths, sources, policy)
        graph = extract_python_dependencies(sources, snapshot_id=sha,
                                            analyzed_paths=tuple(paths))
        metrics = analyze_architecture_metrics(inventory, graph, policy, PROFILE)
        opportunities = discover_architecture_opportunities(inventory, metrics)
        scenarios = generate_virtual_layout_scenarios(
            inventory, metrics, opportunities, policy
        )
        self.assertEqual(scenarios["snapshot_sha"], sha)
        self.assertEqual(scenarios["opportunities_id"], opportunities["opportunities_id"])
        self.assertNotEqual(scenarios["decision"], "PREFER")
        self.assertTrue(all(c["decision"] == "NOT_EVALUATED"
                            for c in scenarios["candidates"]))


if __name__ == "__main__":
    unittest.main()
