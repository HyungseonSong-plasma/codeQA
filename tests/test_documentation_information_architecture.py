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

from codeqa.infrastructure.git import GitReader


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
CATALOG = DOCS / "documentation-catalog-v0.1.json"
AREAS = frozenset({
    "navigation", "architecture", "quality", "integrations", "governance",
    "contracts", "operations", "experiments", "decisions",
})
AUTHORITY_ROLES = frozenset({
    "NAVIGATION_INDEX", "ACCEPTED_ADR", "CONTRACT_EXPLANATION",
    "POLICY_EXPLANATION", "SCOPED_ADOPTION_POLICY",
    "ADOPTED_ARCHITECTURE_GUIDE", "SCOPED_TECHNICAL_GUIDE",
    "OPERATIONAL_RUNBOOK", "PROPOSED_DESIGN", "HISTORICAL_EVIDENCE",
    "SCOPED_DECISION_RECORD", "REVIEW_EVIDENCE", "LEGACY_PATH_ALIAS",
})
RESPONSIBLE_BOUNDARIES = frozenset({
    "DOCUMENTATION_NAVIGATION", "FOUNDATION_ADR",
    "SEMANTIC_ARCHITECTURE", "ARCHITECTURE_EVALUATION",
    "ARCHITECTURE_FOUNDATION_AND_PIPELINE", "NAMING_QUALITY",
    "DEPENDENCY_QUALITY", "MECHANICAL_QUALITY",
    "CPP_MOOSE_INTEGRATION", "RUST_INTEGRATION",
    "EXTERNAL_TOOL_INTEGRATION", "PYTHON_ADAPTER_AND_SDK",
    "CONTRACTS_AND_SEMANTIC_VALIDATION", "SAMUEL_CONSUMER_OPERATIONS",
    "SAMUEL_INTEGRATION_PROVENANCE", "EXPERIMENTAL_EVIDENCE",
    "DOCUMENTATION_GOVERNANCE", "WORKFLOW_GOVERNANCE",
    "EXTERNAL_EVIDENCE_GOVERNANCE", "REPOSITORY_GOVERNANCE",
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
            path for path in GitReader(ROOT).tracked_paths()
            if path.startswith("docs/") and path.endswith(".md")
        }
        self.assertEqual(set(self.by_path), observed,
                         "every tracked Markdown requires a catalog entry")
        self.assertTrue(all((ROOT / path).is_file() for path in observed))

    def test_authority_review_and_move_decision_are_not_assumed(self) -> None:
        for item in self.catalog["documents"]:
            with self.subTest(path=item["path"]):
                required = {"path", "area", "candidate_directory",
                            "disposition", "authority_review",
                            "authority_role", "responsible_boundary",
                            "role_review"}
                optional = {"lifecycle", "authority", "evidence_revision",
                            "primary_owner", "canonical_location",
                            "external_deep_link_policy", "review_revision",
                            "review_issue", "stable_reason", "status_labels"}
                self.assertTrue(required <= set(item))
                self.assertTrue(set(item) <= required | optional)
                path = item["path"]
                target = item["candidate_directory"]
                self.assertTrue(path.startswith("docs/") and path.endswith(".md"))
                self.assertEqual(str(PurePosixPath(path)), path)
                self.assertIn(item["authority_review"],
                              {"NOT_EVALUATED", "REVIEW_REQUIRED",
                               "REVIEWED_WITH_EVIDENCE"})
                if item["authority_review"] == "REVIEWED_WITH_EVIDENCE":
                    self.assertRegex(item.get("review_revision", ""),
                                     r"^[0-9a-f]{40}$")
                    self.assertTrue(item.get("primary_owner"))
                    self.assertRegex(item.get("review_issue", ""),
                                     r"^https://github[.]com/.+/(issues|pull)/[0-9]+$")
                self.assertIn(item["area"], AREAS)
                self.assertEqual(item["role_review"],
                                 "SCOPE_AND_PRIMARY_TOPIC_REVIEWED")
                self.assertIn(item["authority_role"], AUTHORITY_ROLES)
                self.assertIn(item["responsible_boundary"],
                              RESPONSIBLE_BOUNDARIES)
                if item["area"] == "decisions":
                    self.assertEqual(item["authority_role"], "ACCEPTED_ADR")
                    self.assertEqual(item["responsible_boundary"],
                                     "FOUNDATION_ADR")
                if item["authority_role"] == "CONTRACT_EXPLANATION":
                    self.assertEqual(item["area"], "contracts")
                if item["authority_role"] == "LEGACY_PATH_ALIAS":
                    expected_aliases = {
                        move["legacy"]: move["canonical"]
                        for move in json.loads(
                            (DOCS / "governance/document-relocations-v0.1.json")
                            .read_text(encoding="utf-8")
                        )["moves"]
                    }
                    self.assertIn(path, expected_aliases)
                    self.assertEqual(item["area"], "navigation")
                    self.assertEqual(item["responsible_boundary"], "DOCUMENTATION_NAVIGATION")
                    self.assertEqual(item["canonical_location"],
                                     expected_aliases[path])
                    self.assertEqual(item["authority_review"], "NOT_EVALUATED")
                if item["authority_role"] == "NAVIGATION_INDEX":
                    self.assertIn(item["path"],
                                  {"docs/README.md", "docs/experiments/README.md"})
                if item["authority_role"] == "REVIEW_EVIDENCE":
                    self.assertIn(item["path"], {
                        "docs/governance/document-authority-review-v0.1.md",
                        "docs/governance/documentation-reference-audit-v0.1.md",
                    })
                self.assertIn(item["disposition"], STAGES)
                self.assertTrue(target.startswith("docs/") and target.endswith("/"))
                self.assertNotIn("..", PurePosixPath(target).parts)
                stage = item["disposition"]
                if stage == "STABLE_ENTRYPOINT":
                    self.assertEqual(target, str(PurePosixPath(path).parent) + "/")
                    if path not in STABLE:
                        self.assertTrue(item.get("stable_reason"),
                                        "new stable entrypoints need a reason")
                elif stage == "RETAIN_CURRENT_DIRECTORY":
                    self.assertEqual(target, str(PurePosixPath(path).parent) + "/")
                else:
                    self.assertEqual(str(PurePosixPath(path).parent), "docs")
                    self.assertNotEqual(target, "docs/")
        self.assertTrue(STABLE.issubset(
            {x["path"] for x in self.catalog["documents"]
             if x["disposition"] == "STABLE_ENTRYPOINT"}
        ))

    def test_representative_architecture_and_contract_roles(self) -> None:
        expected = {
            "docs/architecture-assessment-v0.1.md": "architecture",
            "docs/semantic-architecture-ontology.md": "architecture",
            "docs/python-override-callback-v02-draft.md": "integrations",
            "docs/naming-official-policy-v05.md": "quality",
            "docs/engineering-principles.md": "quality",
            "docs/pinned-dafny-formal-conformance.md": "integrations",
            "docs/contract-taxonomy-and-composition-v0.1.md": "contracts",
            "docs/experiments/schema-composition-pilot-v0.1.md": "experiments",
            "docs/schema-composition-pilot-v0.1.md": "navigation",
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

    def test_boundary_decisions_do_not_promote_drafts_or_history(self) -> None:
        expected = {
            "docs/cpp-moose-naming-v02-draft.md":
                ("integrations", "docs/integrations/cpp/", "PROPOSED_DESIGN"),
            "docs/python-override-callback-v02-draft.md":
                ("integrations", "docs/integrations/python/", "PROPOSED_DESIGN"),
            "docs/experiments/schema-composition-pilot-v0.1.md":
                ("experiments", "docs/experiments/", "SCOPED_DECISION_RECORD"),
            "docs/schema-composition-pilot-v0.1.md":
                ("navigation", "docs/", "LEGACY_PATH_ALIAS"),
            "docs/historical-branch-reconciliation-2026-11-05.md":
                ("governance", "docs/governance/", "HISTORICAL_EVIDENCE"),
            "docs/naming-official-policy-v05.md":
                ("quality", "docs/quality/naming/", "SCOPED_ADOPTION_POLICY"),
            "docs/naming-official-adoption-v05-proposal.md":
                ("quality", "docs/quality/naming/", "PROPOSED_DESIGN"),
            "docs/workflow-catalog-v0.1.md":
                ("governance", "docs/governance/workflows/", "HISTORICAL_EVIDENCE"),
            "docs/architecture-assessment-design-v0.1.md":
                ("architecture", "docs/architecture/analysis/", "PROPOSED_DESIGN"),
        }
        for path, (area, directory, role) in expected.items():
            with self.subTest(path=path):
                item = self.by_path[path]
                self.assertEqual((item["area"], item["candidate_directory"],
                                  item["authority_role"]), (area, directory, role))
        self.assertTrue(all(
            item["authority_review"] != "REVIEWED_WITH_EVIDENCE"
            for item in self.catalog["documents"]
        ), "topic classification must not fake claim-level source authority")

    def test_new_portal_and_policy_local_links_resolve(self) -> None:
        for source in (DOCS / "README.md",
                       DOCS / "governance/documentation-architecture-v0.1.md",
                       DOCS / "governance/document-authority-review-v0.1.md",
                       DOCS / "governance/documentation-reference-audit-v0.1.md"):
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
        self.assertIn("A Markdown forwarding note is not an HTTP redirect",
                      policy.replace("**", ""))
        self.assertIn("NOT_EVALUATED", policy)
        self.assertIn("not claimed as completed migrations", portal.lower())
        self.assertIn("MOVE_WITH_VERIFIED_REFERENCES", policy)
        self.assertEqual(
            self.by_path["docs/python-override-callback-v02-draft.md"]
            ["candidate_directory"], "docs/integrations/python/"
        )


if __name__ == "__main__":
    unittest.main()
