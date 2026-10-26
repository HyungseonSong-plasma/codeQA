"""Explicit, source-only Python Naming MVP entrypoint (opt-in, #120).

Never participates in the default Mechanical pipeline or a production Gate.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from codeqa.adapters.python_naming import extract_python_naming
from codeqa.adapters.python_snapshot import parse_python_snapshot
from codeqa.core.naming import NamingProfile
from codeqa.evaluation.naming import NamingReport, evaluate_naming


def analyze_python_naming_opt_in(
    sources: Mapping[str, str], *, snapshot_id: str,
    naming_profile: Mapping[str, Any],
) -> NamingReport:
    """Run only the v0.1 safe declaration-spelling witness pipeline.

    The caller explicitly selects the registered Python safe profile. This
    function does not change CCG, Mechanical P1/P3, QA Result, or external
    Gate decisions and does not attest external interfaces or runtime calls.
    """
    if not isinstance(snapshot_id, str) or not snapshot_id:
        raise ValueError("nonempty immutable snapshot identity required")
    if not isinstance(naming_profile, Mapping):
        raise TypeError("explicit Naming profile mapping required")
    profile = NamingProfile.from_mapping(naming_profile)
    parsed = parse_python_snapshot(sources)
    evidence = extract_python_naming(parsed, sources, snapshot_id=snapshot_id)
    return evaluate_naming(evidence, sources, profile)
