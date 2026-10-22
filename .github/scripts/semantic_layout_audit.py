#!/usr/bin/env python3
"""Read-only exact-checkout codeQA directory-role evidence report."""
from __future__ import annotations

import json
import subprocess
from dataclasses import asdict
from pathlib import Path

from codeqa.adapters.python_snapshot import parse_python_snapshot
from codeqa.adapters.python_dependencies import extract_parsed_dependencies
from codeqa.evaluation.semantic_layout import evaluate_semantic_layout
from codeqa.infrastructure.git import GitReader
from codeqa.infrastructure.resources import ResourceRegistry
from codeqa.pipeline.python import analyze_python


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    reader = GitReader(root)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    paths = reader.tracked_paths()
    policy_path = root / "profiles/semantic-directory-roles-v0.1.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    sources = {
        path: reader.read_file(head, path).decode("utf-8")
        for path in paths if path.startswith("src/codeqa/") and path.endswith(".py")
    }
    registry = ResourceRegistry(root)
    analysis = analyze_python(
        sources, snapshot_id=head,
        ccg_schema=registry.load_json("ccg_schema"),
        mechanical_profile=registry.load_json("mechanical_profile"),
        semantic_policy=policy,
    )
    deps = analysis.dependencies
    parsed_unprocessed = analysis.graph.coverage.unprocessed
    assert analysis.semantic_architecture is not None
    ontology = analysis.semantic_architecture
    report = evaluate_semantic_layout(
        paths, [(e.source_path, e.target_path) for e in deps.edges], policy,
    )
    document = {
        "policy_id": report.policy_id,
        "status": report.status,
        "analyzed_python_files": len(analysis.graph.coverage.analyzed_paths),
        "unprocessed": [asdict(entry) for entry in parsed_unprocessed],
        "observed_import_sites": len(deps.edges),
        "unknown_imports": len(deps.unknown),
        "scope": policy["scope"],
        "semantic_architecture_summary": ontology.summary_document(),
        "semantic_architecture": ontology.to_document(),
        "limitations": [
            "Syntax-evidenced direct module paths only, not runtime behavior.",
            "Role-name/implementation semantics are NOT_EVALUATED.",
            "Declared transitional exceptions are REVIEW_REQUIRED, not PASS.",
        ],
    }
    document["findings"] = [asdict(f) for f in report.findings]
    (root / "semantic-layout-audit.json").write_text(
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"SEMANTIC_LAYOUT status={report.status} "
        f"findings={len(report.findings)} parsed={len(analysis.graph.coverage.analyzed_paths)} "
        f"imports={len(deps.edges)} unknown_imports={len(deps.unknown)}",
        flush=True,
    )
    for finding in report.findings:
        print(
            f"  {finding.status} {finding.code}: "
            f"{finding.source} -> {finding.target}: {finding.reason}", flush=True,
        )
    print(
        f"SEMANTIC_ONTOLOGY version={ontology.schema_version} "
        f"entities={len(ontology.entities)} relations={len(ontology.relations)} "
        f"assessments={len(ontology.assessments)} "
        f"violations={sum(a.status == 'VIOLATION' for a in ontology.assessments)} "
        f"status={ontology.status}",
        flush=True,
    )
    return 1 if (
        report.status == "VIOLATION" or
        ontology.status == "VIOLATION" or parsed_unprocessed
    ) else 0


if __name__ == "__main__":
    raise SystemExit(main())
