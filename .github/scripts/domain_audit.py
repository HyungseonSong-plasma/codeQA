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
from codeqa.evaluation.domain_inventory import analyze_domain_inventory
from codeqa.infrastructure.git import GitReader


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sha", required=True)
    parser.add_argument("--output", default="domain-inventory.json")
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
