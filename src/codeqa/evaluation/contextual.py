"""Evidence-backed context for triaging high call-site-count findings.

Non-scoring: P3 rule_id, thresholds, mechanical status and CCG facts remain
unchanged. Context describes syntax only, never actual coupling or runtime
library identity.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any

from codeqa.core.function_context import FunctionSyntaxContext
from codeqa.evaluation.mechanical import MechanicalReport
from codeqa.core.symbols import SymbolCallReport


@dataclass(frozen=True, slots=True)
class ContextualCallReview:
    node_id: str
    call_sites: int
    threshold: int
    name_calls: int
    attribute_calls: int
    chained_attribute_calls: int
    other_calls: int
    distinct_callee_syntax: int
    distinct_resolved_targets: int
    unresolved_call_sites: int
    frequent_callee_syntax: tuple[tuple[str, int], ...]
    declared_import_namespace_hints: tuple[tuple[str, str, int], ...]
    branch_constructs: int
    loop_constructs: int
    try_constructs: int
    raise_statements: int
    return_statements: int
    context_flags: tuple[str, ...]
    cross_file_declaration_candidates: int = 0
    interpretation: str = "SYNTACTIC_TRIAGE_NOT_COUPLING_VERDICT"

    def to_document(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ContextualReviewReport:
    call_site_findings: int
    context_available: int
    context_unavailable: int
    flags_by_kind: tuple[tuple[str, int], ...]
    reviews: tuple[ContextualCallReview, ...]
    interpretation: str = "NON_SCORING_CONTEXT_ONLY"

    def to_document(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_call_context(
    mechanical: MechanicalReport,
    contexts: tuple[FunctionSyntaxContext, ...],
    symbol_calls: SymbolCallReport | None = None,
) -> ContextualReviewReport:
    """Overlay AST context onto unmodified call-site findings."""
    available = {item.node_id: item for item in contexts}
    metrics = {item.node_id: item for item in mechanical.call_metrics}
    cross_file = Counter(
        item.source_node_id for item in symbol_calls.candidates
    ) if symbol_calls is not None else Counter()
    warnings = [
        item for item in mechanical.findings
        if item.rule_id == "outgoing_call_sites_review"
    ]
    reviews: list[ContextualCallReview] = []
    for warning in warnings:
        ctx = available.get(warning.node_id)
        metric = metrics.get(warning.node_id)
        if ctx is None or metric is None or ctx.call_sites != metric.call_sites:
            continue  # No guessed context for unavailable/contradictory data.
        flags: list[str] = []
        if (ctx.attribute_calls + ctx.chained_attribute_calls) * 4 >= ctx.call_sites * 3:
            flags.append("ATTRIBUTE_SYNTAX_DOMINANT")
        if ctx.chained_attribute_calls >= 3:
            flags.append("CHAINED_ATTRIBUTE_SYNTAX")
        if ctx.call_sites >= 2 * max(1, ctx.distinct_callee_syntax):
            flags.append("REPEATED_CALLEE_SYNTAX")
        if ctx.declared_import_namespace_hints:
            flags.append("DECLARED_IMPORT_NAMESPACE_SYNTAX")
        if metric.unresolved_call_sites:
            flags.append("RUNTIME_TARGETS_UNVERIFIED")
        if ctx.branch_constructs or ctx.loop_constructs or ctx.try_constructs:
            flags.append("CONTROL_FLOW_PRESENT")
        reviews.append(ContextualCallReview(
            node_id=warning.node_id, call_sites=metric.call_sites,
            threshold=warning.threshold,
            name_calls=ctx.name_calls,
            attribute_calls=ctx.attribute_calls,
            chained_attribute_calls=ctx.chained_attribute_calls,
            other_calls=ctx.other_calls,
            distinct_callee_syntax=ctx.distinct_callee_syntax,
            distinct_resolved_targets=metric.distinct_resolved_targets,
            unresolved_call_sites=metric.unresolved_call_sites,
            frequent_callee_syntax=ctx.frequent_callee_syntax,
            declared_import_namespace_hints=ctx.declared_import_namespace_hints,
            branch_constructs=ctx.branch_constructs,
            loop_constructs=ctx.loop_constructs,
            try_constructs=ctx.try_constructs,
            raise_statements=ctx.raise_statements,
            return_statements=ctx.return_statements,
            context_flags=tuple(flags),
            cross_file_declaration_candidates=cross_file[warning.node_id],
        ))
    flags = Counter(flag for item in reviews for flag in item.context_flags)
    return ContextualReviewReport(
        call_site_findings=len(warnings),
        context_available=len(reviews),
        context_unavailable=len(warnings) - len(reviews),
        flags_by_kind=tuple(sorted(flags.items())),
        reviews=tuple(sorted(reviews, key=lambda item: item.node_id)),
    )
