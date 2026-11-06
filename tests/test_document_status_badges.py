"""Pilot documentation badge integrity checks. No semantic certification.

Samuel's reusable documentation-consistency skill is developed independently.
codeQA stays pinned to its currently adopted Samuel commit; these tests
guard only the two explicit pilot document labels and local image files.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import unittest
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
CATALOG = DOCS / "documentation-catalog-v0.1.json"
ALLOWED = {
    "decision": {
        "PROPOSED": "0969DA", "ADOPTED": "2DA44E",
        "SUPERSEDED": "6E7781", "NOT_EVALUATED": "6E7781",
    },
    "implementation": {
        "IMPLEMENTED": "2DA44E", "PARTIAL": "BF8700",
        "NOT_IMPLEMENTED": "CF222E", "NOT_EVALUATED": "6E7781",
    },
    "review": {
        "REVIEWED": "2DA44E", "REVIEW_REQUIRED": "BF8700",
        "NOT_EVALUATED": "6E7781",
    },
}
CHIP_PALETTE = {
    "2DA44E": ("DAFBE1", "116329", "ACE6BF"),
    "0969DA": ("DDF4FF", "0550AE", "B6DEFA"),
    "BF8700": ("FFF8C5", "7D4E00", "E7D08A"),
    "CF222E": ("FFEBE9", "B42318", "F5B5B4"),
    "6E7781": ("EAECEF", "57606A", "D0D7DE"),
}
PILOT = {
    "docs/architecture.md": {
        "decision": "ADOPTED",
        "implementation": "NOT_EVALUATED",
        "review": "NOT_EVALUATED",
    },
    "docs/governance/documentation-architecture-v0.1.md": {
        "decision": "PROPOSED",
        "implementation": "NOT_EVALUATED",
        "review": "REVIEW_REQUIRED",
    },
}
BADGE_RE = re.compile(r"!\[([A-Za-z]+): ([A-Z_]+)\]\(([^)\n]+)\)")


class DocumentStatusBadgesTests(unittest.TestCase):
    def test_pilot_metadata_matches_heading_and_local_svg_palette(self):
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        entries = {item["path"]: item for item in catalog["documents"]}
        for doc_path, expected in PILOT.items():
            with self.subTest(document=doc_path):
                entry = entries[doc_path]
                self.assertEqual(entry["status_labels"], expected)
                self.assertEqual(entry["authority_review"], "NOT_EVALUATED")
                file = ROOT / doc_path
                lines = file.read_text(encoding="utf-8").splitlines()
                self.assertTrue(lines[0].startswith("# "), "H1 must be first")
                self.assertEqual(lines[1], "", "blank line follows first H1")
                badges = BADGE_RE.findall(lines[2])
                self.assertEqual(len(badges), 3, "exactly three badges immediately below H1")
                self.assertEqual(
                    [axis.lower() for axis, _value, _target in badges],
                    ["decision", "implementation", "review"],
                )
                self.assertEqual(
                    BADGE_RE.findall("\n".join(lines[3:11])), [],
                    "no extra status badges in the introductory block",
                )
                seen = set()
                for axis_name, value, target in badges:
                    axis = axis_name.casefold()
                    self.assertNotIn(axis, seen)
                    seen.add(axis)
                    self.assertIn(axis, expected)
                    self.assertEqual(value, expected[axis])
                    self.assertIn(value, ALLOWED[axis])
                    self.assertFalse(target.startswith(("http:", "https:", "/")))
                    self.assertNotIn("..", Path(target).parts[1:])
                    asset = (file.parent / target).resolve()
                    self.assertTrue(asset.is_relative_to(DOCS))
                    self.assertTrue(asset.is_file())
                    expected_name = f"{axis}-{value.lower().replace('_', '-')}.svg"
                    self.assertEqual(asset.name, expected_name)
                    root = ElementTree.fromstring(asset.read_text(encoding="utf-8"))
                    self.assertEqual(root.attrib.get("role"), "img")
                    self.assertEqual(root.attrib.get("height"), "22")
                    self.assertEqual(root.attrib.get("aria-label"),
                                     f"{axis_name}: {value}")
                    titles = [node.text for node in root
                              if node.tag.endswith("title")]
                    self.assertEqual(titles, [f"{axis_name}: {value}"])
                    rects = [node for node in root if node.tag.endswith("rect")]
                    self.assertEqual(len(rects), 1)
                    background, ink, border = CHIP_PALETTE[ALLOWED[axis][value]]
                    self.assertEqual(rects[0].attrib.get("rx"), "11")
                    self.assertEqual(rects[0].attrib.get("fill"), "#" + background)
                    self.assertEqual(rects[0].attrib.get("stroke"), "#" + border)
                    texts = [node for node in root if node.tag.endswith("text")]
                    self.assertEqual(len(texts), 1)
                    self.assertEqual(texts[0].text, value)
                    self.assertEqual(texts[0].attrib.get("fill"), "#" + ink)
                self.assertEqual(seen, set(expected))

    def test_labels_do_not_claim_completed_semantic_review(self):
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        entries = {item["path"]: item for item in catalog["documents"]}
        self.assertEqual(
            {path for path, entry in entries.items() if "status_labels" in entry},
            set(PILOT),
            "Phase B should not silently expand the reviewed pilot inventory",
        )
        for doc in PILOT:
            self.assertEqual(entries[doc]["authority_review"], "NOT_EVALUATED")
            self.assertNotEqual(entries[doc]["status_labels"]["review"], "REVIEWED")


if __name__ == "__main__":
    unittest.main()
