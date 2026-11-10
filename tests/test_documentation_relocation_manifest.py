"""Read-only manifest-based doc relocation contract for Issue #288.

This tests source identity, preserved legacy GFM anchor definitions, canonical
link forwarding, tracked local incoming links and distinct catalog authority.
Existing link/anchor parsers remain the single shared implementation. CI
success does NOT attest external backlinks, Raw consumers, scroll position or
technical correctness of historical prose.
"""
from __future__ import annotations

import hashlib
import json
import posixpath
import re
import unittest

from test_documentation_reference_audit import (
    ROOT, heading_anchors, links_from_markdown, tracked_paths,
)
from test_documentation_candidate_impact import _local_target

MANIFEST = ROOT / "docs/governance/document-relocations-v0.1.json"
CATALOG = ROOT / "docs/documentation-catalog-v0.1.json"
SHA40 = re.compile(r"^[a-f0-9]{40}$")
HEADING_H2 = re.compile(r"^## +", re.M)


def _git_blob(text: str) -> str:
    data = text.encode("utf-8")
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") +
                        b"\0" + data).hexdigest()


def _sections(text: str) -> set[str]:
    """Get H2 GitHub slugs with the existing shared parser, not a second slugger."""
    # Every recorded migrated document currently has H1 and unique H2 titles.
    # Compare the number of detected H2 headings to detect unsupported duplicates.
    h2 = [line for line in text.splitlines() if line.startswith("## ")]
    slugs = heading_anchors("\n".join(h2))
    if len(slugs) != len(h2):
        raise AssertionError("Duplicate or unsupported section slugs")
    return slugs


def validate_manifest() -> dict:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest["schema_version"] != "doc288-relocation-contract-v0.1":
        raise AssertionError("Unknown relocation manifest version")
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    by_path = {row["path"]: row for row in catalog["documents"]}
    tracked = tracked_paths()
    moves = manifest["moves"]
    if not moves or len(moves) != len({m["legacy"] for m in moves}):
        raise AssertionError("Missing or duplicate legacy paths")
    if len(moves) != len({m["canonical"] for m in moves}):
        raise AssertionError("Duplicate canonical destinations")
    records = []
    legacy_paths = {m["legacy"] for m in moves}

    for entry in moves:
        old, new = entry["legacy"], entry["canonical"]
        if old == new or old not in tracked or new not in tracked:
            raise AssertionError("Relocation paths absent or overlapping")
        if posixpath.normpath(old) != old or posixpath.normpath(new) != new:
            raise AssertionError("Noncanonical document path")
        if not old.startswith("docs/") or not new.startswith("docs/"):
            raise AssertionError("Documents must remain under docs/")
        if entry["authority_review"] != "NOT_EVALUATED":
            raise AssertionError("Authority must not be implicitly promoted")
        if entry["raw_consumers"] != "UNKNOWN" or entry["external_backlinks"] != "UNKNOWN":
            raise AssertionError("Unverified consumers may not be marked PASS")
        original_blob, canonical_blob = entry["original_blob"], entry["canonical_blob"]
        if not SHA40.fullmatch(original_blob) or not SHA40.fullmatch(canonical_blob):
            raise AssertionError("Blob pin must be exact Git SHA-1")

        old_text = (ROOT / old).read_text(encoding="utf-8")
        new_text = (ROOT / new).read_text(encoding="utf-8")
        if _git_blob(new_text) != canonical_blob:
            raise AssertionError("Canonical full body has drifted: " + new)
        reversed_text = new_text
        for edit in entry["reverse_link_rewrites"]:
            if reversed_text.count(edit["from"]) != edit["count"]:
                raise AssertionError("Approved link rewrite count drifted: " + new)
            reversed_text = reversed_text.replace(edit["from"], edit["to"])
        if _git_blob(reversed_text) != original_blob:
            raise AssertionError("Unapproved technical body difference: " + new)
        if _git_blob(old_text) == original_blob:
            raise AssertionError("Old path is not the expected navigation-only stub: " + old)
        old_slugs = heading_anchors(old_text)
        new_slugs = heading_anchors(new_text)
        if old_slugs != new_slugs:
            raise AssertionError("Legacy heading/fragment set drift: " + old)
        required_sections = set(entry["section_slugs"])
        if _sections(new_text) != required_sections or _sections(old_text) != required_sections:
            raise AssertionError("Declared H2 fragments not exact: " + old)

        # Forwarding paths must be relative and must lead to the one canonical
        # full document; none can silently point to a different destination.
        hrefs = [h for _, h in links_from_markdown(old_text)]
        if len(hrefs) != len(required_sections) + 1:
            raise AssertionError("Legacy stub forwarding count mismatch: " + old)
        root_links, seen_sections = 0, set()
        for href in hrefs:
            target, fragment = _local_target(old, href)
            if target != new:
                raise AssertionError("Unexpected legacy href target: " + href)
            if fragment is None:
                root_links += 1
            elif fragment in new_slugs:
                seen_sections.add(fragment)
            else:
                raise AssertionError("Fragment does not exist in canonical: " + href)
        if root_links != 1 or seen_sections != required_sections:
            raise AssertionError("Missing canonical or fragment forwarding links: " + old)

        alias, full = by_path[old], by_path[new]
        if (alias["authority_role"] != "LEGACY_PATH_ALIAS" or
                alias["area"] != "navigation" or
                alias["canonical_location"] != new or
                alias["disposition"] != "RETAIN_CURRENT_DIRECTORY" or
                alias["authority_review"] != "NOT_EVALUATED"):
            raise AssertionError("Alias catalog claim drift: " + old)
        if (full["authority_role"] != entry["canonical_role"] or
                full["area"] != entry["canonical_area"] or
                full["authority_review"] != "NOT_EVALUATED" or
                full["disposition"] != "RETAIN_CURRENT_DIRECTORY"):
            raise AssertionError("Canonical catalog claim drift: " + new)

        records.append({
            "old": old, "canonical": new, "original_blob": original_blob,
            "canonical_blob": canonical_blob, "legacy_stub_blob": _git_blob(old_text),
            "slug_count": len(old_slugs), "forward_link_count": len(hrefs),
            "raw_byte_parity": "NOT_EQUIVALENT",
            "raw_consumers": "UNKNOWN", "external_backlinks": "UNKNOWN",
            "actual_browser_scroll": "NOT_EVALUATED",
            "semantic_review": "NOT_EVALUATED",
        })

    inbound_old = []
    for source in sorted(tracked):
        if not source.endswith(".md") or source in legacy_paths:
            continue
        for number, href in links_from_markdown(
                (ROOT / source).read_text(encoding="utf-8")):
            target, fragment = _local_target(source, href)
            if target in legacy_paths:
                inbound_old.append({"source": source, "line": number,
                                    "target": target, "fragment": fragment})
    if inbound_old:
        raise AssertionError("Tracked Markdown still points to legacy aliases: " +
                             json.dumps(inbound_old, sort_keys=True))
    if len(records) != sum(
            row["authority_role"] == "LEGACY_PATH_ALIAS"
            for row in catalog["documents"]):
        raise AssertionError("Manifest must describe every cataloged legacy alias")

    return {
        "manifest_version": manifest["schema_version"],
        "relocations": len(records),
        "tracked_files": len(tracked),
        "inbound_legacy_links": inbound_old,
        "records": records,
        "limitations": {
            "external_backlinks": "UNKNOWN",
            "raw_consumer_population": "UNKNOWN",
            "raw_byte_compatibility": "NOT_EQUIVALENT",
            "actual_browser_scroll": "NOT_EVALUATED",
            "semantic_review": "NOT_EVALUATED",
            "proven_coverage": "tracked Markdown relative hyperlinks + exact pinned sources",
            "unproven": "unindexed/private cross-repo references, dynamic paths, HTTP redirect and semantic truth",
        },
    }


class DocumentationRelocationManifestTests(unittest.TestCase):
    def test_every_recorded_move_uses_the_common_contract(self):
        report = validate_manifest()
        self.assertGreaterEqual(report["relocations"], 4)
        self.assertEqual(report["inbound_legacy_links"], [])
        print("DOC288_RELOCATION_CONTRACT " + json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
