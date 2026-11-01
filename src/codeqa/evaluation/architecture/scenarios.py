"""B4 read-only, source-triggered virtual layout candidates.

A virtual path remapping is not a refactor, semantic ownership proof, import
rewrite, or architecture-quality improvement. Only B3 evidence can trigger
automatic proposals. All source bytes and observed static edges stay fixed.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from hashlib import sha256
import json
import re
from typing import Any

from codeqa.evaluation.architecture.opportunities import (
    ArchitectureOpportunityError, discover_architecture_opportunities,
)


class ArchitectureScenarioError(ValueError):
    """Inconsistent source evidence or unsupported virtual mapping."""


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _path_ok(path: Any) -> bool:
    return (isinstance(path, str) and bool(path) and not path.startswith("/")
            and "\\" not in path and ":" not in path
            and all(part not in ("", ".", "..") and not part.endswith((".", " "))
                    for part in path.split("/"))
            and not any(ord(ch) < 32 or ord(ch) == 127 for ch in path))


def _role(path: str, scope: str, roles: set[str]) -> str:
    prefix = scope + "/"
    if not path.startswith(prefix):
        return "OUT_OF_SCOPE"
    parts = path[len(prefix):].split("/")
    return parts[0] if len(parts) >= 2 and parts[0] in roles else "UNCLASSIFIED"


def _ranked_automatic_mappings(
    signal: Mapping[str, Any], inventory_files: Mapping[str, Any],
    scope: str, roles: set[str],
) -> list[tuple[str, int, dict[str, str]]]:
    """Rank independent, source-witnessed moves without inventing filenames."""
    if signal["family"] not in {
        "DECLARED_BOUNDARY_CONFLICT", "CROSS_BOUNDARY_CONCENTRATION",
    }:
        return []
    counts: Counter[tuple[str, str]] = Counter()
    for witness in signal["source_witnesses"]:
        src, dst = witness["source_path"], witness["target_path"]
        if (src not in inventory_files or dst not in inventory_files
                or not src.endswith(".py") or src.endswith("/__init__.py")):
            continue
        sr, dr = _role(src, scope, roles), _role(dst, scope, roles)
        if sr in roles and dr in roles and sr != dr:
            counts[(src, dr)] += 1
    return [
        (src, count, {
            src: scope + "/" + target_role + "/" + src.rsplit("/", 1)[-1],
        })
        for (src, target_role), count in sorted(
            counts.items(), key=lambda item: (-item[1], item[0])
        )
    ]


def _automatic_mapping(
    signal: Mapping[str, Any], inventory_files: Mapping[str, Any],
    scope: str, roles: set[str],
) -> tuple[dict[str, str], str | None]:
    if signal["family"] == "STATIC_IMPORT_CYCLE":
        return {}, "PATH_MOVE_CANNOT_REMOVE_STATIC_CYCLE"
    if signal["family"] not in {
        "DECLARED_BOUNDARY_CONFLICT", "CROSS_BOUNDARY_CONCENTRATION",
    }:
        return {}, "UNSUPPORTED_SIGNAL_FAMILY"
    ranked = _ranked_automatic_mappings(signal, inventory_files, scope, roles)
    if not ranked:
        return {}, "NO_CLASSIFIED_MOVABLE_SOURCE_WITNESS"
    return ranked[0][2], None


def generate_virtual_layout_scenarios(
    inventory: Mapping[str, Any],
    metrics: Mapping[str, Any],
    opportunities: Mapping[str, Any],
    role_policy: Mapping[str, Any],
    *,
    candidate_mappings: Mapping[str, Mapping[str, str]] | None = None,
) -> dict[str, Any]:
    """Generate KEEP plus evidence-bound virtual mappings, without filesystem IO.

    Explicit candidate_mappings are a separate user-supplied comparison path;
    keys must be actual B3 opportunity IDs. Defaults are discovered from B3
    import witnesses only, never from package-name templates.
    """
    try:
        if not all(isinstance(x, Mapping) for x in (
            inventory, metrics, opportunities, role_policy
        )):
            raise ArchitectureScenarioError("mapping inputs required")
        expected = discover_architecture_opportunities(
            inventory, metrics, **opportunities["thresholds"]
        )
        if expected != opportunities:
            raise ArchitectureScenarioError("B3 opportunity report is not authentic to B1/B2")
        identity = inventory["source_identity"]
        if (identity["role_policy_sha256"] != _digest(role_policy)
                or identity["repository_commit_sha"] != metrics["snapshot_sha"]
                or opportunities["snapshot_sha"] != metrics["snapshot_sha"]
                or opportunities["inventory_id"] != inventory["inventory_id"]
                or opportunities["metrics_id"] != metrics["metrics_id"]
                or role_policy["scope"] != inventory["source_scope"]):
            raise ArchitectureScenarioError("source, profile or policy identity mismatch")
        scope = role_policy["scope"]
        roles = set(role_policy["roles"])
        files = {f["path"]: f for f in inventory["files"]}
        modules = {m["path"]: m for m in metrics["modules"]}
        pairs = metrics["resolved_pairs"]
        signals = {s["signal_id"]: s for s in opportunities["architecture_signals"]}
        questions = opportunities["question_opportunities"]
        if len(signals) != len(opportunities["architecture_signals"]):
            raise ArchitectureScenarioError("duplicate signal IDs")
        if any(not set(q["originating_signal_ids"]) <= signals.keys()
               or not q["originating_signal_ids"] for q in questions):
            raise ArchitectureScenarioError("orphan question opportunity")
        if len({q["opportunity_id"] for q in questions}) != len(questions):
            raise ArchitectureScenarioError("duplicate opportunity IDs")
        if candidate_mappings is not None and (
            not isinstance(candidate_mappings, Mapping)
            or not set(candidate_mappings) <= {
                q["opportunity_id"] for q in questions
            }
        ):
            raise ArchitectureScenarioError("untriggered explicit scenario")
    except (KeyError, TypeError, ValueError, ArchitectureOpportunityError) as exc:
        raise ArchitectureScenarioError("untrustworthy architecture scenario inputs") from exc

    baseline = {
        "resolved_pairs": len(pairs),
        "within_declared_pairs": metrics["denominators"]["within_declared_pairs"],
        "cross_declared_pairs": metrics["denominators"]["cross_declared_pairs"],
        "static_cycles": len(metrics["cycles"]),
        "source_files": len(files),
    }
    candidates: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for question in questions:
        qid = question["opportunity_id"]
        if candidate_mappings is None:
            signal = signals[question["originating_signal_ids"][0]]
            mapping, no_candidate = _automatic_mapping(signal, files, scope, roles)
        else:
            mapping = candidate_mappings.get(qid, {})
            no_candidate = None
        reason = no_candidate
        if not isinstance(mapping, Mapping) or not mapping:
            reason = reason or "NO_VIABLE_NONEMPTY_MAPPING"
        elif not all(_path_ok(a) and _path_ok(b) for a, b in mapping.items()):
            reason = "INVALID_PATH"
        elif any(a not in files or files[a]["read_state"] != "READ"
                 or files[a]["language"] != "python"
                 or _role(a, scope, roles) not in roles for a in mapping):
            reason = "UNCLASSIFIED_OR_UNREAD_SOURCE"
        elif any(a.endswith("/__init__.py") for a in mapping):
            reason = "PACKAGE_INITIALIZER_MOVE_UNSUPPORTED"
        elif any(_role(b, scope, roles) not in roles
                 or not b.endswith(".py") for b in mapping.values()):
            reason = "FROZEN_ROOT_OR_UNDECLARED_TARGET"
        elif any(a == b for a, b in mapping.items()):
            reason = "NO_OP_MAPPING"
        elif len(set(mapping.values())) != len(mapping):
            reason = "TARGET_COLLISION"
        elif any(b in files and b not in mapping for b in mapping.values()):
            reason = "TARGET_COLLISION"
        elif any(b in mapping for b in mapping.values()):
            reason = "CYCLIC_OR_CHAINED_MAPPING"
        elif any(a not in modules for a in mapping):
            reason = "UNANALYZED_MOVED_MODULE"
        elif any(
            a not in {
                p for sid in question["originating_signal_ids"]
                for w in signals[sid]["source_witnesses"]
                for p in (w["source_path"], w["target_path"])
            }
            for a in mapping
        ):
            reason = "MAPPING_SOURCE_NOT_IN_ORIGINATING_SIGNAL"
        if reason:
            rejection = {
                "opportunity_id": qid, "originating_signal_ids":
                question["originating_signal_ids"], "reason": reason,
            }
            if reason == "TARGET_COLLISION":
                # Preserve the exact source/target and file-hash evidence.
                # Never invent a different destination to evade this guard.
                collision_witnesses: list[dict[str, Any]] = []
                for source, destination in sorted(mapping.items()):
                    others = sorted(
                        other for other, target in mapping.items()
                        if other != source and target == destination
                    )
                    common = {
                        "source_path": source,
                        "proposed_target_path": destination,
                        "source_sha256": files[source]["source_sha256"],
                    }
                    if others:
                        collision_witnesses.append({
                            **common,
                            "collision_kind": "DUPLICATE_DESTINATION",
                            "conflicting_sources": others,
                        })
                    if destination in files and destination not in mapping:
                        collision_witnesses.append({
                            **common,
                            "collision_kind": "OCCUPIED_TARGET",
                            "occupied_target_sha256":
                                files[destination]["source_sha256"],
                        })
                rejection["collision_witnesses"] = sorted(
                    collision_witnesses,
                    key=lambda w: (w["source_path"], w["collision_kind"]),
                )
            rejected.append(rejection)
            continue

        remap = dict(sorted(mapping.items()))
        before_cross = after_cross = before_within = after_within = 0
        introduced_forbidden: list[dict[str, str]] = []
        rewrites: list[dict[str, Any]] = []
        for pair in pairs:
            src, dst = pair["source_path"], pair["target_path"]
            old_sr, old_dr = pair["source_role"], pair["target_role"]
            new_sr = _role(remap.get(src, src), scope, roles)
            new_dr = _role(remap.get(dst, dst), scope, roles)
            if old_sr in roles and old_dr in roles:
                before_cross += int(old_sr != old_dr)
                before_within += int(old_sr == old_dr)
            if new_sr in roles and new_dr in roles:
                after_cross += int(new_sr != new_dr)
                after_within += int(new_sr == new_dr)
                if new_dr in role_policy["roles"][new_sr]["forbidden_imports"]:
                    if old_dr not in role_policy["roles"][old_sr]["forbidden_imports"]:
                        introduced_forbidden.append({
                            "source_path": src, "target_path": dst,
                            "source_role": new_sr, "target_role": new_dr,
                        })
            if src in remap or dst in remap:
                for w in pair["witnesses"]:
                    rewrites.append({
                        "source_path": src, "target_path": dst,
                        "virtual_source_path": remap.get(src, src),
                        "virtual_target_path": remap.get(dst, dst),
                        "line": w["line"], "expression": w["expression"],
                        "source_sha256": w["source_sha256"],
                        "rewrite_status": "NOT_EVALUATED",
                    })
        if introduced_forbidden:
            rejected.append({
                "opportunity_id": qid,
                "originating_signal_ids": question["originating_signal_ids"],
                "reason": "NEW_DECLARED_BOUNDARY_VIOLATION",
                "witness_pairs": introduced_forbidden,
            })
            continue
        if (before_cross != baseline["cross_declared_pairs"]
                or before_within != baseline["within_declared_pairs"]):
            raise ArchitectureScenarioError("B2 pair denominators changed")
        candidate = {
            "opportunity_id": qid,
            "originating_signal_ids": question["originating_signal_ids"],
            "path_mapping": [
                {"from": a, "to": b, "source_sha256": files[a]["source_sha256"]}
                for a, b in remap.items()
            ],
            "rewrite_candidates": sorted(
                rewrites, key=lambda w: (w["source_path"], w["target_path"], w["line"])
            ),
            "measured_proxy_delta": {
                "cross_declared_pairs": after_cross - before_cross,
                "within_declared_pairs": after_within - before_within,
                "resolved_static_pairs": 0,
                "static_cycles": 0,
                "moved_files": len(remap),
            },
            "source_identity": {
                "snapshot_sha": metrics["snapshot_sha"],
                "inventory_id": inventory["inventory_id"],
                "metrics_id": metrics["metrics_id"],
                "role_policy_sha256": identity["role_policy_sha256"],
                "dependency_profile_id": metrics["dependency_profile_id"],
            },
            "evidence_class": "PROJECTED_PATH_ROLE_PROXY_ONLY",
            "decision": "NOT_EVALUATED",
            "unknowns": sorted(set([
                *opportunities["unknowns"],
                "PUBLIC_IMPORT_COMPATIBILITY_NOT_EVALUATED",
                "RELATIVE_IMPORT_AND_PACKAGE_REWRITE_NOT_EVALUATED",
                "SEMANTIC_OWNERSHIP_NOT_EVALUATED",
            ])),
            "limitations": [
                "all observed static graph edges and cycles are unchanged",
                "path-role relabeling cannot prove a real cohesion or coupling gain",
                "migration, package exports, runtime and external callers unverified",
            ],
        }
        candidate["scenario_id"] = _digest(candidate)
        candidates.append(candidate)

    # A top-ranked occupied target or newly forbidden boundary is a hard
    # rejection. Independently witnessed *other source files* may still be
    # assessed; never rename the rejected source's destination or relax its
    # role policy to manufacture a viable move. Retain every rejection.
    if candidate_mappings is None:
        for primary in tuple(rejected):
            if primary["reason"] not in {
                "TARGET_COLLISION", "NEW_DECLARED_BOUNDARY_VIOLATION",
            }:
                continue
            qid = primary["opportunity_id"]
            question = next(q for q in questions if q["opportunity_id"] == qid)
            signal = signals[question["originating_signal_ids"][0]]
            ranked = _ranked_automatic_mappings(signal, files, scope, roles)
            if not ranked:
                continue
            primary_source = ranked[0][0]
            attempts = 0
            for source, count, alternative in ranked[1:]:
                if source == primary_source or count < 2:
                    continue
                attempts += 1
                if attempts > 4:
                    break
                trial = generate_virtual_layout_scenarios(
                    inventory, metrics, opportunities, role_policy,
                    candidate_mappings={qid: alternative},
                )
                rejected.extend(
                    item for item in trial["rejected"]
                    if item["opportunity_id"] == qid
                )
                viable = [
                    item for item in trial["candidates"]
                    if item["opportunity_id"] == qid
                ]
                if viable:
                    candidates.extend(viable)
                    break

    result = {
        "schema_version": "0.1",
        "snapshot_sha": metrics["snapshot_sha"],
        "inventory_id": inventory["inventory_id"],
        "metrics_id": metrics["metrics_id"],
        "opportunities_id": opportunities["opportunities_id"],
        "role_policy_sha256": identity["role_policy_sha256"],
        "dependency_profile_id": metrics["dependency_profile_id"],
        "baseline": baseline,
        "candidates": sorted(candidates, key=lambda c: c["scenario_id"]),
        "rejected": sorted(rejected, key=lambda r: (r["opportunity_id"], r["reason"])),
        "evidence_status": "INCOMPLETE",
        "decision": "NOT_EVALUATED",
        "limitations": [
            "no scenarios generated without B3 source-triggered opportunities",
            "virtual paths do not change source bytes or static import edges",
            "external consumers, semantic ownership and import rewrites are unverified",
        ],
    }
    result["scenarios_id"] = _digest(result)
    return result
