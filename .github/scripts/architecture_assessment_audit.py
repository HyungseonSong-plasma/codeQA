#!/usr/bin/env python3
"""B7 exact-head source-derived decision report; never execute a migration."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

from jsonschema import Draft202012Validator
from codeqa.evaluation.architecture.assessment import assemble_architecture_advisory


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("inventory", "metrics", "opportunities", "scenarios", "migration",
                 "output", "summary"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    reports = [
        json.loads(getattr(args, name).read_text(encoding="utf-8"))
        for name in ("inventory", "metrics", "opportunities", "scenarios", "migration")
    ]
    if any(r.get("snapshot_sha", r.get("source_identity", {}).get(
            "repository_commit_sha")) != head for r in reports):
        raise ValueError("B1--B5 reports must match checked-out HEAD")
    result = assemble_architecture_advisory(*reports)
    schema = json.loads(Path(
        "contracts/qa/architecture-assessment-v0.1.schema.json"
    ).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(result)
    if (result["source_identity"]["snapshot_sha"] != head
            or result["decision"] != "NOT_EVALUATED"
            or result["mode"] != "DISCOVERY"
            or result["reviewer_decisions"]):
        raise ValueError("B7 cannot claim unverified approval or discovery mode")
    if any(x["decision_evidence"]["decision"] == "PREFER"
           for x in result["scenario_assessments"]):
        raise ValueError("B7 virtual path-only assessment cannot certify PREFER")
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n",
                           encoding="utf-8")

    lines = [
        "# Architecture advisory B7 — exact source evidence",
        "",
        "Source HEAD: " + head,
        "Evidence ID: " + result["assessment_id"],
        "Mode: DISCOVERY (no preseeded questions)",
        "Signals: " + str(len(result["architecture_signals"])),
        "Question opportunities: " + str(len(result["question_opportunities"])),
        "Virtual assessments: " + str(len(result["scenario_assessments"])),
        "Rejected candidates: " + str(len(result["rejected_scenarios"])),
        "Overall disposition: NOT_EVALUATED (not PASS)",
        "",
        "## Source-derived questions",
    ]
    for q in result["question_opportunities"]:
        lines.extend([
            "- " + q["opportunity_id"] + ": " + q["candidate_question"],
            "  - Originating signals: " + ", ".join(q["originating_signal_ids"]),
            "  - Benign counterhypothesis: " + q["benign_counterhypothesis"],
            "  - Witnesses: " + str(len(q["source_witnesses"])),
        ])
    if not result["question_opportunities"]:
        lines.append("- No source-triggered questions at these thresholds; this is not a quality PASS.")
    lines.extend(["", "## Compared scenarios"])
    for s in result["scenario_assessments"]:
        d = s["decision_evidence"]
        lines.extend([
            "- " + s["scenario_id"] + ": " + d["decision"],
            "  - Reasons: " + ", ".join(d["reasons"]),
            "  - Counterhypothesis: " + s["counterhypothesis"],
            "  - Unknowns: " + ", ".join(d["critical_unknowns"]),
        ])
    for r in result["rejected_scenarios"]:
        lines.append("- Rejected (not scored): " + r["opportunity_id"] + " / " + r["reason"])
    lines.extend([
        "", "## Unresolved evidence",
        *("- " + u for u in result["unknowns"]),
        "",
        "No source move, external-consumer compatibility approval or reviewer decision is implied.",
    ])
    args.summary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("ARCHITECTURE_ASSESSMENT_B7 head=" + head
          + " questions=" + str(len(result["question_opportunities"]))
          + " assessed=" + str(len(result["scenario_assessments"]))
          + " artifact=" + str(args.output))


if __name__ == "__main__":
    main()
