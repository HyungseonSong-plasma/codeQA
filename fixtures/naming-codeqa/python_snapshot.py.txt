"""Single-pass Python parsing and caller-owned content-addressed AST reuse.

The cache holds parsed syntax only. Every analysis rebuilds snapshot-level
bindings, relationships and verdicts, so unchanged source text cannot leave
stale cross-file dependency targets after another file changes.
"""
from __future__ import annotations

import ast
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256


@dataclass(frozen=True, slots=True)
class ParsedFile:
    path: str
    digest: str
    tree: ast.Module | None
    syntax_error: str | None = None


@dataclass(frozen=True, slots=True)
class ParsedSnapshot:
    files: tuple[ParsedFile, ...]  # parsed successfully
    unprocessed: tuple[tuple[str, str], ...]
    diagnostics: tuple[dict[str, str], ...]
    parse_count: int
    cache_hits: int

    @property
    def analyzed_paths(self) -> tuple[str, ...]:
        return tuple(item.path for item in self.files)


class PythonParseCache:
    """Opt-in, non-global cache; callers control reuse and lifetime."""

    def __init__(self, max_entries: int = 512) -> None:
        if type(max_entries) is not int or max_entries < 1:
            raise ValueError("max_entries must be a positive integer")
        self.max_entries = max_entries
        self._entries: OrderedDict[tuple[str, str], ParsedFile] = OrderedDict()

    def parse(self, path: str, source: str) -> tuple[ParsedFile, bool]:
        digest = sha256(source.encode("utf-8")).hexdigest()
        key = (path, digest)
        if key in self._entries:
            self._entries.move_to_end(key)
            return self._entries[key], True
        try:
            result = ParsedFile(path, digest, ast.parse(source, filename=path))
        except SyntaxError as exc:
            result = ParsedFile(path, digest, None, exc.msg)
        self._entries[key] = result
        if len(self._entries) > self.max_entries:
            self._entries.popitem(last=False)
        return result, False


def parse_python_snapshot(
    sources: Mapping[str, str], *, cache: PythonParseCache | None = None,
) -> ParsedSnapshot:
    if not isinstance(sources, Mapping) or not all(
        isinstance(path, str) and isinstance(text, str)
        for path, text in sources.items()
    ):
        raise TypeError("sources must map relative paths to Python source strings")

    parser = cache if cache is not None else PythonParseCache()
    files: list[ParsedFile] = []
    unprocessed: list[tuple[str, str]] = []
    diagnostics: list[dict[str, str]] = []
    parses = hits = 0

    for path in sorted(sources):
        if not path.endswith(".py"):
            unprocessed.append((path, "unsupported_extension"))
            continue
        result, hit = parser.parse(path, sources[path])
        hits += int(hit)
        parses += int(not hit)
        if result.syntax_error is not None:
            unprocessed.append((path, "syntax_error"))
            diagnostics.append({
                "severity": "error", "code": "PYTHON_SYNTAX_ERROR",
                "message": result.syntax_error, "path": path,
            })
        else:
            files.append(result)

    return ParsedSnapshot(
        files=tuple(files), unprocessed=tuple(unprocessed),
        diagnostics=tuple(diagnostics), parse_count=parses, cache_hits=hits,
    )


class PythonAnalysisCache:
    """Opt-in cache of parsed ASTs and file-local CCG extraction facts.

    Source content hashes are keys, and all snapshot-wide module bindings,
    semantic validation, verdicts and dependency links are rebuilt per run.
    """

    def __init__(self, max_entries: int = 512) -> None:
        self.parsing = PythonParseCache(max_entries=max_entries)
        self.max_entries = max_entries
        self.graph_facts: OrderedDict[
            tuple[str, str], tuple[tuple[dict, ...], tuple[dict, ...]]
        ] = OrderedDict()

    def clear(self) -> None:
        """Release caller-owned ASTs and local extraction facts."""
        self.parsing._entries.clear()
        self.graph_facts.clear()
