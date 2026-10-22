"""Compose one parsed Python snapshot into separate evidence-backed QA views.

No source acquisition, Git mutation or runtime imports of inspected code.
The optional caller-owned cache reuses only file-local work; all cross-file
relationships, validation, impact and verdicts are rebuilt per snapshot.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Mapping

from codeqa.adapters.python import adapt_parsed_python
from codeqa.adapters.python_dependencies import extract_parsed_dependencies
from codeqa.adapters.python_evidence import build_python_evidence
from codeqa.adapters.python_context import extract_function_context
from codeqa.adapters.python_symbols import extract_symbol_call_candidates
from codeqa.adapters.python_snapshot import (
    PythonAnalysisCache, parse_python_snapshot,
)
from codeqa.core import DependencyGraph, Graph
from codeqa.core.evidence import EvidenceIndex
from codeqa.core.function_context import FunctionSyntaxContext
from codeqa.core.symbols import SymbolCallReport
from codeqa.core.semantic_architecture import SemanticArchitecture
from codeqa.evaluation.semantic_architecture import evaluate_semantic_architecture
from codeqa.evaluation.impact import ImpactReport, analyze_change_impact
from codeqa.evaluation.contextual import ContextualReviewReport, evaluate_call_context
from codeqa.evaluation.mechanical import (
    MechanicalProfile, MechanicalReport, evaluate_mechanical,
)


@dataclass(frozen=True, slots=True)
class AnalysisEfficiency:
    parsed_files: int
    reused_parses: int
    extracted_files: int
    reused_extractions: int

    def to_document(self) -> dict[str, int]:
        return {
            "parsed_files": self.parsed_files,
            "reused_parses": self.reused_parses,
            "extracted_files": self.extracted_files,
            "reused_extractions": self.reused_extractions,
        }


@dataclass(frozen=True, slots=True)
class PythonAnalysis:
    graph: Graph
    quality: MechanicalReport
    dependencies: DependencyGraph
    evidence: EvidenceIndex
    function_context: tuple[FunctionSyntaxContext, ...]
    contextual_review: ContextualReviewReport
    symbol_calls: SymbolCallReport
    efficiency: AnalysisEfficiency
    impact: ImpactReport | None = None
    semantic_architecture: SemanticArchitecture | None = None

    def summary_document(self) -> dict[str, Any]:
        """Common short summary; full details are separate named views."""
        unknown = Counter(entry.reason for entry in self.dependencies.unknown)
        return {
            "snapshot_id": self.graph.snapshot.id,
            "quality": {
                "status": self.quality.status,
                "analysis_status": self.quality.analysis_status,
                "limitations": list(self.quality.analysis_limitations),
                "review_findings": len(self.quality.findings),
            },
            "source": {
                "coverage": self.graph.coverage.status,
                "analyzed_files": len(self.graph.coverage.analyzed_paths),
                "unprocessed_files": len(self.graph.coverage.unprocessed),
            },
            "ccg": {"nodes": len(self.graph.nodes), "edges": len(self.graph.edges)},
            "dependencies": {
                "matched_static_imports": len(self.dependencies.edges),
                "unmatched_by_reason": dict(sorted(unknown.items())),
                "resolution_scope": "STATIC_MODULE_PATH_ONLY",
            },
            "evidence": {
                "source_facts": len(self.evidence.facts),
                "linked_relations": sum(
                    r.evidence_id is not None for r in self.evidence.relations
                ),
                "unlinked_relations": sum(
                    r.evidence_id is None for r in self.evidence.relations
                ),
            },
            "symbol_calls": {
                "assurance": self.symbol_calls.assurance,
                "scanned_call_sites": self.symbol_calls.scanned_call_sites,
                "cross_file_declaration_candidates": len(self.symbol_calls.candidates),
                "excluded_by_reason": dict(self.symbol_calls.excluded_by_reason),
            },
            "contextual_review": {
                "call_site_findings": self.contextual_review.call_site_findings,
                "context_available": self.contextual_review.context_available,
                "context_unavailable": self.contextual_review.context_unavailable,
                "flags_by_kind": dict(self.contextual_review.flags_by_kind),
                "meaning": "NON_SCORING_AST_OBSERVATIONS",
            },
            "semantic_architecture": (
                self.semantic_architecture.summary_document()
                if self.semantic_architecture is not None
                else {"status": "NOT_REQUESTED"}
            ),
            "efficiency": self.efficiency.to_document(),
            "impact": (
                {
                    "status": self.impact.confidence,
                    "changed_files": list(self.impact.changed_paths),
                    "direct_candidates": len(self.impact.direct_dependents),
                    "transitive_candidates": len(self.impact.transitive_dependents),
                    "unknown_sources": len(self.impact.unknown_dependency_sources),
                }
                if self.impact is not None else {"status": "NOT_REQUESTED"}
            ),
        }

    def to_document(self) -> dict[str, Any]:
        """Existing detail views preserved; summary adds a unified entry point."""
        return {
            "summary": self.summary_document(),
            "graph": self.graph.to_document(),
            "quality": self.quality.to_document(),
            "dependencies": self.dependencies.to_document(),
            "evidence": self.evidence.to_document(),
            "function_context": [entry.to_document() for entry in self.function_context],
            "contextual_review": self.contextual_review.to_document(),
            "symbol_calls": self.symbol_calls.to_document(),
            "semantic_architecture": (
                self.semantic_architecture.to_document()
                if self.semantic_architecture is not None else None
            ),
            "efficiency": self.efficiency.to_document(),
            "impact": self.impact.to_document() if self.impact is not None else None,
        }


def analyze_python(
    sources: Mapping[str, str],
    *,
    snapshot_id: str,
    ccg_schema: Mapping[str, Any],
    mechanical_profile: Mapping[str, Any],
    cache: PythonAnalysisCache | None = None,
    changed_paths: Iterable[str] | None = None,
    semantic_policy: Mapping[str, Any] | None = None,
) -> PythonAnalysis:
    """Produce QA views from ONE source parse, optionally reusing file-local work."""
    profile = MechanicalProfile.from_mapping(mechanical_profile)
    parsed = parse_python_snapshot(
        sources, cache=cache.parsing if cache is not None else None,
    )
    stats = {"extracted": 0, "reused": 0}
    graph = adapt_parsed_python(
        parsed, snapshot_id=snapshot_id, schema=ccg_schema,
        cache=cache, stats=stats,
    )
    dependencies = extract_parsed_dependencies(parsed, snapshot_id=snapshot_id)
    evidence = build_python_evidence(
        parsed, graph=graph, dependencies=dependencies,
    )
    function_context = extract_function_context(parsed)
    quality = evaluate_mechanical(graph, profile)
    symbol_calls = extract_symbol_call_candidates(
        parsed, evidence, snapshot_id=snapshot_id,
    )
    contextual = evaluate_call_context(quality, function_context, symbol_calls)
    semantic_architecture = (
        evaluate_semantic_architecture(graph, dependencies, evidence, semantic_policy)
        if semantic_policy is not None else None
    )
    impact = (
        analyze_change_impact(dependencies, changed_paths)
        if changed_paths is not None else None
    )
    return PythonAnalysis(
        graph=graph,
        quality=quality,
        function_context=function_context,
        contextual_review=contextual,
        symbol_calls=symbol_calls,
        dependencies=dependencies,
        evidence=evidence,
        efficiency=AnalysisEfficiency(
            parsed_files=parsed.parse_count,
            reused_parses=parsed.cache_hits,
            extracted_files=stats["extracted"],
            reused_extractions=stats["reused"],
        ),
        impact=impact,
        semantic_architecture=semantic_architecture,
    )
