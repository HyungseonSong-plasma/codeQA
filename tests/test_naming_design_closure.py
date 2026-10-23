"""Keep ADR #61 design closure separate from implementation status.

A green test confirms documented contract inventory and scope transfer,
not actual multi-language or third-party runtime conformance.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]
ADR = ROOT / "docs/adr/0004-versioned-naming-conventions-and-scope.md"
DOC = ROOT / "docs/naming-conventions.md"
BASE = "https://github.com/HyungseonSong-plasma/codeQA/issues/"


class NamingDesignClosureContractTests(unittest.TestCase):
    def test_accepted_decision_explicitly_distinguishes_design_from_capability(self):
        text = ADR.read_text(encoding="utf-8")
        self.assertIn("**Status:** Accepted", text)
        self.assertIn(BASE + "61", text)
        self.assertIn("not complete", text.lower())
        self.assertIn("**not part of this ADR**", text)
        for key in ("`NOT_EVALUATED`", "MOOSE", "type-checker", "directional"):
            self.assertIn(key.replace("\\", ""), text)
        self.assertIn("adr/0004-versioned-naming-conventions-and-scope.md",
                      DOC.read_text(encoding="utf-8"))

    def test_all_original_unfinished_requirements_have_followup_links(self):
        text = ADR.read_text(encoding="utf-8")
        for issue in range(69, 77):
            with self.subTest(issue=issue):
                self.assertIn(BASE + str(issue), text)
        for merged in (62, 66, 67, 68):
            self.assertIn(f"https://github.com/HyungseonSong-plasma/codeQA/pull/{merged}",
                          text)
        for closed in (63, 64, 65):
            self.assertIn(BASE + str(closed), text)
        self.assertIn("historical unfulfilled", text)
        self.assertIn("not", text.lower())

    def test_registry_and_schema_boundaries_remain_versioned(self):
        resources = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
            "tool"]["codeqa"]["resources"]
        known = {
            "python_naming_safe_profile": "profiles/python-naming-safe-v0.1.json",
            "naming_report_schema": "contracts/qa/naming-report-v0.1.schema.json",
            "python_pinned_ancestor_profile": "profiles/python-pinned-ancestor-v0.1.json",
            "pinned_ancestor_report_schema": "contracts/qa/pinned-ancestor-v0.1.schema.json",
            "python_directional_fields_profile": "profiles/python-directional-fields-v0.1.json",
            "directional_fields_report_schema": "contracts/qa/directional-fields-v0.1.schema.json",
            "python_naming_glossary_profile": "profiles/python-naming-glossary-v0.1.json",
            "naming_glossary_report_schema": "contracts/qa/naming-glossary-v0.1.schema.json",
        }
        for logical, path in known.items():
            with self.subTest(resource=logical):
                self.assertEqual(resources[logical], path)
                self.assertTrue((ROOT / path).is_file())
                obj = json.loads((ROOT / path).read_text(encoding="utf-8"))
                if logical.endswith("_schema"):
                    self.assertRegex(obj["$id"], r"^urn:codeqa:qa:.*:v0\.1$")
                else:
                    self.assertEqual(obj["schema_version"], "0.1")
        self.assertIn("strict Delta v0.2", ADR.read_text(encoding="utf-8"))

    def test_all_adr_local_links_refer_to_real_files(self):
        text = ADR.read_text(encoding="utf-8")
        for target in re.findall(r"\]\(([^)]+)\)", text):
            if target.startswith(("https:", "http:", "#")):
                continue
            with self.subTest(link=target):
                path = (ADR.parent / target.split("#", 1)[0]).resolve()
                self.assertTrue(path.is_relative_to(ROOT))
                self.assertTrue(path.is_file())


if __name__ == "__main__":
    unittest.main()
