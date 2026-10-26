"""Trusted Git-provenance gate for the adopted, opt-in Naming v0.5 profile."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any

from codeqa.core.naming_official_adoption_v05 import NamingAdoptionError
from codeqa.core.naming_official_policy_v05 import (
    OfficialNamingV05Decision, evaluate_official_naming_v05,
)
from codeqa.infrastructure.git import GitReader
from codeqa.pipeline.naming_official_adoption_v05 import (
    verify_pinned_naming_adoption_proposal,
)


def evaluate_pinned_official_naming_v05(
    root: Path, policy: Mapping[str, Any],
    proposal: Mapping[str, Any], *, as_of: date,
    path: str, owner: str, name: str, kind: str, line: int,
) -> OfficialNamingV05Decision:
    """Fail closed unless the proposal's historical Git tree was attested."""
    root = Path(root).resolve()
    verify_pinned_naming_adoption_proposal(root, proposal)
    witness = proposal["source_witness"]
    try:
        raw = GitReader(root).read_file(witness["commit"], witness["path"])
    except Exception as exc:
        raise NamingAdoptionError("historical source unavailable") from exc
    return evaluate_official_naming_v05(
        policy, proposal=proposal, source=raw, as_of=as_of,
        path=path, owner=owner, name=name, kind=kind, line=line)
