"""Pinned Semgrep JSON scan adapter (#100); no network, execution or Gate here.

This translates one *reported* native Semgrep scan into a typed #98 evidence
receipt. Caller/orchestrator must independently attest exact executable,
command, local rule configuration and source selection. Semgrep JSON's
paths.scanned is a scanner assertion, not independent proof of effective
rule execution or exhaustive language semantics.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any

from codeqa.core.evidence import EvidenceIndex
from codeqa.core.external_evidence import (
    ExternalEvidence, ExternalEvidenceError, ToolIdentity,
    parse_external_evidence,
)


class SemgrepAdapterError(ValueError):
    """Cannot safely represent Semgrep output as a complete scan receipt."""


_SEVERITY = {
    "ERROR": "HIGH", "WARNING": "MEDIUM", "INFO": "INFO",
    # Future native severity values need independent mapping review.
    "CRITICAL": "CRITICAL", "HIGH": "HIGH", "MEDIUM": "MEDIUM", "LOW": "LOW",
}


def _relative(raw: str) -> str:
    if not isinstance(raw, str) or not raw:
        raise SemgrepAdapterError("missing Semgrep source path")
    path = raw[2:] if raw.startswith("./") else raw
    parts = path.split("/")
    if (path.startswith("/") or "\\" in path or
        any(p in ("", ".", "..") for p in parts)):
        raise SemgrepAdapterError("unsafe/noncanonical Semgrep source path")
    return path


def _paths(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise SemgrepAdapterError("Semgrep scanned-file list missing")
    result = [_relative(item) for item in value]
    if len(result) != len(set(result)):
        raise SemgrepAdapterError("duplicate scan path")
    return tuple(sorted(result))


def _skipped(value: Any) -> list[dict[str, str]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise SemgrepAdapterError("invalid Semgrep skipped-file representation")
    out: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise SemgrepAdapterError("unrecognized Semgrep skipped-file entry")
        path = item.get("path")
        reason = item.get("reason")
        if not isinstance(reason, str):
            # Semgrep may use a structured reason object; keep it as unknown,
            # never silently drop its path from coverage.
            reason = "native_skip_reason_unclassified"
        out.append({"path": _relative(path), "reason": reason or "unspecified"})
    return out


def parse_semgrep_json(
    raw: bytes,
    *,
    schema: Mapping[str, Any],
    snapshot_id: str,
    expected_sources: Mapping[str, str],
    tool: ToolIdentity,
    attested_rules: tuple[str, ...],
    started_at: str,
    finished_at: str | None,
    exit_code: int | None,
    interrupted: bool = False,
    local_ruleset_verified: bool = False,
    artifact_uri: str,
) -> ExternalEvidence:
    """Parse native JSON; never infer no findings from absent JSON or errors.

    Only supports the pinned `semgrep scan --json` (without `--error`) mode.
    Unknown exit behavior or missing complete local rule-set attestation makes
    this receipt INDETERMINATE under #98/#99, never a false clean PASS.
    """
    if not isinstance(raw, bytes) or not raw:
        raise SemgrepAdapterError("missing native Semgrep JSON artifact")
    try:
        native = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise SemgrepAdapterError("malformed native Semgrep JSON artifact") from exc
    if not isinstance(native, dict):
        raise SemgrepAdapterError("unexpected native Semgrep document")
    results = native.get("results")
    errors = native.get("errors")
    paths = native.get("paths")
    if not isinstance(results, list) or not isinstance(errors, list):
        raise SemgrepAdapterError("Semgrep findings/errors arrays unavailable")
    if not isinstance(paths, dict) or "scanned" not in paths:
        raise SemgrepAdapterError("no attested scanned-file manifest")
    scanned = _paths(paths["scanned"])
    skipped = _skipped(paths.get("skipped"))

    selected = dict(expected_sources)
    scan_records = [
        {"path": path, "sha256": selected[path]}
        for path in scanned if path in selected
    ]
    # Do not invent an in-scope mapping for an unrequested path.
    if any(path not in selected for path in scanned):
        raise SemgrepAdapterError("native scanner reports files outside selected snapshot")

    observations = []
    for result in results:
        if not isinstance(result, dict):
            raise SemgrepAdapterError("invalid native Semgrep finding")
        rule_id = result.get("check_id")
        path = _relative(result.get("path"))
        start = result.get("start")
        extra = result.get("extra")
        if not isinstance(start, dict) or not isinstance(extra, dict):
            raise SemgrepAdapterError("finding source location/metadata missing")
        line = start.get("line")
        sev = extra.get("severity")
        if not isinstance(rule_id, str) or not rule_id or type(line) is not int or line < 1:
            raise SemgrepAdapterError("finding has invalid rule or location")
        if rule_id not in attested_rules:
            raise SemgrepAdapterError("finding refers to a rule absent from the pinned ruleset")
        if sev not in _SEVERITY:
            raise SemgrepAdapterError("native severity requires explicit mapping")
        observations.append({
            "kind": "STATIC_FINDING", "rule_id": rule_id,
            "severity": _SEVERITY[sev], "path": path, "line": line,
            "message": str(extra.get("message", "")) or "Semgrep finding",
            "native_status": sev,
        })

    error_reasons: list[dict[str, str]] = []
    for item in errors:
        if not isinstance(item, dict):
            raise SemgrepAdapterError("invalid native Semgrep error entry")
        location = item.get("path")
        if isinstance(location, str) and location:
            path = _relative(location)
            if path in selected:
                error_reasons.append({
                    "path": path,
                    "reason": str(item.get("type", "scanner_error")),
                })

    clean = (
        not interrupted and exit_code == 0 and len(errors) == 0
        and local_ruleset_verified and bool(attested_rules)
    )
    document = {
        "schema_version": "0.1",
        "snapshot_id": snapshot_id,
        "tool": {
            "name": tool.name, "version": tool.version,
            "binary_sha256": tool.binary_sha256,
            "adapter_version": tool.adapter_version,
            "invocation_sha256": tool.invocation_sha256,
            "ruleset_sha256": tool.ruleset_sha256,
            "exit_classifier": tool.exit_classifier,
        },
        "execution": {
            "state": "COMPLETED" if clean else (
                "CANCELLED" if interrupted else "FAILED"
            ),
            "exit_code": exit_code,
            "exit_classification": (
                "VALID_RESULT" if clean else "EXECUTION_FAILURE"
            ),
            "started_at": started_at, "finished_at": finished_at,
        },
        "scope": {
            "expected_files": [
                {"path": path, "sha256": digest}
                for path, digest in sorted(selected.items())
            ],
            "scanned_files": scan_records,
            "skipped_files": skipped,
            "parser_errors": error_reasons,
            "required_rules": sorted(attested_rules),
            "evaluated_rules": sorted(attested_rules) if local_ruleset_verified else [],
        },
        "raw_artifact": {
            "uri": artifact_uri, "sha256": sha256(raw).hexdigest(),
            "media_type": "application/json",
        },
        "observations": observations,
    }
    try:
        return parse_external_evidence(document, schema)
    except ExternalEvidenceError as exc:
        raise SemgrepAdapterError("unsafe native scan receipt: " + str(exc)) from exc


@dataclass(frozen=True, slots=True)
class SemgrepSourceLink:
    """Optional precise source witness, NEVER a proven runtime CCG edge."""
    rule_id: str
    path: str
    line: int
    evidence_id: str | None
    resolution: str  # EXACT_SOURCE_LINE | AMBIGUOUS_LINE | NO_SOURCE_FACT


def link_semgrep_ccg(
    envelope: ExternalEvidence, index: EvidenceIndex,
) -> tuple[SemgrepSourceLink, ...]:
    """Link only unique same-snapshot syntax witnesses by exact path+line.

    A Semgrep match can span syntax nodes; ambiguous same-line evidence is
    unlinked, not guessed. This optional companion does not create graph edges
    or assert semantic/runtime equivalence.
    """
    if envelope.snapshot_id != index.snapshot_id:
        raise SemgrepAdapterError("CCG evidence and scan source snapshots differ")
    by_line: dict[tuple[str, int], set[str]] = {}
    for fact in index.facts:
        by_line.setdefault((fact.path, fact.line), set()).add(fact.evidence_id)
    links: list[SemgrepSourceLink] = []
    for item in envelope.observations:
        if item.kind != "STATIC_FINDING":
            continue
        witnesses = by_line.get((item.path, item.line), set())
        if len(witnesses) == 1:
            ref, resolution = next(iter(witnesses)), "EXACT_SOURCE_LINE"
        elif witnesses:
            ref, resolution = None, "AMBIGUOUS_LINE"
        else:
            ref, resolution = None, "NO_SOURCE_FACT"
        links.append(SemgrepSourceLink(item.rule_id, item.path, item.line,
                                       ref, resolution))
    return tuple(sorted(links, key=lambda x: (x.path, x.line, x.rule_id, x.resolution)))


def validate_semgrep_sarif_parity(
    envelope: ExternalEvidence, sarif_raw: bytes,
) -> int:
    """Verify source-location parity of an independent SARIF artifact.

    SARIF result.level is optional (SARIF 2.1.0 §3.27.10), so only compare
    severity when it is EXPLICITLY present. Do not guess native severity from
    an absent level. JSON is the authoritative severity/coverage source.
    """
    if not isinstance(sarif_raw, bytes) or not sarif_raw:
        raise SemgrepAdapterError("missing SARIF companion artifact")
    try:
        doc = json.loads(sarif_raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise SemgrepAdapterError("malformed SARIF companion") from exc
    if not isinstance(doc, dict) or doc.get("version") != "2.1.0":
        raise SemgrepAdapterError("unsupported SARIF format/version")
    runs = doc.get("runs")
    if not isinstance(runs, list) or len(runs) != 1 or not isinstance(runs[0], dict):
        raise SemgrepAdapterError("expected exactly one SARIF run")
    records = runs[0].get("results")
    if not isinstance(records, list):
        raise SemgrepAdapterError("SARIF result list absent")
    level = {"error": "ERROR", "warning": "WARNING", "note": "INFO"}
    matched = []
    for item in records:
        if not isinstance(item, dict):
            raise SemgrepAdapterError("invalid SARIF result")
        rule = item.get("ruleId")
        level_name = item.get("level")
        locs = item.get("locations")
        if (not isinstance(rule, str) or
            (level_name is not None and level_name not in level) or
            not isinstance(locs, list) or len(locs) != 1 or
            not isinstance(locs[0], dict)):
            raise SemgrepAdapterError("SARIF finding missing supported attributes")
        physical = locs[0].get("physicalLocation")
        if not isinstance(physical, dict):
            raise SemgrepAdapterError("SARIF source location missing")
        artifact = physical.get("artifactLocation")
        region = physical.get("region")
        if not isinstance(artifact, dict) or not isinstance(region, dict):
            raise SemgrepAdapterError("SARIF source region missing")
        line = region.get("startLine")
        if type(line) is not int or line < 1:
            raise SemgrepAdapterError("invalid SARIF line")
        matched.append((rule, _relative(artifact.get("uri")), line,
                        level[level_name] if level_name is not None else None))
    expected = [
        (item.rule_id, item.path, item.line, item.native_status)
        for item in envelope.observations if item.kind == "STATIC_FINDING"
    ]
    if (sorted((a, b, c) for a, b, c, _ in expected) !=
        sorted((a, b, c) for a, b, c, _ in matched)):
        raise SemgrepAdapterError("Semgrep JSON/SARIF source findings differ")
    # An explicit SARIF level can be cross-checked; absent means severity
    # parity NOT_ATTESTED, never an invented default or a Gate permission.
    native = set(expected)
    for rule, path, line, explicit_severity in matched:
        if (explicit_severity is not None and
            (rule, path, line, explicit_severity) not in native):
            raise SemgrepAdapterError("Semgrep JSON/SARIF severity mismatch")
    return len(matched)
