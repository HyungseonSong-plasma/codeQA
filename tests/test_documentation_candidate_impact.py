"""Issue #288: read-only, catalog-driven relocation impact inventory.

Reuse existing documentation link, anchor, literal and git inventory parsers.
Scores are triage only, never semantic, Raw, URL, or merge PASS.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import json
import posixpath
import subprocess
import unittest
from urllib.parse import unquote, urlsplit

from test_documentation_reference_audit import (
    ROOT, DOC_LITERAL, heading_anchors, links_from_markdown, tracked_paths,
)

CATALOG = ROOT / "docs/documentation-catalog-v0.1.json"
CANDIDATE = "CANDIDATE_REQUIRES_BACKLINK_AUDIT"
UNKNOWN = "UNKNOWN"


def _local_target(source: str, href: str) -> tuple[str | None, str | None]:
    parsed = urlsplit(href)
    if parsed.scheme or parsed.netloc:
        return None, None
    if parsed.path.startswith("/"):
        # Site-root absolute paths are not reliable repository paths.
        return None, unquote(parsed.fragment) if parsed.fragment else None
    path = unquote(parsed.path)
    resolved = (posixpath.normpath(posixpath.join(posixpath.dirname(source), path))
                if path else source)
    return resolved, unquote(parsed.fragment) if parsed.fragment else None


def _priority(row: dict) -> tuple[int, str]:
    """Measured migration effort, not proof of semantic or consumer safety."""
    measured = (
        12 * row["inbound_markdown_links"]
        + 8 * row["literal_path_references"]
        + 4 * row["outbound_local_links"]
        + 5 * row["inbound_fragment_links"]
        + 8 * row["raw_url_mentions"]
        + row["heading_count"]
        + row["outbound_external_links"]
    )
    return measured, row["path"]


def candidate_impact_report() -> dict:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    rows = [d for d in catalog["documents"] if d["disposition"] == CANDIDATE]
    known = {d["path"]: d for d in rows}
    if len(known) != len(rows):
        raise AssertionError("Duplicate candidate paths")

    tracked = tracked_paths()
    incoming: dict[str, list[dict]] = defaultdict(list)
    literals: dict[str, list[dict]] = defaultdict(list)
    raw_mentions: dict[str, list[dict]] = defaultdict(list)
    outgoing: dict[str, list[dict]] = defaultdict(list)
    external: dict[str, list[dict]] = defaultdict(list)
    excluded: list[str] = []
    decoded: dict[str, str] = {}

    for source in sorted(tracked):
        file = ROOT / source
        if not file.is_file():
            excluded.append(source)
            continue
        try:
            data = file.read_bytes()
            if b"\x00" in data:
                excluded.append(source)
                continue
            decoded[source] = data.decode("utf-8")
        except (UnicodeError, OSError):
            excluded.append(source)
            continue

    for source, content in sorted(decoded.items()):
        for line_number, line in enumerate(content.splitlines(), 1):
            for match in DOC_LITERAL.finditer(line):
                path = match.group()
                if path in known and source != path:
                    entry = {"source": source, "line": line_number}
                    literals[path].append(entry)
                    if "raw.githubusercontent.com" in line:
                        raw_mentions[path].append(entry)

        if not source.endswith(".md"):
            continue
        for line_number, href in links_from_markdown(content):
            uri = urlsplit(href)
            if uri.scheme or uri.netloc:
                if source in known:
                    external[source].append({"line": line_number, "href": href})
                continue
            target, fragment = _local_target(source, href)
            item = {"source": source, "line": line_number, "href": href,
                    "target": target, "fragment": fragment}
            if target in known and target != source:
                incoming[target].append(item)
            if source in known:
                outgoing[source].append(item)

    result: list[dict] = []
    for path, meta in sorted(known.items()):
        if path not in decoded:
            raise AssertionError(f"Candidate missing or non-text: {path}")
        raw = decoded[path]
        inbound = incoming[path]
        refs = literals[path]
        local_out = outgoing[path]
        external_out = external[path]
        heading = sorted(heading_anchors(raw))
        missing = [link for link in local_out
                   if link["target"] is not None
                   and link["target"] not in tracked
                   and not (ROOT / link["target"]).is_dir()]
        row = {
            "path": path,
            "candidate_directory": meta["candidate_directory"],
            "area": meta["area"],
            "authority_role": meta["authority_role"],
            "authority_review": meta["authority_review"],
            "inbound_markdown_links": len(inbound),
            "inbound_markdown_sources": sorted({i["source"] for i in inbound}),
            "inbound_fragment_links": sum(bool(i["fragment"]) for i in inbound),
            "inbound_references": inbound,
            "outbound_local_links": len(local_out),
            "outbound_local_references": local_out,
            "outbound_missing_local_links": missing,
            "outbound_root_relative_links_unresolved": [
                link for link in local_out if link["target"] is None
            ],
            "outbound_external_links": len(external_out),
            "outbound_external_references": external_out,
            "literal_path_references": len(refs),
            "literal_references": refs,
            "raw_url_mentions": len(raw_mentions[path]),
            "raw_url_references": raw_mentions[path],
            "raw_consumer_population": UNKNOWN,
            "raw_byte_compatibility_after_move": "NOT_EVALUATED",
            "external_backlinks": UNKNOWN,
            "external_url_verification": "NOT_EVALUATED",
            "heading_count": len(heading),
            "heading_slugs": heading,
            "semantic_review": meta["authority_review"],
            "document_bytes": len(raw.encode("utf-8")),
        }
        row["measured_effort_score"] = _priority(row)[0]
        result.append(row)

    result.sort(key=_priority)
    checkout = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    return {
        "schema_version": "doc288-candidate-impact-v0.1",
        "tested_checkout": checkout,
        "catalog_source_commit": catalog.get("source_commit"),
        "candidate_count": len(result),
        "tracked_files": len(tracked),
        "decoded_text_files": len(decoded),
        "excluded_or_unreadable_files": excluded,
        "areas": dict(sorted(Counter(r["area"] for r in result).items())),
        "candidate_files_with_missing_local_links": sum(
            bool(r["outbound_missing_local_links"]) for r in result),
        "measurement_notes": [
            "Parser logic is imported from test_documentation_reference_audit.py.",
            "Inbound links mean tracked Markdown hyperlink references; not third-party backlinks.",
            "Literal references require a qualified docs/*.md or docs/*.json token.",
            "External links are inventoried but not network-verified.",
            "Raw consumer population, external backlinks and semantic truth remain UNKNOWN/NOT_EVALUATED.",
            "A low effort score is not a semantic, external URL, or migration approval.",
            "Exact CI checkout may be a synthetic PR merge commit, not PR branch HEAD.",
        ],
        "candidates": result,
    }


class DocumentationCandidateImpactTests(unittest.TestCase):
    def test_all_catalog_candidates_are_scanned_read_only(self) -> None:
        report = candidate_impact_report()
        self.assertEqual(report["candidate_count"], len(report["candidates"]))
        self.assertGreater(report["candidate_count"], 0)
        self.assertEqual(report["candidate_files_with_missing_local_links"], 0)
        for row in report["candidates"]:
            self.assertEqual(row["raw_consumer_population"], UNKNOWN)
            self.assertEqual(row["external_backlinks"], UNKNOWN)
            self.assertEqual(row["external_url_verification"], "NOT_EVALUATED")
            self.assertEqual(row["semantic_review"], "NOT_EVALUATED")
        compact = {k: v for k, v in report.items() if k != "candidates"}
        print("DOC288_CANDIDATE_IMPACT_SUMMARY " + json.dumps(compact, sort_keys=True))
        for row in report["candidates"]:
            print("DOC288_CANDIDATE_IMPACT_ITEM " + json.dumps(row, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
