"""Validate frozen policy data against an approved Git revision.

All Git process invocation belongs to infrastructure; validation remains pure.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

from codeqa.infrastructure.git import GitReader, GitReadError
from codeqa.infrastructure.resources import (
    ResourceRegistry, ResourceResolutionError, parse_json, parse_registry,
    registry_path,
)


class FrozenPolicyError(ValueError):
    """Frozen policy differs from approved baseline or cannot be checked."""


def verify_policy_unchanged(approved: Any, current: Any, resource_id: str) -> None:
    """Compare policy values without Git or filesystem access."""
    if approved != current:
        raise FrozenPolicyError(f"frozen policy '{resource_id}' changed from baseline")


def baseline_policy(root: Path, revision: str, resource_id: str) -> Any:
    """Resolve policy using the baseline revision's own resource registry."""
    try:
        reader = GitReader(root)
        config = parse_registry(reader.read_file(revision, "pyproject.toml"))
        path = registry_path(config, resource_id)
        return parse_json(reader.read_file(revision, str(path)), resource_id)
    except (GitReadError, ResourceResolutionError) as exc:
        raise FrozenPolicyError("cannot load approved baseline policy") from exc


def verify_frozen_policy(root: Path, revision: str, resource_id: str) -> None:
    """Check a current logical policy against its approved baseline."""
    previous = baseline_policy(root, revision, resource_id)
    try:
        current = ResourceRegistry(root).load_json(resource_id)
    except ResourceResolutionError as exc:
        raise FrozenPolicyError("current resource is unavailable") from exc
    verify_policy_unchanged(previous, current, resource_id)


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
