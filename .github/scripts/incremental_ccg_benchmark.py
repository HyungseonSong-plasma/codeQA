#!/usr/bin/env python3
"""#101: pinned real-codeQA source benchmark; no unsupported speedup promises."""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
from statistics import median
import subprocess
import tempfile
from time import perf_counter
import tracemalloc

from codeqa.adapters.python_persistent_cache import PythonPersistentExtractionCache
from codeqa.adapters.python_snapshot import PythonAnalysisCache
from codeqa.evaluation.incremental import plan_python_invalidation
from codeqa.infrastructure.resources import ResourceRegistry
from codeqa.pipeline.python import analyze_python


ROOT = Path(__file__).resolve().parents[2]


def canonical(doc: dict) -> str:
    result = dict(doc)
    result.pop("efficiency", None)
    result["summary"] = dict(result["summary"])
    result["summary"].pop("efficiency", None)
    return json.dumps(result, sort_keys=True, separators=(",", ":"))


def measured(func):
    tracemalloc.start()
    start = perf_counter()
    try:
        result = func()
        seconds = perf_counter() - start
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    return result, seconds, peak


def percentile(values, pct):
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int((len(ordered) - 1) * pct / 100 + 0.9999)))
    return ordered[index]


def main():
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
    ).strip()
    if len(revision) != 40:
        raise RuntimeError("benchmark source must have a full pinned Git revision")
    registry = ResourceRegistry(ROOT)
    ccg = registry.load_json("ccg_schema")
    mechanical = registry.load_json("mechanical_profile")
    available = sorted(path for path in (ROOT / "src" / "codeqa").rglob("*.py")
                       if path.is_file())
    if len(available) < 20:
        raise RuntimeError("insufficient real codeQA input sources")
    cases = {
        "small": available[:5],
        "medium": available[:25],
        "repository": available,
    }
    summary = []
    for label, paths in cases.items():
        sources = {
            str(path.relative_to(ROOT)).replace(os.sep, "/"): path.read_text()
            for path in paths
        }
        manifest = sha256(json.dumps({
            key: sha256(value.encode()).hexdigest() for key, value in sorted(sources.items())
        }, sort_keys=True).encode()).hexdigest()
        times = {"cold": [], "persistent_warm": []}
        peaks = {"cold": [], "persistent_warm": []}
        reuse = 0
        fallback = 0
        with tempfile.TemporaryDirectory(prefix="codeqa-bench-") as root:
            disk = PythonPersistentExtractionCache(
                Path(root), namespace=f"codeQA:{revision}:{label}",
                max_entries=max(len(sources) + 10, 50),
            )
            for _ in range(3):
                snapshot = f"git:codeQA@{revision}"
                def analyze(cache):
                    return analyze_python(
                        sources, snapshot_id=snapshot, ccg_schema=ccg,
                        mechanical_profile=mechanical, cache=cache,
                    )
                independent, t0, m0 = measured(lambda: analyze(None))
                seeded = PythonAnalysisCache(max_entries=max(50, len(sources) + 10))
                analyze(seeded)
                disk.save(seeded)
                fresh = PythonAnalysisCache(max_entries=max(50, len(sources) + 10))
                reused = disk.hydrate(fresh, sources)
                warm, t1, m1 = measured(lambda: analyze(fresh))
                if canonical(independent.to_document()) != canonical(warm.to_document()):
                    raise AssertionError(f"semantic cache drift for {label}")
                if reused < len(sources):
                    raise AssertionError(f"incomplete intact extraction cache: {label}")
                reuse += warm.efficiency.reused_extractions
                times["cold"].append(t0)
                times["persistent_warm"].append(t1)
                peaks["cold"].append(m0)
                peaks["persistent_warm"].append(m1)
                changed = sorted(sources)[0]
                plan = plan_python_invalidation(warm.dependencies, (changed,))
                fallback += int(plan.mode == "FULL_SNAPSHOT")
        summary.append({
            "label": label, "revision": revision, "source_manifest_sha256": manifest,
            "source_files": len(sources), "iterations": 3,
            "semantic_equality": True,
            "reused_file_local_extractions_total": reuse,
            "full_snapshot_fallbacks": fallback,
            "cold_p50_s": round(median(times["cold"]), 6),
            "cold_p95_s": round(percentile(times["cold"], 95), 6),
            "warm_p50_s": round(median(times["persistent_warm"]), 6),
            "warm_p95_s": round(percentile(times["persistent_warm"], 95), 6),
            "cold_peak_memory_bytes_max": max(peaks["cold"]),
            "warm_peak_memory_bytes_max": max(peaks["persistent_warm"]),
        })
    outfile = Path(os.environ.get("CODEQA_BENCHMARK_OUTPUT",
                                  "incremental-ccg-benchmark.json"))
    outfile.parent.mkdir(parents=True, exist_ok=True)
    outfile.write_text(json.dumps(summary, sort_keys=True, indent=2) + "\n")
    for item in summary:
        print(f"INCREMENTAL_BENCHMARK=PASS label={item['label']} "
              f"files={item['source_files']} "
              f"cold_p95_s={item['cold_p95_s']} warm_p95_s={item['warm_p95_s']} "
              f"semantic_equality={item['semantic_equality']}")
    print(f"INCREMENTAL_FULL_ORACLE=PASS sha={revision} cases={len(summary)}")


if __name__ == "__main__":
    main()
