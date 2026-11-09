"""Read-only first-family relocation impact witness for Issue #288.

No file is moved, rewritten, or declared semantically reviewed by this test.
The report is derived from git-tracked paths at the tested checkout HEAD.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import unittest
from urllib.parse import unquote, urlsplit

from test_documentation_reference_audit import (
    ROOT, DOC_LITERAL, TEXT_SUFFIXES, heading_anchors,
    links_from_markdown, tracked_paths,
)

OLD = "docs/schema-composition-pilot-v0.1.md"
NEW = "/".join(("docs", "experiments", "schema-composition-pilot-v0.1.md"))


def git_head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def target_of(source: str, href: str) -> str | None:
    uri = urlsplit(href)
    if uri.scheme or uri.netloc or uri.path.startswith("/"):
        return None
    path = (ROOT / source).parent / unquote(uri.path) if uri.path else ROOT / source
    path = path.resolve()
    if not path.is_relative_to(ROOT):
        return None
    return path.relative_to(ROOT).as_posix()


def proposed_href_after_move(href: str, destination: str) -> str:
    """Rewrite a local href from OLD's parent to NEW's parent."""
    uri = urlsplit(href)
    if not uri.path:
        return href  # #fragment is local to the moved document
    new_href = Path(__import__("os").path.relpath(
        ROOT / destination, (ROOT / NEW).parent)).as_posix()
    if uri.query:
        new_href += "?" + uri.query
    if uri.fragment:
        new_href += "#" + uri.fragment
    return new_href


def impact_report() -> dict:
    tracked = tracked_paths()
    assert OLD in tracked and NEW not in tracked, "candidate source/destination changed"
    raw = (ROOT / OLD).read_text(encoding="utf-8")
    catalog = json.loads((ROOT / "docs/documentation-catalog-v0.1.json").read_text())
    docs = catalog["documents"]
    row = next(d for d in docs if d["path"] == OLD)
    candidates = sum(d.get("disposition") == "CANDIDATE_REQUIRES_BACKLINK_AUDIT"
                     for d in docs)
    assert row["disposition"] == "CANDIDATE_REQUIRES_BACKLINK_AUDIT"
    assert row["authority_review"] == "NOT_EVALUATED"
    # Coverage must be explicit: suffix filtering is not an exhaustive scan of
    # every tracked blob. Do not interpret missing hits as proof of absence.
    excluded = sorted(
        source for source in tracked
        if (ROOT / source).is_file()
        and (ROOT / source).suffix.lower() not in TEXT_SUFFIXES
    )
    unreadable_text = []
    inbound, outbound, literals, external = [], [], [], []
    for source in sorted(tracked):
        file = ROOT / source
        if not file.is_file() or file.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            unreadable_text.append(source)
            continue
        if source.endswith(".md"):
            for lineno, href in links_from_markdown(text):
                destination = target_of(source, href)
                if destination == OLD:
                    inbound.append({"source": source, "line": lineno, "href": href})
                if source == OLD:
                    entry = {"line": lineno, "href": href, "resolved": destination}
                    if destination is None:
                        external.append(entry)
                    else:
                        entry["after_move_href"] = proposed_href_after_move(
                            href, destination)
                        outbound.append(entry)
        for lineno, line in enumerate(text.splitlines(), 1):
            if OLD in line or NEW in line:
                literals.append({"source": source, "line": lineno,
                                 "old": OLD in line, "new": NEW in line,
                                 "doc_literal": OLD in DOC_LITERAL.findall(line)})
    return {
        "head": git_head(), "source": OLD, "proposed_destination": NEW,
        "source_git_blob": subprocess.check_output(
            ["git", "hash-object", OLD], cwd=ROOT, text=True).strip(),
        "tracked_files": len(tracked),
        "scan_scope": "tracked UTF-8 files with TEXT_SUFFIXES; parsed links only in Markdown",
        "excluded_tracked_files": excluded,
        "unreadable_included_text_files": unreadable_text,
        "unscanned_file_types_complete": False,
        "catalog_documents": len(docs),
        "catalog_relocation_candidates": candidates,
        "responsible_area": row.get("area"),
        "authority_review": row["authority_review"],
        "lifecycle": row.get("lifecycle", "NOT_DECLARED"),
        "inbound_markdown_links": inbound,
        "outbound_local_links": outbound,
        "outbound_external_links_unverified": external,
        "path_string_occurrences": literals,
        "heading_fragments": sorted(heading_anchors(raw)),
        "external_deep_links": "UNKNOWN",
        "cross_repository_references": "UNKNOWN",
        "rendered_github_fragments": "NOT_EVALUATED",
        "semantic_review": "NOT_EVALUATED",
        "destination_index_compatibility": "REQUIRES_HUMAN_TAXONOMY_REVIEW",
        "rollback": "Do not move in this PR. For a later approved move, restore OLD "
                    "and its original relative links, revert inbound link rewrites, "
                    "catalog and navigation edits; validate exact HEAD and historical anchors.",
    }


class FirstFamilyImpactTests(unittest.TestCase):
    def test_fragment_only_rewrite_preserves_document_local_anchor(self):
        # Regression for fragment-only links (even if the first candidate
        # happens not to contain any today).
        self.assertEqual(target_of(OLD, "#decision"), OLD)
        self.assertEqual(proposed_href_after_move("#decision", OLD), "#decision")
        self.assertEqual(proposed_href_after_move("#decision?x=1", OLD),
                         "#decision?x=1")
        self.assertEqual(proposed_href_after_move(
            "../tests/test_schema_composition_pilot_v01.py#case",
            "tests/test_schema_composition_pilot_v01.py"),
            "../../tests/test_schema_composition_pilot_v01.py#case")

    def test_report_first_candidate_without_mutation(self):
        report = impact_report()
        print("DOC288_FIRST_FAMILY_IMPACT " + json.dumps(
            report, ensure_ascii=False, sort_keys=True))
        self.assertEqual(report["authority_review"], "NOT_EVALUATED")
        # Candidate count is recomputed from the current checkout catalog.
        # The historical 84-candidate baseline must not become a frozen gate.
        current_catalog = json.loads(
            (ROOT / "docs/documentation-catalog-v0.1.json").read_text(encoding="utf-8"))
        expected_candidates = sum(
            d.get("disposition") == "CANDIDATE_REQUIRES_BACKLINK_AUDIT"
            for d in current_catalog["documents"])
        self.assertEqual(report["catalog_documents"], len(current_catalog["documents"]))
        self.assertEqual(report["catalog_relocation_candidates"], expected_candidates)
        self.assertGreater(expected_candidates, 0)
        self.assertEqual(len(report["outbound_local_links"]), 3)
        self.assertEqual(report["source_git_blob"],
                         "acf90d0bf9484a56beca66bfbb41dc0037345c6e")
        self.assertTrue(report["heading_fragments"])
        self.assertEqual(report["external_deep_links"], "UNKNOWN")
        self.assertFalse(report["unscanned_file_types_complete"])
        self.assertEqual(report["destination_index_compatibility"],
                         "REQUIRES_HUMAN_TAXONOMY_REVIEW")


if __name__ == "__main__":
    unittest.main()
