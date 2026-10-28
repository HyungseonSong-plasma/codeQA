#!/usr/bin/env python3
"""Produce read-only B2 metrics for the exact checked-out Git HEAD."""
from __future__ import annotations

import argparse
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import subprocess

from codeqa.adapters.python_dependencies import extract_parsed_dependencies
from codeqa.adapters.python_snapshot import parse_python_snapshot
from codeqa.evaluation.architecture.metrics import analyze_architecture_metrics
from codeqa.evaluation.dependency_metrics import DependencyMetricsProfile


def git(*args: str) -> bytes:
    return subprocess.run(["git", *args], capture_output=True, check=True).stdout


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    head = git("rev-parse", "HEAD").decode("ascii").strip()
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    if inventory["source_identity"]["repository_commit_sha"] != head:
        raise ValueError("B1 inventory was not produced for the checked-out HEAD")

    sources: dict[str, str] = {}
    unreadable: list[str] = []
    for item in inventory["files"]:
        if item["read_state"] != "READ" or item["language"] != "python":
            continue
        path = item["path"]
        raw = git("show", f"{head}:{path}")
        if sha256(raw).hexdigest() != item["source_sha256"]:
            raise ValueError("B1 source hash and exact HEAD mismatch")
        try:
            sources[path] = raw.decode("utf-8")
        except UnicodeDecodeError:
            unreadable.append(path)

    parsed = parse_python_snapshot(sources)
    graph = extract_parsed_dependencies(parsed, snapshot_id=head)
    graph = replace(
        graph,
        unprocessed_paths=tuple(sorted(set(graph.unprocessed_paths) | set(unreadable))),
    )
    role_policy = json.loads(
        git("show", f"{head}:profiles/semantic-directory-roles-v0.1.json")
    )
    profile = DependencyMetricsProfile.from_mapping(json.loads(
        git("show", f"{head}:profiles/dependency-metrics-v0.1.json")
    ))
    report = analyze_architecture_metrics(inventory, graph, role_policy, profile)
    args.output.write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"ARCHITECTURE_METRICS_B2 head={head} analyzed="
        f"{report['coverage']['python_analyzed']} pairs="
        f"{report['denominators']['resolved_distinct_pairs']} cycles="
        f"{len(report['cycles'])} status={report['status']} artifact={args.output}"
    )


if __name__ == "__main__":
    main()
