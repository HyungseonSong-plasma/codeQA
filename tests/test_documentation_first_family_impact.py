"""Issue #288: read-only proof for the *proposed* first-family relocation.

The old path remains an intentionally non-HTTP-redirecting Markdown alias.
The original semantic body must be preserved at the new canonical path,
apart from three depth-adjusted relative links. This test asserts source
invariants but does NOT certify external backlinks or GitHub-rendered HTML.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import unittest
from urllib.parse import unquote, urlsplit

from test_documentation_reference_audit import (
    ROOT, TEXT_SUFFIXES, heading_anchors, links_from_markdown, tracked_paths,
)

OLD = "docs/schema-composition-pilot-v0.1.md"
NEW = "docs/experiments/schema-composition-pilot-v0.1.md"
ORIGINAL_BLOB = "acf90d0bf9484a56beca66bfbb41dc0037345c6e"
EXPECTED_SLUGS = frozenset({
    "schema-composition-pilot-v01--exact-non-migrating-evidence",
    "question",
    "exact-sources-and-findings",
    "reproducible-executable-pilot",
    "decision",
})
INBOUND = frozenset({
    "docs/README.md",
    "docs/contract-taxonomy-and-composition-v0.1.md",
    "docs/governance/document-authority-review-v0.1.md",
    "docs/experiments/README.md",
})


def _git_blob(text: str) -> str:
    data = text.encode("utf-8")
    return hashlib.sha1(
        f"blob {len(data)}\0".encode("ascii") + data
    ).hexdigest()


def _target_of(source: str, href: str) -> str | None:
    uri = urlsplit(href)
    if uri.scheme or uri.netloc or uri.path.startswith("/"):
        return None
    dest = (ROOT / source).parent / unquote(uri.path) if uri.path else ROOT / source
    dest = dest.resolve()
    if not dest.is_relative_to(ROOT):
        return None
    return dest.relative_to(ROOT).as_posix()


def _catalog_roles():
    catalog = json.loads(
        (ROOT / "docs/documentation-catalog-v0.1.json").read_text(encoding="utf-8")
    )
    rows = {row["path"]: row for row in catalog["documents"]}
    return catalog, rows[OLD], rows[NEW]


def _reverse_relative_link_rewrites(canonical: str) -> str:
    # Reverse only the three known relative link rewrites.
    return (
        canonical.replace("](../../contracts/qa/", "](../contracts/qa/")
                 .replace("](../../tests/test_schema_composition_pilot_v01.py)",
                          "](../tests/test_schema_composition_pilot_v01.py)")
    )


def relocation_report() -> dict:
    tracked = tracked_paths()
    assert OLD in tracked and NEW in tracked, "alias and canonical file must both exist"
    alias = (ROOT / OLD).read_text(encoding="utf-8")
    canonical = (ROOT / NEW).read_text(encoding="utf-8")
    catalog, legacy_row, canonical_row = _catalog_roles()

    inbound, old_inbound, literal_refs = [], [], []
    unreadable, excluded = [], []
    for source in sorted(tracked):
        file = ROOT / source
        if not file.is_file():
            continue
        if file.suffix.lower() not in TEXT_SUFFIXES:
            excluded.append(source)
            continue
        try:
            raw = file.read_text(encoding="utf-8")
        except UnicodeError:
            unreadable.append(source)
            continue
        if source.endswith(".md"):
            for lineno, href in links_from_markdown(raw):
                resolved = _target_of(source, href)
                if resolved == NEW:
                    inbound.append({"source": source, "line": lineno, "href": href})
                if resolved == OLD:
                    old_inbound.append(
                        {"source": source, "line": lineno, "href": href}
                    )
        for lineno, line in enumerate(raw.splitlines(), 1):
            if OLD in line or NEW in line:
                literal_refs.append({
                    "source": source, "line": lineno,
                    "old": OLD in line, "new": NEW in line,
                })
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    return {
        "tested_checkout": head,
        "source": OLD,
        "canonical": NEW,
        "original_blob": ORIGINAL_BLOB,
        "recovered_original_blob": _git_blob(
            _reverse_relative_link_rewrites(canonical)
        ),
        "canonical_blob": _git_blob(canonical),
        "alias_blob": _git_blob(alias),
        "legacy_headings": sorted(heading_anchors(alias)),
        "canonical_headings": sorted(heading_anchors(canonical)),
        "inbound_canonical": inbound,
        "inbound_legacy": old_inbound,
        "path_literal_occurrences": literal_refs,
        "catalog_count": len(catalog["documents"]),
        "candidate_count": sum(
            r["disposition"] == "CANDIDATE_REQUIRES_BACKLINK_AUDIT"
            for r in catalog["documents"]
        ),
        "legacy_role": legacy_row["authority_role"],
        "canonical_role": canonical_row["authority_role"],
        "legacy_authority_review": legacy_row["authority_review"],
        "canonical_authority_review": canonical_row["authority_review"],
        "tracked_files": len(tracked),
        "excluded_tracked_files": excluded,
        "unreadable_text_files": unreadable,
        "external_backlinks": "UNKNOWN",
        "cross_repository_references": "UNKNOWN",
        "github_rendered_anchor_compatibility": "NOT_EVALUATED",
        "semantic_review": "NOT_EVALUATED",
        "http_redirect": False,
    }


class FirstFamilyRelocationTests(unittest.TestCase):
    def test_canonical_document_is_original_experiment_with_three_link_fixes(self):
        canonical = (ROOT / NEW).read_text(encoding="utf-8")
        self.assertEqual(
            _git_blob(_reverse_relative_link_rewrites(canonical)), ORIGINAL_BLOB,
            "any changed experiment prose beyond three href depth fixes needs review",
        )
        self.assertEqual(canonical.count("](../../contracts/qa/"), 2)
        self.assertEqual(
            canonical.count("](../../tests/test_schema_composition_pilot_v01.py)"),
            1,
        )
        self.assertNotIn("](../contracts/qa/", canonical)
        self.assertNotIn("](../tests/test_schema_composition_pilot_v01.py)", canonical)
        for _, href in links_from_markdown(canonical):
            uri = urlsplit(href)
            if uri.scheme or uri.netloc:
                continue
            target = _target_of(NEW, href)
            self.assertIsNotNone(target)
            self.assertTrue((ROOT / target).is_file(), href)

    def test_old_path_preserves_all_five_heading_slugs_and_forwards_each(self):
        canonical = (ROOT / NEW).read_text(encoding="utf-8")
        alias = (ROOT / OLD).read_text(encoding="utf-8")
        self.assertEqual(heading_anchors(canonical), EXPECTED_SLUGS)
        self.assertEqual(heading_anchors(alias), EXPECTED_SLUGS)
        self.assertIn("not** an HTTP redirect", alias)
        self.assertIn("NOT_EVALUATED", alias)
        self.assertIn("](experiments/schema-composition-pilot-v0.1.md)", alias)
        for slug in EXPECTED_SLUGS - {
            "schema-composition-pilot-v01--exact-non-migrating-evidence"
        }:
            self.assertIn(
                "](experiments/schema-composition-pilot-v0.1.md#" + slug + ")",
                alias,
            )

    def test_catalog_keeps_alias_and_canonical_separate_and_unreviewed(self):
        _, old, new = _catalog_roles()
        self.assertEqual(old["area"], "navigation")
        self.assertEqual(old["authority_role"], "LEGACY_PATH_ALIAS")
        self.assertEqual(old["canonical_location"], NEW)
        self.assertEqual(old["disposition"], "RETAIN_CURRENT_DIRECTORY")
        self.assertEqual(new["area"], "experiments")
        self.assertEqual(new["authority_role"], "SCOPED_DECISION_RECORD")
        self.assertEqual(new["candidate_directory"], "docs/experiments/")
        self.assertEqual(new["disposition"], "RETAIN_CURRENT_DIRECTORY")
        self.assertEqual(old["authority_review"], "NOT_EVALUATED")
        self.assertEqual(new["authority_review"], "NOT_EVALUATED")

    def test_all_known_inbound_links_target_new_canonical_document(self):
        for path in INBOUND:
            body = (ROOT / path).read_text(encoding="utf-8")
            targets = [_target_of(path, h) for _, h in links_from_markdown(body)]
            with self.subTest(path=path):
                self.assertIn(NEW, targets)
                self.assertNotIn(OLD, targets)
        report = relocation_report()
        self.assertTrue(INBOUND.issubset({
            r["source"] for r in report["inbound_canonical"]
        }))
        # No other tracked Markdown file should point to the legacy file
        # after the four approved navigation/reference rewrites.
        self.assertEqual(report["inbound_legacy"], [])

    def test_report_preserves_unknowns_and_exact_original_source_proof(self):
        report = relocation_report()
        print("DOC288_FIRST_FAMILY_RELOCATION " + json.dumps(
            report, ensure_ascii=False, sort_keys=True
        ))
        self.assertEqual(report["original_blob"], report["recovered_original_blob"])
        self.assertEqual(report["legacy_headings"], sorted(EXPECTED_SLUGS))
        self.assertEqual(report["canonical_headings"], sorted(EXPECTED_SLUGS))
        self.assertGreater(report["tracked_files"], 0)
        self.assertFalse(report["unreadable_text_files"])
        self.assertEqual(report["external_backlinks"], "UNKNOWN")
        self.assertEqual(report["cross_repository_references"], "UNKNOWN")
        self.assertEqual(report["github_rendered_anchor_compatibility"], "NOT_EVALUATED")
        self.assertFalse(report["http_redirect"])


if __name__ == "__main__":
    unittest.main()
