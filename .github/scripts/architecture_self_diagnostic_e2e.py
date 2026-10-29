#!/usr/bin/env python3
"""Run B1--B8 on one exact HEAD, without a seeded question or source mutation."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from jsonschema import Draft202012Validator
from codeqa.evaluation.architecture.self_diagnostic import (
    project_self_diagnostic, build_b8_artifact_manifest, verify_b8_artifact_manifest,
)
from codeqa.evaluation.architecture.policy_triage import (
    render_policy_triage_markdown, render_policy_candidate_decisions,
    triage_cross_role_concentration,
)
from codeqa.evaluation.architecture.internal_consumers import (
    census_internal_consumers, render_internal_consumers_markdown,
)
from codeqa.evaluation.architecture.package_surface import (
    census_package_surface, render_package_surface_markdown,
)
from codeqa.evaluation.architecture.edge_responsibility import (
    census_edge_responsibility, render_edge_responsibility_markdown,
)
from codeqa.infrastructure.git import GitReader
from codeqa.evaluation.architecture.runtime_call_pairs import capture_unittest_call_pairs
from codeqa.evaluation.architecture.runtime_pair_selection import select_b8_runtime_pairs
from codeqa.evaluation.architecture.runtime_edge_correlation import correlate_b8_runtime_pairs
from codeqa.evaluation.architecture.callsite_context import census_b8_callsite_context
from codeqa.evaluation.architecture.import_binding_usage import census_b8_import_binding_uses
from codeqa.evaluation.architecture.import_initialization import capture_cold_import_line_entries
from codeqa.evaluation.architecture.test_behavior_candidates import (
    census_test_behavior_candidates, render_test_behavior_candidates_markdown,
)
from codeqa.evaluation.architecture.bounded_disposition import (
    assess_bounded_disposition, render_bounded_disposition_markdown,
)

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / ".github" / "scripts"


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def execute(script: str, *args: str) -> None:
    subprocess.run([sys.executable, str(SCRIPTS / script), *args],
                   cwd=ROOT, check=True)


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    head = git("rev-parse", "HEAD")
    if os.environ.get("EXPECTED_HEAD", head) != head:
        raise ValueError("CI expected HEAD differs from checkout")
    before = git("status", "--porcelain", "--untracked-files=no")
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="codeqa-b8-") as temp:
        p = {name: str(Path(temp) / (name + ".json")) for name in (
            "inventory", "metrics", "opportunities", "adapter", "scenarios",
            "migration", "assessment"
        )}
        execute("architecture_inventory_audit.py", "--output", p["inventory"])
        execute("architecture_metrics_audit.py", "--inventory", p["inventory"],
                "--output", p["metrics"])
        execute("architecture_opportunities_audit.py", "--inventory", p["inventory"],
                "--metrics", p["metrics"], "--output", p["opportunities"])
        execute("architecture_adapter_boundaries_audit.py", "--inventory", p["inventory"],
                "--metrics", p["metrics"], "--output", p["adapter"])
        execute("architecture_scenarios_audit.py", "--inventory", p["inventory"],
                "--metrics", p["metrics"], "--opportunities", p["opportunities"],
                "--output", p["scenarios"])
        execute("architecture_migration_audit.py", "--inventory", p["inventory"],
                "--scenarios", p["scenarios"], "--output", p["migration"])
        execute("architecture_assessment_audit.py", "--inventory", p["inventory"],
                "--metrics", p["metrics"], "--opportunities", p["opportunities"],
                "--scenarios", p["scenarios"], "--migration", p["migration"],
                "--adapter-boundaries", p["adapter"], "--output", p["assessment"],
                "--summary", str(Path(temp) / "b7.md"))
        inventory, assessment = read(Path(p["inventory"])), read(Path(p["assessment"]))
        role_policy = read(ROOT / "profiles/semantic-directory-roles-v0.1.json")
        metrics = read(Path(p["metrics"]))
        triage = triage_cross_role_concentration(
            inventory, metrics, read(Path(p["opportunities"])), role_policy,
        )
        consumers = census_internal_consumers(inventory, metrics, triage)
        package_surface = census_package_surface(
            inventory, consumers, (ROOT / "pyproject.toml").read_bytes(),
        )
        responsibility = census_edge_responsibility(
            inventory, metrics, triage, consumers, role_policy,
        )
        # Read only test blobs already witnessed by B2/B3/B8 at the same HEAD.
        test_paths = sorted({
            witness["source_path"]
            for edge in responsibility["edges"]
            for witness in edge["known_test_path_importers"]
        })
        reader = GitReader(ROOT)
        test_sources = {path: reader.read_file(head, path) for path in test_paths}
        test_candidates = census_test_behavior_candidates(
            inventory, responsibility, test_sources,
        )
        disposition = assess_bounded_disposition(
            inventory, triage, responsibility, assessment,
        )
        signals, questions, summary = project_self_diagnostic(assessment, inventory)
        summary += "\n" + render_policy_triage_markdown(triage)
        summary += "\n" + render_policy_candidate_decisions(triage, assessment)
        summary += "\n" + render_internal_consumers_markdown(consumers)
        summary += "\n" + render_package_surface_markdown(package_surface)
        summary += "\n" + render_edge_responsibility_markdown(responsibility)
        summary += "\n" + render_test_behavior_candidates_markdown(test_candidates)
        summary += "\n" + render_bounded_disposition_markdown(disposition)
        schema = read(ROOT / "contracts/qa/architecture-self-diagnostic-v0.1.schema.json")
        Draft202012Validator.check_schema(schema)
        for projection in (signals, questions):
            Draft202012Validator(schema).validate(projection)
        if (assessment["source_identity"]["snapshot_sha"] != head
                or signals["source_identity"]["snapshot_sha"] != head
                or questions["source_identity"]["snapshot_sha"] != head
                or triage["source_identity"]["snapshot_sha"] != head
                or consumers["source_identity"]["snapshot_sha"] != head
                or package_surface["source_identity"]["snapshot_sha"] != head
                or responsibility["source_identity"]["snapshot_sha"] != head
                or test_candidates["source_identity"]["snapshot_sha"] != head
                or disposition["source_identity"]["snapshot_sha"] != head):
            raise ValueError("B8 source identity drift")
        write(output / "architecture-signals.json", signals)
        write(output / "question-opportunities.json", questions)
        write(output / "architecture-internal-consumers.json", consumers)
        write(output / "architecture-package-surface.json", package_surface)
        write(output / "architecture-edge-responsibility.json", responsibility)
        write(output / "architecture-test-behavior-candidates.json", test_candidates)
        write(output / "architecture-bounded-disposition.json", disposition)
        shutil.copyfile(p["assessment"], output / "architecture-assessment.json")
        (output / "architecture-self-diagnostic.md").write_text(summary, encoding="utf-8")
        # Bind all B8 measured cross-role pairs to the same Git HEAD, then
        # observe a small, explicit unittest sample. No question is seeded.
        selection = select_b8_runtime_pairs(inventory, responsibility)
        for path, expected_hash in selection["source_sha256"].items():
            if sha256(reader.read_file(head, path)).hexdigest() != expected_hash:
                raise ValueError("runtime selected source differs from B1 Git blob")
        # Observe module-initialization import-line entry in a fresh interpreter.
        # This opt-in B8 job executes trusted repository code; line entry alone
        # does not establish import completion, binding or semantic ownership.
        cold_import = capture_cold_import_line_entries(
            selection, responsibility, repository_root=ROOT,
            timeout_seconds=90,
        )
        if (cold_import["source_identity"]["snapshot_sha"] != head
                or cold_import["static_pairs"] != len(selection["pairs"])
                or not 0 <= cold_import["pairs_with_target_module_path_match"] <= len(selection["pairs"])
                or cold_import["target_module_cache_evidence"] != "PROCESS_LOCAL_PATH_METADATA_UNATTESTED"
                or cold_import["decision"] != "NOT_EVALUATED"):
            raise ValueError("cold interpreter import evidence drift")
        write(output / "architecture-import-initialization.json", cold_import)
        # Lexical loads are source-only candidates; never infer target binding,
        # import execution, dead dependencies or a package-move recommendation.
        lexical_usage = census_b8_import_binding_uses(
            selection, responsibility, {
                path: reader.read_file(head, path)
                for path in sorted({edge["source_path"] for edge in responsibility["edges"]})
            },
        )
        write(output / "architecture-import-binding-usage.json", lexical_usage)
        observation = None
        # Extend the bounded sample using test modules that statically import
        # pipeline sources among the 31 previously unobserved cross-role pairs.
        # Candidate imports select tests; they do not prove runtime traversal.
        test_patterns = (
            "test_analysis_request.py",
            "test_mechanical_pipeline.py",
            "test_shared_evidence_pipeline.py",
            "test_naming_product_boundary.py",
            "test_naming_field_evidence_v03.py",
            "test_naming_internal_import_census_v04.py",
            "test_naming_official_adoption_v05.py",
            "test_naming_official_policy_v05.py",
            "test_naming_rule_inventory_v03.py",
            "test_naming_scope_discovery_v04.py",
            "test_naming_snapshot_coverage_v03.py",
            "test_mixed_source_coverage.py",
            "test_git_tree_reader_v01.py",
        )
        if selection["pairs"]:
            loader = unittest.TestLoader()
            suite = unittest.TestSuite()
            for pattern in test_patterns:
                suite.addTests(loader.discover(str(ROOT / "tests"), pattern=pattern))
            observation = capture_unittest_call_pairs(
                suite, snapshot_sha=head, repository_root=ROOT,
                source_sha256=selection["source_sha256"],
                pairs=[tuple(pair) for pair in selection["pairs"]],
                import_witness_lines={
                    (edge["source_path"], edge["target_path"]): sorted({
                        witness["line"] for witness in edge["import_witnesses"]
                    })
                    for edge in responsibility["edges"]
                },
            )
            if not observation["suite_was_successful"] or observation["tests_run"] == 0:
                raise ValueError("runtime test sample did not execute successfully")
        runtime_report = {
            "schema_version": "0.1",
            "source_identity": selection["source_identity"],
            "selection_id": selection["selection_id"],
            "observed_cross_role_pairs": selection["observed_cross_role_pairs"],
            "test_patterns": list(test_patterns) if observation else [],
            "observation": observation,
            "runtime_collection_state": (
                "BOUNDED_SAMPLE_EXECUTED" if observation else "NO_MEASURED_PAIRS"
            ),
            "ci_provenance": "NOT_INDEPENDENTLY_ATTESTED",
            "static_import_edge_traversal": "NOT_EVALUATED",
            "semantic_ownership": "NOT_EVALUATED",
            "public_api_compatibility": "NOT_EVALUATED",
            "decision": "NOT_EVALUATED",
            "limitations": [
                "observed direct Python frame calls do not prove import statement traversal",
                "selected unittest modules are a bounded sample, not full test coverage",
                "unobserved pairs may execute through other tests, threads or native calls",
                "import-line entry precedes statement execution; imported target resolution is unverified",
                "Git blob hashes verify on-disk bytes, not interpreter-loaded bytecode",
                "CI provenance requires independent GitHub run and artifact verification",
            ],
        }
        write(output / "architecture-runtime-call-pairs.json", runtime_report)
        correlation = correlate_b8_runtime_pairs(selection, responsibility, observation)
        write(output / "architecture-runtime-edge-correlation.json", correlation)
        # Preserve each observed call's lexical caller function at the same
        # source HEAD. This is review context, not semantic ownership proof.
        context = census_b8_callsite_context(
            selection, correlation, {
                path: reader.read_file(head, path)
                for path in sorted({source for source, _ in selection["pairs"]})
            },
        )
        if (context["source_identity"]["snapshot_sha"] != head
                or context["static_pairs"] != len(selection["pairs"])
                or context["direct_call_observed_pairs"] != correlation["direct_call_observed_pairs"]
                or context["sampled_ast_call_candidate_witnesses"]
                   + context["sampled_no_ast_call_candidate_witnesses"]
                   != context["sampled_call_witnesses"]
                or context["sampled_import_alias_call_candidate_witnesses"]
                   + context["sampled_without_direct_import_alias_call_candidate"]
                   != context["sampled_call_witnesses"]
                or not 0 <= context["sampled_alias_parameter_shadowing_warning_witnesses"]
                        <= context["sampled_import_alias_call_candidate_witnesses"]
                or context["decision"] != "NOT_EVALUATED"):
            raise ValueError("B8 caller context identity or denominator drift")
        write(output / "architecture-callsite-context.json", context)
        with (output / "architecture-self-diagnostic.md").open("a", encoding="utf-8") as handle:
            handle.write(
                "\n## Bounded static/runtime pair correlation\n\n"
                f"- Static pairs: {correlation['static_pairs']}\n"
                f"- Direct-call observed: {correlation['direct_call_observed_pairs']}\n"
                f"- Sampled call witnesses with lexical caller context: {context['sampled_call_witnesses']}\n"
                f"- Sampled witnesses within function bodies: {context['sampled_function_body_witnesses']}\n"
                f"- Caller lines with AST Call span candidates: {context['sampled_ast_call_candidate_witnesses']}\n"
                f"- Caller lines without AST Call span candidates: {context['sampled_no_ast_call_candidate_witnesses']}\n"
                f"- Caller witnesses with target import-alias lexical call candidates: {context['sampled_import_alias_call_candidate_witnesses']}\n"
                f"- Caller witnesses without direct target import-alias call candidates: {context['sampled_without_direct_import_alias_call_candidate']}\n"
                f"- Caller witnesses with lexical parameter-shadowing warnings: {context['sampled_alias_parameter_shadowing_warning_witnesses']}\n"
                "- Parameter collisions are source-only warnings, not runtime attribution; global/nonlocal and lambda scope remain unresolved.\n"
                "- Import alias call matches are lexical only: shadowing, rebinding and indirect receivers remain unresolved.\n"
                "- AST Call spans and enclosing statement kinds are source candidates, not callee or ownership proof.\n"
                "- Lexical caller function spans do not establish intentional orchestration or ownership.\n"
                f"- Not observed in sample: {correlation['not_observed_in_sample_pairs']}\n"
                f"- Import-line visited pairs: {correlation['import_line_visited_pairs']}\n"
                f"- Import-line not visited pairs: {correlation['not_visited_import_line_pairs']}\n"
                f"- Direct module-level import pairs: {correlation['module_top_level_import_pairs']}\n"
                f"- Nested/conditional import pairs: {correlation['nested_or_conditional_import_pairs']}\n"
                f"- Import-line lexical Name(Load) candidate pairs: {lexical_usage['pairs_with_name_load_candidates']}\n"
                f"- No lexical Name(Load) candidate pairs: {lexical_usage['pairs_without_name_load_candidates']}\n"
                "- Lexical candidates are line-co-located, not resolved target bindings.\n"
                "- Module-level imports may finish before the bounded test-time trace.\n"
                f"- Cold-interpreter import-line observed pairs: {cold_import['pairs_with_line_entries']}/{cold_import['static_pairs']}\n"
                f"- Cold-interpreter line visits truncated: {cold_import['line_visits_truncated']}\n"
                f"- Process-local target module path matches: {cold_import['pairs_with_target_module_path_match']}/{cold_import['static_pairs']}\n"
                "- Module cache path metadata is mutable and does not prove import binding or bytecode identity.\n"
                "- Cold interpreter line entry does not prove import target resolution.\n"
                "- Import-line entry is pre-execution, not proof of target resolution.\n"
                "- Import-statement traversal and semantic ownership: NOT_EVALUATED.\n"
            )
        manifest = build_b8_artifact_manifest(output, head)
        write(output / "architecture-evidence-manifest.json", manifest)
        verify_b8_artifact_manifest(output, manifest)
    if git("status", "--porcelain", "--untracked-files=no") != before:
        raise ValueError("B8 pipeline mutated tracked source")
    print("ARCHITECTURE_B8 head=" + head
          + " signals=" + str(len(signals["items"]))
          + " questions=" + str(len(questions["items"]))
          + " decision=NOT_EVALUATED output=" + str(output))


if __name__ == "__main__":
    main()
