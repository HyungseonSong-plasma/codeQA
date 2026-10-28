#!/usr/bin/env python3
"""B5 exact-head static import and migration-impact audit, read-only."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess

from jsonschema import Draft202012Validator

from codeqa.evaluation.architecture.migration import assess_architecture_migration


def git(*args: str) -> bytes:
    return subprocess.run(["git", *args], capture_output=True, check=True).stdout


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--scenarios", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    head = git("rev-parse", "HEAD").decode("ascii").strip()
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    scenarios = json.loads(args.scenarios.read_text(encoding="utf-8"))
    if (inventory["source_identity"]["repository_commit_sha"] != head
            or scenarios["snapshot_sha"] != head):
        raise ValueError("B1/B4 reports are not for exact checked-out HEAD")

    # Verify all available blobs against B1, not just paths referenced by B4.
    # This prevents claiming no internal consumers when the caller silently
    # omitted tests, scripts, packaging metadata or documentation.
    sources: dict[str, bytes] = {}
    for item in inventory["files"]:
        if item["read_state"] != "READ":
            continue
        path = item["path"]
        raw = git("show", f"{head}:{path}")
        if sha256(raw).hexdigest() != item["source_sha256"]:
            raise ValueError("source hash does not match B1: " + path)
        sources[path] = raw
    report = assess_architecture_migration(inventory, scenarios, sources)
    schema = json.loads(Path(
        "contracts/qa/architecture-migration-v0.1.schema.json"
    ).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(report)
    if report["decision"] != "NOT_EVALUATED" or report["evidence_status"] == "PASS":
        raise ValueError("B5 cannot certify migration safety")
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(
        f"ARCHITECTURE_MIGRATION_B5 head={head} "
        f"candidates={len(report['candidates'])} "
        f"rejected={len(report['rejected_scenarios'])} "
        f"read={report['source_coverage']['read_source_texts']} "
        f"evidence={report['evidence_status']} artifact={args.output}"
    )


if __name__ == "__main__":
    main()
