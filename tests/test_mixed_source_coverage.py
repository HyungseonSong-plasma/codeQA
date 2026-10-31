"""#41: strict caller source inventory, immutable provenance and mixed coverage."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha1
import json
from pathlib import Path
import unittest

from codeqa.adapters import adapt_python_sources
from codeqa.core import parse_graph
from codeqa.infrastructure.resources import ResourceRegistry
from codeqa.pipeline.source_coverage import (
    SourceSelectionError, aggregate_source_coverage, validate_source_selection,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures/mixed"


def blob_sha(data: bytes) -> str:
    return sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


class MixedLanguageCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        registry = ResourceRegistry(ROOT)
        cls.selection_schema = registry.load_json("source_selection_schema")
        cls.capability_schema = registry.load_json("adapter_capability_schema")
        cls.ccg_schema = registry.load_json("ccg_schema")
        cls.python_capability = registry.load_json("python_adapter_capability")
        cls.manifest = json.loads(
            (FIXTURE / "moose-selection-v0.1.json").read_text(encoding="utf-8")
        )
        sources = {
            "ci/guards/physics_dependency_guard.py":
                ("python/physics_dependency_guard.py.txt",
                 "dc36f7c8a43a5563e86021289f95e6b1de3147d8"),
            "physics_app/src/base/PhysicsApp.C":
                ("cpp/PhysicsApp.C.txt", "412a4d0b2faf8c228732f5ff64e26f6909340ac3"),
        }
        cls.raw = {}
        for path, (fixture, expected) in sources.items():
            data = (FIXTURE / fixture).read_bytes()
            if blob_sha(data) != expected:
                raise AssertionError("pinned MOOSE source byte provenance mismatch")
            cls.raw[path] = data.decode("utf-8")
        cls.graph = adapt_python_sources(
            {path: cls.raw[path] for path in cls.raw if path.endswith(".py")},
            snapshot_id="git:HyungseonSong-plasma/moose-test-repo@1977ad5559e5aa7a1c8d04c83735c15e007130d5",
            schema=cls.ccg_schema,
        )

    def evaluate(self, manifest=None, graphs=None, capabilities=None):
        return aggregate_source_coverage(
            self.manifest if manifest is None else manifest,
            selection_schema=self.selection_schema,
            capability_schema=self.capability_schema,
            capabilities={"python": self.python_capability}
            if capabilities is None else capabilities,
            graphs={"python": self.graph} if graphs is None else graphs,
        )

    def test_real_pinned_python_and_cpp_mixed_inventory_never_full_pass(self):
        report = self.evaluate()
        items = {entry.path: entry for entry in report.files}
        self.assertEqual(report.snapshot_id, self.graph.snapshot.id)
        self.assertEqual(items["ci/guards/physics_dependency_guard.py"].status, "analyzed")
        self.assertEqual(items["physics_app/src/base/PhysicsApp.C"].status, "unsupported")
        self.assertEqual(items["README.md"].status, "excluded")
        self.assertEqual(report.selected_status, "partial")
        self.assertEqual(report.inventory_confidence, "not_attested")
        self.assertEqual(report.analyzed_languages, ("python",))
        self.assertEqual(report.unsupported_languages, ("cpp",))
        self.assertIn("NOT_A_REPOSITORY_QUALITY_VERDICT", report.assurance)

    def test_caller_attested_inventory_is_not_false_claim_of_parser_support(self):
        manifest = deepcopy(self.manifest)
        manifest["discovery"]["inventory_complete"] = True
        report = self.evaluate(manifest=manifest)
        self.assertEqual(report.inventory_confidence, "caller_attested")
        self.assertEqual(report.selected_status, "partial")
        self.assertEqual({x.language: x.status for x in report.files if x.status != "excluded"},
                         {"python": "analyzed", "cpp": "unsupported"})

    def test_graph_requires_correct_repo_snapshot_and_path_selection(self):
        for mutation in ("sha", "repo", "exclude_python", "language", "extension"):
            with self.subTest(mutation=mutation):
                manifest = deepcopy(self.manifest)
                if mutation == "sha":
                    manifest["snapshot"]["commit_sha"] = "0" * 40
                elif mutation == "repo":
                    manifest["snapshot"]["repository"] = "other/repo"
                elif mutation == "exclude_python":
                    manifest["files"][0]["selection"] = "excluded"
                    manifest["files"][0]["exclusion_reason"] = "excluded"
                elif mutation == "language":
                    manifest["files"][0]["language"] = "rust"
                else:
                    manifest["files"][0]["path"] += ".txt"
                with self.assertRaises(SourceSelectionError):
                    self.evaluate(manifest=manifest)

    def test_duplicate_traversal_and_missing_exclusion_reason_fail_closed(self):
        for mutation in ("duplicate", "unsafe", "no_exclusion", "included_exclusion"):
            with self.subTest(mutation=mutation):
                manifest = deepcopy(self.manifest)
                if mutation == "duplicate":
                    manifest["files"].append(deepcopy(manifest["files"][0]))
                elif mutation == "unsafe":
                    manifest["files"][0]["path"] = "../escape.py"
                elif mutation == "no_exclusion":
                    del manifest["files"][2]["exclusion_reason"]
                else:
                    manifest["files"][0]["exclusion_reason"] = "contradicts inclusion"
                with self.assertRaises(SourceSelectionError):
                    validate_source_selection(manifest, self.selection_schema)

    def test_unsupported_missing_and_not_run_are_not_analyzed(self):
        report = self.evaluate(graphs={})
        statuses = {x.path: x.status for x in report.files}
        self.assertEqual(statuses["ci/guards/physics_dependency_guard.py"], "unprocessed")
        self.assertEqual(statuses["physics_app/src/base/PhysicsApp.C"], "unsupported")
        self.assertEqual(report.selected_status, "none")
        self.assertEqual(report.analyzed_languages, ())

    def test_all_excluded_selection_has_no_complete_coverage(self):
        manifest = deepcopy(self.manifest)
        for entry in manifest["files"]:
            entry["selection"] = "excluded"
            entry["exclusion_reason"] = "caller_excluded"
        # A caller's complete-inventory attestation cannot certify any analysis.
        manifest["discovery"]["inventory_complete"] = True
        report = self.evaluate(manifest=manifest, graphs={}, capabilities={})
        self.assertEqual(report.selected_status, "none")
        self.assertEqual(report.inventory_confidence, "caller_attested")
        self.assertEqual(report.analyzed_languages, ())
        self.assertEqual(report.unsupported_languages, ())
        self.assertTrue(all(item.status == "excluded" for item in report.files))
        self.assertIn("NOT_A_REPOSITORY_QUALITY_VERDICT", report.assurance)

    def test_excluding_unsupported_files_preserves_complete_selected_coverage(self):
        # The zero-denominator guard must not demote a genuinely analyzed
        # nonempty selection simply because other inventory files are excluded.
        manifest = deepcopy(self.manifest)
        for entry in manifest["files"]:
            if entry["language"] != "python":
                entry["selection"] = "excluded"
                entry["exclusion_reason"] = "caller_excluded"
        report = self.evaluate(manifest=manifest)
        self.assertEqual(report.selected_status, "complete")
        self.assertEqual(report.analyzed_languages, ("python",))
        self.assertEqual(report.unsupported_languages, ())
        self.assertEqual(
            [item.path for item in report.files if item.status == "analyzed"],
            ["ci/guards/physics_dependency_guard.py"],
        )
        self.assertTrue(all(
            item.status == "excluded" for item in report.files
            if item.language != "python"
        ))
        self.assertIn("NOT_A_REPOSITORY_QUALITY_VERDICT", report.assurance)

    def test_missing_python_capability_and_manual_rust_golden_cannot_pass(self):
        with self.assertRaises(SourceSelectionError):
            self.evaluate(capabilities={}, graphs={"python": self.graph})
        rust = json.loads(
            (ROOT / "fixtures/rust/sol-adapter-moose/ccg-v0.1.golden.json")
            .read_text(encoding="utf-8")
        )
        golden = parse_graph(rust, self.ccg_schema)
        rust_manifest = {
            "schema_version": "0.1",
            "snapshot": {
                "repository": "HyungseonSong-plasma/sol-adapter-moose",
                "commit_sha": "ce40af4ffda17feaef99f4de328c9a37b6019553",
            },
            "discovery": {
                "method": "caller_explicit_path_inventory", "inventory_complete": False,
            },
            "files": [
                {"path": name, "language": "rust",
                 "selection": "included", "category": "product"}
                for name in sorted(rust["coverage"]["analyzed_paths"])
            ],
        }
        report = self.evaluate(manifest=rust_manifest, capabilities={}, graphs={})
        self.assertEqual(report.selected_status, "none")
        self.assertEqual(report.unsupported_languages, ("rust",))
        self.assertTrue(all(x.status == "unsupported" for x in report.files))
        with self.assertRaises(SourceSelectionError):
            self.evaluate(manifest=rust_manifest, capabilities={}, graphs={"rust": golden})

    def test_covered_scope_not_auto_extended_to_unselected_files(self):
        manifest = deepcopy(self.manifest)
        manifest["files"].pop(0)
        with self.assertRaises(SourceSelectionError):
            self.evaluate(manifest=manifest)

    def test_schema_rejects_unknown_selection_and_conflicting_status(self):
        for mutation in ("unknown_status", "bad_commit", "missing_language"):
            manifest = deepcopy(self.manifest)
            if mutation == "unknown_status":
                manifest["files"][0]["selection"] = "analyzed"
            elif mutation == "bad_commit":
                manifest["snapshot"]["commit_sha"] = "unknown"
            else:
                manifest["files"][0].pop("language")
            with self.subTest(mutation=mutation), self.assertRaises(SourceSelectionError):
                self.evaluate(manifest=manifest)

    def test_stable_report_independent_of_caller_file_listing_order(self):
        first = self.evaluate().to_document()
        manifest = deepcopy(self.manifest)
        manifest["files"].reverse()
        self.assertEqual(first, self.evaluate(manifest=manifest).to_document())


if __name__ == "__main__":
    unittest.main()
