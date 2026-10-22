"""Pure semantic architecture projection from existing, independently sourced facts.

Policy role statements are normative; CCG nodes/edges and import syntax are
observations. This module does not parse files, read Git or infer behaviors from
names. It MUST NOT upgrade static matches to verified runtime targets.
"""
from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
import json
from typing import Mapping, Any

from codeqa.core.graph import Graph
from codeqa.core.dependency import DependencyGraph
from codeqa.core.evidence import EvidenceIndex
from codeqa.core.semantic_architecture import (
    SemanticArchitecture, SemanticAssessment, SemanticEntity, SemanticRelation,
)
from codeqa.evaluation.semantic_layout import evaluate_semantic_layout


UNASSESSED = (
    "behavior_vs_responsibility",
    "runtime_dependency_semantics",
    "library_and_dsl_semantics",
    "scientific_domain_contract",
    "test_relevance",
)


def _observation_id(parts: tuple[str, ...]) -> str:
    source = json.dumps(parts, ensure_ascii=False, separators=(",", ":"))
    return "import-observation:" + sha256(source.encode("utf-8")).hexdigest()


def evaluate_semantic_architecture(
    graph: Graph,
    dependencies: DependencyGraph,
    evidence: EvidenceIndex,
    role_policy: Mapping[str, Any],
) -> SemanticArchitecture:
    """Construct a small, versioned semantic view without asserting behavior.

    A single Import statement on one source line can ground a static link.
    If multiple Import statements share a line and CCG lacks column-level
    correspondence, the link remains evidence_id=None (not invented).
    """
    sha = graph.snapshot.id
    if sha != dependencies.snapshot_id or sha != evidence.snapshot_id:
        raise ValueError("CCG, dependency and evidence snapshots must match")

    # This existing evaluator validates policy structure and governs results.
    # Never invent a second, potentially contradictory boundary decision.
    complete = not graph.coverage.unprocessed
    directory_report = (
        evaluate_semantic_layout(
            graph.coverage.analyzed_paths,
            ((d.source_path, d.target_path) for d in dependencies.edges),
            role_policy,
        ) if complete else None
    )
    root = role_policy["scope"]
    roles = role_policy["roles"]
    files = sorted(
        p for p in graph.coverage.analyzed_paths
        if p.startswith(root + "/") and
        "/" in p[len(root)+1:] and
        p[len(root)+1:].split("/")[0] in roles
    )

    entities: dict[str, SemanticEntity] = {}
    relations: set[SemanticRelation] = set()

    def add(id: str, kind: str, label: str) -> None:
        entity = SemanticEntity(id, kind, label)
        if id in entities and entities[id] != entity:
            raise ValueError("semantic entity id collision")
        entities[id] = entity

    for role, definition in sorted(roles.items()):
        role_id = "role:" + role
        responsibility_id = "responsibility:" + role
        add(role_id, "DirectoryRole", role)
        add(responsibility_id, "Responsibility", definition["responsibility"])
        relations.add(SemanticRelation(
            role_id, "owns_responsibility", responsibility_id, "POLICY_DECLARATION",
        ))
        for forbidden in sorted(definition["forbidden_imports"]):
            constraint_id = f"constraint:{role}->{forbidden}"
            add(constraint_id, "Constraint", f"{role} cannot import {forbidden}")
            relations.add(SemanticRelation(
                constraint_id, "constrains_source", role_id, "POLICY_DECLARATION",
            ))
            relations.add(SemanticRelation(
                constraint_id, "constrains_target", "role:" + forbidden,
                "POLICY_DECLARATION",
            ))
            relations.add(SemanticRelation(
                role_id, "prohibited_dependency", "role:" + forbidden,
                "POLICY_DECLARATION",
            ))

    for path in files:
        role = path[len(root)+1:].split("/")[0]
        add("file:" + path, "SourceFile", path)
        relations.add(SemanticRelation(
            "role:" + role, "contains", "file:" + path, "PATH_OBSERVATION",
        ))

    codes: set[str] = set()
    for node in graph.nodes:
        loc = node.location
        if loc is None or loc.path not in files:
            continue
        cid = "code:" + node.id
        add(cid, "CodeEntity", node.name)
        codes.add(node.id)
        role = loc.path[len(root)+1:].split("/")[0]
        relations.add(SemanticRelation(
            cid, "belongs_to_role", "role:" + role, "PATH_OBSERVATION",
        ))

    # Preserve CCG's established resolution semantics; do not reinterpret it.
    for edge in graph.edges:
        if edge.kind not in ("defines", "calls"):
            continue
        if edge.resolution != "resolved" or edge.target is None:
            continue
        if edge.source not in codes or edge.target not in codes:
            continue
        relations.add(SemanticRelation(
            "code:" + edge.source, edge.kind, "code:" + edge.target,
            "CCG_RESOLVED_LOCAL" if edge.kind == "calls" else "CCG_OBSERVATION",
        ))

    # Evidence is indexed by exact path+line and is used ONLY when precisely
    # one import fact exists on that source line.
    found: dict[tuple[str, int], set[str]] = defaultdict(set)
    for fact in evidence.facts:
        if fact.kind == "import":
            found[(fact.path, fact.line)].add(fact.evidence_id)

    by_pair: dict[tuple[str, str], set[str]] = defaultdict(set)
    for edge in dependencies.edges:
        if edge.source_path not in files or edge.target_path not in files:
            continue
        src = "file:" + edge.source_path
        dst = "file:" + edge.target_path
        witnesses = found.get((edge.source_path, edge.line), set())
        witness = next(iter(witnesses)) if len(witnesses) == 1 else None
        by_pair[(edge.source_path, edge.target_path)].add(witness or "")
        relations.add(SemanticRelation(
            src, "imports", dst, "STATIC_MODULE_PATH", witness,
        ))
        observation_id = _observation_id((
            edge.source_path, edge.target_path, str(edge.line),
            edge.expression, edge.execution,
        ))
        add(observation_id, "DependencyObservation", edge.expression)
        relations.add(SemanticRelation(
            observation_id, "observed_in", src, "PATH_OBSERVATION",
        ))
        relations.add(SemanticRelation(
            observation_id, "observed_target", dst, "STATIC_MODULE_PATH",
        ))
        if witness is not None:
            add("evidence:" + witness, "Evidence", witness)
            relations.add(SemanticRelation(
                observation_id, "supported_by", "evidence:" + witness,
                "SOURCE_WITNESS", witness,
            ))

    assessments: list[SemanticAssessment] = []
    if directory_report is not None:
        for item in directory_report.findings:
            witness_ids = by_pair.get((item.source, item.target or ""), set())
            witness = next(iter(witness_ids)) if len(witness_ids) == 1 else None
            assessments.append(SemanticAssessment(
                item.status, item.code, item.source, item.target,
                item.reason, witness or None,
            ))
    else:
        assessments.append(SemanticAssessment(
            "NOT_EVALUATED", "PARTIAL_SOURCE_COVERAGE", root, None,
            "At least one input source was unprocessed; missing role evidence cannot be assessed",
        ))
    if dependencies.unknown:
        assessments.append(SemanticAssessment(
            "NOT_EVALUATED", "UNMAPPED_IMPORT_SEMANTICS", root, None,
            f"{len(dependencies.unknown)} import observations have no verified snapshot-local target",
        ))

    assessments = sorted(assessments, key=lambda a: (
        a.status, a.code, a.source, a.target or "", a.evidence_id or "",
    ))
    status = "VIOLATION" if any(x.status == "VIOLATION" for x in assessments) else (
        "REVIEW_REQUIRED" if any(x.status == "REVIEW_REQUIRED" for x in assessments)
        else "NOT_EVALUATED"
    )
    return SemanticArchitecture(
        schema_version="0.1",
        snapshot_id=sha,
        policy_id=str(role_policy["policy_id"]),
        entities=tuple(sorted(entities.values(), key=lambda e: e.id)),
        relations=tuple(sorted(relations, key=lambda e: (
            e.kind, e.source, e.target, e.assurance, e.evidence_id or "",
        ))),
        assessments=tuple(assessments),
        unassessed_dimensions=UNASSESSED,
        status=status,
    )
