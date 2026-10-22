"""Pure reverse-dependency impact traversal on statically observed imports.

Impact is a lower bound for imports explicitly mapped to analyzed source
files, never a claim of complete runtime or behavioral change propagation.
"""
from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Any

from codeqa.core.dependency import DependencyGraph


@dataclass(frozen=True, slots=True)
class AffectedSource:
    path: str
    distance: int
    witness: tuple[str, ...]  # changed source -> ... -> importer


@dataclass(frozen=True, slots=True)
class ImpactReport:
    changed_paths: tuple[str, ...]
    affected: tuple[AffectedSource, ...]
    untracked_changed_paths: tuple[str, ...]
    unknown_dependency_sources: tuple[str, ...]
    unprocessed_paths: tuple[str, ...]
    confidence: str = "STATIC_LOWER_BOUND"

    @property
    def direct_dependents(self) -> tuple[str, ...]:
        return tuple(item.path for item in self.affected if item.distance == 1)

    @property
    def transitive_dependents(self) -> tuple[str, ...]:
        return tuple(item.path for item in self.affected if item.distance > 1)

    def to_document(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "direct_dependents": list(self.direct_dependents),
            "transitive_dependents": list(self.transitive_dependents),
        }


def analyze_change_impact(
    graph: DependencyGraph, changed_paths: Iterable[str],
) -> ImpactReport:
    """Compute deterministic shortest reverse-import witnesses; cycles terminate."""
    if not isinstance(graph, DependencyGraph):
        raise TypeError("expected a DependencyGraph")
    paths = tuple(sorted(set(changed_paths)))
    if not paths:
        raise ValueError("at least one changed path is required")
    if any(not isinstance(path, str) or not path or path.startswith("/")
           or "\\" in path or "\x00" in path
           or any(part in ("", ".", "..") for part in path.split("/"))
           for path in paths):
        raise ValueError("changed paths must be snapshot-relative POSIX paths")

    analyzed = set(graph.analyzed_paths)
    reverse: dict[str, set[str]] = defaultdict(set)
    for edge in graph.edges:
        reverse[edge.target_path].add(edge.source_path)

    # Seeding every changed source prevents reporting another changed file as
    # a dependent, while still tracing dependencies downstream of both.
    present = tuple(path for path in paths if path in analyzed)
    witnesses: dict[str, tuple[str, ...]] = {path: (path,) for path in present}
    todo = deque(present)
    while todo:
        target = todo.popleft()
        for importer in sorted(reverse[target]):
            if importer not in witnesses:
                witnesses[importer] = (*witnesses[target], importer)
                todo.append(importer)

    affected = tuple(sorted(
        (
            AffectedSource(path, len(chain) - 1, chain)
            for path, chain in witnesses.items()
            if path not in paths
        ),
        key=lambda item: (item.distance, item.path),
    ))
    return ImpactReport(
        changed_paths=paths,
        affected=affected,
        untracked_changed_paths=tuple(path for path in paths if path not in analyzed),
        unknown_dependency_sources=tuple(sorted({
            item.source_path for item in graph.unknown
        })),
        unprocessed_paths=graph.unprocessed_paths,
    )
