#!/usr/bin/env python3
"""Generate B3 unprompted architecture opportunities from same-head B1/B2 artifacts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

from jsonschema import Draft202012Validator

from codeqa.evaluation.architecture.opportunities import discover_architecture_opportunities


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--metrics", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    metrics = json.loads(args.metrics.read_text(encoding="utf-8"))
    if (inventory["source_identity"]["repository_commit_sha"] != head
            or metrics["snapshot_sha"] != head):
        raise ValueError("B1/B2 artifacts do not match exact checked-out HEAD")
    report = discover_architecture_opportunities(inventory, metrics)
    schema = json.loads(Path(
        "contracts/qa/architecture-opportunities-v0.1.schema.json"
    ).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(report)
    if any(
        not set(o["originating_signal_ids"]) <= {
            s["signal_id"] for s in report["architecture_signals"]
        }
        for o in report["question_opportunities"]
    ):
        raise ValueError("orphan question opportunity")
    args.output.write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"ARCHITECTURE_OPPORTUNITIES_B3 head={head} "
        f"signals={len(report['architecture_signals'])} "
        f"questions={len(report['question_opportunities'])} "
        f"observation={report['observation']} "
        f"evidence={report['evidence_status']} artifact={args.output}"
    )


if __name__ == "__main__":
    main()
