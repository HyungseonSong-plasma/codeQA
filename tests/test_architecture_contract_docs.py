"""Guard canonical design docs against drift from shipped v0.1 contracts.

The mandatory layout workflow discovers this test without another workflow.
Checks include resolved normative references, all P1-P8 statuses, existing
schema authority and pinned independent reproduction evidence.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import tomllib
import unittest
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
DOCS = (
    "docs/architecture.md",
    "docs/engineering-principles.md",
    "docs/adr/0001-contract-authority-and-versioning.md",
    "docs/adr/0002-repository-policy-as-data.md",
    "docs/adr/0003-evidence-coverage-and-verdicts.md",
)
PRINCIPLES = {
    "P1": "MECHANICAL_HEURISTIC",
    "P2": "NOT_EVALUATED",
    "P3": "MECHANICAL_HEURISTIC",
    "P4": "COMPANION_POLICY_REVIEW",
    "P5": "NOT_EVALUATED",
    "P6": "NOT_EVALUATED",
    "P7": "NOT_EVALUATED",
    "P8": "COMPANION_POTENTIAL_ONLY",
}
FIELDS = (
    "**Status:**",
    "**Automated evidence now:**",
    "**Context required:**",
    "**False-positive / negative control:**",
    "**Applicability/profile:**",
    "**Next evidence gate:**",
)
LINK_RE = re.compile(r"(?<!!)\[[^\]\n]+\]\(([^)\s]+)(?:\s+[^)]+)?\)")


def _prose(text: str) -> str:
    """Skip fenced code: examples are not the normative link inventory."""
    output = []
    inside = False
    for line in text.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            inside = not inside
            continue
        if not inside:
            output.append(line)
    if inside:
        raise AssertionError("unclosed code fence in architecture document")
    return "\n".join(output)


class ArchitectureDocumentationTests(unittest.TestCase):
    def read(self, path: str) -> str:
        return (ROOT / path).read_text(encoding="utf-8")

    def test_every_normative_local_reference_resolves_in_repo(self) -> None:
        for name in (*DOCS, "README.md"):
            prose = _prose(self.read(name))
            for match in LINK_RE.finditer(prose):
                with self.subTest(source=name, reference=match.group(1)):
                    uri = match.group(1)
                    split = urlsplit(uri)
                    if split.scheme in {"http", "https", "mailto"}:
                        continue
                    self.assertFalse(split.scheme, "unknown URL scheme")
                    if not split.path:
                        continue  # local heading anchor; not another file
                    target = (ROOT / name).parent.joinpath(unquote(split.path)).resolve()
                    self.assertTrue(target.is_relative_to(ROOT), f"unsafe link: {uri}")
                    self.assertTrue(target.is_file(), f"missing normative reference: {uri}")

    def test_all_eight_principles_have_exact_status_and_negative_controls(self) -> None:
        text = _prose(self.read("docs/engineering-principles.md"))
        sections = re.split(r"(?=^### P[1-8] — )", text, flags=re.MULTILINE)
        mapped = {}
        for section in sections:
            match = re.match(r"^### (P[1-8]) — ([^\n]+)", section)
            if not match:
                continue
            principle = match.group(1)
            self.assertNotIn(principle, mapped, "duplicate P1–P8 heading")
            mapped[principle] = section
            for field in FIELDS:
                self.assertIn(field, section, (principle, field))
            self.assertIn(
                f"**Status:** `{PRINCIPLES[principle]}`", section,
                "principle status drifted from implemented evidence",
            )
        self.assertEqual(set(mapped), set(PRINCIPLES))
        self.assertEqual(len(mapped), 8)
        self.assertIn("P2 and P4–P8 as unsupported", text)
        self.assertIn("PASS", text)
        self.assertIn("NOT_EVALUATED", text)

    def test_architecture_separates_five_facts_and_samuel_ownership(self) -> None:
        text = self.read("docs/architecture.md")
        for concept in ("**Source Snapshot**", "**Canonical Code Graph (CCG)**",
                        "**Measured Finding**", "**Semantic Judgment**", "**Verdict**"):
            self.assertIn(concept, text)
        self.assertIn("chatgpt-operation", text)
        self.assertIn("snapshot", text.lower())
        self.assertIn("unresolved", text)
        self.assertIn("PASS", text)
        self.assertIn("NOT_EVALUATED", text)
        self.assertIn("P1/P3", text)
        self.assertIn("analysis=LIMITED", text)

    def test_adr_authority_and_resource_registry_match_actual_schemas(self) -> None:
        registry = tomllib.loads(self.read("pyproject.toml"))["tool"]["codeqa"]["resources"]
        expected = {
            "ccg_schema": ("contracts/ccg/graph-v0.1.schema.json",
                           "urn:codeqa:ccg:graph:v0.1"),
            "adapter_capability_schema": (
                "contracts/adapters/capability-v0.1.schema.json",
                "urn:codeqa:adapter:capability:v0.1",
            ),
            "qa_result_schema": ("contracts/qa/result-v0.1.schema.json",
                                 "urn:codeqa:qa:result:v0.1"),
            "qa_delta_schema": ("contracts/qa/delta-v0.1.schema.json",
                                "urn:codeqa:qa:delta:v0.1"),
        }
        for rid, (path, urn) in expected.items():
            with self.subTest(resource=rid):
                self.assertEqual(registry[rid], path)
                self.assertEqual(json.loads(self.read(path))["$id"], urn)
        decision = self.read("docs/adr/0001-contract-authority-and-versioning.md")
        self.assertIn("**Status:** Accepted", decision)
        self.assertIn("docs/contracts/ccg-0.1.md", decision)
        self.assertIn("relocated", decision)
        self.assertIn("contracts/ccg/", decision)
        self.assertFalse((ROOT / "docs/contracts/ccg-0.1.md").exists())
        for entry in DOCS[2:]:
            self.assertIn("**Status:** Accepted", self.read(entry))

    def test_documented_mechanical_scope_matches_shipped_code(self) -> None:
        mechanical = self.read("src/codeqa/evaluation/mechanical.py")
        public = self.read("src/codeqa/evaluation/qa_result.py")
        principles = self.read("docs/engineering-principles.md")
        for expected in ("function_span_review", "outgoing_call_sites_review"):
            self.assertIn(expected, mechanical)
            self.assertIn(expected, public)
            self.assertIn(expected, principles)
        self.assertIn("for i in (2, 4, 5, 6, 7, 8)", public)
        self.assertIn("descriptive", self.read("docs/architecture.md"))
        self.assertIn("descriptive", self.read("docs/engineering-principles.md"))

    def test_pinned_reference_evidence_is_real_not_asserted_runtime(self) -> None:
        text = self.read("docs/architecture.md")
        manifest = json.loads(self.read("fixtures/samuel/provenance.json"))
        samuel_sha = manifest["commit_sha"]
        self.assertRegex(samuel_sha, r"^[0-9a-f]{40}$")
        self.assertIn(samuel_sha, text)
        historical = "6a6676e70ed60f440cfc00a878f24ef6ee2b91a5"
        self.assertIn(historical, text)
        self.assertIn(historical, self.read("docs/self-audit.md"))
        moose = "1977ad5559e5aa7a1c8d04c83735c15e007130d5"
        self.assertIn(moose, text)
        self.assertIn(moose, self.read(".github/workflows/moose-test-audit.yml"))
        self.assertIn("not proof", text.lower())
        self.assertIn("not a", self.read("docs/engineering-principles.md").lower())


if __name__ == "__main__":
    unittest.main()
