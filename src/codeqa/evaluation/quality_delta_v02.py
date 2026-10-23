"""Versioned evidence-aware metric snapshots and strict QA Delta v0.2.

V0.1 QA Result/Delta are immutable: this is a separate, opt-in exchange
contract. All metric comparisons are descriptive, not proven regressions.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import asdict
from hashlib import sha256
import json
import math
import re
from typing import Any

from jsonschema import Draft202012Validator

from codeqa.evaluation.qa_result import validate_qa_result, canonical_qa_json


class QualityDeltaV02Error(ValueError):
    """Invalid provenance, ungrounded rule evidence or unsafe change manifest."""


def _fail(reason: str) -> None:
    raise QualityDeltaV02Error(reason)


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha(data: str) -> str:
    return sha256(data.encode("utf-8")).hexdigest()


def _fingerprint(data: Any) -> str:
    return _sha(_json(data))


def _safe_path(value: Any) -> bool:
    return (isinstance(value, str) and bool(value) and not value.startswith("/")
            and "\\" not in value and "\x00" not in value
            and not (len(value) > 1 and value[0].isalpha() and value[1] == ":")
            and all(p not in ("", ".", "..") for p in value.split("/")))


def _schema_check(value: Mapping[str, Any], schema: Mapping[str, Any]) -> None:
    Draft202012Validator.check_schema(schema)
    errors = sorted(Draft202012Validator(schema).iter_errors(value),
                    key=lambda err: (str(list(err.absolute_path)), err.message))
    if errors:
        _fail("v0.2 schema: " + errors[0].message)
    try:
        _json(value)
    except (TypeError, ValueError):
        _fail("invalid non-finite / non-JSON document")


def _identity(repo: str, commit: str) -> str:
    if (not isinstance(repo, str) or len(repo.split("/")) != 2
            or any(not x or x in (".", "..") for x in repo.split("/"))
            or not isinstance(commit, str) or re.fullmatch(r"[0-9a-f]{40}", commit) is None):
        _fail("invalid immutable source repository or commit")
    return f"git:{repo}@{commit}"


def _stable_symbol(node_id: str) -> str:
    # A declaration's lexical qualified name is independent of line movement.
    # Duplicate qualified declarations are refused during snapshot validation.
    if "::" not in node_id or "@" not in node_id:
        _fail("unsupported source symbol identity")
    return "lexical::" + node_id.split("::")[-1].rsplit("@", 1)[0]


def validate_metric_snapshot(
    document: Mapping[str, Any], schema: Mapping[str, Any],
) -> dict[str, Any]:
    _schema_check(document, schema)
    source = document["source"]
    if document["snapshot_id"] != _identity(source["repository"], source["commit_sha"]):
        _fail("snapshot ID does not match immutable commit")
    paths = [x["path"] for x in source["files"]]
    unprocessed = [x["path"] for x in source["unprocessed"]]
    if (not all(_safe_path(x) for x in paths + unprocessed)
            or len(set(paths)) != len(paths)
            or len(set(unprocessed)) != len(unprocessed)
            or set(paths) & set(unprocessed)):
        _fail("invalid or contradictory source path inventory")
    expected_coverage = ("partial" if paths and unprocessed else
                         "complete" if paths else "none")
    if source["coverage"] != expected_coverage:
        _fail("source coverage contradicts selected paths")
    ids = set()
    supported_principles = set()
    for rule in document["rules"]:
        if rule["id"] in ids:
            _fail("duplicate rule ID")
        ids.add(rule["id"])
        supported_principles.add(rule["principle"])
        if rule["evidence_status"] == "MEASURED" and rule["limitations"]:
            _fail("MEASURED rule has unresolved limitations")
        if rule["evidence_status"] != "MEASURED" and not rule["limitations"]:
            _fail("unmeasured or limited rule lacks a reason")
        if rule["evidence_status"] == "MEASURED" and (
                rule["denominator"]["value"] < 1 or source["coverage"] != "complete"):
            _fail("MEASURED rule requires nonempty complete selected coverage")
        seen = set()
        for obs in rule["observations"]:
            key = (obs["path"], obs["subject_key"])
            if key in seen:
                _fail("ambiguous duplicate lexical subject identity")
            seen.add(key)
            if obs["path"] is None:
                if obs["line"] is not None:
                    _fail("aggregate metric cannot assert a source line")
            elif obs["path"] not in paths or obs["line"] is None:
                _fail("observation lacks an analyzed source path and line")
            if type(obs["value"]) not in (int, float) or not math.isfinite(obs["value"]):
                _fail("nonfinite or nonnumeric observed metric")
        if rule["evidence_status"] == "MEASURED" and not rule["observations"]:
            _fail("empty measured rule cannot be silently treated as zero")
        if rule["denominator"]["value"] < len(rule["observations"]):
            _fail("denominator smaller than observed subjects")
    omitted = [x["id"] for x in document["unsupported_principles"]]
    if (len(set(omitted)) != len(omitted)
            or supported_principles & set(omitted)
            or supported_principles | set(omitted) != {f"P{i}" for i in range(1, 9)}):
        _fail("P1–P8 support or omission claims contradict declared rules")
    return dict(document)


def metric_snapshot_from_qa_result(
    result: Mapping[str, Any],
    sources: Mapping[str, str],
    *,
    repository: str,
    commit_sha: str,
    result_schema: Mapping[str, Any],
    snapshot_schema: Mapping[str, Any],
    companions: tuple[Mapping[str, Any], ...] = (),
) -> dict[str, Any]:
    """Opt-in checked projection of actual Mechanical v0.1 evidence + companions.

    The caller owns pinned Git source bytes. Hashes are independently computed
    here from the supplied mapping, not inferred from names or line numbers.
    """
    base = validate_qa_result(result, result_schema)
    identity = _identity(repository, commit_sha)
    if base["snapshot"]["id"] != identity:
        _fail("QA v0.1 result and pinned source identity disagree")
    analyzed = set(base["coverage"]["analyzed_paths"])
    if (not isinstance(sources, Mapping) or set(sources) != analyzed
            or any(not isinstance(content, str) for content in sources.values())):
        _fail("source bytes absent or extra compared with QA Result coverage")
    source = {
        "repository": repository, "commit_sha": commit_sha,
        "files": [{"path": path, "sha256": _sha(sources[path])}
                  for path in sorted(analyzed)],
        "coverage": base["coverage"]["status"],
        "unprocessed": sorted(base["coverage"]["unprocessed"], key=lambda x: x["path"]),
    }
    indexed = {x["id"]: x for x in base["evidence"]}
    rules = []
    for rule in sorted(base["rules"], key=lambda x: x["id"]):
        observations = []
        for ev_id in rule["evidence_ids"]:
            ev = indexed[ev_id]
            observations.append({
                "path": ev["location"]["path"],
                "subject_key": _stable_symbol(ev["node_id"]),
                "value": ev["metric"]["value"],
                "review_required": ev["status"] == "REVIEW_REQUIRED",
                "line": ev["location"]["start_line"],
                "evidence_id": ev["id"],
                "producer": ev["provenance"]["producer"],
            })
        incomplete = sorted(set(rule["limitations"]) |
            set(base["analysis"]["limitations"]))
        status = ("NOT_EVALUATED" if rule["verdict"] == "NOT_EVALUATED"
                  else "LIMITED" if incomplete else "MEASURED")
        if status != "MEASURED" and not incomplete:
            incomplete = ["rule_not_evaluated"]
        rules.append({
            "id": rule["id"], "version": rule["version"],
            "principle": rule["principle"], "engine": dict(base["engine"]),
            "profile": dict(base["profile"]), "metric": dict(rule["metric"]),
            "denominator": {"kind": "measured_functions", "value": len(observations)},
            "evidence_status": status,
            "limitations": incomplete,
            "observations": sorted(observations, key=lambda x: (x["path"], x["subject_key"])),
        })
    rules.extend(dict(item) for item in companions)
    included_principles = {r["principle"] for r in rules}
    unsupported = [dict(x) for x in base["unsupported_rules"]
                   if x["id"] not in included_principles]
    doc = {
        "schema_version": "0.2", "snapshot_id": identity, "source": source,
        "rules": sorted(rules, key=lambda x: x["id"]),
        "unsupported_principles": sorted(unsupported, key=lambda x: x["id"]),
        "interpretation": "MEASURED_RULE_OBSERVATIONS_NOT_GENERAL_QUALITY",
    }
    return validate_metric_snapshot(doc, snapshot_schema)


def compare_metric_snapshots(
    baseline: Mapping[str, Any], candidate: Mapping[str, Any],
    change_manifest: Mapping[str, Any],
    *,
    snapshot_schema: Mapping[str, Any],
    change_schema: Mapping[str, Any],
    delta_schema: Mapping[str, Any],
) -> dict[str, Any]:
    """Never create a regression claim from a missing or incompatible metric."""
    before = validate_metric_snapshot(baseline, snapshot_schema)
    after = validate_metric_snapshot(candidate, snapshot_schema)
    _schema_check(change_manifest, change_schema)
    if (change_manifest["baseline_snapshot_id"] != before["snapshot_id"]
            or change_manifest["candidate_snapshot_id"] != after["snapshot_id"]):
        _fail("source change manifest refers to different snapshots")
    if before["snapshot_id"] == after["snapshot_id"]:
        _fail("distinct immutable snapshots required")
    if before["source"]["repository"] != after["source"]["repository"]:
        _fail("cannot compare distinct source repositories")
    old_files = {x["path"]: x["sha256"] for x in before["source"]["files"]}
    new_files = {x["path"]: x["sha256"] for x in after["source"]["files"]}
    rename_to_old = {}
    used_old = set()
    for change in change_manifest["renames"]:
        src, dst = change["before"], change["after"]
        if (src in used_old or dst in rename_to_old or not _safe_path(src)
                or not _safe_path(dst) or src == dst
                or old_files.get(src) != change["before_sha256"]
                or new_files.get(dst) != change["after_sha256"]):
            _fail("ambiguous, ungrounded or duplicate explicit rename mapping")
        used_old.add(src)
        rename_to_old[dst] = src
    normalized_new = {rename_to_old.get(p, p) for p in new_files}
    reasons = []
    if old_files.keys() != normalized_new:
        reasons.append("selected_paths_changed_without_grounded_renames")
    if before["source"]["coverage"] != "complete" or after["source"]["coverage"] != "complete":
        reasons.append("incomplete_or_failed_source_parsing")
    before_rules = {r["id"]: r for r in before["rules"]}
    after_rules = {r["id"]: r for r in after["rules"]}
    all_rule_ids = sorted(set(before_rules) | set(after_rules))
    comparisons = []
    for rule_id in all_rule_ids:
        first = before_rules.get(rule_id)
        last = after_rules.get(rule_id)
        reference = first or last
        metric = reference["metric"]
        denominator = reference["denominator"]
        local = list(reasons)
        if first is None or last is None:
            local.append("rule_missing_or_unsupported_in_one_snapshot")
        else:
            for key in ("version", "principle", "engine", "profile", "metric", "denominator"):
                if first[key] != last[key]:
                    local.append(key + "_changed")
            if first["evidence_status"] != "MEASURED" or last["evidence_status"] != "MEASURED":
                local.append("rule_evidence_incomplete_or_not_evaluated")
        edits = []
        if first is not None and last is not None and not local:
            def observed(rule: dict, *, normalized: bool) -> dict:
                records = {}
                for obs in rule["observations"]:
                    path = rename_to_old.get(obs["path"], obs["path"]) if normalized else obs["path"]
                    key = (path, obs["subject_key"])
                    if key in records:
                        _fail("renamed source creates colliding observation identities")
                    records[key] = obs
                return records
            left = observed(first, normalized=False)
            right = observed(last, normalized=True)
            unchanged_input = (len(old_files) == len(new_files)
                and all(old_files.get(rename_to_old.get(path,path)) == checksum
                        for path, checksum in new_files.items()))
            if unchanged_input and ({key:(x["value"],x["review_required"]) for key,x in left.items()}
                                    != {key:(x["value"],x["review_required"]) for key,x in right.items()}):
                local.append("unchanged_source_bytes_conflicting_metrics")
            if not local:
                for path, subject in sorted(set(left) | set(right)):
                    b = left.get((path,subject))
                    c = right.get((path,subject))
                    edits.append({
                        "path": path or "(selected_scope)", "subject_key": subject,
                        "change": "MATCHED" if b is not None and c is not None
                                  else "ADDED" if c is not None else "REMOVED",
                        "baseline_value": b["value"] if b else None,
                        "candidate_value": c["value"] if c else None,
                        "value_delta": c["value"]-b["value"] if b and c else None,
                        "baseline_review_required": b["review_required"] if b else None,
                        "candidate_review_required": c["review_required"] if c else None,
                    })
        comparable = not local
        bsum = sum(obs["value"] for obs in first["observations"]) if comparable else None
        csum = sum(obs["value"] for obs in last["observations"]) if comparable else None
        br = sum(obs["review_required"] for obs in first["observations"]) if comparable else None
        cr = sum(obs["review_required"] for obs in last["observations"]) if comparable else None
        comparisons.append({
            "rule_id": rule_id,
            "status": "COMPARABLE" if comparable else "NOT_COMPARABLE",
            "reasons": sorted(set(local)), "metric": metric, "denominator": denominator,
            "baseline_sum": bsum, "candidate_sum": csum,
            "sum_delta": csum - bsum if comparable else None,
            "baseline_reviews": br, "candidate_reviews": cr,
            "review_delta": cr-br if comparable else None,
            "observations": edits,
        })
    good = sum(x["status"] == "COMPARABLE" for x in comparisons)
    state = ("COMPARABLE" if good == len(comparisons) and good else
             "PARTIAL" if good else "NOT_COMPARABLE")
    doc = {
        "schema_version": "0.2",
        "baseline_snapshot_id": before["snapshot_id"],
        "candidate_snapshot_id": after["snapshot_id"],
        "status": state, "reasons": sorted(set(reasons)),
        "rule_deltas": comparisons,
        "interpretation": "DESCRIPTIVE_METRIC_CHANGES_NOT_PROVEN_REGRESSIONS",
    }
    _schema_check(doc, delta_schema)
    return doc


def build_source_change_manifest(
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    renames: tuple[tuple[str, str], ...] = (),
) -> dict[str, Any]:
    """Build a change manifest with exact observed per-file bytes hashes."""
    old = {x["path"]: x["sha256"] for x in baseline["source"]["files"]}
    new = {x["path"]: x["sha256"] for x in candidate["source"]["files"]}
    records = []
    for before, after in sorted(renames):
        if before not in old or after not in new:
            _fail("rename has no matching pinned input file")
        records.append({
            "before": before, "after": after,
            "before_sha256": old[before], "after_sha256": new[after],
        })
    return {
        "schema_version": "0.2",
        "baseline_snapshot_id": baseline["snapshot_id"],
        "candidate_snapshot_id": candidate["snapshot_id"],
        "renames": records,
    }
