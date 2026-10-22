#!/usr/bin/env python3
"""Inspect a pinned codeQA Git checkout using the actual codeQA pipeline."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
import subprocess

from codeqa.infrastructure.git import GitReader
from codeqa.infrastructure.resources import ResourceRegistry
from codeqa.pipeline.python import analyze_python


ROOT = Path(__file__).resolve().parents[2]


def analyze_checkout(root: Path, sha: str) -> dict:
    """Group product and test sources, retaining reproducible graph evidence."""
    actual_head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    if sha != actual_head:
        raise ValueError("the pinned snapshot must match checkout HEAD")
    for arguments in (("git", "diff", "--quiet"), ("git", "diff", "--cached", "--quiet")):
        if subprocess.run(arguments, cwd=root, check=False).returncode:
            raise ValueError("tracked checkout differs from pinned snapshot")

    reader = GitReader(root)
    registry = ResourceRegistry(root)
    schema = registry.load_json("ccg_schema")
    profile = registry.load_json("mechanical_profile")
    paths = sorted(p for p in reader.tracked_paths() if p.endswith(".py"))
    sources = {path: reader.read_file(sha, path).decode("utf-8") for path in paths}
    groups = {
        "production": {p: v for p, v in sources.items() if p.startswith("src/codeqa/")},
        "tests": {p: v for p, v in sources.items() if p.startswith("tests/")},
        "all_python": sources,
    }
    results = {}
    for name, inputs in groups.items():
        analysis = analyze_python(
            inputs, snapshot_id=f"git:{sha}",
            ccg_schema=schema, mechanical_profile=profile,
        )
        graph, report = analysis.graph, analysis.quality
        results[name] = {
            "source_files": len(inputs),
            "source_paths": sorted(inputs),
            "ccg_nodes": len(graph.nodes),
            "ccg_edges": len(graph.edges),
            "node_kinds": dict(sorted(Counter(n.kind for n in graph.nodes).items())),
            "edge_kinds": dict(sorted(Counter(e.kind for e in graph.edges).items())),
            "coverage": graph.coverage.status,
            "diagnostics": [asdict(d) for d in graph.diagnostics],
            "quality": report.to_document(),
        }
        print(
            f"SELF_AUDIT {name}: files={len(inputs)} nodes={len(graph.nodes)} "
            f"edges={len(graph.edges)} functions={report.function_count} "
            f"unresolved={report.unresolved_edges} "
            f"findings={len(report.findings)} coverage={graph.coverage.status} "
            f"status={report.status}", flush=True,
        )
        for finding in report.findings:
            print(
                f"  REVIEW {finding.rule_id} {finding.node_id} "
                f"observed={finding.observed} threshold={finding.threshold}",
                flush=True,
            )

    return {
        "snapshot_sha": sha,
        "profile": profile,
        "limitations": (
            "Mechanical QA v0.1 evaluates only two review heuristics. "
            "Neither PASS nor REVIEW_REQUIRED represents full P1–P8 assessment."
        ),
        "scopes": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sha", required=True, help="Pinned full Git commit SHA")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = analyze_checkout(ROOT, args.sha)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"SELF_AUDIT report saved: {args.output}", flush=True)


if __name__ == "__main__":
    main()
