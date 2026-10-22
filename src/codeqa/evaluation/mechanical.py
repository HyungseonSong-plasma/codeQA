"""Conservative mechanical review signals with separate evidence limitations.

Function span and call-site count are heuristics, NOT evidence of a proven
SRP/coupling defect. A distinct target is counted only for resolved calls.
External dependency counts cannot yet be computed reliably (reported as None).
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from typing import Any, Mapping

from codeqa.core import Graph, SourceLocation


@dataclass(frozen=True, slots=True)
class MechanicalProfile:
    profile_id: str
    max_function_lines: int
    max_call_sites: int

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> MechanicalProfile:
        fields = {"profile_id", "max_function_lines", "max_call_sites"}
        if not isinstance(value, Mapping) or set(value) != fields:
            raise ValueError("mechanical profile requires exactly the declared fields")
        if value["profile_id"] != "codeqa.mechanical.v0.1":
            raise ValueError("unknown mechanical profile version")
        for key in ("max_function_lines", "max_call_sites"):
            number = value[key]
            if type(number) is not int or number < 1:
                raise ValueError(f"{key} must be a positive integer")
        return cls(**value)


@dataclass(frozen=True, slots=True)
class MechanicalFinding:
    rule_id: str
    principle: str
    node_id: str
    observed: int
    threshold: int
    status: str
    location: SourceLocation | None


@dataclass(frozen=True, slots=True)
class CallMetrics:
    """Observed call sites are NOT the same as distinct resolved dependencies."""

    node_id: str
    call_sites: int
    distinct_resolved_targets: int
    unresolved_call_sites: int
    distinct_unresolved_hints: int
    external_dependencies: int | None = None


@dataclass(frozen=True, slots=True)
class MechanicalReport:
    status: str
    analysis_status: str
    analysis_limitations: tuple[str, ...]
    coverage_status: str
    profile_id: str
    function_count: int
    unresolved_edges: int
    findings: tuple[MechanicalFinding, ...]
    not_evaluated: tuple[str, ...]
    call_metrics: tuple[CallMetrics, ...] = ()

    def to_document(self) -> dict[str, Any]:
        """Serializable internal report; no public quality contract yet."""
        return asdict(self)


def _call_metrics(graph: Graph, function_ids: set[str]) -> tuple[CallMetrics, ...]:
    call_sites: Counter[str] = Counter()
    unresolved_sites: Counter[str] = Counter()
    resolved_targets: dict[str, set[str]] = defaultdict(set)
    unresolved_hints: dict[str, set[str]] = defaultdict(set)
    for edge in graph.edges:
        if edge.kind != "calls" or edge.source not in function_ids:
            continue
        call_sites[edge.source] += 1
        if edge.resolution == "resolved":
            if edge.target is not None:
                resolved_targets[edge.source].add(edge.target)
        else:
            unresolved_sites[edge.source] += 1
            if edge.target_hint is not None:
                unresolved_hints[edge.source].add(edge.target_hint)
    return tuple(
        CallMetrics(
            node_id=node_id, call_sites=call_sites[node_id],
            distinct_resolved_targets=len(resolved_targets[node_id]),
            unresolved_call_sites=unresolved_sites[node_id],
            distinct_unresolved_hints=len(unresolved_hints[node_id]),
        )
        for node_id in sorted(function_ids)
    )


def _measure_rules(
    functions: list, metrics: tuple[CallMetrics, ...], profile: MechanicalProfile,
) -> tuple[tuple[MechanicalFinding, ...], tuple[str, ...]]:
    by_id = {metric.node_id: metric for metric in metrics}
    findings: list[MechanicalFinding] = []
    missing_evidence: set[str] = set()
    for node in functions:
        if node.location is None:
            missing_evidence.add("function_span_without_location")
        else:
            length = node.location.end_line - node.location.start_line + 1
            if length > profile.max_function_lines:
                findings.append(MechanicalFinding(
                    rule_id="function_span_review", principle="P1",
                    node_id=node.id, observed=length, threshold=profile.max_function_lines,
                    status="REVIEW_REQUIRED", location=node.location,
                ))
        sites = by_id[node.id].call_sites
        if sites > profile.max_call_sites:
            findings.append(MechanicalFinding(
                rule_id="outgoing_call_sites_review", principle="P3",
                node_id=node.id, observed=sites, threshold=profile.max_call_sites,
                status="REVIEW_REQUIRED", location=node.location,
            ))
    if not functions:
        missing_evidence.add("no_function_or_method")
    return (
        tuple(sorted(findings, key=lambda f: (f.node_id, f.rule_id))),
        tuple(sorted(missing_evidence)),
    )


def _assess_evidence(
    graph: Graph, unresolved: int, missing: tuple[str, ...],
) -> tuple[str, tuple[str, ...]]:
    limitations: set[str] = set()
    if graph.coverage.status != "complete":
        limitations.add("incomplete_source_coverage")
    if unresolved:
        limitations.add("unresolved_relationships")
    if missing:
        limitations.add("incomplete_rule_evidence")
    status = (
        "NONE" if graph.coverage.status == "none"
        else "LIMITED" if limitations else "COMPLETE"
    )
    return status, tuple(sorted(limitations))


def _quality_status(
    graph: Graph, findings: tuple[MechanicalFinding, ...], missing: tuple[str, ...],
) -> str:
    if findings:
        return "REVIEW_REQUIRED"
    if graph.coverage.status == "none" or missing:
        return "NOT_EVALUATED"
    return "PASS"  # Only measured v0.1 rules on analyzed sources.


def evaluate_mechanical(graph: Graph, profile: MechanicalProfile) -> MechanicalReport:
    """Compose measurements, evidence assessment and limited rule verdict."""
    if not isinstance(graph, Graph) or not isinstance(profile, MechanicalProfile):
        raise TypeError("expected validated CCG Graph and MechanicalProfile")
    functions = sorted(
        (node for node in graph.nodes if node.kind in ("function", "method")),
        key=lambda node: node.id,
    )
    metrics = _call_metrics(graph, {node.id for node in functions})
    findings, missing = _measure_rules(functions, metrics, profile)
    unresolved = sum(edge.resolution == "unresolved" for edge in graph.edges)
    analysis_status, limitations = _assess_evidence(graph, unresolved, missing)

    return MechanicalReport(
        status=_quality_status(graph, findings, missing),
        analysis_status=analysis_status,
        analysis_limitations=limitations,
        coverage_status=graph.coverage.status,
        profile_id=profile.profile_id,
        function_count=len(functions),
        unresolved_edges=unresolved,
        findings=findings,
        not_evaluated=missing,
        call_metrics=metrics,
    )
