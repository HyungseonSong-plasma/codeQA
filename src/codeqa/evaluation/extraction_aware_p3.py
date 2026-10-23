"""Opt-in extraction-aware P3 review: distinguish threshold relief from call relocation.

Consumes validated Python CCG + existing Mechanical v0.1 report and the exact
caller-supplied source text. Never changes P3 verdicts, resolves a runtime
callee, infers an extraction automatically, or executes target source.
"""
from __future__ import annotations

import ast
from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from hashlib import sha256
import re
from typing import Any

from codeqa.adapters.python_snapshot import parse_python_snapshot
from codeqa.core import Graph
from codeqa.evaluation.mechanical import MechanicalProfile, MechanicalReport


class ExtractionP3Error(ValueError):
    """Unverified input identity, source facts, owner or declared extraction."""


def _safe_path(path: str) -> bool:
    return (
        isinstance(path, str) and bool(path) and not path.startswith("/")
        and "\\" not in path and "\x00" not in path
        and not (len(path) >= 2 and path[0].isalpha() and path[1] == ":")
        and all(part not in ("", ".", "..") for part in path.split("/"))
    )


def _identity(value: str) -> tuple[str, str]:
    if not isinstance(value, str):
        raise ExtractionP3Error("expected immutable git source identity")
    match = re.fullmatch(r"git:([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@([a-f0-9]{40})", value)
    if match is None:
        raise ExtractionP3Error("expected git:owner/repository@40-hex-commit")
    return match.group(1), match.group(2)


@dataclass(frozen=True, slots=True)
class ExtractionP3Profile:
    schema_version: str
    profile_id: str
    mechanical_profile_id: str
    max_call_sites: int

    @classmethod
    def from_mapping(cls, document: Mapping[str, Any]) -> ExtractionP3Profile:
        if not isinstance(document, Mapping) or set(document) != {
            "schema_version", "profile_id", "mechanical_profile_id", "max_call_sites"
        }:
            raise ExtractionP3Error("invalid extraction P3 profile shape")
        if (document["schema_version"] != "0.1"
                or document["profile_id"] != "codeqa.p3.extraction.v0.1"
                or document["mechanical_profile_id"] != "codeqa.mechanical.v0.1"
                or type(document["max_call_sites"]) is not int
                or document["max_call_sites"] < 1):
            raise ExtractionP3Error("unsupported profile version or threshold")
        return cls(**document)


@dataclass(frozen=True, slots=True)
class ExtractionSpec:
    """Caller-declared owners; NOT an inferred function-move mapping."""

    path: str
    before_parent: str
    after_parent: str
    before_helpers: tuple[str, ...] = ()
    after_helpers: tuple[str, ...] = ()

    def validate(self) -> None:
        if (not _safe_path(self.path)
                or not self.path.endswith(".py")
                or not self.before_parent or not self.after_parent
                or any(not isinstance(x, str) or not x for x in (
                    *self.before_helpers, *self.after_helpers))
                or len(set((self.before_parent, *self.before_helpers))) != 1 + len(self.before_helpers)
                or len(set((self.after_parent, *self.after_helpers))) != 1 + len(self.after_helpers)):
            raise ExtractionP3Error("invalid or overlapping explicit extraction owners")


@dataclass(frozen=True, slots=True)
class CallWitness:
    """Exact AST Call syntax from one source location and lexical owner."""

    owner: str
    path: str
    line: int
    expression: str
    syntax_sha256: str


@dataclass(frozen=True, slots=True)
class ExactSyntaxRelocation:
    """Same AST text at different lexical owners; no runtime move assertion."""

    before_parent: str
    before_line: int
    after_helper: str
    after_line: int
    expression: str
    syntax_sha256: str


@dataclass(frozen=True, slots=True)
class ArmP3Observation:
    snapshot_id: str
    source_sha256: str
    coverage_status: str
    analysis_status: str
    limitations: tuple[str, ...]
    selected_file_count: int
    function_count: int
    selected_scope_calls: int
    selected_scope_review_triggers: int
    selected_scope_unresolved_calls: int
    parent: str
    parent_calls: int
    parent_review: bool
    helpers: tuple[tuple[str, int], ...]
    cohort_calls: int


@dataclass(frozen=True, slots=True)
class ExtractionP3Comparison:
    schema_version: str
    profile_id: str
    max_call_sites: int
    path: str
    before: ArmP3Observation
    after: ArmP3Observation
    parent_call_delta: int
    cohort_call_delta: int
    selected_scope_call_delta: int
    selected_scope_review_delta: int
    relocated_exact_syntax: tuple[ExactSyntaxRelocation, ...]
    status: str
    limitations: tuple[str, ...]
    interpretation: str = "FUNCTION_THRESHOLD_REDISTRIBUTION_NOT_PROVEN_DEPENDENCY_IMPROVEMENT"

    def to_document(self) -> dict[str, Any]:
        def serial(value: Any) -> Any:
            if isinstance(value, dict):
                return {key: serial(item) for key, item in value.items()}
            if isinstance(value, (list, tuple)):
                return [serial(item) for item in value]
            return value
        return serial(asdict(self))


class _Calls(ast.NodeVisitor):
    def __init__(self, path: str, owner: str) -> None:
        self.path = path
        self.owner = owner
        self.items: list[CallWitness] = []

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        return  # Nested function's calls are attributed to its own declaration.

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return  # CCG v0.1 excludes the lambda's separate execution scope.

    def visit_Call(self, node: ast.Call) -> None:
        syntax = ast.dump(node, include_attributes=False)
        self.items.append(CallWitness(
            owner=self.owner, path=self.path, line=node.lineno,
            expression=ast.unparse(node),
            syntax_sha256=sha256(syntax.encode("utf-8")).hexdigest(),
        ))
        self.generic_visit(node)


class _Functions(ast.NodeVisitor):
    def __init__(self, path: str) -> None:
        self.path = path
        self.prefix: list[str] = []
        self.witnesses: dict[str, list[CallWitness]] = {}

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.prefix.append(node.name)
        for statement in node.body:
            self.visit(statement)
        self.prefix.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        qualified = ".".join((*self.prefix, node.name))
        if qualified in self.witnesses:
            raise ExtractionP3Error("ambiguous duplicate lexical declaration: " + qualified)
        witness = _Calls(self.path, qualified)
        for statement in node.body:
            witness.visit(statement)
        self.witnesses[qualified] = sorted(
            witness.items, key=lambda x: (x.syntax_sha256, x.line, x.expression)
        )
        self.prefix.append(node.name)
        for statement in node.body:
            self.visit(statement)
        self.prefix.pop()

    visit_AsyncFunctionDef = visit_FunctionDef


def _arm(
    graph: Graph,
    report: MechanicalReport,
    sources: Mapping[str, str],
    profile: ExtractionP3Profile,
    spec: ExtractionSpec,
    *,
    before: bool,
) -> tuple[ArmP3Observation, dict[str, list[CallWitness]]]:
    _identity(graph.snapshot.id)
    if graph.schema_version != "0.1":
        raise ExtractionP3Error("only validated CCG v0.1 facts may be consumed")
    if (report.profile_id != profile.mechanical_profile_id
            or report.function_count != len(report.call_metrics)
            or report.coverage_status != graph.coverage.status):
        raise ExtractionP3Error("Mechanical report differs from extraction profile or CCG coverage")
    selected = tuple(sorted(graph.coverage.analyzed_paths))
    unprocessed = tuple(sorted(x.path for x in graph.coverage.unprocessed))
    if (not isinstance(sources, Mapping)
            or set(sources) != set(selected) | set(unprocessed)
            or not all(_safe_path(p) and isinstance(value, str)
                       for p, value in sources.items())
            or spec.path not in selected):
        raise ExtractionP3Error("caller source selection or target coverage mismatch")
    parsed = parse_python_snapshot(sources)
    if (parsed.analyzed_paths != selected
            or tuple(sorted(p for p, _ in parsed.unprocessed)) != unprocessed):
        raise ExtractionP3Error("source bytes do not reproduce declared CCG parse coverage")
    nodes = {
        node.id: node for node in graph.nodes
        if node.kind in ("function", "method")
    }
    if len(nodes) != len(report.call_metrics) or set(nodes) != {
        metric.node_id for metric in report.call_metrics
    }:
        raise ExtractionP3Error("Mechanical per-function metrics cannot be matched to CCG nodes")
    witnesses: dict[str, list[CallWitness]] = {}
    for item in parsed.files:
        assert item.tree is not None
        visitor = _Functions(item.path)
        visitor.visit(item.tree)
        for qualified, calls in visitor.witnesses.items():
            matching = [
                node for node in nodes.values()
                if node.id.startswith(f"def::{item.path}::{qualified}@")
            ]
            if len(matching) != 1:
                raise ExtractionP3Error("AST declaration is missing or ambiguous in CCG")
            if matching[0].location is None or matching[0].location.path != item.path:
                raise ExtractionP3Error("CCG declaration is missing source provenance")
            witnesses[matching[0].id] = calls
    if set(witnesses) != set(nodes):
        raise ExtractionP3Error("AST/CCG functions missing or extra")
    by_metrics = {metric.node_id: metric for metric in report.call_metrics}
    for node_id, calls in witnesses.items():
        source_edges = [
            e for e in graph.edges if e.kind == "calls" and e.source == node_id
        ]
        if (len(calls) != by_metrics[node_id].call_sites
                or Counter((e.location.path, e.location.start_line)
                           for e in source_edges if e.location) !=
                   Counter((c.path, c.line) for c in calls)):
            raise ExtractionP3Error("AST Call locations do not agree with CCG source evidence")
    total = sum(x.call_sites for x in report.call_metrics)
    unresolved = sum(x.unresolved_call_sites for x in report.call_metrics)
    if (total != sum(e.kind == "calls" and e.source in nodes for e in graph.edges)
            or report.unresolved_edges < unresolved):
        raise ExtractionP3Error("Mechanical call totals or uncertainty contradict CCG")
    current_parent = spec.before_parent if before else spec.after_parent
    current_helpers = spec.before_helpers if before else spec.after_helpers
    selected_names = (current_parent, *current_helpers)
    selected_owner_ids = []
    for qualified in selected_names:
        candidates = [
            node_id for node_id in nodes
            if node_id.startswith(f"def::{spec.path}::{qualified}@")
        ]
        if len(candidates) != 1:
            raise ExtractionP3Error("declared extraction owner missing or ambiguous: " + qualified)
        selected_owner_ids.append(candidates[0])
    owner_counts = {owner: by_metrics[node_id].call_sites
                    for owner, node_id in zip(selected_names, selected_owner_ids)}
    summary = ArmP3Observation(
        snapshot_id=graph.snapshot.id,
        source_sha256=sha256(sources[spec.path].encode("utf-8")).hexdigest(),
        coverage_status=graph.coverage.status,
        analysis_status=report.analysis_status,
        limitations=report.analysis_limitations,
        selected_file_count=len(selected),
        function_count=len(report.call_metrics),
        selected_scope_calls=total,
        selected_scope_review_triggers=sum(
            x.call_sites > profile.max_call_sites for x in report.call_metrics
        ),
        selected_scope_unresolved_calls=unresolved,
        parent=current_parent,
        parent_calls=owner_counts[current_parent],
        parent_review=owner_counts[current_parent] > profile.max_call_sites,
        helpers=tuple((name, owner_counts[name]) for name in current_helpers),
        cohort_calls=sum(owner_counts.values()),
    )
    return summary, {
        qualified: witnesses[node_id]
        for qualified, node_id in zip(selected_names, selected_owner_ids)
    }


def compare_extraction_aware_p3(
    before_graph: Graph,
    before_report: MechanicalReport,
    before_sources: Mapping[str, str],
    after_graph: Graph,
    after_report: MechanicalReport,
    after_sources: Mapping[str, str],
    *,
    spec: ExtractionSpec,
    profile: ExtractionP3Profile,
    mechanical_profile: MechanicalProfile,
) -> ExtractionP3Comparison:
    """Compare fixed selected files with explicit parent/helper attribution.

    A source-identical AST expression moving to a helper is an *exact syntax
    candidate*, not proof the runtime call or responsibility moved.
    """
    if not isinstance(spec, ExtractionSpec) or not isinstance(profile, ExtractionP3Profile):
        raise TypeError("expected ExtractionSpec and ExtractionP3Profile")
    spec.validate()
    if (not isinstance(mechanical_profile, MechanicalProfile)
            or profile.max_call_sites != mechanical_profile.max_call_sites
            or profile.mechanical_profile_id != mechanical_profile.profile_id):
        raise ExtractionP3Error("P3 threshold/profile drift from existing Mechanical v0.1")
    identity_before = _identity(before_graph.snapshot.id)
    identity_after = _identity(after_graph.snapshot.id)
    if identity_before[0] != identity_after[0] or identity_before[1] == identity_after[1]:
        raise ExtractionP3Error("comparison requires distinct commits in same pinned repository")
    if (set(before_graph.coverage.analyzed_paths) != set(after_graph.coverage.analyzed_paths)
            or {x.path for x in before_graph.coverage.unprocessed} !=
               {x.path for x in after_graph.coverage.unprocessed}):
        raise ExtractionP3Error("changed selected source-path population")
    if (set(before_sources) != set(after_sources) or
            any(before_sources[p] != after_sources[p]
                for p in before_sources if p != spec.path)):
        raise ExtractionP3Error("experiment includes unscoped edits in other files")
    first, before_witnesses = _arm(
        before_graph, before_report, before_sources, profile, spec, before=True
    )
    last, after_witnesses = _arm(
        after_graph, after_report, after_sources, profile, spec, before=False
    )

    pre_calls = before_witnesses[spec.before_parent]
    post_helpers = [
        x for name in spec.after_helpers for x in after_witnesses[name]
    ]
    by_hash: dict[str, list[CallWitness]] = defaultdict(list)
    for call in sorted(post_helpers, key=lambda x: (x.syntax_sha256, x.owner, x.line)):
        by_hash[call.syntax_sha256].append(call)
    moved = []
    for old in sorted(pre_calls, key=lambda x: (x.syntax_sha256, x.line)):
        if by_hash.get(old.syntax_sha256):
            recent = by_hash[old.syntax_sha256].pop(0)
            moved.append(ExactSyntaxRelocation(
                old.owner, old.line, recent.owner, recent.line,
                old.expression, old.syntax_sha256,
            ))
    limitations = set(first.limitations) | set(last.limitations)
    if first.selected_scope_unresolved_calls or last.selected_scope_unresolved_calls:
        limitations.add("unresolved_call_targets_are_not_proven_dependencies")
    if (first.coverage_status != "complete" or last.coverage_status != "complete"):
        limitations.add("incomplete_selected_source_coverage")
    if not spec.after_helpers:
        limitations.add("no_caller_declared_extracted_helpers")
    if not moved:
        limitations.add("no_identical_syntax_call_relocations_proven")
    if (first.source_sha256 == last.source_sha256):
        status = "UNCHANGED_SOURCE"
    elif (first.coverage_status != "complete" or last.coverage_status != "complete"):
        status = "INSUFFICIENT_COVERAGE"
    elif (first.parent_review and not last.parent_review
          and bool(spec.after_helpers)
          and last.cohort_calls >= first.cohort_calls):
        status = "REVIEW_TRIGGER_REDISTRIBUTION"
    elif last.cohort_calls < first.cohort_calls and last.selected_scope_calls < first.selected_scope_calls:
        status = "LOWER_STATIC_CALL_COUNT_OBSERVED"
    else:
        status = "NO_THRESHOLD_REDISTRIBUTION"
    return ExtractionP3Comparison(
        schema_version=profile.schema_version,
        profile_id=profile.profile_id,
        max_call_sites=profile.max_call_sites,
        path=spec.path,
        before=first,
        after=last,
        parent_call_delta=last.parent_calls - first.parent_calls,
        cohort_call_delta=last.cohort_calls - first.cohort_calls,
        selected_scope_call_delta=last.selected_scope_calls - first.selected_scope_calls,
        selected_scope_review_delta=last.selected_scope_review_triggers -
                                    first.selected_scope_review_triggers,
        relocated_exact_syntax=tuple(sorted(
            moved, key=lambda x: (x.syntax_sha256, x.before_line, x.after_line)
        )),
        status=status,
        limitations=tuple(sorted(limitations)),
    )
