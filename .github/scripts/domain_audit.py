#!/usr/bin/env python3
"""Emit exact-checkout, read-only domain/import evidence for #119."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess

from codeqa.adapters.python_snapshot import parse_python_snapshot
from codeqa.adapters.python_dependencies import extract_parsed_dependencies
from codeqa.evaluation.domain_inventory import analyze_domain_inventory, compare_domain_inventories
from codeqa.infrastructure.git import GitReader


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sha", required=True)
    parser.add_argument("--output", default="domain-inventory.json")
    parser.add_argument("--baseline-source-sha")
    parser.add_argument("--comparison-output", default="domain-inventory-comparison.json")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.sha):
        parser.error("exact lowercase 40-character commit SHA required")
    root = Path(__file__).resolve().parents[2]
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    if head != args.sha:
        parser.error("requested SHA does not match checked-out revision")
    for command in (["git", "diff", "--quiet"], ["git", "diff", "--cached", "--quiet"]):
        if subprocess.run(command, cwd=root).returncode:
            parser.error("dirty tracked source cannot be an exact-SHA witness")
    reader = GitReader(root)
    sources = {
        path: reader.read_file(args.sha, path).decode("utf-8")
        for path in reader.tracked_paths()
        if path.startswith("src/codeqa/") and path.endswith(".py")
    }
    parsed = parse_python_snapshot(sources)
    dependencies = extract_parsed_dependencies(parsed, snapshot_id=args.sha)
    domain_policy = json.loads((root / "profiles/domain-grouping-v0.1.json").read_text())
    role_policy = json.loads((root / "profiles/semantic-directory-roles-v0.1.json").read_text())
    result = analyze_domain_inventory(sources, dependencies, domain_policy, role_policy)
    (root / args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    if args.baseline_source_sha is not None:
        baseline = args.baseline_source_sha
        if not re.fullmatch(r"[0-9a-f]{40}", baseline) or baseline == args.sha:
            parser.error("baseline must be a distinct exact source commit")
        prior_paths = subprocess.check_output(
            ["git", "ls-tree", "-r", "--name-only", "-z", baseline], cwd=root
        ).split(b"\0")
        prior_sources = {
            path: reader.read_file(baseline, path).decode("utf-8")
            for entry in prior_paths if entry
            for path in [entry.decode("utf-8")]
            if path.startswith("src/codeqa/") and path.endswith(".py")
        }
        prior_parsed = parse_python_snapshot(prior_sources)
        prior_dependencies = extract_parsed_dependencies(prior_parsed, snapshot_id=baseline)
        prior_result = analyze_domain_inventory(
            prior_sources, prior_dependencies, domain_policy, role_policy,
        )
        comparison = compare_domain_inventories(
            prior_result, result, analyzer_sha=args.sha,
        )
        (root / args.comparison_output).write_text(
            json.dumps(comparison, indent=2, sort_keys=True) + "\n"
        )
        print("DOMAIN_INVENTORY_COMPARISON status=NOT_EVALUATED"
              " analyzer=" + args.sha + " baseline=" + baseline)
    print(
        f"DOMAIN_INVENTORY status={result['status']} sha={args.sha} "
        f"files={len(result['inventory'])} imports={result['observed_import_sites']} "
        f"cross_domain={result['classified_cross_import_sites']} "
        f"unknown_imports={len(result['unknown_imports'])}"
    )
    if result["status"] == "VIOLATION":
        raise SystemExit("declared role dependency violation")


if __name__ == "__main__":
    main()
