#!/usr/bin/env python3
"""Run B1--B8 on one exact HEAD, without a seeded question or source mutation."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from jsonschema import Draft202012Validator
from codeqa.evaluation.architecture.self_diagnostic import project_self_diagnostic
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
        signals, questions, summary = project_self_diagnostic(assessment, inventory)
        summary += "\n" + render_policy_triage_markdown(triage)
        summary += "\n" + render_policy_candidate_decisions(triage, assessment)
        summary += "\n" + render_internal_consumers_markdown(consumers)
        summary += "\n" + render_package_surface_markdown(package_surface)
        summary += "\n" + render_edge_responsibility_markdown(responsibility)
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
                or responsibility["source_identity"]["snapshot_sha"] != head):
            raise ValueError("B8 source identity drift")
        write(output / "architecture-signals.json", signals)
        write(output / "question-opportunities.json", questions)
        write(output / "architecture-internal-consumers.json", consumers)
        write(output / "architecture-package-surface.json", package_surface)
        write(output / "architecture-edge-responsibility.json", responsibility)
        shutil.copyfile(p["assessment"], output / "architecture-assessment.json")
        (output / "architecture-self-diagnostic.md").write_text(summary, encoding="utf-8")
    if git("status", "--porcelain", "--untracked-files=no") != before:
        raise ValueError("B8 pipeline mutated tracked source")
    print("ARCHITECTURE_B8 head=" + head
          + " signals=" + str(len(signals["items"]))
          + " questions=" + str(len(questions["items"]))
          + " decision=NOT_EVALUATED output=" + str(output))


if __name__ == "__main__":
    main()
