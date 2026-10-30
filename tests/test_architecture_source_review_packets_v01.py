"""#166/#184: complete, exact-byte review context without semantic promotion."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import unittest

from codeqa.evaluation.architecture.edge_review_worklist import build_edge_review_worklist
from codeqa.evaluation.architecture.source_review_packets import (
    SourceReviewPacketError, build_source_review_packets,
    render_source_review_packets_markdown,
)
from test_architecture_edge_review_worklist_v01 import inputs
from test_architecture_opportunities_v01 import SOURCES


def pack(*, edges=None):
    reports = inputs() if edges is None else inputs(edges=edges)
    worklist = build_edge_review_worklist(*reports)
    blobs = {row["source_path"]: SOURCES[row["source_path"]].encode("utf-8")
             for row in worklist["edges"]}
    return worklist, blobs


def seal(report):
    report["worklist_id"] = sha256(json.dumps(
        {k: v for k, v in report.items() if k != "worklist_id"},
        sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()


class SourceReviewPacketTests(unittest.TestCase):
    def test_all_edges_have_exact_source_context_not_a_semantic_verdict(self):
        worklist, blobs = pack()
        result = build_source_review_packets(worklist, blobs)
        self.assertEqual(result["observed_cross_role_pairs"], len(worklist["edges"]))
        self.assertEqual(result, build_source_review_packets(worklist, blobs))
        self.assertTrue(all(row["import_excerpts"] and
                            row["review_status"] == "HUMAN_EVIDENCE_REQUIRED" and
                            row["semantic_ownership"] == "NOT_EVALUATED"
                            for row in result["packets"]))
        self.assertIn("from orchard.earth.model import Model",
                      render_source_review_packets_markdown(result))
        self.assertNotIn("PREFER", render_source_review_packets_markdown(result))

    def test_zero_signal_remains_zero_and_does_not_force_review(self):
        worklist, blobs = pack(edges=())
        result = build_source_review_packets(worklist, blobs)
        self.assertEqual(result["packets"], [])
        self.assertIn("no forced question", render_source_review_packets_markdown(result))

    def test_reject_missing_extra_or_tampered_source(self):
        worklist, blobs = pack()
        with self.assertRaises(SourceReviewPacketError):
            build_source_review_packets(worklist, {})
        with self.assertRaises(SourceReviewPacketError):
            build_source_review_packets(worklist, {**blobs, "extra.py": b"pass\n"})
        changed = dict(blobs)
        changed[next(iter(changed))] += b"# mutated\n"
        with self.assertRaises(SourceReviewPacketError):
            build_source_review_packets(worklist, changed)

    def test_reject_resealed_forged_line_and_semantic_promotion(self):
        worklist, blobs = pack()
        changed = deepcopy(worklist)
        changed["edges"][0]["import_witnesses"][0]["line"] = 1000
        seal(changed)
        with self.assertRaises(SourceReviewPacketError):
            build_source_review_packets(changed, blobs)
        changed = deepcopy(worklist)
        changed["edges"][0]["semantic_ownership"] = "INTENTIONAL_COMPOSITION"
        seal(changed)
        with self.assertRaises(SourceReviewPacketError):
            build_source_review_packets(changed, blobs)

    def test_reject_resealed_report_with_false_decision(self):
        worklist, blobs = pack()
        result = build_source_review_packets(worklist, blobs)
        result["packets"][0]["review_status"] = "APPROVED"
        with self.assertRaises(SourceReviewPacketError):
            render_source_review_packets_markdown(result)


if __name__ == "__main__":
    unittest.main()
