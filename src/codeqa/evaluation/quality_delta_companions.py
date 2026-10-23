"""Opt-in grounded companion metrics for QA Delta v0.2.

Each conversion uses an existing immutable evaluator report and its matching
profile; no parsing, source acquisition or mutation is performed here.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
from typing import Any, Mapping

from codeqa.evaluation.quality_delta_v02 import _fingerprint, _stable_symbol, _fail
from codeqa.evaluation.dependency_metrics import (
    DependencyMetricsProfile, DependencyMetricsReport,
)
from codeqa.evaluation.complexity import ComplexityProfile, ComplexityReport
from codeqa.evaluation.duplication import DuplicationProfile, DuplicationReport
from codeqa.evaluation.architecture_rules import DeclaredRuleReport


def _rule(id: str, principle: str, engine: str, profile_id: str,
          fingerprint: str, metric: str, unit: str, denominator_kind: str,
          denominator_value: int, observations: list[dict],
          limitations: list[str], status: str, version: str = "0.1") -> dict:
    if status == "MEASURED" and limitations:
        _fail("measured companion cannot conceal limitations")
    return {
        "id": id, "version": version, "principle": principle,
        "engine": {"id": engine, "version": version},
        "profile": {"id": profile_id, "fingerprint": fingerprint},
        "metric": {"name": metric, "unit": unit},
        "denominator": {"kind": denominator_kind, "value": denominator_value},
        "evidence_status": status,
        "limitations": sorted(set(limitations)),
        "observations": sorted(observations, key=lambda x: (
            x["path"] or "", x["subject_key"]
        )),
    }


def dependency_metric_rule(
    report: DependencyMetricsReport,
    profile: DependencyMetricsProfile,
) -> dict:
    if not isinstance(report, DependencyMetricsReport) or not isinstance(profile, DependencyMetricsProfile):
        raise TypeError("expected versioned DependencyMetricsReport + profile")
    if report.profile_id != profile.profile_id or report.schema_version != profile.schema_version:
        _fail("dependency report/profile drift")
    flagged = set(report.flagged_out_degree)
    if flagged != {x.path for x in report.files
                   if x.fan_out > profile.max_out_degree_review}:
        _fail("dependency review status disagrees with profile thresholds")
    observations = [{
        "path": x.path, "subject_key": "selected_static_file",
        "value": x.fan_out, "review_required": x.path in flagged,
        "line": 1, "evidence_id": "dependency-fan-out:" + x.path,
        "producer": "codeqa.dependency_metrics",
    } for x in report.files]
    limitations = []
    if report.unprocessed_paths:
        limitations.append("unprocessed_source_paths")
    if report.unknown_by_reason:
        limitations.append("unresolved_static_import_targets")
    if not observations:
        limitations.append("no_static_source_paths")
    status = ("NOT_EVALUATED" if not observations else
              "LIMITED" if limitations else "MEASURED")
    return _rule(
        "static_fan_out_review", "P3", "codeqa.dependency_metrics",
        profile.profile_id, _fingerprint(asdict(profile)),
        "static_file_out_degree", "file", "selected_files",
        len(report.files), observations, limitations, status,
    )


def complexity_metric_rules(
    report: ComplexityReport,
    profile: ComplexityProfile,
) -> tuple[dict, dict]:
    if not isinstance(report, ComplexityReport) or not isinstance(profile, ComplexityProfile):
        raise TypeError("expected ComplexityReport and profile")
    if report.profile_id != profile.profile_id or report.schema_version != profile.schema_version:
        _fail("complexity report/profile drift")
    fingerprint = _fingerprint(asdict(profile))
    result = []
    for rule_id, metric, threshold in (
        ("cyclomatic_proxy_review", "cyclomatic_proxy", profile.max_cyclomatic_proxy_review),
        ("branch_nesting_review", "branch_nesting_max", profile.max_branch_nesting_review),
    ):
        obs, limitations = [], []
        for item in report.reviews:
            if item.status == "NOT_EVALUATED":
                limitations.extend(item.limitations or ("not_evaluated_source_function",))
                continue
            value = getattr(item, metric)
            if value is None:
                _fail("measured function missing complexity value")
            obs.append({
                "path": item.path, "subject_key": _stable_symbol(item.node_id),
                "value": value, "review_required": value > threshold,
                "line": item.start_line,
                "evidence_id": rule_id + ":" + item.node_id,
                "producer": item.producer,
            })
        if report.unprocessed_paths:
            limitations.append("unprocessed_source_paths")
        if not report.reviews:
            limitations.append("no_function_evidence")
        status = ("NOT_EVALUATED" if not obs else
                  "LIMITED" if limitations else "MEASURED")
        result.append(_rule(
            rule_id, "P6", "codeqa.complexity", profile.profile_id,
            fingerprint, metric, "decision_count" if metric == "cyclomatic_proxy"
            else "nesting_level", "observed_functions",
            len(report.reviews), obs, limitations, status,
        ))
    return tuple(result)


def duplication_metric_rule(
    report: DuplicationReport,
    profile: DuplicationProfile,
) -> dict:
    if not isinstance(report, DuplicationReport) or not isinstance(profile, DuplicationProfile):
        raise TypeError("expected DuplicationReport and profile")
    if report.profile_id != profile.profile_id or report.profile_fingerprint != profile.fingerprint():
        _fail("duplication report/profile fingerprint mismatch")
    if report.observed_duplicate_fraction is None:
        obs = []
    else:
        if (report.evaluated_tokens <= 0
                or abs(report.observed_duplicate_fraction -
                       report.duplicate_excess_tokens / report.evaluated_tokens) > 1e-12):
            _fail("observed duplication fraction contradicts explicit denominator")
        obs = [{
            "path": None, "subject_key": "entire_selected_token_scope",
            "value": report.observed_duplicate_fraction, "review_required": False,
            "line": None, "evidence_id": "duplication:eligible-token-scope",
            "producer": "codeqa.duplication",
        }]
    limitations = list(report.not_evaluated)
    if report.unprocessed:
        limitations.append("unprocessed_source_paths")
    if not obs:
        limitations.append("no_eligible_duplicate_metric")
    status = ("NOT_EVALUATED" if not obs else
              "LIMITED" if limitations else "MEASURED")
    return _rule(
        "normalized_duplicate_fraction", "P6", "codeqa.duplication",
        profile.profile_id, profile.fingerprint(),
        "observed_duplicate_fraction", "fraction",
        "eligible_tokens", report.evaluated_tokens,
        obs, limitations, status,
    )


def architecture_metric_rule(
    report: DeclaredRuleReport,
    policy: Mapping[str, Any],
    *,
    analyzed_paths: tuple[str, ...],
) -> dict:
    if not isinstance(report, DeclaredRuleReport):
        raise TypeError("expected declared architecture report")
    if (report.policy_id != policy.get("policy_id")
            or report.revision != policy.get("revision")):
        _fail("declared policy identity/revision mismatch")
    observations = []
    grouped: dict[tuple[str, str], list] = defaultdict(list)
    for finding in report.findings:
        if finding.status in ("VIOLATION", "REVIEW_REQUIRED") and finding.target:
            grouped[(finding.source, finding.target)].append(finding)
    for (src, dst), findings in sorted(grouped.items()):
        if src not in analyzed_paths or any(f.line is None for f in findings):
            _fail("architecture finding missing selected source-line witness")
        observations.append({
            "path": src, "subject_key": "declared_direction::" + dst,
            "value": len(findings), "review_required": True,
            "line": min(f.line for f in findings),
            "evidence_id": "architecture:" + src + "->" + dst,
            "producer": "codeqa.architecture_rules",
        })
    limitations = []
    if report.status == "NOT_EVALUATED":
        limitations.append("declared_policy_has_no_positive_violation_evidence")
    if report.unprocessed_paths:
        limitations.append("unprocessed_source_paths")
    if any(f.status == "NOT_EVALUATED" for f in report.findings):
        limitations.append("unassessed_dynamic_or_policy_evidence")
    if not observations:
        limitations.append("no_grounded_policy_violation_witness")
    status = ("NOT_EVALUATED" if not observations else
              "LIMITED" if limitations else "MEASURED")
    return _rule(
        "declared_policy_violation_witnesses", "P4", "codeqa.architecture_rules",
        report.policy_id + "@" + report.revision, _fingerprint(policy),
        "declared_static_policy_witness_count", "static_import_statement",
        "selected_files", len(analyzed_paths), observations, limitations, status,
    )
