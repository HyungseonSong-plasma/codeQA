"""#30: immutable real Rust source -> manually curated CCG v0.1 reference.

No Rust parser is used or claimed. All evidence is checked against exact
byte-identical pinned source files; both Rust and Python use the same Core.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha1
import json
from pathlib import Path
import unittest

from codeqa.adapters import adapt_python_sources
from codeqa.core import Graph, GraphValidationError, canonical_json, parse_graph
from codeqa.infrastructure.resources import ResourceRegistry


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures/rust/sol-adapter-moose"


def git_blob_id(data: bytes) -> str:
    return sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


class PinnedRustCcgConformance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = ResourceRegistry(ROOT).load_json("ccg_schema")
        cls.provenance = json.loads((FIXTURE / "provenance.json").read_text(encoding="utf-8"))
        cls.document = json.loads((FIXTURE / "ccg-v0.1.golden.json").read_text(encoding="utf-8"))
        cls.sources = {}
        for spec in cls.provenance["files"]:
            data = (ROOT / spec["fixture"]).read_bytes()
            if git_blob_id(data) != spec["git_blob_sha"]:
                raise AssertionError(f"pinned Rust source Git blob drift: {spec['path']}")
            cls.sources[spec["path"]] = data.decode("utf-8").splitlines()

    def parse(self, document=None) -> Graph:
        return parse_graph(self.document if document is None else document, self.schema)

    def assert_issue(self, doc: dict, code: str) -> None:
        with self.assertRaises(GraphValidationError) as context:
            self.parse(doc)
        self.assertIn(code, {issue.code for issue in context.exception.issues})

    def test_exact_source_commit_identity_and_no_auto_parser_claim(self):
        manifest = self.provenance
        self.assertEqual(manifest["source_repository"], "HyungseonSong-plasma/sol-adapter-moose")
        sha = "ce40af4ffda17feaef99f4de328c9a37b6019553"
        self.assertEqual(manifest["commit_sha"], sha)
        self.assertEqual(manifest["snapshot_id"],
                         f"git:HyungseonSong-plasma/sol-adapter-moose@{sha}")
        self.assertEqual(self.document["snapshot"]["id"], manifest["snapshot_id"])
        self.assertEqual(len(self.sources), 3)
        self.assertIn("manually_curated", manifest["provenance"])
        self.assertEqual({p for p in self.sources}, set(self.document["coverage"]["analyzed_paths"]))
        self.assertTrue(all(item["fixture"].endswith(".rs.txt")
                            for item in manifest["files"]))

    def test_grounded_rust_module_types_and_function_declarations(self):
        graph = self.parse()
        self.assertIsInstance(graph, Graph)
        self.assertEqual(graph.coverage.status, "complete")
        by_id = {node.id: node for node in graph.nodes}
        expected_ids = {"rust:file:" + name for name in self.sources}
        for path in self.sources:
            file_node = by_id["rust:file:" + path]
            self.assertEqual(file_node.kind, "file")
            self.assertEqual(file_node.name, path)
        for item in self.provenance["declarations"]:
            with self.subTest(node=item["id"]):
                self.assertEqual(
                    self.sources[item["path"]][item["line"] - 1].strip().startswith(item["anchor"]),
                    True, "declaration anchor not present in pinned source",
                )
                node = by_id[item["id"]]
                expected_ids.add(node.id)
                self.assertEqual((node.kind, node.name), (item["kind"], item["name"]))
                self.assertEqual(node.location.path, item["path"])
                self.assertEqual(node.location.start_line, item["line"])
                self.assertEqual(node.location.end_line, item["line"])
                self.assertEqual(node.provenance.producer, "manual-rust-ccg-golden")
                witnesses = [
                    edge for edge in graph.edges
                    if edge.kind == "defines" and edge.source == item["parent"]
                    and edge.target == item["id"] and edge.resolution == "resolved"
                    and edge.location is not None
                    and edge.location.path == item["path"]
                    and edge.location.start_line == item["line"]
                ]
                self.assertEqual(len(witnesses), 1)
        self.assertEqual(set(by_id), expected_ids)
        self.assertEqual(sum(e.kind == "defines" for e in graph.edges),
                         len(self.provenance["declarations"]))
        self.assertTrue({"module", "symbol", "function", "method", "file"}
                        <= {node.kind for node in graph.nodes})

    def test_grounded_use_syntax_is_unresolved_not_runtime_linkage(self):
        graph = self.parse()
        imports = [e for e in graph.edges if e.kind == "imports"]
        self.assertEqual(len(imports), len(self.provenance["imports"]))
        for item in self.provenance["imports"]:
            with self.subTest(use=item["hint"]):
                self.assertTrue(
                    self.sources[item["path"]][item["line"] - 1].strip().startswith(item["anchor"])
                )
                found = [e for e in imports
                         if e.source == "rust:file:" + item["path"]
                         and e.target_hint == item["hint"] and e.target is None
                         and e.resolution == "unresolved"
                         and e.location and e.location.path == item["path"]
                         and e.location.start_line == item["line"]]
                self.assertEqual(len(found), 1)
        self.assertEqual(len([e for e in imports if e.resolution == "resolved"]), 0)

    def test_same_ccg_core_accepts_python_and_manually_curated_rust(self):
        rust = self.parse()
        python = adapt_python_sources(
            {"sample.py": "def helper():\n    return 1\n"},
            snapshot_id="pinned-python", schema=self.schema,
        )
        self.assertIsInstance(rust, Graph)
        self.assertIsInstance(python, Graph)
        self.assertEqual(rust.to_document()["schema_version"], "0.1")
        self.assertEqual(python.to_document()["schema_version"], "0.1")
        self.assertEqual(self.schema["$id"], "urn:codeqa:ccg:graph:v0.1")

    def test_canonical_graph_independent_of_node_and_edge_listing_order(self):
        first = canonical_json(self.parse())
        reordered = deepcopy(self.document)
        reordered["nodes"].reverse()
        reordered["edges"].reverse()
        reordered["coverage"]["analyzed_paths"].reverse()
        self.assertEqual(first, canonical_json(self.parse(reordered)))
        self.assertEqual(first, canonical_json(self.parse()))
        self.assertEqual(self.document, self.parse().to_document())

    def test_unknown_import_is_not_invented_as_resolved_target(self):
        first = deepcopy(self.document)
        edge = next(e for e in first["edges"] if e["kind"] == "imports")
        edge["target_hint"] = "unknown::item"
        self.assertEqual(
            next(e for e in self.parse(first).edges if e.target_hint == "unknown::item").resolution,
            "unresolved",
        )
        guessed = deepcopy(self.document)
        edge = next(e for e in guessed["edges"] if e["kind"] == "imports")
        edge.pop("target_hint")
        edge["resolution"] = "resolved"
        edge["target"] = "rust:invented:external_symbol"
        self.assert_issue(guessed, "missing_target")
        illegal = deepcopy(self.document)
        edge = next(e for e in illegal["edges"] if e["kind"] == "imports")
        edge["target"] = "rust:invented:external_symbol"
        self.assert_issue(illegal, "schema_violation")

    def test_missing_define_target_and_source_are_rejected(self):
        bad_target = deepcopy(self.document)
        edge = next(e for e in bad_target["edges"] if e["kind"] == "defines")
        edge["target"] = "missing-declaration"
        self.assert_issue(bad_target, "missing_target")
        bad_source = deepcopy(self.document)
        edge = next(e for e in bad_source["edges"] if e["kind"] == "defines")
        edge["source"] = "missing-owner"
        self.assert_issue(bad_source, "missing_source")
        duplicates = deepcopy(self.document)
        duplicates["nodes"].append(deepcopy(duplicates["nodes"][0]))
        self.assert_issue(duplicates, "duplicate_node_id")

    def test_partial_file_coverage_explicit_and_uncovered_facts_rejected(self):
        partial = deepcopy(self.document)
        partial["coverage"]["status"] = "partial"
        partial["coverage"]["unprocessed"] = [
            {"path": "src/backend.rs", "reason": "outside_curated_fixture_selection"}
        ]
        parsed = self.parse(partial)
        self.assertEqual(parsed.coverage.status, "partial")
        self.assertEqual(parsed.coverage.unprocessed[0].path, "src/backend.rs")
        contradiction = deepcopy(partial)
        contradiction["coverage"]["status"] = "complete"
        self.assert_issue(contradiction, "coverage_status")
        uncovered = deepcopy(partial)
        definition = next(n for n in uncovered["nodes"] if n["kind"] == "symbol")
        definition["location"]["path"] = "src/backend.rs"
        self.assert_issue(uncovered, "uncovered_fact")

    def test_unresolved_target_without_hint_and_invalid_span_rejected(self):
        no_hint = deepcopy(self.document)
        next(e for e in no_hint["edges"] if e["kind"] == "imports").pop("target_hint")
        self.assert_issue(no_hint, "schema_violation")
        wrong_span = deepcopy(self.document)
        next(n for n in wrong_span["nodes"] if "location" in n)["location"]["end_line"] = 0
        self.assert_issue(wrong_span, "schema_violation")

    def test_scope_documented_without_rust_parser_or_quality_verdict(self):
        readme = (ROOT / "docs/rust-ccg-reference.md").read_text(encoding="utf-8")
        self.assertIn("manually curated", readme)
        self.assertIn("NOT a Rust Adapter", readme)
        self.assertIn("source selection", readme)
        self.assertIn("runtime", readme)
        self.assertIn("P1–P8", readme)
        self.assertNotIn("quality_verdict", self.document)


if __name__ == "__main__":
    unittest.main()
