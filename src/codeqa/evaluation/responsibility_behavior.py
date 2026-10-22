"""Non-scoring responsibility/behavior syntax triage from declared roles.

No inference from file/function names. Even a cataloged API call remains
a syntactic observation: monkeypatching, wrappers, runtime resolution and
actual effects are not verified by this layer.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any

from codeqa.core.behavior import (
    BehaviorObservation, BehaviorPlacement, ResponsibilityBehaviorReport,
)


def validate_behavior_policy(
    policy: Mapping[str, Any],
    role_policy: Mapping[str, Any],
) -> dict[tuple[str, str], str]:
    if (
        not isinstance(policy, Mapping) or policy.get("schema_version") != "0.1"
        or not isinstance(policy.get("policy_id"), str) or not policy["policy_id"]
        or policy.get("scope") != role_policy.get("scope")
    ):
        raise ValueError("invalid or incompatible responsibility-behavior policy")
    roles = role_policy.get("roles")
    configured = policy.get("roles")
    catalog = policy.get("catalog")
    if (
        not isinstance(roles, dict) or not isinstance(configured, dict)
        or set(configured) != set(roles) or not isinstance(catalog, list)
        or not catalog
    ):
        raise ValueError("behavior policy must cover exactly declared roles")
    signatures: dict[tuple[str, str], str] = {}
    kinds: set[str] = set()
    for item in catalog:
        if not isinstance(item, dict):
            raise ValueError("invalid behavior signature")
        module, symbol, kind = (
            item.get("module"), item.get("symbol"), item.get("kind")
        )
        if not all(
            isinstance(x, str) and x and x == x.strip()
            for x in (module, symbol, kind)
        ) or not module.replace(".", "").isidentifier() or not symbol.isidentifier():
            raise ValueError("invalid import signature")
        if (module, symbol) in signatures:
            raise ValueError("duplicate API signature")
        signatures[(module, symbol)] = kind
        kinds.add(kind)
    for role, config in configured.items():
        if not isinstance(config, dict) or not isinstance(config.get("forbidden"), list):
            raise ValueError("invalid role behavior restrictions")
        restricted = config["forbidden"]
        if len(set(restricted)) != len(restricted) or any(x not in kinds for x in restricted):
            raise ValueError("unknown or duplicate forbidden behavior")
    return signatures


def evaluate_responsibility_behavior(
    observations: tuple[BehaviorObservation, ...],
    *,
    snapshot_id: str,
    scanned_call_sites: int,
    excluded_by_reason: tuple[tuple[str, int], ...],
    role_policy: Mapping[str, Any],
    behavior_policy: Mapping[str, Any],
) -> ResponsibilityBehaviorReport:
    """Compare narrow source syntax to *declared* exclusions only."""
    signatures = validate_behavior_policy(behavior_policy, role_policy)
    permitted_kinds = set(signatures.values())
    root = behavior_policy["scope"]
    positions: list[BehaviorPlacement] = []
    for item in observations:
        if item.behavior_kind not in permitted_kinds or not item.evidence_id:
            raise ValueError("unrecognized or unsupported observation")
        if not item.path.startswith(root + "/"):
            raise ValueError("observation lies outside declared role scope")
        relative = item.path[len(root)+1:].split("/")
        if len(relative) < 2 or relative[0] not in behavior_policy["roles"]:
            raise ValueError("observation lies in an unclassified directory role")
        role = relative[0]
        forbidden = item.behavior_kind in behavior_policy["roles"][role]["forbidden"]
        positions.append(BehaviorPlacement(
            source_node_id=item.source_node_id, path=item.path,
            directory_role=role, behavior_kind=item.behavior_kind,
            status=(
                "ROLE_CONFLICT_REVIEW" if forbidden
                else "ROLE_COMPATIBLE_OBSERVATION"
            ),
            evidence_id=item.evidence_id,
            reason=(
                "Declared role excludes this imported API call syntax; "
                "runtime side effects are unverified"
                if forbidden else
                "No exclusion applies to this observed API call syntax; "
                "this does not certify semantic alignment"
            ),
        ))
    positions.sort(key=lambda p: (
        p.path, p.source_node_id, p.behavior_kind, p.evidence_id,
    ))
    return ResponsibilityBehaviorReport(
        snapshot_id=snapshot_id,
        policy_id=behavior_policy["policy_id"],
        scanned_call_sites=scanned_call_sites,
        observations=observations,
        placements=tuple(positions),
        excluded_by_reason=tuple(sorted(excluded_by_reason)),
        status=(
            "REVIEW_REQUIRED"
            if any(p.status == "ROLE_CONFLICT_REVIEW" for p in positions)
            else "NOT_EVALUATED"
        ),
    )
