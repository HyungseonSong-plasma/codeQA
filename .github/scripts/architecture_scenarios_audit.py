#!/usr/bin/env python3
"""Generate B4 read-only virtual scenarios from exact-head B1/B2/B3 evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

from jsonschema import Draft202012Validator

from codeqa.evaluation.architecture.scenarios import generate_virtual_layout_scenarios


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--metrics", type=Path, required=True)
    parser.add_argument("--opportunities", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    metrics = json.loads(args.metrics.read_text(encoding="utf-8"))
    opportunities = json.loads(args.opportunities.read_text(encoding="utf-8"))
    policy = json.loads(Path(
        "profiles/semantic-directory-roles-v0.1.json"
    ).read_text(encoding="utf-8"))
    if (inventory["source_identity"]["repository_commit_sha"] != head
            or metrics["snapshot_sha"] != head
            or opportunities["snapshot_sha"] != head):
        raise ValueError("B1/B2/B3 artifacts do not match exact checked-out HEAD")
    report = generate_virtual_layout_scenarios(
        inventory, metrics, opportunities, policy
    )
    schema = json.loads(Path(
        "contracts/qa/architecture-scenarios-v0.1.schema.json"
    ).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(report)
    if report["decision"] != "NOT_EVALUATED" or report["evidence_status"] == "PASS":
        raise ValueError("B4 cannot certify a virtual architecture change")
    args.output.write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"ARCHITECTURE_SCENARIOS_B4 head={head} "
        f"candidates={len(report['candidates'])} "
        f"rejected={len(report['rejected'])} "
        f"evidence={report['evidence_status']} artifact={args.output}"
    )


if __name__ == "__main__":
    main()
