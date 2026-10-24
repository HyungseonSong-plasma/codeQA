"""Conservative snapshot invalidation plan (#101), not a safe test selector.

No path-only static graph is an upper bound on runtime dependencies. This
planner never authorizes skipping snapshot-wide semantic/QA recomputation;
it classifies potential affected paths and auditable FULL fallback reasons.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass

from codeqa.core.dependency import DependencyGraph
from codeqa.evaluation.impact import analyze_change_impact


@dataclass(frozen=True, slots=True)
class InvalidationPlan:
    mode: str  # FULL_SNAPSHOT | LOCAL_EXTRACTION_REUSE_FULL_SEMANTICS
    changed_paths: tuple[str, ...]
    potential_dependents: tuple[str, ...]
    invalidation_scope: tuple[str, ...]
    reasons: tuple[str, ...]
    guarantees: str = "SNAPSHOT_WIDE_SEMANTICS_RECOMPUTED"

    def to_document(self):
        return asdict(self)


def plan_python_invalidation(
    graph: DependencyGraph,
    changed_paths: Iterable[str],
    *,
    source_selection_changed: bool = False,
    policy_changed: bool = False,
    toolchain_changed: bool = False,
    parser_changed: bool = False,
    compile_context_changed: bool = False,
) -> InvalidationPlan:
    """Classify *potential* dependencies; all cross-file facts are rebuilt.

    Safe file-local cache entries may be reused independently by exact source
    digest + producer identity; unlike semantic records they need no
    transitive dependency fingerprint.
    """
    impact = analyze_change_impact(graph, changed_paths)
    reasons = []
    if graph.unknown:
        reasons.append("UNRESOLVED_DEPENDENCY_BOUNDARY")
        if any(x.reason == "dynamic_import" for x in graph.unknown):
            reasons.append("DYNAMIC_IMPORT_REQUIRES_FULL_FALLBACK")
    if graph.unprocessed_paths:
        reasons.append("UNPROCESSED_SOURCE")
    if impact.untracked_changed_paths:
        reasons.append("UNTRACKED_CHANGED_SOURCE")
    if source_selection_changed:
        reasons.append("SOURCE_SELECTION_DRIFT")
    if policy_changed:
        reasons.append("POLICY_DRIFT")
    if toolchain_changed:
        reasons.append("TOOLCHAIN_OR_SDK_DRIFT")
    if parser_changed:
        reasons.append("PARSER_PRODUCER_DRIFT")
    if compile_context_changed:
        reasons.append("COMPILER_MACRO_TEMPLATE_CONTEXT_UNATTESTED")
    # No general static graph can exclude getattr/monkey patch/reflection or
    # compiler-generated dependencies; even an "all observed edges resolved"
    # case DOES NOT certify selective semantic invalidation.
    reasons.append("STATIC_GRAPH_NOT_RUNTIME_DEPENDENCY_UPPER_BOUND")
    full = len(reasons) > 1
    mode = "FULL_SNAPSHOT" if full else "LOCAL_EXTRACTION_REUSE_FULL_SEMANTICS"
    scope = tuple(sorted(set(impact.changed_paths) | {
        item.path for item in impact.affected
    }))
    return InvalidationPlan(
        mode=mode,
        changed_paths=impact.changed_paths,
        potential_dependents=tuple(x.path for x in impact.affected),
        invalidation_scope=scope,
        reasons=tuple(sorted(set(reasons))),
    )
