"""Positive/adversarial cold-interpreter import-line evidence tests."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from codeqa.evaluation.architecture.import_initialization import (
    ImportInitializationError, capture_cold_import_line_entries,
)


def seal(obj, key):
    obj[key] = sha256(json.dumps({k: v for k, v in obj.items() if k != key},
                                 sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class ColdImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.src = "src/demo/pipeline.py"
        self.dst = "src/demo/target.py"
        for path, raw in ((self.src, b"from demo import target\nVALUE = target.VALUE\n"),
                          (self.dst, b"VALUE = 7\n")):
            dest = self.root / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(raw)
        self.hashes = {p: sha256((self.root / p).read_bytes()).hexdigest()
                       for p in (self.src, self.dst)}
        self.resp = {"schema_version": "0.1", "source_identity": {"snapshot_sha": "a" * 40},
                     "observed_cross_role_pairs": 1, "decision": "NOT_EVALUATED",
                     "edges": [{"source_path": self.src, "target_path": self.dst,
                                "import_witnesses": [{"source_path": self.src,
                                                     "target_path": self.dst,
                                                     "source_sha256": self.hashes[self.src],
                                                     "line": 1}]}]}
        seal(self.resp, "responsibility_id")
        self.sel = {"schema_version": "0.1", "source_identity": {
            "snapshot_sha": "a" * 40, "responsibility_id": self.resp["responsibility_id"]},
            "pairs": [[self.src, self.dst]], "observed_cross_role_pairs": 1,
            "source_sha256": self.hashes, "decision": "NOT_EVALUATED"}
        seal(self.sel, "selection_id")

    def probe(self):
        return capture_cold_import_line_entries(self.sel, self.resp, repository_root=self.root)

    def test_cold_import_observes_top_level_import(self):
        report = self.probe()
        self.assertEqual(report["static_pairs"], 1)
        self.assertEqual(report["pairs_with_line_entries"], 1)
        self.assertEqual(report["records"][0]["line_entries"], 1)
        self.assertEqual(report["module_statuses"]["demo.pipeline"], "IMPORTED")
        self.assertEqual(report["decision"], "NOT_EVALUATED")
        self.assertEqual(report["import_target_resolution"], "NOT_EVALUATED")

    def test_import_error_does_not_claim_target_resolution(self):
        (self.root / self.dst).write_text("raise RuntimeError('controlled')\n")
        self.hashes[self.dst] = sha256((self.root / self.dst).read_bytes()).hexdigest()
        self.sel["source_sha256"] = self.hashes
        seal(self.sel, "selection_id")
        report = self.probe()
        self.assertEqual(report["records"][0]["line_entries"], 1)
        self.assertEqual(report["module_statuses"]["demo.pipeline"], "IMPORT_ERROR:RuntimeError")
        self.assertEqual(report["import_target_resolution"], "NOT_EVALUATED")

    def test_reject_stale_source_hash(self):
        (self.root / self.src).write_text("from demo import target\nprint('changed')\n")
        with self.assertRaises(ImportInitializationError):
            self.probe()

    def test_reject_forged_witness_line_even_if_resealed(self):
        self.resp["edges"][0]["import_witnesses"][0]["line"] = 2
        seal(self.resp, "responsibility_id")
        self.sel["source_identity"]["responsibility_id"] = self.resp["responsibility_id"]
        seal(self.sel, "selection_id")
        with self.assertRaises(ImportInitializationError):
            self.probe()

    def test_reject_unsafe_path(self):
        self.sel["pairs"][0][0] = "src/../demo/pipeline.py"
        seal(self.sel, "selection_id")
        with self.assertRaises(ImportInitializationError):
            self.probe()

    def test_reject_symlinked_source(self):
        original = self.root / self.src
        elsewhere = self.root / "copy.py"
        elsewhere.write_bytes(original.read_bytes())
        original.unlink()
        original.symlink_to(elsewhere)
        with self.assertRaises(ImportInitializationError):
            self.probe()

    def test_reject_invalid_limit(self):
        with self.assertRaises(ImportInitializationError):
            capture_cold_import_line_entries(self.sel, self.resp,
                repository_root=self.root, max_line_visits=0)

    def test_empty_pair_control(self):
        resp = {"schema_version": "0.1", "source_identity": {"snapshot_sha": "a" * 40},
                "observed_cross_role_pairs": 0, "decision": "NOT_EVALUATED", "edges": []}
        seal(resp, "responsibility_id")
        sel = {"schema_version": "0.1", "source_identity": {
            "snapshot_sha": "a" * 40, "responsibility_id": resp["responsibility_id"]},
            "pairs": [], "observed_cross_role_pairs": 0,
            "source_sha256": {}, "decision": "NOT_EVALUATED"}
        seal(sel, "selection_id")
        report = capture_cold_import_line_entries(sel, resp, repository_root=self.root)
        self.assertEqual(report["records"], [])
        self.assertEqual(report["static_pairs"], 0)


if __name__ == "__main__":
    unittest.main()
