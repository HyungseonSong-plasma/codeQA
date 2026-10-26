"""GitReader-backed adapter for versioned rule-based source classification."""
from __future__ import annotations
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from codeqa.core.naming_rule_inventory_v03 import classify_exact_rule_inventory
from codeqa.core.naming_review_worklist_v03 import build_review_worklist
from codeqa.infrastructure.git import GitReader


def evaluate_pinned_rule_inventory(root: Path, proposal: Mapping[str, Any]) -> dict[str, Any]:
    """Load exact historical Git commit/blob, then use pure core rules."""
    pinned = build_review_worklist(proposal)["source"]
    source = GitReader(root).read_file(pinned["commit"], pinned["path"])
    return classify_exact_rule_inventory(proposal, source=source)
