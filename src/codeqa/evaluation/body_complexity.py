"""Opt-in P6 v0.2: count function *body* AST control flow, not signatures.

Annotation/decorator/default expressions are explicitly out of measurement
scope, without being executed. Ambiguous body lambda/type-alias expressions
remain NOT_EVALUATED. v0.1 evaluator and schemas are unchanged.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from codeqa.core import Graph
from codeqa.core.complexity import BodyComplexityEvidence
from codeqa.evaluation.complexity import ComplexityProfile, ComplexityProfileError


@dataclass(frozen=True, slots=True)
class BodyComplexityReview:
    node_id: str
    path: str
    start_line: int
    end_line: int
    status: str
    cyclomatic_proxy: int | None
    branch_nesting_max: int | None
    limitations: tuple[str, ...]
    excluded_declaration_scope: tuple[str, ...]
    producer: str


@dataclass(frozen=True, slots=True)
class BodyComplexityReport:
    snapshot_id: str
    profile_id: str
    profile_version: str
    analyzed_paths: tuple[str, ...]
    unprocessed_paths: tuple[str, ...]
    reviews: tuple[BodyComplexityReview, ...]
    coverage_status: str
    status: str
    schema_version: str = "0.2"
    interpretation: str = "FUNCTION_BODY_SYNTAX_PROXY_WITH_DECLARATION_EXCLUSIONS_NOT_P6_VERDICT"

    def to_document(self) -> dict[str, Any]:
        def serial(value: Any) -> Any:
            if isinstance(value, (tuple, list)):
                return [serial(x) for x in value]
            if isinstance(value, dict):
                return {k: serial(v) for k,v in value.items()}
            return value
        return serial(asdict(self))


def evaluate_body_complexity(
    graph: Graph, evidence: BodyComplexityEvidence, profile: ComplexityProfile,
) -> BodyComplexityReport:
    if not isinstance(graph, Graph) or not isinstance(evidence, BodyComplexityEvidence):
        raise TypeError("validated CCG Graph and body-only evidence required")
    if not isinstance(profile, ComplexityProfile) or profile.schema_version != "0.1":
        raise ComplexityProfileError("unsupported threshold profile")
    if evidence.producer != "python-ast-body-complexity-v0.2":
        raise ComplexityProfileError("incorrect body-only producer")
    if tuple(sorted(p for p,_ in evidence.unprocessed)) != tuple(sorted(
        u.path for u in graph.coverage.unprocessed
    )):
        raise ComplexityProfileError("unprocessed path list differs from CCG")
    functions = {n.id: n for n in graph.nodes if n.kind in ("function","method")}
    items = evidence.observations
    if len(items) != len(functions) or {x.node_id for x in items} != set(functions):
        raise ComplexityProfileError("function evidence set differs from CCG")
    ignored = {}
    for node_id, reasons in evidence.ignored_declarations:
        if node_id in ignored or node_id not in functions or not reasons:
            raise ComplexityProfileError("invalid or duplicate declaration exclusion")
        if any(reason not in (
            "decorators_excluded_from_body_scope",
            "signature_expressions_excluded_from_body_scope",
        ) for reason in reasons):
            raise ComplexityProfileError("unsupported declaration exclusion")
        ignored[node_id] = tuple(sorted(set(reasons)))
    reports = []
    for item in items:
        node = functions[item.node_id]
        if (node.location is None or node.location.path != item.path
                or (node.location.start_line,node.location.end_line) != (
                    item.start_line,item.end_line)
                or item.producer != evidence.producer
                or item.method != "bounded_body_ast_syntax_no_annotation_execution"):
            raise ComplexityProfileError("unwitnessed or wrong-method source evidence")
        if item.status == "NOT_EVALUATED":
            if not item.limitations or any(x is not None for x in (
                item.decision_count,item.cyclomatic_proxy,item.branch_nesting_max)):
                raise ComplexityProfileError("not evaluated must not claim a number")
            status = "NOT_EVALUATED"
        elif item.status == "MEASURED":
            if (item.limitations or type(item.decision_count) is not int
                    or item.decision_count < 0
                    or item.cyclomatic_proxy != item.decision_count+1
                    or type(item.branch_nesting_max) is not int
                    or item.branch_nesting_max < 0):
                raise ComplexityProfileError("contradictory measured body complexity")
            status = "REVIEW_REQUIRED" if (
                item.cyclomatic_proxy > profile.max_cyclomatic_proxy_review
                or item.branch_nesting_max > profile.max_branch_nesting_review
            ) else "PASS"
        else:
            raise ComplexityProfileError("unsupported observation status")
        reports.append(BodyComplexityReview(
            item.node_id,item.path,item.start_line,item.end_line,status,
            item.cyclomatic_proxy,item.branch_nesting_max,
            item.limitations,ignored.get(item.node_id,()),item.producer,
        ))
    states = {x.status for x in reports}
    status = ("REVIEW_REQUIRED" if "REVIEW_REQUIRED" in states else
              "NOT_EVALUATED" if "NOT_EVALUATED" in states or
              not reports or graph.coverage.status != "complete" else "PASS")
    return BodyComplexityReport(
        snapshot_id=graph.snapshot.id,
        profile_id=profile.profile_id,
        profile_version=profile.schema_version,
        analyzed_paths=tuple(sorted(graph.coverage.analyzed_paths)),
        unprocessed_paths=tuple(sorted(u.path for u in graph.coverage.unprocessed)),
        reviews=tuple(sorted(reports,key=lambda x:x.node_id)),
        coverage_status=graph.coverage.status,
        status=status,
    )
