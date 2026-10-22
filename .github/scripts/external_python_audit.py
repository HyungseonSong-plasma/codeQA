#!/usr/bin/env python3
"""Read-only, pinned-SHA codeQA audit of a different Python repository.

Only parses source; never imports or executes analyzed files, fixtures, MOOSE,
tests or shell scripts. Raw CCG facts are evaluated with the unchanged
Mechanical Profile. The audit is evidence, not a full P1-P8 certification.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
import subprocess

from codeqa.adapters import PythonAnalysisCache
from codeqa.evaluation.impact import analyze_change_impact
from codeqa.infrastructure.git import GitReader
from codeqa.infrastructure.resources import ResourceRegistry
from codeqa.pipeline.python import analyze_python


def _head(root: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True,
        capture_output=True, text=True,
    ).stdout.strip()


def _scope(path: str) -> str:
    if path.startswith("physics_harness/"):
        return "product"
    if path.startswith("tests/"):
        return "tests"
    if path.startswith(("experiments/", "studies/")):
        return "experiments"
    if path.startswith("archive/"):
        return "archive"
    return "support"


def _summarize(name: str, analysis, *, rank_impacts: bool = False) -> dict:
    graph, quality, dep = analysis.graph, analysis.quality, analysis.dependencies
    findings = sorted(
        quality.findings,
        key=lambda f: (-(f.observed - f.threshold), f.node_id, f.rule_id),
    )
    pairs = sorted({(edge.source_path, edge.target_path) for edge in dep.edges})
    incoming = Counter(target for source, target in pairs)
    outgoing = Counter(source for source, target in pairs)
    top_impact = []
    if rank_impacts:
        candidates = (
            path for path in dep.analyzed_paths
            if path.startswith("physics_harness/")
        )
        for path in candidates:
            impact = analyze_change_impact(dep, (path,))
            direct, indirect = len(impact.direct_dependents), len(impact.transitive_dependents)
            if direct or indirect:
                top_impact.append({
                    "changed_path": path,
                    "direct_count": direct,
                    "transitive_count": indirect,
                    "affected_count": direct + indirect,
                    "affected_product_count": sum(
                        item.path.startswith("physics_harness/")
                        for item in impact.affected
                    ),
                    "affected_tests_count": sum(
                        item.path.startswith("tests/")
                        for item in impact.affected
                    ),
                    "witness_examples": [
                        {"path": x.path, "witness": list(x.witness)}
                        for x in impact.affected[:6]
                    ],
                    "confidence": impact.confidence,
                })
        top_impact.sort(key=lambda r: (
            -r["affected_count"], -r["affected_product_count"], r["changed_path"],
        ))

    data = {
        "scope": name,
        "source_files": len(graph.coverage.analyzed_paths) + len(graph.coverage.unprocessed),
        "analyzed_paths_count": len(graph.coverage.analyzed_paths),
        "coverage": graph.coverage.status,
        "unprocessed": [asdict(x) for x in graph.coverage.unprocessed],
        "diagnostics": [asdict(x) for x in graph.diagnostics[:30]],
        "ccg_nodes": len(graph.nodes),
        "ccg_edges": len(graph.edges),
        "node_kinds": dict(sorted(Counter(n.kind for n in graph.nodes).items())),
        "edge_kinds": dict(sorted(Counter(e.kind for e in graph.edges).items())),
        "unresolved_by_kind": dict(sorted(Counter(
            e.kind for e in graph.edges if e.resolution == "unresolved"
        ).items())),
        "quality": {
            "status": quality.status,
            "analysis_status": quality.analysis_status,
            "analysis_limitations": list(quality.analysis_limitations),
            "functions": quality.function_count,
            "unresolved_edges": quality.unresolved_edges,
            "finding_count": len(quality.findings),
            "findings_by_rule": dict(sorted(Counter(f.rule_id for f in findings).items())),
            "top_findings": [asdict(f) for f in findings[:25]],
        },
        "dependencies": {
            "import_sites": len(dep.edges),
            "unique_pairs": len(pairs),
            "unknown_import_observations": len(dep.unknown),
            "unknown_by_reason": dict(sorted(Counter(e.reason for e in dep.unknown).items())),
            "unknown_examples": [asdict(e) for e in dep.unknown[:20]],
            "top_imported": [
                {"path": path, "importing_files": count}
                for path, count in incoming.most_common(20)
            ],
            "top_importers": [
                {"path": path, "imported_files": count}
                for path, count in outgoing.most_common(15)
            ],
            "example_pairs": [
                {"source_path": a, "target_path": b} for a, b in pairs[:30]
            ],
            "confidence": "STATIC_MODULE_PATH_ONLY",
        },
        "impact": {
            "top_product_change_candidates": top_impact[:20],
            "confidence": "STATIC_POTENTIAL_ONLY",
        },
        "efficiency": analysis.efficiency.to_document(),
        "evidence": {
            "facts": len(analysis.evidence.facts),
            "linked_relations": sum(
                r.evidence_id is not None for r in analysis.evidence.relations
            ),
        },
    }
    print(
        f"EXTERNAL_AUDIT {name}: files={data['source_files']} "
        f"parsed={data['analyzed_paths_count']} coverage={data['coverage']} "
        f"functions={quality.function_count} nodes={len(graph.nodes)} "
        f"edges={len(graph.edges)} unresolved={quality.unresolved_edges} "
        f"findings={len(findings)} status={quality.status} "
        f"analysis={quality.analysis_status} "
        f"imports={len(dep.edges)} unique_pairs={len(pairs)} "
        f"unknown_imports={len(dep.unknown)}",
        flush=True,
    )
    for f in findings[:8]:
        print(
            f"  REVIEW {name}: {f.rule_id} node={f.node_id} "
            f"observed={f.observed} threshold={f.threshold}",
            flush=True,
        )
    for item in top_impact[:8]:
        print(
            f"  IMPACT {name}: source={item['changed_path']} "
            f"direct={item['direct_count']} transitive={item['transitive_count']} "
            f"tests={item['affected_tests_count']} confidence={item['confidence']}",
            flush=True,
        )
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-root", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--codeqa-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    target_root = args.target_root.resolve()
    codeqa_root = args.codeqa_root.resolve()
    if len(args.source_sha) != 40 or _head(target_root) != args.source_sha:
        raise ValueError("source revision does not match pinned target checkout")
    target_reader = GitReader(target_root)
    registry = ResourceRegistry(codeqa_root)
    schema = registry.load_json("ccg_schema")
    profile = registry.load_json("mechanical_profile")

    tracked = sorted(path for path in target_reader.tracked_paths() if path.endswith(".py"))
    inputs: dict[str, str] = {}
    decoding_errors: list[str] = []
    for path in tracked:
        content = target_reader.read_file(args.source_sha, path)
        try:
            inputs[path] = content.decode("utf-8")
        except UnicodeDecodeError:
            decoding_errors.append(path)

    scoped_inputs = {
        name: {path: text for path, text in inputs.items() if _scope(path) == name}
        for name in ("product", "tests", "experiments", "archive", "support")
    }
    scoped_inputs["all_python"] = inputs
    cache = PythonAnalysisCache(max_entries=1024)
    results = {}
    for name, sources in scoped_inputs.items():
        print(f"RUN_SCOPE {name}: selected_python={len(sources)}", flush=True)
        analysis = analyze_python(
            sources,
            snapshot_id=f"git:{args.source_sha}",
            ccg_schema=schema,
            mechanical_profile=profile,
            cache=cache,
        )
        results[name] = _summarize(
            name, analysis, rank_impacts=name in ("product", "all_python"),
        )
    report = {
        "target": "HyungseonSong-plasma/moose-test-repo",
        "source_sha": args.source_sha,
        "analyzer_repo": "HyungseonSong-plasma/codeQA",
        "analyzer_sha": _head(codeqa_root),
        "profile": profile,
        "tracked_python_files": len(tracked),
        "readable_python_files": len(inputs),
        "decode_failed_paths": decoding_errors,
        "scope_definition": {
            "product": "physics_harness/",
            "tests": "tests/",
            "experiments": "experiments/ and studies/",
            "archive": "archive/",
            "support": "everything else (CI, bin/, scripts/, etc.)",
            "all_python": "all readable tracked .py files",
        },
        "limitations": [
            "Python AST v0.1 and Mechanical QA only; not complete P1-P8 review.",
            "Review findings are heuristics, not verified defects.",
            "Static import-path links are not runtime symbol bindings.",
            "Impact paths are STATIC_POTENTIAL_ONLY, not safe test-exclusion evidence.",
            "Archive and experiments do not imply active product execution.",
            "No analyzed target source, test, MOOSE runtime or fixture was executed.",
        ],
        "scopes": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"EXTERNAL_AUDIT_FINISHED target={report['target']} "
        f"source_sha={report['source_sha']} "
        f"analyzer_sha={report['analyzer_sha']} "
        f"total_python={len(tracked)} "
        f"decode_failed={len(decoding_errors)} "
        f"report={args.output}",
        flush=True,
    )


if __name__ == "__main__":
    main()
