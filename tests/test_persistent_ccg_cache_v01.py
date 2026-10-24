"""#101: persistent local-extraction cache integrity and full-analysis oracle."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from random import Random
import tempfile
import unittest

from codeqa.adapters.python_snapshot import PythonAnalysisCache
from codeqa.adapters.python_persistent_cache import (
    PersistentCacheError, PythonPersistentExtractionCache,
)
from codeqa.evaluation.incremental import plan_python_invalidation
from codeqa.infrastructure.resources import ResourceRegistry
from codeqa.pipeline.python import analyze_python

ROOT = Path(__file__).resolve().parents[1]


def semantics(value):
    doc = deepcopy(value.to_document())
    doc.pop("efficiency", None)
    doc["summary"].pop("efficiency", None)
    return doc


class PersistentCacheAndInvalidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        registry = ResourceRegistry(ROOT)
        cls.ccg = registry.load_json("ccg_schema")
        cls.profile = registry.load_json("mechanical_profile")

    def source(self):
        return {
            "pkg/helper.py": "def helper():\n    return 42\n",
            "pkg/consumer.py": "from pkg.helper import helper\n\ndef consumer():\n    return helper()\n",
        }

    def analyze(self, sources, cache=None, snapshot="sha-static"):
        return analyze_python(
            sources, snapshot_id=snapshot, ccg_schema=self.ccg,
            mechanical_profile=self.profile, cache=cache,
            changed_paths=("pkg/helper.py",),
        )

    def test_persistent_warm_matches_full_semantics_and_reuses_extractions(self):
        sources = self.source()
        with tempfile.TemporaryDirectory() as folder:
            disk = PythonPersistentExtractionCache(
                Path(folder), namespace="example/repo/main",
            )
            cache = PythonAnalysisCache()
            self.assertEqual(disk.hydrate(cache, sources), 0)
            cold = self.analyze(sources, cache=cache)
            self.assertEqual(cold.efficiency.extracted_files, 2)
            self.assertEqual(disk.save(cache), 2)

            another_process = PythonAnalysisCache()
            self.assertEqual(disk.hydrate(another_process, sources), 2)
            warm = self.analyze(sources, cache=another_process)
            independent = self.analyze(sources)
            self.assertEqual(warm.efficiency.reused_extractions, 2)
            self.assertEqual(warm.efficiency.parsed_files, 2)
            self.assertEqual(semantics(warm), semantics(independent))
            self.assertEqual(semantics(cold), semantics(independent))

    def test_cross_file_change_rebuilds_full_snapshot_semantics(self):
        old = self.source()
        changed = dict(old)
        changed["pkg/helper.py"] = "def helper(value):\n    return value * 2\n"
        with tempfile.TemporaryDirectory() as folder:
            disk = PythonPersistentExtractionCache(Path(folder), namespace="ns-a")
            seeded = PythonAnalysisCache()
            self.analyze(old, cache=seeded)
            disk.save(seeded)
            warmed = PythonAnalysisCache()
            self.assertEqual(disk.hydrate(warmed, changed), 1)
            result = self.analyze(changed, cache=warmed)
            self.assertEqual(result.efficiency.reused_extractions, 1)
            self.assertEqual(semantics(result), semantics(self.analyze(changed)))
            plan = plan_python_invalidation(result.dependencies, ("pkg/helper.py",))
            self.assertIn("STATIC_GRAPH_NOT_RUNTIME_DEPENDENCY_UPPER_BOUND", plan.reasons)
            self.assertIn(plan.guarantees, "SNAPSHOT_WIDE_SEMANTICS_RECOMPUTED")

    def test_missing_or_corrupted_blob_falls_back_to_fresh_extraction(self):
        source = self.source()
        with tempfile.TemporaryDirectory() as folder:
            disk = PythonPersistentExtractionCache(Path(folder), namespace="ns")
            first = PythonAnalysisCache()
            self.analyze(source, cache=first)
            disk.save(first)
            files = sorted(Path(folder).glob("*.json"))
            self.assertEqual(len(files), 2)
            files[0].write_text('{"sha256":"forged","payload":{}}')
            warm = PythonAnalysisCache()
            self.assertEqual(disk.hydrate(warm, source), 1)
            result = self.analyze(source, cache=warm)
            self.assertEqual(result.efficiency.extracted_files, 1)
            self.assertEqual(semantics(result), semantics(self.analyze(source)))

    def test_namespace_and_producer_fingerprint_isolate_old_artifacts(self):
        source = self.source()
        with tempfile.TemporaryDirectory() as folder:
            one = PythonPersistentExtractionCache(Path(folder), namespace="repo/main")
            cache = PythonAnalysisCache()
            self.analyze(source, cache=cache)
            one.save(cache)
            other = PythonPersistentExtractionCache(Path(folder), namespace="repo/topic")
            self.assertEqual(other.hydrate(PythonAnalysisCache(), source), 0)
            stale = PythonPersistentExtractionCache(Path(folder), namespace="repo/main")
            stale.producer = "f" * 64
            self.assertEqual(stale.hydrate(PythonAnalysisCache(), source), 0)

    def test_evicts_old_records_and_cannot_load_symlinked_blob(self):
        source = self.source()
        with tempfile.TemporaryDirectory() as folder:
            disk = PythonPersistentExtractionCache(
                Path(folder), namespace="repo", max_entries=1,
            )
            cache = PythonAnalysisCache()
            self.analyze(source, cache=cache)
            self.assertEqual(disk.save(cache), 2)
            self.assertEqual(len(list(Path(folder).glob("*.json"))), 1)
            cached_file = next(Path(folder).glob("*.json"))
            cached_file.unlink()
            with tempfile.NamedTemporaryFile(mode="w", delete=False) as external:
                external.write("{}")
                external_file = external.name
            try:
                cached_file.symlink_to(external_file)
                self.assertEqual(disk.hydrate(PythonAnalysisCache(), source), 0)
            finally:
                cached_file.unlink(missing_ok=True)
                Path(external_file).unlink(missing_ok=True)

    def test_rejects_invalid_cache_identities(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in ("", "\x00", " "):
                with self.subTest(name=repr(name)):
                    with self.assertRaises(PersistentCacheError):
                        PythonPersistentExtractionCache(Path(folder), namespace=name)
            disk = PythonPersistentExtractionCache(Path(folder), namespace="valid")
            with self.assertRaises(PersistentCacheError):
                disk._file("../escape.py", "a" * 64)
            with self.assertRaises(PersistentCacheError):
                disk._file("ok.py", "bogus")

    def test_dynamic_or_untracked_dependencies_force_full_fallback(self):
        sources = self.source()
        sources["pkg/dynamic.py"] = (
            "import importlib\n"
            "name = 'pkg.helper'\n"
            "result = importlib.import_module(name)\n"
        )
        result = self.analyze(sources)
        plan = plan_python_invalidation(result.dependencies, ("pkg/helper.py",))
        self.assertEqual(plan.mode, "FULL_SNAPSHOT")
        self.assertIn("UNRESOLVED_DEPENDENCY_BOUNDARY", plan.reasons)
        drift = plan_python_invalidation(
            result.dependencies, ("pkg/helper.py",),
            policy_changed=True, compile_context_changed=True,
        )
        self.assertEqual(drift.mode, "FULL_SNAPSHOT")
        self.assertIn("POLICY_DRIFT", drift.reasons)
        self.assertIn("COMPILER_MACRO_TEMPLATE_CONTEXT_UNATTESTED", drift.reasons)
        untracked = plan_python_invalidation(
            result.dependencies, ("pkg/removed.py",),
        )
        self.assertIn("UNTRACKED_CHANGED_SOURCE", untracked.reasons)

    def test_randomized_differential_full_vs_warm_across_mutations(self):
        rand = Random(101)
        sources = self.source()
        with tempfile.TemporaryDirectory() as folder:
            disk = PythonPersistentExtractionCache(Path(folder), namespace="differential")
            for iteration in range(18):
                latest = dict(sources)
                mode = rand.randrange(5)
                if mode == 0:
                    latest["pkg/helper.py"] = f"def helper():\n    return {iteration}\n"
                elif mode == 1:
                    latest["pkg/consumer.py"] = (
                        f"from pkg.helper import helper\n\nx = helper({iteration})\n"
                    )
                elif mode == 2:
                    latest["pkg/new.py"] = "from pkg.helper import helper\n"
                elif mode == 3:
                    latest["pkg/dynamic.py"] = (
                        "import importlib\nx = importlib.import_module('pkg.helper')\n"
                    )
                else:
                    latest["pkg/helper.py"] = "def broken(:\n"
                cache = PythonAnalysisCache()
                disk.hydrate(cache, latest)
                warm = self.analyze(latest, cache=cache, snapshot=f"seed-{iteration}")
                cold = self.analyze(latest, snapshot=f"seed-{iteration}")
                self.assertEqual(semantics(warm), semantics(cold))
                disk.save(cache)
                sources = latest


if __name__ == "__main__":
    unittest.main()
