"""Caller-scoped mixed-language coverage reconciliation, not source discovery.

A report only merges independently validated CCGs from one *identical* pinned
snapshot, with language adapter capabilities explicitly declared. Unavailable
Rust/C++/Fortran parsers remain unsupported, never silently analyzed.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

from jsonschema import Draft202012Validator

from codeqa.adapters.capability import validate_adapter_capability
from codeqa.core import Graph


class SourceSelectionError(ValueError):
    """Invalid source inventory or unsupported/misrepresented CCG coverage."""


def _safe_path(path: str) -> bool:
    return (isinstance(path, str) and bool(path) and not path.startswith("/")
            and "\\" not in path and "\x00" not in path
            and not (len(path) >= 2 and path[0].isalpha() and path[1] == ":")
            and all(segment not in ("", ".", "..") for segment in path.split("/")))


def validate_source_selection(
    manifest: Mapping[str, Any], schema: Mapping[str, Any],
) -> dict[str, Any]:
    Draft202012Validator.check_schema(schema)
    errors = sorted(Draft202012Validator(schema).iter_errors(manifest),
                    key=lambda e: (str(list(e.absolute_path)), e.message))
    if errors:
        raise SourceSelectionError("invalid selection schema: " + errors[0].message)
    repo = manifest["snapshot"]["repository"]
    if (len(repo.split("/")) != 2 or
            any(not part or part in (".", "..") for part in repo.split("/"))):
        raise SourceSelectionError("invalid repository identity")
    paths = [item["path"] for item in manifest["files"]]
    if not all(_safe_path(path) for path in paths) or len(set(paths)) != len(paths):
        raise SourceSelectionError("invalid or duplicated source selection path")
    for item in manifest["files"]:
        reason = item.get("exclusion_reason")
        if item["selection"] == "excluded" and not reason:
            raise SourceSelectionError("exclusion requires a concrete reason")
        if item["selection"] == "included" and reason is not None:
            raise SourceSelectionError("included path cannot claim an exclusion")
    return dict(manifest)


@dataclass(frozen=True, slots=True)
class SourceOutcome:
    path: str
    language: str
    category: str
    status: str  # analyzed | unprocessed | unsupported | excluded
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class SourceCoverageReport:
    snapshot_id: str
    files: tuple[SourceOutcome, ...]
    selected_status: str  # complete | partial | none, for explicitly included files
    inventory_confidence: str  # caller_attested | not_attested
    analyzed_languages: tuple[str, ...]
    unsupported_languages: tuple[str, ...]
    schema_version: str = "0.1"
    assurance: str = "SELECTED_FILES_ONLY_NOT_A_REPOSITORY_QUALITY_VERDICT"

    def to_document(self) -> dict[str, Any]:
        return asdict(self)


def aggregate_source_coverage(
    manifest: Mapping[str, Any],
    *,
    selection_schema: Mapping[str, Any],
    capabilities: Mapping[str, Mapping[str, Any]],
    capability_schema: Mapping[str, Any],
    graphs: Mapping[str, Graph],
) -> SourceCoverageReport:
    """Reconcile exact snapshot-labeled CCG facts with caller selection.

    Caller-acquired source inventory and Git commit identity are declarations,
    not independently authenticated here. No files or repositories are read.
    """
    selected = validate_source_selection(manifest, selection_schema)
    snapshot = selected["snapshot"]
    snapshot_id = f"git:{snapshot['repository']}@{snapshot['commit_sha']}"
    known = {entry["path"]: entry for entry in selected["files"]}
    supported: dict[str, dict[str, Any]] = {}
    for language, declaration in capabilities.items():
        valid = validate_adapter_capability(declaration, capability_schema)
        if valid["adapter"]["language"] != language:
            raise SourceSelectionError("capability language key mismatch")
        if valid["adapter"]["parser"]["execution"] != "syntax_only":
            raise SourceSelectionError("only syntax-only adapters supported in v0.1 aggregation")
        if valid["output"]["graph_contract"] != "CCG:0.1":
            raise SourceSelectionError("unsupported graph version")
        supported[language] = valid

    analyzed: set[str] = set()
    unprocessed: dict[str, str] = {}
    for language, graph in graphs.items():
        if language not in supported or not isinstance(graph, Graph):
            raise SourceSelectionError("graph supplied without a declared supported adapter")
        if graph.snapshot.id != snapshot_id:
            raise SourceSelectionError("CCG graph and caller snapshot identity differ")
        expected = {
            item["path"] for item in selected["files"]
            if item["language"] == language and item["selection"] == "included"
        }
        covered = set(graph.coverage.analyzed_paths)
        excluded = {entry.path: entry.reason for entry in graph.coverage.unprocessed}
        if (not (covered | set(excluded)) <= expected
                or covered & set(excluded)
                or any(path in analyzed or path in unprocessed
                       for path in covered | set(excluded))):
            raise SourceSelectionError("cross-language graph has unselected/duplicate path")
        suffixes = supported[language]["input"]["extensions"]
        if any(not path.endswith(tuple(suffixes))
               for path in covered | set(excluded)):
            raise SourceSelectionError("graph path outside declared adapter extensions")
        for node in graph.nodes:
            if node.provenance.producer == "manual-rust-ccg-golden":
                raise SourceSelectionError("manually curated Rust golden is not parser output")
        analyzed.update(covered)
        unprocessed.update(excluded)
    results: list[SourceOutcome] = []
    for path, item in sorted(known.items()):
        language = item["language"]
        if item["selection"] == "excluded":
            status, reason = "excluded", item["exclusion_reason"]
        elif language not in supported or not path.endswith(
            tuple(supported[language]["input"]["extensions"])
        ):
            status, reason = "unsupported", "no_declared_compatible_adapter"
        elif path in analyzed:
            status, reason = "analyzed", None
        elif path in unprocessed:
            status, reason = "unprocessed", unprocessed[path]
        else:
            status, reason = "unprocessed", "adapter_not_executed_or_path_missing"
        results.append(SourceOutcome(path, language, item["category"], status, reason))
    included = [x for x in results if x.status != "excluded"]
    n = sum(x.status == "analyzed" for x in included)
    # Zero included files means zero evaluated coverage, not a complete audit.
    status = "complete" if included and n == len(included) else "partial" if n else "none"
    return SourceCoverageReport(
        snapshot_id=snapshot_id,
        files=tuple(results),
        selected_status=status,
        inventory_confidence=(
            "caller_attested" if selected["discovery"]["inventory_complete"]
            else "not_attested"
        ),
        analyzed_languages=tuple(sorted({x.language for x in results if x.status == "analyzed"})),
        unsupported_languages=tuple(sorted({x.language for x in results if x.status == "unsupported"})),
    )
