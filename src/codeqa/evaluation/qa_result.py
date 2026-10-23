"""Versioned QA Result v0.1: validated source-bounded facts and strict delta.

Not a replacement for the internal MechanicalReport. Does not infer runtime
behavior, domain correctness or universal P1–P8 success.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict
from hashlib import sha256
import json
import math
from typing import Any

from jsonschema import Draft202012Validator

from codeqa.core import Graph
from codeqa.evaluation.mechanical import MechanicalProfile, MechanicalReport


class QaResultContractError(ValueError):
    """A purported QA result or comparison lacks required grounded evidence."""


_RULES = (
    ("function_span_review", "P1", "function_span_lines", "line", "max_function_lines"),
    ("outgoing_call_sites_review", "P3", "outgoing_call_sites", "call_site", "max_call_sites"),
)
_ALL_PRINCIPLES = {f"P{i}" for i in range(1, 9)}


def _fail(message: str) -> None:
    raise QaResultContractError(message)


def _require_schema(document: Mapping[str, Any], schema: Mapping[str, Any]) -> None:
    Draft202012Validator.check_schema(schema)
    errors = list(Draft202012Validator(schema).iter_errors(document))
    if errors:
        first = sorted(errors, key=lambda e: (str(list(e.absolute_path)), e.message))[0]
        _fail("QA contract schema: " + first.message)
    try:
        json.dumps(document, allow_nan=False)
    except (ValueError, TypeError):
        _fail("non-finite or non-JSON QA data")


def _safe_path(path: str) -> bool:
    return (
        isinstance(path, str) and bool(path) and not path.startswith("/")
        and "\\" not in path and "\x00" not in path
        and not (len(path) > 1 and path[0].isalpha() and path[1] == ":")
        and all(part not in {"", ".", ".."} for part in path.split("/"))
    )


def _coverage_check(coverage: Mapping[str, Any]) -> None:
    analyzed = coverage["analyzed_paths"]
    unprocessed = [x["path"] for x in coverage["unprocessed"]]
    if any(not _safe_path(x) for x in analyzed + unprocessed):
        _fail("coverage includes an unsafe source path")
    if len(set(unprocessed)) != len(unprocessed) or set(analyzed) & set(unprocessed):
        _fail("duplicate or overlapping file coverage")
    expected = (
        "partial" if analyzed and unprocessed else
        "complete" if analyzed else "none"
    )
    if coverage["status"] != expected:
        _fail("coverage status contradicts paths")


def validate_qa_result(
    document: Mapping[str, Any], schema: Mapping[str, Any],
) -> dict[str, Any]:
    """Check schema, provenance references, evidence coverage and verdict truth."""
    _require_schema(document, schema)
    _coverage_check(document["coverage"])
    rules = document["rules"]
    if not rules:
        _fail("at least one declared, scoped rule is required")
    by_rule = {r["id"]: r for r in rules}
    if len(by_rule) != len(rules):
        _fail("duplicate QA rule identities")
    unsupported = document["unsupported_rules"]
    excluded_ids = [r["id"] for r in unsupported]
    if len(set(excluded_ids)) != len(excluded_ids) or set(excluded_ids) & set(by_rule):
        _fail("duplicate or contradictory unsupported rule")
    if {r["principle"] for r in rules} | set(excluded_ids) != _ALL_PRINCIPLES:
        _fail("P1–P8 must be evaluated or explicitly unsupported")
    evidence = document["evidence"]
    by_id = {e["id"]: e for e in evidence}
    if len(by_id) != len(evidence):
        _fail("duplicate QA evidence IDs")
    associated = set()
    for rule in rules:
        ids = rule["evidence_ids"]
        if rule["verdict"] == "FAIL":
            _fail("FAIL has no grounded evidence semantics in QA Result v0.1")
        if not ids and rule["verdict"] != "NOT_EVALUATED":
            _fail("PASS/REVIEW requires observed evidence")
        if rule["verdict"] == "NOT_EVALUATED" and not rule["limitations"]:
            _fail("NOT_EVALUATED needs a concrete reason")
        if rule["verdict"] == "PASS" and rule["limitations"]:
            _fail("incomplete rule evidence cannot PASS")
        if rule["verdict"] == "PASS" and any(
            by_id.get(eid, {}).get("status") != "PASS" for eid in ids
        ):
            _fail("PASS contradicts evidence status")
        if rule["verdict"] == "REVIEW_REQUIRED" and not any(
            by_id.get(eid, {}).get("status") == "REVIEW_REQUIRED" for eid in ids
        ):
            _fail("REVIEW_REQUIRED without a review observation")
        for eid in ids:
            if eid not in by_id or eid in associated:
                _fail("missing or reused evidence reference")
            observation = by_id[eid]
            if observation["rule_id"] != rule["id"]:
                _fail("evidence belongs to another rule")
            if (observation["metric"]["name"], observation["metric"]["unit"]) != (
                rule["metric"]["name"], rule["metric"]["unit"]
            ):
                _fail("metric/unit is inconsistent with the declared rule")
            loc = observation["location"]
            if loc["path"] not in document["coverage"]["analyzed_paths"]:
                _fail("evidence refers to an unprocessed source")
            if loc["end_line"] < loc["start_line"]:
                _fail("source location has reversed line interval")
            observed = observation["metric"]["value"]
            threshold = observation["threshold"]["value"]
            if not all(math.isfinite(x) for x in (observed, threshold)):
                _fail("non-finite measured evidence")
            actual = "REVIEW_REQUIRED" if observed > threshold else "PASS"
            if observation["status"] != actual:
                _fail("observation contradicts strict threshold")
            associated.add(eid)
    if associated != set(by_id):
        _fail("orphan QA evidence")
    coverage = document["coverage"]
    analysis = document["analysis"]
    if analysis["status"] == "COMPLETE":
        if coverage["status"] != "complete" or analysis["limitations"]:
            _fail("analysis COMPLETE contradicts coverage/limitations")
    elif analysis["status"] == "NONE":
        if coverage["status"] != "none":
            _fail("analysis NONE contradicts parse coverage")
    elif coverage["status"] == "none":
        _fail("analysis LIMITED cannot claim zero parsed sources")
    if coverage["status"] != "complete" and analysis["status"] != "NONE" and (
        "incomplete_source_coverage" not in analysis["limitations"]
    ):
        _fail("partial source coverage needs explicit analysis limitation")
    verdicts = {r["verdict"] for r in rules}
    inferred = (
        "REVIEW_REQUIRED" if "REVIEW_REQUIRED" in verdicts else
        "NOT_EVALUATED" if "NOT_EVALUATED" in verdicts else "PASS"
    )
    if document["verdict"]["status"] != inferred:
        _fail("overall verdict contradicts per-rule scope")
    if analysis["status"] == "NONE" and inferred != "NOT_EVALUATED":
        _fail("zero-source coverage cannot have a PASS verdict")
    return dict(document)


def canonical_qa_json(document: Mapping[str, Any]) -> str:
    """Canonical, byte-stable JSON excluding volatile timestamps by contract."""
    return json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False)


def mechanical_to_qa_result(
    graph: Graph,
    report: MechanicalReport,
    profile: MechanicalProfile,
    *,
    schema: Mapping[str, Any],
) -> dict[str, Any]:
    """Opt-in adapter; never mutates the existing PythonAnalysis or CCG."""
    if not isinstance(graph, Graph) or not isinstance(report, MechanicalReport):
        raise TypeError("a validated Graph and a MechanicalReport are required")
    if not isinstance(profile, MechanicalProfile) or report.profile_id != profile.profile_id:
        _fail("profile identity does not match the measured report")
    if report.coverage_status != graph.coverage.status:
        _fail("report coverage does not match the CCG")
    functions = sorted(
        (n for n in graph.nodes if n.kind in ("function", "method")),
        key=lambda n: n.id,
    )
    if len(functions) != report.function_count:
        _fail("function count disagrees with the CCG")
    call_metrics = {m.node_id: m for m in report.call_metrics}
    if set(call_metrics) != {n.id for n in functions}:
        _fail("missing or conflicting per-function call metrics")
    if report.unresolved_edges != sum(e.resolution == "unresolved" for e in graph.edges):
        _fail("unresolved edge count disagrees with CCG")
    expected_reviews = {(f.rule_id, f.node_id) for f in report.findings}
    profile_digest = sha256(canonical_qa_json(asdict(profile)).encode()).hexdigest()
    evidence: list[dict[str, Any]] = []
    rules: list[dict[str, Any]] = []
    for rule_id, principle, metric_id, unit, threshold_key in _RULES:
        threshold = getattr(profile, threshold_key)
        observed_ids = []
        not_evaluated = []
        for node in functions:
            if node.location is None:
                not_evaluated.append("missing_source_location")
                continue
            if rule_id == "function_span_review":
                value = node.location.end_line - node.location.start_line + 1
            else:
                value = call_metrics[node.id].call_sites
            evid_id = "qaev::" + sha256(
                (graph.snapshot.id + "\0" + rule_id + "\0" + node.id).encode()
            ).hexdigest()
            evidence.append({
                "id": evid_id, "rule_id": rule_id, "node_id": node.id,
                "location": {
                    "path": node.location.path,
                    "start_line": node.location.start_line,
                    "end_line": node.location.end_line,
                },
                "metric": {"name": metric_id, "value": value, "unit": unit},
                "threshold": {"operator": ">", "value": threshold},
                "status": "REVIEW_REQUIRED" if value > threshold else "PASS",
                "provenance": {"producer": "codeqa.mechanical", "method": "syntax_heuristic"},
            })
            observed_ids.append(evid_id)
        if not functions:
            not_evaluated.append("no_function_or_method")
        has_review = any(e["status"] == "REVIEW_REQUIRED" and e["rule_id"] == rule_id
                         for e in evidence)
        status = ("REVIEW_REQUIRED" if has_review else
                  "NOT_EVALUATED" if not_evaluated else "PASS")
        rules.append({
            "id": rule_id, "version": "0.1", "principle": principle,
            "metric": {"name": metric_id, "unit": unit},
            "verdict": status, "evidence_ids": observed_ids,
            "limitations": sorted(set(not_evaluated)),
        })
    generated_reviews = {(e["rule_id"], e["node_id"]) for e in evidence
                         if e["status"] == "REVIEW_REQUIRED"}
    if expected_reviews != generated_reviews or len(expected_reviews) != len(report.findings):
        _fail("mechanical findings disagree with measured evidence")
    statuses = {r["verdict"] for r in rules}
    verdict = ("REVIEW_REQUIRED" if "REVIEW_REQUIRED" in statuses else
               "NOT_EVALUATED" if "NOT_EVALUATED" in statuses else "PASS")
    if verdict != report.status:
        _fail("the internal report and bounded external verdict disagree")
    document = {
        "schema_version": "0.1",
        "snapshot": {"id": graph.snapshot.id},
        "engine": {"id": "codeqa.mechanical", "version": "0.1"},
        "profile": {"id": profile.profile_id, "fingerprint": profile_digest},
        "scope": {"meaning": "analyzed_paths_only"},
        "coverage": {
            "status": graph.coverage.status,
            "analyzed_paths": list(graph.coverage.analyzed_paths),
            "unprocessed": [asdict(x) for x in graph.coverage.unprocessed],
        },
        "analysis": {"status": report.analysis_status,
                     "limitations": list(report.analysis_limitations)},
        "verdict": {"status": verdict, "scope": "evaluated_rules_only"},
        "rules": rules, "evidence": evidence,
        "unsupported_rules": [
            {"id": f"P{i}", "reason": "not implemented by Mechanical v0.1"}
            for i in (2, 4, 5, 6, 7, 8)
        ],
    }
    return validate_qa_result(document, schema)


def compare_quality_delta(
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    result_schema: Mapping[str, Any],
    delta_schema: Mapping[str, Any],
) -> dict[str, Any]:
    """Fail closed on incomparable evidence; report descriptive review deltas."""
    base = validate_qa_result(baseline, result_schema)
    new = validate_qa_result(candidate, result_schema)
    if base["snapshot"]["id"] == new["snapshot"]["id"]:
        _fail("distinct immutable snapshot IDs required for quality delta")
    for field in ("engine", "profile", "scope"):
        if base[field] != new[field]:
            _fail("incomparable QA " + field)
    if base["coverage"]["status"] != "complete" or new["coverage"]["status"] != "complete":
        _fail("quality delta requires complete supplied-input parsing")
    if base["coverage"]["analyzed_paths"] != new["coverage"]["analyzed_paths"]:
        _fail("quality delta requires identical selected source paths")
    for document in (base, new):
        if document["analysis"]["status"] != "COMPLETE" or document["analysis"]["limitations"]:
            _fail("quality delta requires complete rule evidence without unresolved limitations")
        if any(rule["verdict"] == "NOT_EVALUATED" for rule in document["rules"]):
            _fail("quality delta cannot compare NOT_EVALUATED rules")
    def specs(document: Mapping[str, Any]) -> list[tuple[str, str, str, str, str]]:
        return sorted((r["id"], r["version"], r["principle"],
                       r["metric"]["name"], r["metric"]["unit"])
                      for r in document["rules"])
    if specs(base) != specs(new) or base["unsupported_rules"] != new["unsupported_rules"]:
        _fail("incomparable rule IDs, versions, units or unsupported scope")
    rule_deltas = []
    for left, right in zip(sorted(base["rules"], key=lambda r: r["id"]),
                           sorted(new["rules"], key=lambda r: r["id"])):
        def reviews(doc: Mapping[str, Any], rule: Mapping[str, Any]) -> int:
            evidence = {e["id"]: e for e in doc["evidence"]}
            return sum(evidence[eid]["status"] == "REVIEW_REQUIRED"
                       for eid in rule["evidence_ids"])
        old_count = reviews(base, left)
        new_count = reviews(new, right)
        rule_deltas.append({
            "rule_id": left["id"], "metric": left["metric"]["name"],
            "unit": left["metric"]["unit"],
            "baseline_review_count": old_count,
            "candidate_review_count": new_count,
            "review_count_delta": new_count - old_count,
        })
    delta = {
        "schema_version": "0.1",
        "baseline_snapshot_id": base["snapshot"]["id"],
        "candidate_snapshot_id": new["snapshot"]["id"],
        "engine": base["engine"], "profile": base["profile"],
        "analyzed_paths": base["coverage"]["analyzed_paths"],
        "interpretation": "descriptive_review_counts_only",
        "rule_deltas": rule_deltas,
    }
    _require_schema(delta, delta_schema)
    return delta
