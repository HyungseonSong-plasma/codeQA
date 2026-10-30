"""#166/#184: complete, exact-byte review context without semantic promotion."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import unittest

from codeqa.evaluation.architecture.source_review_packets import (
    SourceReviewPacketError, build_source_review_packets,
    render_source_review_packets_markdown,
)


SOURCES = {
    "src/orchard/sky/view.py": (
        "from orchard.earth.model import Model\n"
        "from orchard.rain.flow import flow\n"
    ),
    "src/orchard/sky/helper.py": "from orchard.earth.model import Model\n",
}


def pack(*, edges=None):
    """Source-consistent fixture: every witness resolves to its actual module."""
    blobs = {path: text.encode("utf-8") for path, text in SOURCES.items()}
    pairs = (
        ("src/orchard/sky/view.py", "src/orchard/earth/model.py", 1,
         "from orchard.earth.model import Model"),
        ("src/orchard/sky/view.py", "src/orchard/rain/flow.py", 2,
         "from orchard.rain.flow import flow"),
        ("src/orchard/sky/helper.py", "src/orchard/earth/model.py", 1,
         "from orchard.earth.model import Model"),
    ) if edges is None else edges
    rows = []
    for src, dst, line, expression in pairs:
        rows.append({
            "source_path": src, "target_path": dst,
            "source_role": "sky",
            "target_role": "earth" if "/earth/" in dst else "rain",
            "declared_policy_direction": "DECLARED_ALLOWED",
            "review_focus": "UNOBSERVED_IN_BOUNDED_SAMPLE",
            "import_witnesses": [{
                "source_path": src, "target_path": dst,
                "source_sha256": sha256(blobs[src]).hexdigest(),
                "line": line, "expression": expression, "execution": "top_level",
            }],
            "callsite_examples": [], "candidate_test_paths": [],
            "fixture_call_candidate_sites": 0,
            "semantic_ownership": "NOT_EVALUATED",
            "public_api_compatibility": "NOT_EVALUATED",
            "recommended_action": "NO_AUTOMATIC_MOVE",
        })
    blobs = {row["source_path"]: blobs[row["source_path"]] for row in rows}
    worklist = {
        "schema_version": "0.1",
        "source_identity": {"snapshot_sha": "a" * 40},
        "observed_cross_role_pairs": len(rows),
        "edges": rows,
        "decision": "NOT_EVALUATED",
        "semantic_ownership": "NOT_EVALUATED",
        "recommended_action": "NO_AUTOMATIC_MOVE",
    }
    seal(worklist)
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

    def test_reject_resealed_packet_review_and_excerpt_forgery(self):
        worklist, blobs = pack()
        original = build_source_review_packets(worklist, blobs)

        def reseal(report):
            report["packets_id"] = sha256(json.dumps(
                {k: v for k, v in report.items() if k != "packets_id"},
                sort_keys=True, separators=(",", ":"),
            ).encode()).hexdigest()

        for field, forged in (
            ("review_status", "APPROVED"),
            ("semantic_ownership", "INTENTIONAL_COMPOSITION"),
            ("public_api_compatibility", "PASS"),
        ):
            with self.subTest(field=field):
                changed = deepcopy(original)
                changed["packets"][0][field] = forged
                reseal(changed)
                with self.assertRaises(SourceReviewPacketError):
                    render_source_review_packets_markdown(changed)

        changed = deepcopy(original)
        changed["packets"][1]["source_path"] = changed["packets"][0]["source_path"]
        changed["packets"][1]["target_path"] = changed["packets"][0]["target_path"]
        reseal(changed)
        with self.assertRaises(SourceReviewPacketError):
            render_source_review_packets_markdown(changed)

        changed = deepcopy(original)
        changed["packets"][0]["import_excerpts"][0]["witness_line"] = 999
        reseal(changed)
        with self.assertRaises(SourceReviewPacketError):
            render_source_review_packets_markdown(changed)

    def test_reject_resealed_wrong_target_on_real_import_line(self):
        worklist, blobs = pack()
        changed = deepcopy(worklist)
        # This line imports earth.model, not rain.flow. A same-line AST
        # ImportFrom was previously sufficient to forge the pair.
        changed["edges"][2]["target_path"] = "src/orchard/rain/flow.py"
        changed["edges"][2]["import_witnesses"][0]["target_path"] = (
            "src/orchard/rain/flow.py"
        )
        seal(changed)
        with self.assertRaises(SourceReviewPacketError):
            build_source_review_packets(changed, blobs)

    def test_reject_resealed_wrong_expression_or_execution(self):
        worklist, blobs = pack()
        for field, forged in (
            ("expression", "import orchard.earth.model"),
            ("execution", "conditional_or_deferred"),
        ):
            with self.subTest(field=field):
                changed = deepcopy(worklist)
                changed["edges"][0]["import_witnesses"][0][field] = forged
                seal(changed)
                with self.assertRaises(SourceReviewPacketError):
                    build_source_review_packets(changed, blobs)

    def test_relative_import_is_bound_without_guessing_members(self):
        src = "src/orchard/sky/helper.py"
        dst = "src/orchard/earth/model.py"
        raw = b"def run():\n    from ..earth.model import Model\n"
        worklist, _ = pack()
        worklist["edges"] = [deepcopy(worklist["edges"][2])]
        row = worklist["edges"][0]
        row["import_witnesses"][0].update({
            "source_sha256": sha256(raw).hexdigest(),
            "line": 2,
            "expression": "from ..earth.model import Model",
            "execution": "conditional_or_deferred",
        })
        worklist["observed_cross_role_pairs"] = 1
        seal(worklist)
        self.assertEqual(
            build_source_review_packets(worklist, {src: raw})["observed_cross_role_pairs"], 1
        )
        # 'from package import member' does not resolve to a member module.
        row["import_witnesses"][0]["expression"] = "from ..earth import model"
        seal(worklist)
        with self.assertRaises(SourceReviewPacketError):
            build_source_review_packets(worklist, {src: raw})

    def test_multi_alias_imports_use_per_module_dependency_expressions(self):
        src = "src/orchard/sky/view.py"
        raw = (
            b"import orchard.earth.model as earth, "
            b"orchard.rain.flow as rain\n"
        )
        worklist, _ = pack()
        worklist["edges"] = deepcopy(worklist["edges"][:2])
        for row in worklist["edges"]:
            witness = row["import_witnesses"][0]
            witness["source_sha256"] = sha256(raw).hexdigest()
            witness["line"] = 1
            module = (
                "orchard.earth.model" if "/earth/" in row["target_path"]
                else "orchard.rain.flow"
            )
            witness["expression"] = "import " + module
        worklist["observed_cross_role_pairs"] = 2
        seal(worklist)
        result = build_source_review_packets(worklist, {src: raw})
        self.assertEqual(result["observed_cross_role_pairs"], 2)

    def test_imported_member_is_not_guessed_to_be_submodule(self):
        src = "src/orchard/sky/helper.py"
        raw = b"from orchard.earth import model\n"
        worklist, _ = pack()
        worklist["edges"] = [deepcopy(worklist["edges"][2])]
        row = worklist["edges"][0]
        row["import_witnesses"][0].update({
            "source_sha256": sha256(raw).hexdigest(),
            "expression": "from orchard.earth import model",
        })
        worklist["observed_cross_role_pairs"] = 1
        seal(worklist)
        with self.assertRaises(SourceReviewPacketError):
            build_source_review_packets(worklist, {src: raw})

    def test_callsite_metadata_is_bound_to_actual_source_syntax(self):
        src = "src/orchard/sky/helper.py"
        raw = (
            b"from orchard.earth.model import Model\\n"
            b"def run():\\n"
            b"    return Model()\\n"
        )
        worklist, _ = pack()
        worklist["edges"] = [deepcopy(worklist["edges"][2])]
        row = worklist["edges"][0]
        row["import_witnesses"][0]["source_sha256"] = sha256(raw).hexdigest()
        row["callsite_examples"] = [{
            "test_id": "unit::test_run", "caller_line": 3,
            "function_qualname": "run", "enclosing_statement_kind": "Return",
        }]
        worklist["observed_cross_role_pairs"] = 1
        seal(worklist)
        report = build_source_review_packets(worklist, {src: raw})
        self.assertEqual(report["packets"][0]["sampled_callsite_excerpts"][0]["witness_line"], 3)

        for key, forged in (
            ("function_qualname", "unrelated_function"),
            ("enclosing_statement_kind", "Assign"),
            ("test_id", ""),
            ("caller_line", 1),
        ):
            with self.subTest(key=key):
                altered = deepcopy(worklist)
                altered["edges"][0]["callsite_examples"][0][key] = forged
                seal(altered)
                with self.assertRaises(SourceReviewPacketError):
                    build_source_review_packets(altered, {src: raw})

    def test_reject_resealed_report_with_false_decision(self):
        worklist, blobs = pack()
        result = build_source_review_packets(worklist, blobs)
        result["packets"][0]["review_status"] = "APPROVED"
        with self.assertRaises(SourceReviewPacketError):
            render_source_review_packets_markdown(result)


if __name__ == "__main__":
    unittest.main()
