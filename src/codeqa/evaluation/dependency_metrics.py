"""Versioned *static potential* dependency metrics, no runtime import inference.

This companion consumes existing language-neutral DependencyGraph observations.
It is independent of the frozen CCG and Mechanical P1/P3 report contracts.
"""
from __future__ import annotations

from collections import Counter, defaultdict, deque
from dataclasses import asdict, dataclass
from typing import Any, Mapping

from codeqa.core.dependency import DependencyGraph


class DependencyMetricsError(ValueError):
    """Unsafe graph, invalid profile, or contradictory static source evidence."""


def _safe(path: str) -> bool:
    return (isinstance(path, str) and bool(path) and not path.startswith("/")
            and "\\" not in path and "\x00" not in path
            and not (len(path) > 1 and path[0].isalpha() and path[1] == ":")
            and all(part not in ("", ".", "..") for part in path.split("/")))


@dataclass(frozen=True, slots=True)
class DependencyMetricsProfile:
    profile_id: str
    schema_version: str
    max_out_degree_review: int
    max_cycle_nodes_review: int

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DependencyMetricsProfile":
        if not isinstance(value, Mapping) or set(value) != {
            "profile_id", "schema_version", "max_out_degree_review",
            "max_cycle_nodes_review",
        }:
            raise DependencyMetricsError("incomplete or unknown dependency profile keys")
        if (not isinstance(value["profile_id"], str) or not value["profile_id"].strip()
                or value["schema_version"] != "0.1"):
            raise DependencyMetricsError("unsupported dependency profile identity/version")
        for field in ("max_out_degree_review", "max_cycle_nodes_review"):
            if type(value[field]) is not int or value[field] < 0:
                raise DependencyMetricsError("dependency thresholds must be nonnegative integers")
        return cls(**value)


@dataclass(frozen=True, slots=True)
class FileDegrees:
    path: str
    fan_in: int
    fan_out: int
    unknown_statements: int


@dataclass(frozen=True, slots=True)
class StaticPair:
    source_path: str
    target_path: str
    statement_count: int
    conditional_or_deferred_count: int
    witness_lines: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class StaticCycle:
    nodes: tuple[str, ...]
    witness: tuple[str, ...]  # closed source->target edge sequence


@dataclass(frozen=True, slots=True)
class DependencyMetricsReport:
    snapshot_id: str
    profile_id: str
    analyzed_paths: tuple[str, ...]
    unprocessed_paths: tuple[str, ...]
    files: tuple[FileDegrees, ...]
    pairs: tuple[StaticPair, ...]
    cycles: tuple[StaticCycle, ...]
    unknown_by_reason: tuple[tuple[str, int], ...]
    flagged_out_degree: tuple[str, ...]
    flagged_cycles: tuple[tuple[str, ...], ...]
    schema_version: str = "0.1"
    interpretation: str = "STATIC_POTENTIAL_ONLY"

    def to_document(self) -> dict[str, Any]:
        value = asdict(self)
        value["unknown_by_reason"] = dict(self.unknown_by_reason)
        return value


def _cycle_witness(component: tuple[str, ...], adjacent: dict[str, set[str]]) -> tuple[str, ...]:
    """Find a deterministic, actual closed walk inside one SCC."""
    scope = set(component)
    for start in component:
        queue = deque([(start, (start,))])
        while queue:
            node, path = queue.popleft()
            for target in sorted(adjacent[node] & scope):
                if target == start:
                    return (*path, start)
                if target not in path:
                    queue.append((target, (*path, target)))
    raise DependencyMetricsError("internal SCC witness could not be established")


def _components(paths: tuple[str, ...], adjacent: dict[str, set[str]]) -> tuple[StaticCycle, ...]:
    """Deterministic Tarjan SCC, then source-backed cycle witnesses."""
    index = 0
    stack: list[str] = []
    active: set[str] = set()
    position: dict[str, int] = {}
    low: dict[str, int] = {}
    cycles: list[StaticCycle] = []

    def visit(node: str) -> None:
        nonlocal index
        position[node] = low[node] = index
        index += 1
        stack.append(node)
        active.add(node)
        for target in sorted(adjacent[node]):
            if target not in position:
                visit(target)
                low[node] = min(low[node], low[target])
            elif target in active:
                low[node] = min(low[node], position[target])
        if low[node] == position[node]:
            members = []
            while True:
                target = stack.pop()
                active.remove(target)
                members.append(target)
                if target == node:
                    break
            component = tuple(sorted(members))
            if len(component) > 1 or node in adjacent[node]:
                cycles.append(StaticCycle(component, _cycle_witness(component, adjacent)))

    for path in paths:
        if path not in position:
            visit(path)
    return tuple(sorted(cycles, key=lambda c: c.nodes))


def evaluate_dependency_metrics(
    graph: DependencyGraph, profile: DependencyMetricsProfile,
) -> DependencyMetricsReport:
    if not isinstance(graph, DependencyGraph) or not isinstance(profile, DependencyMetricsProfile):
        raise TypeError("expected DependencyGraph and DependencyMetricsProfile")
    if not graph.snapshot_id:
        raise DependencyMetricsError("missing immutable snapshot identity")
    paths = tuple(sorted(graph.analyzed_paths))
    excluded = tuple(sorted(graph.unprocessed_paths))
    if (len(set(paths)) != len(paths) or len(set(excluded)) != len(excluded)
            or set(paths) & set(excluded)
            or not all(_safe(p) for p in (*paths, *excluded))):
        raise DependencyMetricsError("invalid or contradictory source coverage")
    analyzed = set(paths)
    pair_statements: dict[tuple[str, str], list[tuple[int, str]]] = defaultdict(list)
    adjacent: dict[str, set[str]] = {p: set() for p in paths}
    inverse: dict[str, set[str]] = {p: set() for p in paths}
    unknown: Counter[str] = Counter()
    unknown_by_source: Counter[str] = Counter()
    for edge in graph.edges:
        if (edge.source_path not in analyzed or edge.target_path not in analyzed
                or type(edge.line) is not int or edge.line < 1
                or not edge.expression or edge.execution not in
                ("top_level", "conditional_or_deferred")):
            raise DependencyMetricsError("invalid, ungrounded or uncovered static import edge")
        pair_statements[(edge.source_path, edge.target_path)].append(
            (edge.line, edge.execution)
        )
        adjacent[edge.source_path].add(edge.target_path)
        inverse[edge.target_path].add(edge.source_path)
    for item in graph.unknown:
        if (item.source_path not in analyzed or type(item.line) is not int
                or item.line < 1 or not item.expression or not item.reason):
            raise DependencyMetricsError("invalid or ungrounded unknown dependency")
        unknown[item.reason] += 1
        unknown_by_source[item.source_path] += 1

    # Fan-in/out count distinct *matched target paths*, never import statement
    # multiplicity. Unknown targets are disclosed, not treated as zero edges.
    records = tuple(FileDegrees(
        path, len(inverse[path]), len(adjacent[path]), unknown_by_source[path]
    ) for path in paths)
    pairs = tuple(StaticPair(
        source, target, len(statements),
        sum(execution == "conditional_or_deferred" for _, execution in statements),
        tuple(sorted(line for line, _ in statements)),
    ) for (source, target), statements in sorted(pair_statements.items()))
    cycles = _components(paths, adjacent)
    return DependencyMetricsReport(
        snapshot_id=graph.snapshot_id,
        profile_id=profile.profile_id,
        analyzed_paths=paths,
        unprocessed_paths=excluded,
        files=records,
        pairs=pairs,
        cycles=cycles,
        unknown_by_reason=tuple(sorted(unknown.items())),
        flagged_out_degree=tuple(
            item.path for item in records if item.fan_out > profile.max_out_degree_review
        ),
        flagged_cycles=tuple(
            item.nodes for item in cycles
            if len(item.nodes) > profile.max_cycle_nodes_review
        ),
    )
