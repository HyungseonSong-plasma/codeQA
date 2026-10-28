#!/usr/bin/env python3
"""B6 exact-head read-only adapter boundary report from B1/B2 artifacts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

from jsonschema import Draft202012Validator
from codeqa.evaluation.architecture.adapter_boundaries import assess_adapter_boundaries


def git(*args: str) -> bytes:
    return subprocess.run(["git", *args], check=True, capture_output=True).stdout


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--metrics", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    head = git("rev-parse", "HEAD").decode("ascii").strip()
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    metrics = json.loads(args.metrics.read_text(encoding="utf-8"))
    declaration = json.loads(git(
        "show", f"{head}:profiles/architecture-adapter-boundaries-v0.1.json"
    ))
    if (inventory["source_identity"]["repository_commit_sha"] != head
            or metrics["snapshot_sha"] != head):
        raise ValueError("B6 requires exact-HEAD B1/B2 artifacts")
    report = assess_adapter_boundaries(inventory, metrics, declaration)
    schema = json.loads(git(
        "show", f"{head}:contracts/qa/architecture-adapter-boundaries-v0.1.schema.json"
    ))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(report)
    if report["decision"] != "NOT_EVALUATED" or report["evidence_status"] == "PASS":
        raise ValueError("B6 must not certify package migration")
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(
        f"ARCHITECTURE_ADAPTER_BOUNDARIES_B6 head={head} "
        f"families={len(report['family_capabilities'])} "
        f"signals={len(report['architecture_signals'])} "
        f"unclassified={len(report['coverage']['unclassified_paths'])} "
        f"evidence={report['evidence_status']} artifact={args.output}"
    )


if __name__ == "__main__":
    main()
