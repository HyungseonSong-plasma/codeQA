#!/usr/bin/env python3
"""Read-only exact-checkout codeQA directory-role evidence report."""
from __future__ import annotations

import json
from pathlib import Path

from codeqa.adapters.python_snapshot import parse_python_snapshot
from codeqa.adapters.python_dependencies import extract_parsed_dependencies
from codeqa.evaluation.semantic_layout import evaluate_semantic_layout
from codeqa.infrastructure.git import GitReader


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    reader = GitReader(root)
    paths = reader.tracked_paths()
    policy_path = root / "profiles/semantic-directory-roles-v0.1.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    sources = {
        path: reader.read_file("HEAD", path).decode("utf-8")
        for path in paths if path.startswith("src/codeqa/") and path.endswith(".py")
    }
    parsed = parse_python_snapshot(sources)
    deps = extract_parsed_dependencies(parsed, snapshot_id="HEAD")
    report = evaluate_semantic_layout(
        paths, [(e.source_path, e.target_path) for e in deps.edges], policy,
    )
    document = {
        "policy_id": report.policy_id,
        "status": report.status,
        "analyzed_python_files": len(parsed.analyzed_paths),
        "unprocessed": list(parsed.unprocessed),
        "observed_import_sites": len(deps.edges),
        "unknown_imports": len(deps.unknown),
        "scope": policy["scope"],
        "limitations": [
            "Syntax-evidenced direct module paths only, not runtime behavior.",
            "Role-name/implementation semantics are NOT_EVALUATED.",
            "Declared transitional exceptions are REVIEW_REQUIRED, not PASS.",
        ],
    }
    from dataclasses import asdict
    document["findings"] = [asdict(f) for f in report.findings]
    (root / "semantic-layout-audit.json").write_text(
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"SEMANTIC_LAYOUT status={report.status} "
        f"findings={len(report.findings)} parsed={len(parsed.analyzed_paths)} "
        f"imports={len(deps.edges)} unknown_imports={len(deps.unknown)}",
        flush=True,
    )
    for finding in report.findings:
        print(
            f"  {finding.status} {finding.code}: "
            f"{finding.source} -> {finding.target}: {finding.reason}", flush=True,
        )
    return 1 if report.status == "VIOLATION" or parsed.unprocessed else 0


if __name__ == "__main__":
    raise SystemExit(main())
