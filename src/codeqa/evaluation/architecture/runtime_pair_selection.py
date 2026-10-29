"""Select exact-source B8 cross-role pairs for bounded runtime observation.

Selection authenticates the B1 inventory and B8 responsibility ledger, but
does not infer that a static import was executed or that a move is safe.
"""
from __future__ import annotations

from hashlib import sha256
import json
from collections.abc import Mapping
from typing import Any


class RuntimePairSelectionError(ValueError):
    """B8 source identity, denominator or selected pair cannot be trusted."""


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def select_b8_runtime_pairs(
    inventory: Mapping[str, Any],
    responsibility: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind *all* measured B8 pairs to inventory SHA-256 values, including zero."""
    try:
        head = inventory["source_identity"]["repository_commit_sha"]
        files = {f["path"]: f for f in inventory["files"]}
        edges = responsibility["edges"]
        if (
            inventory["schema_version"] != "0.1"
            or responsibility["schema_version"] != "0.1"
            or inventory["inventory_id"] != _digest({
                k: v for k, v in inventory.items() if k != "inventory_id"
            })
            or responsibility["responsibility_id"] != _digest({
                k: v for k, v in responsibility.items() if k != "responsibility_id"
            })
            or responsibility["source_identity"]["snapshot_sha"] != head
            or responsibility["source_identity"]["inventory_id"] != inventory["inventory_id"]
            or responsibility["observed_cross_role_pairs"] != len(edges)
            or responsibility["decision"] != "NOT_EVALUATED"
            or responsibility["test_behavior_coverage"] != "NOT_EVALUATED"
            or len(files) != len(inventory["files"])
        ):
            raise RuntimePairSelectionError("untrusted B8 source or denominator")
        pairs = []
        selected_paths: set[str] = set()
        for edge in edges:
            src, dst = edge["source_path"], edge["target_path"]
            if (
                not isinstance(src, str) or not isinstance(dst, str)
                or not src.startswith("src/") or not dst.startswith("src/")
                or not src.endswith(".py") or not dst.endswith(".py")
                or src == dst or edge["source_role"] == edge["target_role"]
                or not edge["import_witnesses"]
            ):
                raise RuntimePairSelectionError("invalid B8 cross-role pair")
            for path in (src, dst):
                record = files.get(path)
                if (
                    record is None or record["read_state"] != "READ"
                    or not isinstance(record["source_sha256"], str)
                    or len(record["source_sha256"]) != 64
                ):
                    raise RuntimePairSelectionError("unreadable selected source")
                selected_paths.add(path)
            for witness in edge["import_witnesses"]:
                if (
                    witness["source_path"] != src or witness["target_path"] != dst
                    or witness["source_sha256"] != files[src]["source_sha256"]
                    or type(witness["line"]) is not int or witness["line"] < 1
                ):
                    raise RuntimePairSelectionError("unbound import witness")
            pairs.append((src, dst))
        if len(set(pairs)) != len(pairs):
            raise RuntimePairSelectionError("duplicate B8 source/target pair")
        result = {
            "schema_version": "0.1",
            "source_identity": {
                "snapshot_sha": head,
                "inventory_id": inventory["inventory_id"],
                "responsibility_id": responsibility["responsibility_id"],
            },
            "observed_cross_role_pairs": len(pairs),
            "pairs": [list(p) for p in sorted(pairs)],
            "source_sha256": {
                path: files[path]["source_sha256"] for path in sorted(selected_paths)
            },
            "static_import_edge_traversal": "NOT_EVALUATED",
            "semantic_ownership": "NOT_EVALUATED",
            "decision": "NOT_EVALUATED",
        }
        result["selection_id"] = _digest(result)
        return result
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        raise RuntimePairSelectionError("invalid B8 runtime pair selection") from exc
