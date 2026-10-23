"""Pure optional P6 complexity review; never modifies Mechanical P1/P3."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from codeqa.core import Graph
from codeqa.core.complexity import ControlFlowObservation


class ComplexityProfileError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ComplexityProfile:
    profile_id: str
    schema_version: str
    max_cyclomatic_proxy_review: int
    max_branch_nesting_review: int

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ComplexityProfile":
        fields = {"profile_id", "schema_version", "max_cyclomatic_proxy_review",
                  "max_branch_nesting_review"}
        if not isinstance(value, Mapping) or set(value) != fields:
            raise ComplexityProfileError("invalid complexity profile shape")
        if (not isinstance(value["profile_id"], str) or not value["profile_id"]
                or value["schema_version"] != "0.1"
                or any(type(value[k]) is not int or value[k] < 0
                       for k in ("max_cyclomatic_proxy_review",
                                 "max_branch_nesting_review"))):
            raise ComplexityProfileError("unsupported complexity profile version/threshold")
        return cls(**value)


@dataclass(frozen=True, slots=True)
class ComplexityReview:
    node_id: str
    path: str
    start_line: int
    end_line: int
    status: str   # PASS | REVIEW_REQUIRED | NOT_EVALUATED
    cyclomatic_proxy: int | None
    branch_nesting_max: int | None
    limitations: tuple[str, ...]
    producer: str


@dataclass(frozen=True, slots=True)
class ComplexityReport:
    snapshot_id: str
    profile_id: str
    coverage_status: str
    unprocessed_paths: tuple[str, ...]
    reviews: tuple[ComplexityReview, ...]
    status: str
    schema_version: str = "0.1"
    interpretation: str = "HEURISTIC_SYNTAX_PROXY_NOT_P6_VERDICT"

    def to_document(self) -> dict[str, Any]:
        def json_value(value: Any) -> Any:
            if isinstance(value, (tuple, list)):
                return [json_value(v) for v in value]
            if isinstance(value, dict):
                return {k: json_value(v) for k, v in value.items()}
            return value

        return json_value(asdict(self))


def evaluate_complexity(
    graph: Graph,
    observations: tuple[ControlFlowObservation, ...],
    profile: ComplexityProfile,
) -> ComplexityReport:
    if not isinstance(graph, Graph) or not isinstance(profile, ComplexityProfile):
        raise TypeError("expected CCG Graph and ComplexityProfile")
    functions = {n.id: n for n in graph.nodes if n.kind in ("function", "method")}
    if len(observations) != len(functions) or {o.node_id for o in observations} != set(functions):
        raise ComplexityProfileError("per-function observations differ from grounded CCG")
    reports: list[ComplexityReview] = []
    for item in observations:
        node = functions[item.node_id]
        if (node.location is None or item.path != node.location.path
                or (item.start_line, item.end_line) != (
                    node.location.start_line, node.location.end_line)):
            raise ComplexityProfileError("unwitnessed source location or node ID")
        if item.status == "NOT_EVALUATED":
            if (not item.limitations or any(v is not None for v in
                    (item.decision_count, item.cyclomatic_proxy, item.branch_nesting_max))):
                raise ComplexityProfileError("unmeasured function claims numerical complexity")
            status = "NOT_EVALUATED"
        elif item.status == "MEASURED":
            if (item.limitations or item.decision_count is None
                    or item.cyclomatic_proxy != 1 + item.decision_count
                    or item.branch_nesting_max is None
                    or item.decision_count < 0 or item.branch_nesting_max < 0):
                raise ComplexityProfileError("contradictory complexity observation")
            status = ("REVIEW_REQUIRED" if (
                item.cyclomatic_proxy > profile.max_cyclomatic_proxy_review
                or item.branch_nesting_max > profile.max_branch_nesting_review
            ) else "PASS")
        else:
            raise ComplexityProfileError("unsupported complexity measurement state")
        reports.append(ComplexityReview(
            item.node_id, item.path, item.start_line, item.end_line, status,
            item.cyclomatic_proxy, item.branch_nesting_max,
            item.limitations, item.producer,
        ))
    states = {x.status for x in reports}
    overall = ("REVIEW_REQUIRED" if "REVIEW_REQUIRED" in states else
               "NOT_EVALUATED" if "NOT_EVALUATED" in states or not reports or
               graph.coverage.status != "complete" else "PASS")
    return ComplexityReport(
        snapshot_id=graph.snapshot.id, profile_id=profile.profile_id,
        coverage_status=graph.coverage.status,
        unprocessed_paths=tuple(sorted(u.path for u in graph.coverage.unprocessed)),
        reviews=tuple(sorted(reports, key=lambda x: x.node_id)),
        status=overall,
    )
