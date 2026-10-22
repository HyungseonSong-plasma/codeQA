"""Compose source -> Python AST adapter -> validated CCG -> mechanical signals.

The caller supplies snapshot contents and resource-backed configuration; this
module does not load source paths, perform GitHub mutation or own OS workflows.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from codeqa.adapters import adapt_python_sources
from codeqa.core import Graph
from codeqa.evaluation.mechanical import (
    MechanicalProfile, MechanicalReport, evaluate_mechanical,
)


@dataclass(frozen=True, slots=True)
class PythonAnalysis:
    graph: Graph
    quality: MechanicalReport

    def to_document(self) -> dict[str, Any]:
        return {
            "graph": self.graph.to_document(),
            "quality": self.quality.to_document(),
        }


def analyze_python(
    sources: Mapping[str, str],
    *,
    snapshot_id: str,
    ccg_schema: Mapping[str, Any],
    mechanical_profile: Mapping[str, Any],
) -> PythonAnalysis:
    """Produce a deterministic, structured analysis from a pinned input."""
    profile = MechanicalProfile.from_mapping(mechanical_profile)
    graph = adapt_python_sources(sources, snapshot_id=snapshot_id, schema=ccg_schema)
    return PythonAnalysis(graph=graph, quality=evaluate_mechanical(graph, profile))
