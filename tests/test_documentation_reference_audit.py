"""Reproducible repository-wide local documentation link and path audit.

Audits tracked Markdown files and exact doc paths in tracked text, rather
than blindly trusting a portal. Does not contact external URL services or
attest third-party backlinks or document content truth.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from html import unescape
import json
from pathlib import Path
import re
import subprocess
import unittest
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r'!?\[[^\]\n]*\]\((<[^>]*>|[^)\s]+)')
HTML_LINK = re.compile(r'<(?:a|img)\s+[^>]*(?:href|src)=["\']([^"\']+)["\']', re.I)
REFERENCE = re.compile(r'(?<!!)\[[^\]\n]+\]\[([^\]\n]+)\]')
REFERENCE_DEF = re.compile(r'^\s{0,3}\[([^\]]+)\]:\s*(<[^>]*>|\S+)', re.M)
INLINE_CODE = re.compile(r'`+[^`\n]*`+')
FENCE = re.compile(r'^\s{0,3}(`{3,}|~{3,})')
HEADING = re.compile(r'^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$')
SETEXT = re.compile(r'^\s{0,3}(=+|-+)\s*$')
HTML_ID = re.compile(r'<(?:a|div|span)\s+[^>]*(?:id|name)=["\']([^"\']+)["\']', re.I)
DOC_LITERAL = re.compile(r'(?<![\w/])docs/[A-Za-z0-9_.\-/]+\.(?:md|json)\b')
TEXT_SUFFIXES = frozenset({".md", ".py", ".json", ".yml", ".yaml", ".toml",
                           ".txt", ".sh", ".ini", ".cfg"})


def tracked_paths() -> set[str]:
    data = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True,
                          capture_output=True).stdout
    return {entry.decode("utf-8") for entry in data.split(b"\x00") if entry}


def markdown_prose(raw: str) -> str:
    """Keep stable source line numbers while discarding fenced code samples."""
    output = []
    delimiter = ""
    for line in raw.splitlines():
        f = FENCE.match(line)
        if f:
            token = f.group(1)
            if not delimiter:
                delimiter = token[0] * len(token)
                output.append("")
                continue
            if token[0] == delimiter[0] and len(token) >= len(delimiter):
                delimiter = ""
                output.append("")
                continue
        output.append("" if delimiter else line)
    return "\n".join(output)


def heading_anchors(raw: str) -> set[str]:
    prose = markdown_prose(raw)
    counts: dict[str, int] = defaultdict(int)
    result: set[str] = set()
    lines = prose.splitlines()
    for i, line in enumerate(lines):
        match = HEADING.match(line)
        candidate = match.group(1) if match else None
        if candidate is None and i + 1 < len(lines) and SETEXT.match(lines[i+1]):
            if line.strip():
                candidate = line.strip()
        if candidate is not None:
            candidate = INLINE_CODE.sub(lambda m: m.group().strip("`"), candidate)
            candidate = unescape(re.sub(r"<[^>]+>", "", candidate))
            slug = re.sub(r"[^\w\s-]", "", candidate.lower())
            slug = re.sub(r"\s", "-", slug)
            number = counts[slug]
            counts[slug] += 1
            result.add(slug if number == 0 else f"{slug}-{number}")
    result.update(unescape(x) for x in HTML_ID.findall(prose))
    return result


def links_from_markdown(raw: str) -> list[tuple[int, str]]:
    prose = markdown_prose(raw)
    refs = {key.casefold().strip(): url.strip("<>")
            for key, url in REFERENCE_DEF.findall(prose)}
    results = []
    for lineno, line in enumerate(prose.splitlines(), start=1):
        text = INLINE_CODE.sub("", line)
        found = [x.strip("<>") for x in LINK.findall(text)]
        found.extend(HTML_LINK.findall(text))
        found.extend(refs[k.casefold().strip()] for k in REFERENCE.findall(text)
                     if k.casefold().strip() in refs)
        if REFERENCE_DEF.match(text):
            found.extend(url.strip("<>") for _, url in REFERENCE_DEF.findall(text))
        results.extend((lineno, href) for href in found)
    return results


def scan_links(paths: set[str]) -> tuple[dict, list[tuple[str, int, str, str]]]:
    markdown = sorted(p for p in paths if p.endswith(".md")
                      and (ROOT / p).is_file())
    cache: dict[str, set[str]] = {}
    inbound: Counter[str] = Counter()
    bad: list[tuple[str, int, str, str]] = []
    total = 0
    external = 0
    fragment_count = 0
    for source in markdown:
        text = (ROOT / source).read_text(encoding="utf-8")
        for lineno, href in links_from_markdown(text):
            total += 1
            uri = urlsplit(unescape(href))
            if uri.scheme in {"https", "http", "mailto"} or uri.netloc:
                external += 1
                continue
            if uri.scheme or (not uri.path and not uri.fragment):
                bad.append((source, lineno, href, "unsupported URI"))
                continue
            if uri.path.startswith("/"):
                bad.append((source, lineno, href, "repository-absolute link"))
                continue
            destination = (ROOT / source).parent / unquote(uri.path)
            destination = destination.resolve()
            if not destination.is_relative_to(ROOT):
                bad.append((source, lineno, href, "escapes repository"))
                continue
            relative = destination.relative_to(ROOT).as_posix()
            if uri.path and (relative not in paths and
                             not (destination.is_dir() and destination.exists())):
                bad.append((source, lineno, href, "missing target"))
                continue
            inbound[relative] += 1
            if uri.fragment and destination.suffix.lower() == ".md":
                fragment_count += 1
                if relative not in cache:
                    cache[relative] = heading_anchors(
                        destination.read_text(encoding="utf-8"))
                if unquote(uri.fragment) not in cache[relative]:
                    bad.append((source, lineno, href, "missing GFM fragment"))
    stats = {
        "tracked_files": len(paths),
        "markdown_files": len(markdown),
        "all_local_and_external_links": total,
        "external_urls_not_verified": external,
        "local_targets": total - external,
        "local_markdown_fragments": fragment_count,
        "distinct_inbound_targets": len(inbound),
        "docs_with_inbound": sum(1 for k in inbound if k.startswith("docs/")),
        "broken_local_references": len(bad),
        "top_inbound_paths": inbound.most_common(18),
    }
    return stats, bad


def scan_literals(paths: set[str]) -> tuple[dict, list[tuple[str, int, str]]]:
    references = []
    for path in sorted(paths):
        file = ROOT / path
        if not file.is_file() or file.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for literal in DOC_LITERAL.findall(line):
                references.append((path, lineno, literal))
    missing = [x for x in references if x[2] not in paths]
    stats = {"text_path_occurrences": len(references),
             "distinct_literal_paths": len({x[2] for x in references}),
             "missing_literal_path_occurrences": len(missing),
             "candidate_migration_references":
                 len([x for x in references if x[0] != x[2]])}
    return stats, missing


class DocumentationReferenceAuditTests(unittest.TestCase):
    def test_all_tracked_markdown_local_links_and_fragments(self):
        paths = tracked_paths()
        stats, bad = scan_links(paths)
        print("DOCUMENTATION_LINK_AUDIT", json.dumps(
            {"statistics": stats, "problems": bad[:100]}, ensure_ascii=False))
        self.assertEqual(bad, [],
                         "broken tracked Markdown local links or fragments; "
                         "see DOCUMENTATION_LINK_AUDIT output above")

    def test_embedded_docs_paths_are_enumerated_not_approved(self):
        """Literal path occurrences need semantic review before any relocation."""
        stats, missing = scan_literals(tracked_paths())
        print("DOCUMENTATION_LITERAL_REFERENCE_AUDIT", json.dumps(
            {"statistics": stats, "missing_examples": missing[:80]},
            ensure_ascii=False))
        self.assertGreater(stats["text_path_occurrences"], 0)
        # Literal paths in historical examples, negative fixtures and source
        # strings are not automatically asserted to be live resource imports.


if __name__ == "__main__":
    unittest.main()
