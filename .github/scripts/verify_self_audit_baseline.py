"""Verify historic codeQA self-audit facts on the exact same source SHA."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def compare(reference: dict, result: dict) -> list[str]:
    errors: list[str] = []
    if reference["snapshot_sha"] != result["snapshot_sha"]:
        errors.append("source snapshot SHA mismatch")
    for scope, expected in reference["scopes"].items():
        actual = result["scopes"][scope]
        for key in ("source_files", "ccg_nodes", "ccg_edges", "coverage", "resolved_local_calls"):
            if expected[key] != actual[key]:
                errors.append(f"{scope}.{key}: expected {expected[key]!r}, got {actual[key]!r}")
        for key, reference_value in expected["quality"].items():
            actual_value = (
                len(actual["quality"]["findings"]) if key == "finding_count"
                else actual["quality"][key]
            )
            if reference_value != actual_value:
                errors.append(
                    f"{scope}.quality.{key}: expected {reference_value!r}, got {actual_value!r}"
                )
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("current", type=Path)
    args = parser.parse_args()
    reference = json.loads(args.baseline.read_text(encoding="utf-8"))
    current = json.loads(args.current.read_text(encoding="utf-8"))
    errors = compare(reference, current)
    if errors:
        raise SystemExit("PINNED AUDIT REGRESSION:\n" + "\n".join(errors))
    print("PINNED AUDIT BASELINE PASS: same input SHA; historic facts unchanged")


if __name__ == "__main__":
    main()
