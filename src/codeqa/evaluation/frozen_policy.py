"""Compare a frozen logical JSON policy against a trusted base Git revision.

The policy path on either side comes from that revision's own resource registry.
This catches concurrent edits to the repository layout and its policy file
without hard-coding repository-specific layout names or a physical policy path.

Note: CI logic in a PR is not immutable. Strong anti-tampering requires a separate
GitHub ruleset or an externally maintained required check.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import tomllib
from typing import Any

from codeqa.resources import ResourceRegistry, ResourceResolutionError, registry_path


class FrozenPolicyError(ValueError):
    """Frozen policy differs from its approved baseline or cannot be verified."""


def _git_file(root: Path, revision: str, relative: str) -> bytes:
    proc = subprocess.run(
        ["git", "show", f"{revision}:{relative}"],
        cwd=root, capture_output=True, check=False,
    )
    if proc.returncode:
        raise FrozenPolicyError(f"cannot load baseline Git file: {relative}")
    return proc.stdout


def baseline_policy(root: Path, revision: str, resource_id: str) -> Any:
    """Resolve logical ID using a specific commit's registry and JSON blob."""
    if not re.fullmatch(r"[0-9a-fA-F]{40}", revision):
        raise FrozenPolicyError("baseline must be a full Git commit SHA")
    try:
        config = tomllib.loads(
            _git_file(root, revision, "pyproject.toml").decode("utf-8")
        )
        relative = registry_path(config, resource_id)
        return json.loads(
            _git_file(root, revision, str(relative)).decode("utf-8")
        )
    except (UnicodeError, tomllib.TOMLDecodeError, json.JSONDecodeError,
            ResourceResolutionError) as exc:
        raise FrozenPolicyError("invalid baseline resource registry or policy") from exc


def verify_frozen_policy(root: Path, revision: str, resource_id: str) -> None:
    """Fail closed if the frozen policy's contents changed from the base commit."""
    previous = baseline_policy(root, revision, resource_id)
    try:
        current = ResourceRegistry(root).load_json(resource_id)
    except ResourceResolutionError as exc:
        raise FrozenPolicyError("current resource is unavailable") from exc
    if previous != current:
        raise FrozenPolicyError(
            f"frozen policy '{resource_id}' changed versus base {revision}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--resource-id", required=True)
    args = parser.parse_args()
    try:
        verify_frozen_policy(args.repository_root, args.base_sha, args.resource_id)
    except FrozenPolicyError as exc:
        print(f"FROZEN POLICY GUARD FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"FROZEN POLICY GUARD PASS: {args.resource_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
