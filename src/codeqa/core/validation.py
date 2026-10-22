"""CCG graph schema + semantic checks, independent of resource loading and Git."""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable
import json
from typing import Any, Mapping

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from .graph import Graph, SourceLocation


@dataclass(frozen=True, slots=True)
class GraphIssue:
    code: str
    path: str
    message: str


class GraphValidationError(ValueError):
    """Invalid graph data, with machine-readable findings."""

    def __init__(self, issues: tuple[GraphIssue, ...]) -> None:
        self.issues = issues
        super().__init__(
            f"{len(issues)} CCG issue(s): {issues[0].path}: {issues[0].message}"
            if issues else "CCG validation failed"
        )


def _safe_path(path: str) -> bool:
    return (
        bool(path)
        and not path.startswith("/")
        and not (len(path) >= 2 and path[0].isalpha() and path[1] == ":")
        and "\\" not in path
        and "\x00" not in path
        and all(p not in ("", ".", "..") for p in path.split("/"))
    )


def _validate_coverage(graph: Graph, add: Callable[[str, str, str], None]) -> set[str]:
    """Check path accounting before testing facts against the covered files."""
    analyzed = set(graph.coverage.analyzed_paths)
    unprocessed = graph.coverage.unprocessed
    for index, path in enumerate(graph.coverage.analyzed_paths):
        if not _safe_path(path):
            add("invalid_path", f"coverage/analyzed_paths/{index}", "not a relative POSIX path")

    seen_unprocessed: set[str] = set()
    for index, item in enumerate(unprocessed):
        field = f"coverage/unprocessed/{index}/path"
        if not _safe_path(item.path):
            add("invalid_path", field, "not a relative POSIX path")
        if item.path in seen_unprocessed:
            add("duplicate_unprocessed", field, "unprocessed path repeated")
        if item.path in analyzed:
            add("coverage_overlap", field, "path also appears as analyzed")
        seen_unprocessed.add(item.path)

    status = graph.coverage.status
    if status == "complete" and unprocessed:
        add("coverage_status", "coverage/status", "complete cannot have unprocessed paths")
    if status == "none" and graph.coverage.analyzed_paths:
        add("coverage_status", "coverage/status", "none cannot have analyzed paths")
    if status == "none" and (graph.nodes or graph.edges):
        add("coverage_status", "coverage/status", "none cannot contain extracted facts")
    if status == "partial" and (not analyzed or not unprocessed):
        add("coverage_status", "coverage/status", "partial requires analyzed and unprocessed paths")
    return analyzed


def _validate_location(
    loc: SourceLocation | None, field: str, analyzed: set[str],
    add: Callable[[str, str, str], None], *, fact: bool = False,
) -> None:
    if loc is None:
        return
    if not _safe_path(loc.path):
        add("invalid_path", f"{field}/path", "not a relative POSIX path")
    if loc.end_line < loc.start_line:
        add("invalid_span", field, "end_line precedes start_line")
    if (
        loc.start_line == loc.end_line
        and loc.start_column is not None and loc.end_column is not None
        and loc.end_column < loc.start_column
    ):
        add("invalid_span", field, "end_column precedes start_column")
    if fact and loc.path not in analyzed:
        add("uncovered_fact", f"{field}/path", "fact path was not analyzed")


def _validate_nodes(
    graph: Graph, analyzed: set[str], add: Callable[[str, str, str], None],
) -> set[str]:
    node_ids: set[str] = set()
    for index, node in enumerate(graph.nodes):
        if node.id in node_ids:
            add("duplicate_node_id", f"nodes/{index}/id", "node ID must be unique")
        node_ids.add(node.id)
        _validate_location(node.location, f"nodes/{index}/location", analyzed, add, fact=True)
    return node_ids


def _validate_edges(
    graph: Graph, node_ids: set[str], analyzed: set[str],
    add: Callable[[str, str, str], None],
) -> None:
    for index, edge in enumerate(graph.edges):
        if edge.source not in node_ids:
            add("missing_source", f"edges/{index}/source", "edge source is not a node")
        if edge.resolution == "resolved" and edge.target not in node_ids:
            add("missing_target", f"edges/{index}/target", "resolved target is not a node")
        _validate_location(edge.location, f"edges/{index}/location", analyzed, add, fact=True)


def _validate_diagnostics(
    graph: Graph, analyzed: set[str], add: Callable[[str, str, str], None],
) -> None:
    for index, diagnostic in enumerate(graph.diagnostics):
        _validate_location(diagnostic.location, f"diagnostics/{index}/location", analyzed, add)
        if diagnostic.path is not None and not _safe_path(diagnostic.path):
            add("invalid_path", f"diagnostics/{index}/path", "not a relative POSIX path")


def validate_semantics(graph: Graph) -> tuple[GraphIssue, ...]:
    """Check graph-wide invariants in the original stable issue order.

    Assumes input has passed the supplied JSON Schema through parse_graph.
    """
    issues: list[GraphIssue] = []

    def add(code: str, path: str, message: str) -> None:
        issues.append(GraphIssue(code, path, message))

    analyzed = _validate_coverage(graph, add)
    node_ids = _validate_nodes(graph, analyzed, add)
    _validate_edges(graph, node_ids, analyzed, add)
    _validate_diagnostics(graph, analyzed, add)
    return tuple(issues)


def parse_graph(document: Mapping[str, Any], schema: Mapping[str, Any]) -> Graph:
    """Validate shape against injected schema, then validate semantic integrity."""
    try:
        Draft202012Validator.check_schema(schema)
        errors = sorted(
            Draft202012Validator(schema).iter_errors(document),
            key=lambda error: (tuple(str(v) for v in error.absolute_path), error.message),
        )
    except (SchemaError, TypeError, ValueError) as exc:
        raise GraphValidationError((GraphIssue("invalid_schema", "schema", str(exc)),)) from exc
    if errors:
        raise GraphValidationError(tuple(
            GraphIssue(
                "schema_violation",
                "/".join(str(v) for v in error.absolute_path) or "$",
                error.message,
            )
            for error in errors
        ))
    result = Graph.from_document(document)
    issues = validate_semantics(result)
    if issues:
        raise GraphValidationError(issues)
    return result


def canonical_json(graph: Graph) -> str:
    """Sort facts for deterministic encoding; callers still own stable node IDs."""
    value = graph.to_document()
    value["nodes"].sort(key=lambda n: (n["id"], json.dumps(n, sort_keys=True)))
    value["edges"].sort(key=lambda e: json.dumps(e, sort_keys=True, ensure_ascii=False))
    value["coverage"]["analyzed_paths"].sort()
    value["coverage"]["unprocessed"].sort(key=lambda x: (x["path"], x["reason"]))
    value["diagnostics"].sort(key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False))
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
