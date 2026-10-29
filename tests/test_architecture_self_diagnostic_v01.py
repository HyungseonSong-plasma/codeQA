"""B8 independent unprompted, renamed, no-signal and source-binding regressions."""
from __future__ import annotations

import ast
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from jsonschema import Draft202012Validator
from codeqa.core.dependency import DependencyGraph, StaticDependency
from codeqa.evaluation.architecture.assessment import assemble_architecture_advisory
from codeqa.evaluation.architecture.inventory import analyze_architecture_inventory
from codeqa.evaluation.architecture.metrics import analyze_architecture_metrics
from codeqa.evaluation.architecture.opportunities import discover_architecture_opportunities
from codeqa.evaluation.architecture.scenarios import generate_virtual_layout_scenarios
from codeqa.evaluation.architecture.migration import assess_architecture_migration
from codeqa.evaluation.architecture.self_diagnostic import (
    SelfDiagnosticEvidenceError, project_self_diagnostic,
    B8_REQUIRED_ARTIFACTS, build_b8_artifact_manifest, verify_b8_artifact_manifest,
)
from test_architecture_assessment_v01 import assembled
from test_architecture_scenarios_v01 import (
    CONCENTRATED, POLICY, PROFILE, SHA, SOURCES, edge, reports,
)

ROOT = Path(__file__).resolve().parents[1]


def seal(report):
    report["assessment_id"] = sha256(json.dumps(
        {k: v for k, v in report.items() if k != "assessment_id"},
        sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()
    return report


def renamed_concentration():
    sources = {p.replace("orchard", "woodland"): v.replace("orchard", "woodland")
               for p, v in SOURCES.items()}
    policy = deepcopy(POLICY)
    policy["scope"] = "src/woodland"
    edges = tuple(StaticDependency(
        e.source_path.replace("orchard", "woodland"),
        e.target_path.replace("orchard", "woodland"), e.line,
        e.expression.replace("orchard", "woodland"), e.execution,
    ) for e in CONCENTRATED)
    inv = analyze_architecture_inventory(SHA, sources, sources, policy)
    graph = DependencyGraph(SHA, tuple(sorted(sources)), (), edges, ())
    metrics = analyze_architecture_metrics(inv, graph, policy, PROFILE)
    opp = discover_architecture_opportunities(inv, metrics)
    scenarios = generate_virtual_layout_scenarios(inv, metrics, opp, policy)
    migration = assess_architecture_migration(inv, scenarios, sources)
    return inv, assemble_architecture_advisory(inv, metrics, opp, scenarios, migration)


class SelfDiagnosticE2ETests(unittest.TestCase):
    def test_pipeline_git_subprocess_is_infrastructure_owned(self):
        """Repository self-audit: pipeline must not execute Git directly."""
        offenders = []
        for path in sorted((ROOT / "src/codeqa/pipeline").glob("*.py")):
            tree = ast.parse(path.read_bytes(), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import) and any(
                    alias.name == "subprocess" for alias in node.names
                ):
                    offenders.append((path.name, node.lineno))
                if isinstance(node, ast.ImportFrom) and node.module == "subprocess":
                    offenders.append((path.name, node.lineno))
        self.assertEqual(offenders, [])

    def test_no_signal_yields_zero_questions_not_pass(self):
        inv, _, _, _ = reports(edges=())
        signals, questions, human = project_self_diagnostic(assembled(edges=()), inv)
        self.assertEqual(signals["items"], [])
        self.assertEqual(questions["items"], [])
        self.assertEqual(questions["decision"], "NOT_EVALUATED")
        self.assertIn("zero questions is valid", human)
        self.assertNotIn("PREFER", human)

    def test_independent_structural_problems_generate_different_questions(self):
        inv, _, _, _ = reports(edges=CONCENTRATED)
        concentration = project_self_diagnostic(assembled(), inv)
        cycle_edges = (edge("sky/view", "sky/other"), edge("sky/other", "sky/view"))
        inv2, _, _, _ = reports(edges=cycle_edges)
        cycle = project_self_diagnostic(assembled(edges=cycle_edges), inv2)
        self.assertEqual(concentration[0]["items"][0]["family"],
                         "CROSS_BOUNDARY_CONCENTRATION")
        self.assertEqual(cycle[0]["items"][0]["family"], "STATIC_IMPORT_CYCLE")
        self.assertNotEqual(concentration[1]["items"][0]["opportunity_id"],
                            cycle[1]["items"][0]["opportunity_id"])
        self.assertIn("KEEP", concentration[2])
        self.assertIn("Benign alternative:", cycle[2])

    def test_renamed_package_has_equivalent_discovery_not_seeded_name(self):
        inv, result = renamed_concentration()
        signals, questions, human = project_self_diagnostic(result, inv)
        self.assertEqual(len(questions["items"]), 1)
        self.assertEqual(signals["items"][0]["family"], "CROSS_BOUNDARY_CONCENTRATION")
        self.assertIn("woodland", human)
        self.assertNotIn("Should Naming", human)

    def test_deceptive_naming_class_without_relationships_no_question(self):
        sources = {**SOURCES, "src/orchard/earth/naming.py":
                   "class AdapterNamingService: pass\\n"}
        inv, _, _, _ = reports(sources=sources, edges=())
        assessment = assembled(edges=(), sources=sources)
        self.assertEqual(project_self_diagnostic(assessment, inv)[1]["items"], [])

    def test_reject_forged_source_witness_even_with_resealed_report(self):
        inv, _, _, _ = reports(edges=CONCENTRATED)
        forged = deepcopy(assembled())
        forged["architecture_signals"][0]["source_witnesses"][0]["source_sha256"] = "0" * 64
        seal(forged)
        with self.assertRaises(SelfDiagnosticEvidenceError):
            project_self_diagnostic(forged, inv)

    def test_reject_orphan_question_even_with_resealed_report(self):
        inv, _, _, _ = reports(edges=CONCENTRATED)
        forged = deepcopy(assembled())
        forged["question_opportunities"][0]["originating_signal_ids"] = ["orphan"]
        seal(forged)
        with self.assertRaises(SelfDiagnosticEvidenceError):
            project_self_diagnostic(forged, inv)

    def test_reject_mismatched_source_identity(self):
        inv, _, _, _ = reports(edges=CONCENTRATED)
        changed = deepcopy(inv)
        changed["source_identity"]["repository_commit_sha"] = "f" * 40
        with self.assertRaises(SelfDiagnosticEvidenceError):
            project_self_diagnostic(assembled(), changed)

    def test_rejected_collision_paths_reach_human_report(self):
        inv, metrics, opportunities, policy = reports(edges=CONCENTRATED)
        qid = opportunities["question_opportunities"][0]["opportunity_id"]
        scenarios = generate_virtual_layout_scenarios(
            inv, metrics, opportunities, policy,
            candidate_mappings={qid: {
                "src/orchard/sky/view.py": "src/orchard/earth/model.py"
            }},
        )
        migration = assess_architecture_migration(inv, scenarios, SOURCES)
        assessment = assemble_architecture_advisory(
            inv, metrics, opportunities, scenarios, migration
        )
        summary = project_self_diagnostic(assessment, inv)[2]
        self.assertIn(
            "Collision (OCCUPIED_TARGET): src/orchard/sky/view.py"
            " -> src/orchard/earth/model.py", summary
        )
        self.assertIn("Existing target sha256:", summary)
        self.assertIn("Overall decision: NOT_EVALUATED", summary)

    def test_deterministic_projections_and_schema(self):
        inv, _, _, _ = reports(edges=CONCENTRATED)
        a = project_self_diagnostic(assembled(), inv)
        b = project_self_diagnostic(assembled(), inv)
        self.assertEqual(a, b)
        schema = json.loads((ROOT / "contracts/qa/architecture-self-diagnostic-v0.1.schema.json")
                            .read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        for report in a[:2]:
            Draft202012Validator(schema).validate(report)
            self.assertEqual(report["source_identity"]["snapshot_sha"], SHA)
            self.assertNotEqual(report["decision"], "PASS")


class B8ArtifactManifestTests(unittest.TestCase):
    def make_pack(self, root: Path, *, sha: str = SHA) -> None:
        for name in B8_REQUIRED_ARTIFACTS:
            path = root / name
            if name.endswith(".json"):
                path.write_text(json.dumps({"source_identity": {"snapshot_sha": sha}}))
            else:
                path.write_text("# B8 report\nExact source HEAD: " + sha + "\n")

    def seal(self, root: Path):
        manifest = build_b8_artifact_manifest(root, SHA)
        (root / "architecture-evidence-manifest.json").write_text(
            json.dumps(manifest, sort_keys=True, indent=2) + "\n"
        )
        return manifest

    def test_complete_pack_sealed_and_reverified(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_pack(root)
            manifest = self.seal(root)
            self.assertEqual(len(manifest["files"]), len(B8_REQUIRED_ARTIFACTS))
            self.assertEqual(manifest["decision"], "NOT_EVALUATED")
            self.assertEqual(manifest["runtime_edge_traversal"], "NOT_EVALUATED")
            verify_b8_artifact_manifest(root, manifest)

    def test_missing_extra_or_mixed_source_rejected(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_pack(root)
            (root / "architecture-edge-responsibility.json").unlink()
            with self.assertRaises(SelfDiagnosticEvidenceError):
                build_b8_artifact_manifest(root, SHA)
            self.make_pack(root)
            (root / "architecture-test-behavior-candidates.json").write_text(
                json.dumps({"source_identity": {"snapshot_sha": "b" * 40}})
            )
            with self.assertRaises(SelfDiagnosticEvidenceError):
                build_b8_artifact_manifest(root, SHA)
            self.make_pack(root)
            (root / "stale.json").write_text("{}")
            with self.assertRaises(SelfDiagnosticEvidenceError):
                build_b8_artifact_manifest(root, SHA)

    def test_tampering_after_seal_rejected(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_pack(root)
            manifest = self.seal(root)
            (root / "architecture-edge-responsibility.json").write_text(
                json.dumps({"source_identity": {"snapshot_sha": SHA}, "forged": True})
            )
            with self.assertRaises(SelfDiagnosticEvidenceError):
                verify_b8_artifact_manifest(root, manifest)

    def test_forged_manifest_rejected(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_pack(root)
            manifest = self.seal(root)
            manifest["evidence_class"] = "TRUSTED_CI"
            with self.assertRaises(SelfDiagnosticEvidenceError):
                verify_b8_artifact_manifest(root, manifest)

    def test_workflow_uploads_complete_pack(self):
        workflow = (ROOT / ".github/workflows/architecture-self-diagnostic.yml").read_text()
        script = (ROOT / ".github/scripts/architecture_self_diagnostic_e2e.py").read_text()
        self.assertIn("path: architecture-e2e/", workflow)
        self.assertIn("if-no-files-found: error", workflow)
        self.assertIn("build_b8_artifact_manifest(output, head)", script)
        self.assertIn("verify_b8_artifact_manifest(output, manifest)", script)


if __name__ == "__main__":
    unittest.main()
