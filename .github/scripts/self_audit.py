#!/usr/bin/env python3
"""Inspect a pinned codeQA Git checkout using the actual codeQA pipeline."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import json
import re
from pathlib import Path
import subprocess

from codeqa.infrastructure.git import GitReader
from codeqa.infrastructure.resources import ResourceRegistry
from codeqa.pipeline.python import analyze_python


ROOT = Path(__file__).resolve().parents[2]


def _paths_at_revision(root: Path, source_sha: str) -> list[str]:
    """List Python blobs from a frozen source tree, not the analyzer checkout."""
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise ValueError("source revision must be a full lowercase commit SHA")
    result = subprocess.run(
        ["git", "ls-tree", "-r", "-z", "--name-only", source_sha],
        cwd=root, check=True, capture_output=True,
    )
    return sorted(
        item.decode("utf-8")
        for item in result.stdout.split(b"\x00")
        if item and item.endswith(b".py")
    )


def analyze_checkout(root: Path, sha: str, source_sha: str | None = None) -> dict:
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
    source_sha = source_sha or sha
    paths = _paths_at_revision(root, source_sha)
    sources = {path: reader.read_file(source_sha, path).decode("utf-8") for path in paths}
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
            "resolved_by_kind": dict(sorted(Counter(
                e.kind for e in graph.edges if e.resolution == "resolved"
            ).items())),
            "unresolved_by_kind": dict(sorted(Counter(
                e.kind for e in graph.edges if e.resolution == "unresolved"
            ).items())),
            "resolved_local_calls": sum(
                e.kind == "calls"
                and e.resolution == "resolved"
                and e.provenance.method == "lexical_module_binding"
                for e in graph.edges
            ),
            "coverage": graph.coverage.status,
            "diagnostics": [asdict(d) for d in graph.diagnostics],
            "quality": report.to_document(),
        }
        print(
            f"SELF_AUDIT {name}: files={len(inputs)} nodes={len(graph.nodes)} "
            f"edges={len(graph.edges)} functions={report.function_count} "
            f"unresolved={report.unresolved_edges} "
            f"findings={len(report.findings)} coverage={graph.coverage.status} "
            f"status={report.status} analysis={report.analysis_status} "
            f"limitations={','.join(report.analysis_limitations) or 'none'}",
            flush=True,
        )
        print(
            f"  RESOLUTION {name}: lexical_calls={results[name]['resolved_local_calls']} "
            f"resolved_by_kind={results[name]['resolved_by_kind']} "
            f"unresolved_by_kind={results[name]['unresolved_by_kind']}",
            flush=True,
        )
        for finding in report.findings:
            print(
                f"  REVIEW {finding.rule_id} {finding.node_id} "
                f"observed={finding.observed} threshold={finding.threshold}",
                flush=True,
            )

    return {
        "snapshot_sha": source_sha,
        "analyzer_sha": sha,
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
    parser.add_argument("--source-sha", help="Optional pinned input tree; defaults to --sha")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = analyze_checkout(ROOT, args.sha, source_sha=args.source_sha)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"SELF_AUDIT report saved: {args.output}", flush=True)


if __name__ == "__main__":
    main()
