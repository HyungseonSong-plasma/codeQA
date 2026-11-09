"""Issue #288: three formal-evidence document moves, no new authority.

The canonical contents must have their EXACT original Git blobs. Legacy stubs
keep GitHub source heading slugs and section forwarding links, but do not offer
Raw-byte equivalence, HTTP redirects or independent semantic acceptance.
"""
from __future__ import annotations

import hashlib
import json
import unittest

from test_documentation_reference_audit import ROOT, heading_anchors, links_from_markdown, tracked_paths
from test_documentation_candidate_impact import _local_target


MOVES = {
    "docs/formal-binding-identity-v01.md": (
        "docs/governance/evidence/formal-binding-identity-v01.md",
        "9828855c44036823ad8cc8967e0065a6fb7bba0d",
        {"canonical-artifact-path-identity"},
    ),
    "docs/formal-proof-receipt-v0.1.md": (
        "docs/governance/evidence/formal-proof-receipt-v0.1.md",
        "d6e42028f51d8f59cbcfc2935c640c1fc94ce24d",
        {"observed-vs-asserted-tool-provenance",
         "fail-closed-regression-scope", "canonical-dafny-source-paths"},
    ),
    "docs/generated-formal-fixture-gate-v01.md": (
        "docs/governance/evidence/generated-formal-fixture-gate-v01.md",
        "0b2f0961d32279834ca1d8b95f7dbd6684671b5e",
        {"explicit-authority-boundary", "what-a-fixture-pass-does-not-mean",
         "full-production-verification-remains-an-independent-design-problem"},
    ),
}


def _blob(raw: str) -> str:
    data = raw.encode("utf-8")
    return hashlib.sha1(f"blob {len(data)}\0".encode("utf-8") + data).hexdigest()


def relocation_report() -> dict:
    catalog = json.loads((ROOT / "docs/documentation-catalog-v0.1.json").read_text(encoding="utf-8"))
    by_path = {row["path"]: row for row in catalog["documents"]}
    tracked = tracked_paths()
    records = []
    old_paths = set(MOVES)
    incoming_old = []
    for source in sorted(tracked):
        if not source.endswith(".md"):
            continue
        for line, href in links_from_markdown((ROOT / source).read_text(encoding="utf-8")):
            target, fragment = _local_target(source, href)
            if target in old_paths and source not in old_paths:
                incoming_old.append({"source": source, "line": line, "target": target,
                                     "fragment": fragment})
    for old, (new, original, section_slugs) in sorted(MOVES.items()):
        alias = (ROOT / old).read_text(encoding="utf-8")
        canonical = (ROOT / new).read_text(encoding="utf-8")
        old_row, new_row = by_path[old], by_path[new]
        records.append({
            "old_path": old, "canonical_path": new,
            "original_blob": original, "canonical_blob": _blob(canonical),
            "old_stub_blob": _blob(alias),
            "old_heading_slugs": sorted(heading_anchors(alias)),
            "new_heading_slugs": sorted(heading_anchors(canonical)),
            "expected_sections": sorted(section_slugs),
            "legacy_role": old_row["authority_role"],
            "canonical_role": new_row["authority_role"],
            "legacy_review": old_row["authority_review"],
            "canonical_review": new_row["authority_review"],
            "raw_bytes_equal": _blob(alias) == original,
            "raw_consumers": "UNKNOWN",
            "external_backlinks": "UNKNOWN",
            "rendered_anchor_compatibility": "NOT_EVALUATED",
            "semantic_review": "NOT_EVALUATED",
            "http_redirect": False,
        })
    return {"candidate_count": sum(x["disposition"] == "CANDIDATE_REQUIRES_BACKLINK_AUDIT"
                                   for x in catalog["documents"]),
            "catalog_count": len(catalog["documents"]),
            "inbound_legacy": incoming_old, "documents": records}


class SecondFamilyRelocationTests(unittest.TestCase):
    def test_three_canonical_documents_match_original_git_blobs(self):
        for old, (new, original, _) in MOVES.items():
            with self.subTest(old=old):
                self.assertEqual(_blob((ROOT / new).read_text(encoding="utf-8")),
                                 original, "original technical text changed during move")
                self.assertTrue((ROOT / old).is_file())

    def test_old_headings_and_canonical_forward_links(self):
        for old, (new, original, sections) in MOVES.items():
            with self.subTest(old=old):
                alias = (ROOT / old).read_text(encoding="utf-8")
                canonical = (ROOT / new).read_text(encoding="utf-8")
                legacy_headings = heading_anchors(alias)
                self.assertEqual(legacy_headings, heading_anchors(canonical))
                self.assertTrue(sections.issubset(legacy_headings))
                self.assertIn("not an HTTP redirect", alias)
                self.assertIn("NOT_EVALUATED", alias)
                self.assertIn("UNKNOWN", alias)
                self.assertIn("](governance/evidence/" + old.split("/")[-1] + ")", alias)
                self.assertNotEqual(_blob(alias), original)
                for slug in sections:
                    self.assertIn("](governance/evidence/" + old.split("/")[-1] +
                                  "#" + slug + ")", alias)
                for _, href in links_from_markdown(alias):
                    target, fragment = _local_target(old, href)
                    self.assertEqual(target, new, "stub links must target canonical")
                    if fragment:
                        self.assertIn(fragment, heading_anchors(canonical))

    def test_catalog_roles_unchanged_and_aliases_not_normative(self):
        catalog = json.loads((ROOT / "docs/documentation-catalog-v0.1.json").read_text(encoding="utf-8"))
        rows = {row["path"]: row for row in catalog["documents"]}
        self.assertGreaterEqual(len(rows), 115)
        self.assertLessEqual(sum(row["disposition"] == "CANDIDATE_REQUIRES_BACKLINK_AUDIT"
                             for row in catalog["documents"]), 80)
        for old, (new, _, _) in MOVES.items():
            with self.subTest(old=old):
                prior, canonical = rows[old], rows[new]
                self.assertEqual(prior["authority_role"], "LEGACY_PATH_ALIAS")
                self.assertEqual(prior["area"], "navigation")
                self.assertEqual(prior["canonical_location"], new)
                self.assertEqual(prior["disposition"], "RETAIN_CURRENT_DIRECTORY")
                self.assertEqual(canonical["authority_role"], "SCOPED_TECHNICAL_GUIDE")
                self.assertEqual(canonical["area"], "governance")
                self.assertEqual(canonical["disposition"], "RETAIN_CURRENT_DIRECTORY")
                self.assertEqual(canonical["candidate_directory"], "docs/governance/evidence/")
                self.assertEqual(prior["authority_review"], "NOT_EVALUATED")
                self.assertEqual(canonical["authority_review"], "NOT_EVALUATED")

    def test_inbound_legacy_and_portal_routing(self):
        report = relocation_report()
        self.assertEqual(report["inbound_legacy"], [],
                         "tracked Markdown links must not still target old stubs")
        portal = (ROOT / "docs/README.md").read_text(encoding="utf-8")
        resolved = {_local_target("docs/README.md", href)[0]
                    for _, href in links_from_markdown(portal)}
        for old, (new, _, _) in MOVES.items():
            with self.subTest(old=old):
                self.assertIn(new, resolved)
                self.assertNotIn(old, resolved)

    def test_report_preserves_raw_external_and_semantic_unknowns(self):
        report = relocation_report()
        self.assertLessEqual(report["candidate_count"], 80)
        self.assertEqual(len(report["documents"]), 3)
        for entry in report["documents"]:
            self.assertEqual(entry["original_blob"], entry["canonical_blob"])
            self.assertEqual(entry["old_heading_slugs"], entry["new_heading_slugs"])
            self.assertFalse(entry["raw_bytes_equal"])
            self.assertEqual(entry["raw_consumers"], "UNKNOWN")
            self.assertEqual(entry["external_backlinks"], "UNKNOWN")
            self.assertEqual(entry["semantic_review"], "NOT_EVALUATED")
            self.assertEqual(entry["rendered_anchor_compatibility"], "NOT_EVALUATED")
            self.assertFalse(entry["http_redirect"])
        print("DOC288_SECOND_FAMILY_RELOCATION " + json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
