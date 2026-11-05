"""Documentation routing coverage and minimal link-safety gates (Issue #288).

These tests verify the proposed taxonomy and new portal. They do NOT certify
the semantic truth or current authority of the 107 legacy Markdown documents.
"""
from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
import re
import unittest
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
CATALOG = DOCS / "documentation-catalog-v0.1.json"
AREAS = frozenset({
    "navigation", "architecture", "quality", "integrations", "governance",
    "contracts", "operations", "experiments", "evidence", "decisions",
})
STAGES = frozenset({
    "STABLE_ENTRYPOINT", "RETAIN_CURRENT_DIRECTORY",
    "CANDIDATE_REQUIRES_BACKLINK_AUDIT",
})
STABLE = frozenset({
    "docs/README.md", "docs/architecture.md",
    "docs/engineering-principles.md", "docs/repository-structure.md",
    "docs/mechanical-pipeline.md", "docs/python-package.md",
})
LINK = re.compile(r"(?<!!)\[[^\]\n]+\]\(([^)\s]+)\)")
HTML_LINK = re.compile(r'<a\s+[^>]*href=["\']([^"\']+)["\']', re.I)


def _prose(markdown: str) -> str:
    output: list[str] = []
    inside = False
    for line in markdown.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            inside = not inside
        elif not inside:
            output.append(line)
    if inside:
        raise ValueError("unclosed Markdown fence")
    return "\n".join(output)


class DocumentationInformationArchitectureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        cls.by_path = {item["path"]: item
                       for item in cls.catalog["documents"]}

    def test_complete_exact_tracked_markdown_population(self) -> None:
        docs = self.catalog["documents"]
        self.assertEqual(self.catalog["schema_version"], "0.1")
        self.assertRegex(self.catalog["source_commit"], r"^[0-9a-f]{40}$")
        self.assertEqual(self.catalog["initial_markdown_count"], 107)
        self.assertEqual(len(self.by_path), len(docs), "duplicate catalog paths")
        observed = {
            p.relative_to(ROOT).as_posix() for p in DOCS.rglob("*.md")
            if p.is_file()
        }
        self.assertEqual(set(self.by_path), observed,
                         "every Markdown requires explicit owner-area routing")
        self.assertEqual(len(observed), 109, "Phase 1 adds only portal and policy")

    def test_authority_review_and_move_decision_are_not_assumed(self) -> None:
        for item in self.catalog["documents"]:
            with self.subTest(path=item["path"]):
                self.assertEqual(
                    set(item),
                    {"path", "area", "candidate_directory",
                     "disposition", "authority_review"},
                )
                path = item["path"]
                target = item["candidate_directory"]
                self.assertTrue(path.startswith("docs/") and path.endswith(".md"))
                self.assertEqual(str(PurePosixPath(path)), path)
                self.assertEqual(item["authority_review"], "NOT_EVALUATED")
                self.assertIn(item["area"], AREAS)
                self.assertIn(item["disposition"], STAGES)
                self.assertTrue(target.startswith("docs/") and target.endswith("/"))
                self.assertNotIn("..", PurePosixPath(target).parts)
                stage = item["disposition"]
                if stage == "STABLE_ENTRYPOINT":
                    self.assertIn(path, STABLE)
                    self.assertEqual(target, "docs/")
                elif stage == "RETAIN_CURRENT_DIRECTORY":
                    self.assertEqual(target, str(PurePosixPath(path).parent) + "/")
                else:
                    self.assertEqual(str(PurePosixPath(path).parent), "docs")
                    self.assertNotEqual(target, "docs/")
        self.assertEqual(
            {x["path"] for x in self.catalog["documents"]
             if x["disposition"] == "STABLE_ENTRYPOINT"}, STABLE
        )

    def test_representative_architecture_and_contract_roles(self) -> None:
        expected = {
            "docs/architecture-assessment-v0.1.md": "architecture",
            "docs/semantic-architecture-ontology.md": "architecture",
            "docs/naming-official-policy-v05.md": "quality",
            "docs/engineering-principles.md": "quality",
            "docs/pinned-dafny-formal-conformance.md": "integrations",
            "docs/contract-taxonomy-and-composition-v0.1.md": "contracts",
            "docs/schema-composition-pilot-v0.1.md": "contracts",
            "docs/adr/0001-contract-authority-and-versioning.md": "decisions",
            "docs/samuel/220-controller-preflight.md": "operations",
            "docs/experiments/README.md": "experiments",
        }
        for path, area in expected.items():
            with self.subTest(path=path):
                self.assertEqual(self.by_path[path]["area"], area)
        self.assertEqual(
            self.by_path["docs/architecture-assessment-v0.1.md"]
            ["candidate_directory"], "docs/architecture/analysis/"
        )
        self.assertEqual(
            self.by_path["docs/semantic-architecture-ontology.md"]
            ["candidate_directory"], "docs/architecture/semantic/"
        )

    def test_new_portal_and_policy_local_links_resolve(self) -> None:
        for source in (DOCS / "README.md",
                       DOCS / "governance/documentation-architecture-v0.1.md"):
            text = _prose(source.read_text(encoding="utf-8"))
            self.assertIn("# ", text)
            links = [*LINK.findall(text), *HTML_LINK.findall(text)]
            self.assertGreater(len(links), 3)
            for href in links:
                with self.subTest(source=source.name, target=href):
                    uri = urlsplit(href)
                    if uri.scheme in ("https", "mailto"):
                        continue
                    self.assertFalse(uri.scheme or uri.netloc,
                                     "unexpected local-link scheme")
                    if not uri.path:
                        continue
                    resolved = (source.parent / unquote(uri.path)).resolve()
                    self.assertTrue(resolved.is_relative_to(ROOT))
                    self.assertTrue(resolved.exists(), f"missing target: {href}")

    def test_renaming_cannot_be_mistaken_for_completed_migration(self) -> None:
        policy = (
            DOCS / "governance/documentation-architecture-v0.1.md"
        ).read_text(encoding="utf-8")
        portal = (DOCS / "README.md").read_text(encoding="utf-8")
        self.assertIn("an HTTP redirect", policy)
        self.assertIn("NOT_EVALUATED", policy)
        self.assertIn("not claimed as completed migrations", portal.lower())
        candidates = [
            d for d in self.catalog["documents"]
            if d["disposition"] == "CANDIDATE_REQUIRES_BACKLINK_AUDIT"
        ]
        self.assertGreaterEqual(len(candidates), 80)


if __name__ == "__main__":
    unittest.main()
