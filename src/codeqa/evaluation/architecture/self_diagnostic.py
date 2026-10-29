"""Read-only B8 projections of authenticated B7 evidence; never infer PASS."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping


class SelfDiagnosticEvidenceError(ValueError):
    """The self-diagnostic cannot bind an observation to its source."""


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def project_self_diagnostic(
    assessment: Mapping[str, Any], inventory: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], str]:
    """Project source-backed signals, question packs and a deterministic human report.

    No question list, desired module name, or architecture target is an input.
    The B7 assembler owns discovery; this projection checks its source witnesses.
    """
    try:
        if (assessment["schema_version"] != "0.1"
                or assessment["mode"] != "DISCOVERY"
                or assessment["decision"] != "NOT_EVALUATED"
                or assessment["reviewer_decisions"]
                or assessment["assessment_id"] != _digest({
                    k: v for k, v in assessment.items() if k != "assessment_id"
                })
                or inventory["inventory_id"] != _digest({
                    k: v for k, v in inventory.items() if k != "inventory_id"
                })
                or assessment["source_identity"]["snapshot_sha"]
                   != inventory["source_identity"]["repository_commit_sha"]
                or assessment["source_identity"]["inventory_id"] != inventory["inventory_id"]):
            raise SelfDiagnosticEvidenceError("untrusted assessment/source identity")
        files = {f["path"]: f for f in inventory["files"]}
        if len(files) != len(inventory["files"]):
            raise SelfDiagnosticEvidenceError("duplicate inventory paths")

        def verify_witnesses(items: list[dict[str, Any]]) -> None:
            for item in items:
                witnesses = item["source_witnesses"]
                if not witnesses:
                    raise SelfDiagnosticEvidenceError("evidence-free signal/question")
                for w in witnesses:
                    file = files.get(w["source_path"])
                    if (file is None or file["read_state"] != "READ"
                            or file["source_sha256"] != w["source_sha256"]
                            or type(w["line"]) is not int or w["line"] < 1):
                        raise SelfDiagnosticEvidenceError("unbound source witness")

        signals = assessment["architecture_signals"]
        questions = assessment["question_opportunities"]
        verify_witnesses(signals)
        verify_witnesses(questions)
        signal_ids = {s["signal_id"] for s in signals}
        question_ids = {q["opportunity_id"] for q in questions}
        if (len(signal_ids) != len(signals)
                or len(question_ids) != len(questions)
                or any(not q["originating_signal_ids"]
                       or not set(q["originating_signal_ids"]) <= signal_ids
                       or "KEEP" not in q["alternatives"]
                       or q["decision"] != "NOT_EVALUATED"
                       for q in questions)
                or any(s["opportunity_id"] not in question_ids
                       for s in assessment["scenario_assessments"])):
            raise SelfDiagnosticEvidenceError("orphan, duplicate or pre-approved question")
        unknowns = sorted(set(assessment["unknowns"]))
        common = {
            "schema_version": "0.1",
            "source_identity": assessment["source_identity"],
            "assessment_id": assessment["assessment_id"],
            "coverage": assessment["coverage"],
            "unknowns": unknowns,
            "decision": "NOT_EVALUATED",
        }
        signal_report = {**common, "kind": "architecture_signals", "items": signals}
        question_report = {**common, "kind": "question_opportunities", "items": questions}
        lines = [
            "# codeQA B8 unprompted architecture self-diagnostic",
            "",
            "Exact source HEAD: " + common["source_identity"]["snapshot_sha"],
            "B7 assessment ID: " + common["assessment_id"],
            "Signals: " + str(len(signals)),
            "Questions: " + str(len(questions)),
            "Virtual comparisons: " + str(len(assessment["scenario_assessments"])),
            "Rejected virtual candidates: " + str(len(assessment["rejected_scenarios"])),
            "Overall decision: NOT_EVALUATED (not PASS)",
            "",
            "## Source-derived questions",
        ]
        for q in questions:
            lines.extend([
                "- " + q["opportunity_id"] + ": " + q["candidate_question"],
                "  - Origin: " + ", ".join(q["originating_signal_ids"]),
                "  - Witnesses: " + ", ".join(
                    w["source_path"] + ":" + str(w["line"])
                    for w in q["source_witnesses"]
                ),
                "  - Trigger: " + q["why_question_arises"],
                "  - Benign alternative: " + q["benign_counterhypothesis"],
                "  - Alternatives: " + ", ".join(q["alternatives"]),
                "  - Unknowns: " + ", ".join(q["unknowns"]),
            ])
        if not questions:
            lines.append("- No measured trigger at this source/profile; zero questions is valid, not PASS.")
        lines.extend(["", "## Bounded scenario comparisons"])
        for s in assessment["scenario_assessments"]:
            d = s["decision_evidence"]
            lines.extend([
                "- " + s["scenario_id"] + ": " + d["decision"],
                "  - Reasons: " + ", ".join(d["reasons"]),
                "  - Migration risk: " + d["migration_risk"],
                "  - Unknowns: " + ", ".join(d["critical_unknowns"]),
            ])
        for rejected in assessment["rejected_scenarios"]:
            lines.append("- Rejected candidate: " + rejected["reason"])
            for witness in rejected.get("collision_witnesses", []):
                lines.append(
                    "  - Collision (" + witness["collision_kind"] + "): "
                    + witness["source_path"] + " -> "
                    + witness["proposed_target_path"]
                    + " [source_sha256=" + witness["source_sha256"] + "]"
                )
                if "occupied_target_sha256" in witness:
                    lines.append(
                        "    - Existing target sha256: "
                        + witness["occupied_target_sha256"]
                    )
                if "conflicting_sources" in witness:
                    lines.append(
                        "    - Conflicting sources: "
                        + ", ".join(witness["conflicting_sources"])
                    )
        lines.extend([
            "", "## Coverage and unverified evidence",
            *("- " + u for u in unknowns),
            "",
            "Static evidence is not semantic cohesion or external-consumer certification.",
            "No source is moved. Any cleanup requires a separate reviewed PR and same-scope rerun.",
            "",
        ])
        return signal_report, question_report, "\n".join(lines)
    except (KeyError, TypeError, AttributeError) as exc:
        raise SelfDiagnosticEvidenceError("incomplete B7 source evidence") from exc


# Every B8 output must survive the CI artifact boundary. This manifest
# proves byte consistency within one artifact, NOT external CI provenance.
B8_REQUIRED_ARTIFACTS = (
    "architecture-assessment.json",
    "architecture-bounded-disposition.json",
    "architecture-callsite-context.json",
    "architecture-edge-responsibility.json",
    "architecture-import-initialization.json",
    "architecture-internal-consumers.json",
    "architecture-import-binding-usage.json",
    "architecture-package-surface.json",
    "architecture-runtime-call-pairs.json",
    "architecture-runtime-edge-correlation.json",
    "architecture-self-diagnostic.md",
    "architecture-signals.json",
    "architecture-test-behavior-candidates.json",
    "question-opportunities.json",
)


def _b8_artifact_entries(output_dir: Path, snapshot_sha: str, *, sealed: bool) -> list[dict[str, Any]]:
    expected = set(B8_REQUIRED_ARTIFACTS)
    if sealed:
        expected.add("architecture-evidence-manifest.json")
    if (not output_dir.is_dir()
            or {p.name for p in output_dir.iterdir()} != expected):
        raise SelfDiagnosticEvidenceError("missing, extra or stale B8 artifact")
    entries = []
    for name in B8_REQUIRED_ARTIFACTS:
        path = output_dir / name
        if not path.is_file() or path.is_symlink():
            raise SelfDiagnosticEvidenceError("invalid B8 artifact path")
        raw = path.read_bytes()
        if not raw:
            raise SelfDiagnosticEvidenceError("empty B8 artifact")
        if name.endswith(".json"):
            try:
                record = json.loads(raw)
                if record["source_identity"]["snapshot_sha"] != snapshot_sha:
                    raise SelfDiagnosticEvidenceError("mixed-source B8 artifact")
            except (ValueError, KeyError, TypeError) as exc:
                raise SelfDiagnosticEvidenceError("invalid B8 JSON identity") from exc
        elif ("Exact source HEAD: " + snapshot_sha).encode() not in raw:
            raise SelfDiagnosticEvidenceError("B8 markdown source identity mismatch")
        entries.append({
            "path": name, "sha256": sha256(raw).hexdigest(), "size_bytes": len(raw),
        })
    return entries


def build_b8_artifact_manifest(output_dir: Path, snapshot_sha: str) -> dict[str, Any]:
    """Seal the complete B8 evidence pack without claiming trusted CI attestation."""
    if not isinstance(snapshot_sha, str) or re.fullmatch(r"[0-9a-f]{40}", snapshot_sha) is None:
        raise SelfDiagnosticEvidenceError("invalid B8 source SHA")
    manifest = {
        "schema_version": "0.1",
        "source_identity": {"snapshot_sha": snapshot_sha},
        "files": _b8_artifact_entries(output_dir, snapshot_sha, sealed=False),
        "evidence_class": "ARTIFACT_BYTE_INTEGRITY_UNATTESTED",
        "runtime_edge_traversal": "NOT_EVALUATED",
        "decision": "NOT_EVALUATED",
    }
    manifest["manifest_id"] = _digest(manifest)
    return manifest


def verify_b8_artifact_manifest(output_dir: Path, manifest: Mapping[str, Any]) -> None:
    """Reject missing, stale, altered or extra files in a downloaded B8 pack."""
    try:
        sha = manifest["source_identity"]["snapshot_sha"]
        if (not isinstance(sha, str)
                or re.fullmatch(r"[0-9a-f]{40}", sha) is None
                or manifest["schema_version"] != "0.1"
                or manifest["evidence_class"] != "ARTIFACT_BYTE_INTEGRITY_UNATTESTED"
                or manifest["runtime_edge_traversal"] != "NOT_EVALUATED"
                or manifest["decision"] != "NOT_EVALUATED"
                or manifest["manifest_id"] != _digest({
                    k: v for k, v in manifest.items() if k != "manifest_id"
                })
                or manifest["files"] != _b8_artifact_entries(output_dir, sha, sealed=True)
                or json.loads(
                    (output_dir / "architecture-evidence-manifest.json").read_text(encoding="utf-8")
                ) != manifest):
            raise SelfDiagnosticEvidenceError("B8 artifact manifest mismatch")
    except (KeyError, TypeError, AttributeError, ValueError, OSError) as exc:
        raise SelfDiagnosticEvidenceError("untrustworthy B8 artifact manifest") from exc
