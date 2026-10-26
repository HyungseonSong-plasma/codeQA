"""Read-only Git provenance adapter for opt-in field evidence projection."""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from codeqa.core.naming_field_evidence_v03 import build_shadow_field_evidence
from codeqa.core.naming_review_worklist_v03 import build_review_worklist
from codeqa.infrastructure.git import GitReader


def project_pinned_field_evidence(
    root: Path, proposal: Mapping[str, Any],
) -> dict[str, Any]:
    """Read the exact commit's blob; all interpretation stays in pure core."""
    identity = build_review_worklist(proposal)["source"]
    source = GitReader(root).read_file(identity["commit"], identity["path"])
    return build_shadow_field_evidence(proposal, source=source)
