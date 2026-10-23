"""Source-scope structural P3 counts across function-extraction refactors.

Opt-in companion for #48 ExtractionP3Comparison; never loosens strict
QA Delta v0.2 or claims runtime coupling/P8 quality equivalence.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
import re
from typing import Any

from jsonschema import Draft202012Validator

from codeqa.evaluation.extraction_aware_p3 import ExtractionP3Comparison


class StructuralP3DeltaError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class StructuralCount:
    metric: str
    unit: str
    scope: str
    baseline: int
    candidate: int
    delta: int
    interpretation: str


@dataclass(frozen=True, slots=True)
class StructuralP3Delta:
    schema_version: str
    baseline_snapshot_id: str
    candidate_snapshot_id: str
    selected_file_count: int
    declared_path: str
    status: str
    source_coverage: str
    analysis_limitations: tuple[str, ...]
    function_counts: tuple[int, int]
    rule_profile_id: str
    maximum_function_call_sites: int
    counts: tuple[StructuralCount, ...]
    exact_syntax_relocation_candidates: int
    interpretation: str = "STATIC_SCOPE_COUNTS_NOT_PROVEN_ARCHITECTURE_OR_BEHAVIOR_IMPROVEMENT"

    def to_document(self) -> dict[str, Any]:
        def as_json(value: Any) -> Any:
            if isinstance(value, tuple):
                return [as_json(item) for item in value]
            if isinstance(value, dict):
                return {k: as_json(v) for k, v in value.items()}
            return value
        return as_json(asdict(self))


def structural_p3_delta(
    evidence: ExtractionP3Comparison,
    *,
    schema: Mapping[str, Any],
) -> StructuralP3Delta:
    """Compare *counts* with an unchanged caller-selected file population.

    #48 comparison already checks exact CCG/AST source witnesses, identical
    selection and unedited other files. This converter independently checks
    arithmetic and immutable identities; never automatically maps helpers.
    """
    if not isinstance(evidence, ExtractionP3Comparison):
        raise StructuralP3DeltaError("extraction-aware P3 evidence required")
    before, after = evidence.before, evidence.after
    pattern = re.compile(r"git:([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@([a-f0-9]{40})")
    left, right = pattern.fullmatch(before.snapshot_id), pattern.fullmatch(after.snapshot_id)
    if (left is None or right is None or left.group(1) != right.group(1)
            or left.group(2) == right.group(2)):
        raise StructuralP3DeltaError("different full pinned revisions of one repository required")
    if (evidence.schema_version != "0.1"
            or evidence.profile_id != "codeqa.p3.extraction.v0.1"
            or type(evidence.max_call_sites) is not int or evidence.max_call_sites < 1
            or not evidence.path or before.selected_file_count != after.selected_file_count
            or before.selected_file_count < 1
            or before.parent_calls < 0 or after.parent_calls < 0
            or before.cohort_calls != before.parent_calls + sum(n for _, n in before.helpers)
            or after.cohort_calls != after.parent_calls + sum(n for _, n in after.helpers)
            or before.parent_review != (before.parent_calls > evidence.max_call_sites)
            or after.parent_review != (after.parent_calls > evidence.max_call_sites)
            or evidence.parent_call_delta != after.parent_calls-before.parent_calls
            or evidence.cohort_call_delta != after.cohort_calls-before.cohort_calls
            or evidence.selected_scope_call_delta !=
                after.selected_scope_calls-before.selected_scope_calls
            or evidence.selected_scope_review_delta !=
                after.selected_scope_review_triggers-before.selected_scope_review_triggers):
        raise StructuralP3DeltaError("contradictory selected-scope P3 measurements or profile")
    for arm in (before, after):
        if (arm.function_count < 1 or arm.selected_scope_calls < arm.cohort_calls
                or arm.selected_scope_unresolved_calls > arm.selected_scope_calls
                or arm.selected_scope_review_triggers > arm.function_count
                or arm.coverage_status not in ("complete", "partial", "none")
                or arm.analysis_status not in ("COMPLETE", "LIMITED", "NONE")):
            raise StructuralP3DeltaError("invalid per-arm source-scope metrics")
    complete = before.coverage_status == after.coverage_status == "complete"
    changed = before.source_sha256 != after.source_sha256
    reasons = set(evidence.limitations)
    if not complete:
        reasons.add("incomplete_selected_source_coverage")
    if not changed:
        reasons.add("unchanged_selected_source_bytes")
    if before.analysis_status != "COMPLETE" or after.analysis_status != "COMPLETE":
        reasons.add("analysis_limited_not_runtime_dependencies")
    if before.selected_scope_unresolved_calls or after.selected_scope_unresolved_calls:
        reasons.add("unresolved_static_call_targets")
    comparable = complete and changed and evidence.status not in (
        "INSUFFICIENT_COVERAGE", "UNCHANGED_SOURCE"
    )
    records: list[StructuralCount] = []
    if comparable:
        for metric, scope, old, new, meaning in (
            ("selected_ast_call_sites", "same_selected_file_population",
             before.selected_scope_calls, after.selected_scope_calls,
             "Static AST call sites; no resolved coupling claim"),
            ("declared_parent_helper_ast_calls", "caller_declared_parent_helper_cohort",
             before.cohort_calls, after.cohort_calls,
             "Caller-declared ownership; structural/function population may change"),
            ("selected_p3_review_trigger_count", "same_selected_file_population",
             before.selected_scope_review_triggers, after.selected_scope_review_triggers,
             "Threshold count only; changed function denominator is explicit"),
            ("selected_unresolved_call_sites", "same_selected_file_population",
             before.selected_scope_unresolved_calls, after.selected_scope_unresolved_calls,
             "Unknown runtime call targets, not evidence of fewer dependencies"),
        ):
            records.append(StructuralCount(metric, "AST_call_site" if "call_sites" in metric or
                                           "ast_calls" in metric else "function_review_count",
                                           scope, old, new, new-old, meaning))
    result = StructuralP3Delta(
        schema_version="0.1",
        baseline_snapshot_id=before.snapshot_id,
        candidate_snapshot_id=after.snapshot_id,
        selected_file_count=before.selected_file_count,
        declared_path=evidence.path,
        status="COMPARABLE_STATIC_COUNTS" if comparable else "NOT_COMPARABLE",
        source_coverage="complete" if complete else "partial_or_none",
        analysis_limitations=tuple(sorted(reasons)),
        function_counts=(before.function_count, after.function_count),
        rule_profile_id=evidence.profile_id,
        maximum_function_call_sites=evidence.max_call_sites,
        counts=tuple(records),
        exact_syntax_relocation_candidates=len(evidence.relocated_exact_syntax),
    )
    Draft202012Validator.check_schema(schema)
    errors = list(Draft202012Validator(schema).iter_errors(result.to_document()))
    if errors:
        raise StructuralP3DeltaError("invalid structural P3 report: " + errors[0].message)
    return result
