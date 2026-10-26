"""Read-only exact Git attestation for proposed Naming v0.5 owner decision."""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from codeqa.core.naming_official_adoption_v05 import (
    NamingAdoptionError, assess_official_naming_adoption_proposal,
)
from codeqa.infrastructure.git import GitReader
from codeqa.pipeline.naming_scope_discovery_v04 import _tree_manifest


def verify_pinned_naming_adoption_proposal(
    root: Path, proposal: Mapping[str, Any],
) -> dict[str, Any]:
    """Verify revision->tree->blob through Git, then core AST/source evidence."""
    if not isinstance(proposal, Mapping) or not isinstance(
            proposal.get("source_witness"), Mapping):
        raise NamingAdoptionError("missing pinned historical source")
    pin = proposal["source_witness"]
    commit, path, blob, tree_expected = (
        pin.get("commit"), pin.get("path"), pin.get("git_blob_sha"),
        pin.get("tree_sha"),
    )
    if not all(isinstance(x, str) for x in (commit, path, blob, tree_expected)):
        raise NamingAdoptionError("malformed historical Git pin")
    try:
        tree, files = _tree_manifest(Path(root).resolve(), commit)
    except Exception as exc:
        raise NamingAdoptionError("historical Git commit unavailable") from exc
    if tree != tree_expected or files.get(path) != blob:
        raise NamingAdoptionError("commit tree or source blob mismatch")
    try:
        data = GitReader(Path(root).resolve()).read_file(commit, path)
    except Exception as exc:
        raise NamingAdoptionError("historical source unavailable") from exc
    return assess_official_naming_adoption_proposal(proposal, source=data)
