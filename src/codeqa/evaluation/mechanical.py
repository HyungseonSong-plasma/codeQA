"""Conservative mechanical quality signals over an already validated CCG.

No claim of full P1–P8 compliance: function length and outgoing call sites are
review heuristics, not proven SRP/coupling violations. Unresolved facts remain
explicit and prevent a confident mechanical PASS.
"""
from __future__ import annotations

from collections import Counter
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
class MechanicalReport:
    status: str
    coverage_status: str
    profile_id: str
    function_count: int
    unresolved_edges: int
    findings: tuple[MechanicalFinding, ...]
    not_evaluated: tuple[str, ...]

    def to_document(self) -> dict[str, Any]:
        """Serializable internal report; no public quality contract yet."""
        return asdict(self)


def evaluate_mechanical(graph: Graph, profile: MechanicalProfile) -> MechanicalReport:
    """Measure limited structure without turning review heuristics into FAIL."""
    if not isinstance(graph, Graph) or not isinstance(profile, MechanicalProfile):
        raise TypeError("expected validated CCG Graph and MechanicalProfile")

    functions = sorted(
        (node for node in graph.nodes if node.kind in ("function", "method")),
        key=lambda node: node.id,
    )
    call_sites = Counter(edge.source for edge in graph.edges if edge.kind == "calls")
    findings: list[MechanicalFinding] = []
    missing_evidence: set[str] = set()

    for node in functions:
        if node.location is None:
            missing_evidence.add("function_span_without_location")
        else:
            lines = node.location.end_line - node.location.start_line + 1
            if lines > profile.max_function_lines:
                findings.append(MechanicalFinding(
                    rule_id="function_span_review", principle="P1",
                    node_id=node.id, observed=lines,
                    threshold=profile.max_function_lines,
                    status="REVIEW_REQUIRED", location=node.location,
                ))

        observed_calls = call_sites[node.id]
        if observed_calls > profile.max_call_sites:
            findings.append(MechanicalFinding(
                rule_id="outgoing_call_sites_review", principle="P3",
                node_id=node.id, observed=observed_calls,
                threshold=profile.max_call_sites,
                status="REVIEW_REQUIRED", location=node.location,
            ))

    if not functions:
        missing_evidence.add("no_function_or_method")

    unresolved = sum(edge.resolution == "unresolved" for edge in graph.edges)
    if graph.coverage.status == "none":
        status = "NOT_EVALUATED"
    elif (
        graph.coverage.status != "complete"
        or unresolved
        or findings
        or missing_evidence
    ):
        status = "REVIEW_REQUIRED"
    else:
        status = "PASS"  # Only the measured v0.1 signals, NOT overall code quality.

    return MechanicalReport(
        status=status,
        coverage_status=graph.coverage.status,
        profile_id=profile.profile_id,
        function_count=len(functions),
        unresolved_edges=unresolved,
        findings=tuple(sorted(findings, key=lambda f: (f.node_id, f.rule_id))),
        not_evaluated=tuple(sorted(missing_evidence)),
    )
