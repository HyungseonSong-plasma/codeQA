"""Correlate exact-source B8 import pairs with bounded Python call observations.

The join is a review ledger, not proof that an import statement executed, that
an unobserved edge is dead, or that a responsibility boundary is correct.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from hashlib import sha256
import json
from typing import Any


class RuntimeEdgeCorrelationError(ValueError):
    """A runtime witness cannot be bound to the B8 source/selection ledger."""


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _authentic(record: Mapping[str, Any], key: str) -> bool:
    return record[key] == _digest({k: v for k, v in record.items() if k != key})


def correlate_b8_runtime_pairs(
    selection: Mapping[str, Any],
    responsibility: Mapping[str, Any],
    observation: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Account for every measured static pair, including unobserved and zero.

    Observed direct Python frame calls are source-bound *call* evidence only.
    No inference of import-statement traversal or semantic ownership is made.
    """
    try:
        identity = selection["source_identity"]
        head = identity["snapshot_sha"]
        pairs = [tuple(p) for p in selection["pairs"]]
        edges = {(e["source_path"], e["target_path"]): e
                 for e in responsibility["edges"]}
        if (
            selection["schema_version"] != "0.1"
            or responsibility["schema_version"] != "0.1"
            or not _authentic(selection, "selection_id")
            or not _authentic(responsibility, "responsibility_id")
            or identity["responsibility_id"] != responsibility["responsibility_id"]
            or identity["inventory_id"] != responsibility["source_identity"]["inventory_id"]
            or head != responsibility["source_identity"]["snapshot_sha"]
            or selection["decision"] != "NOT_EVALUATED"
            or responsibility["decision"] != "NOT_EVALUATED"
            or selection["static_import_edge_traversal"] != "NOT_EVALUATED"
            or responsibility["semantic_ownership"] != "NOT_EVALUATED"
            or len(pairs) != selection["observed_cross_role_pairs"]
            or len(edges) != responsibility["observed_cross_role_pairs"]
            or len(edges) != len(responsibility["edges"])
            or len(set(pairs)) != len(pairs)
            or set(pairs) != set(edges)
            or any(len(p) != 2 or not all(isinstance(x, str) for x in p)
                   for p in pairs)
        ):
            raise RuntimeEdgeCorrelationError("untrusted B8 selection/responsibility")
        paths = {p for pair in pairs for p in pair}
        hashes = selection["source_sha256"]
        if set(hashes) != paths:
            raise RuntimeEdgeCorrelationError("source hash denominator mismatch")
        for pair, edge in edges.items():
            if (edge["source_role"] == edge["target_role"]
                    or not edge["import_witnesses"]
                    or any(w["source_path"] != pair[0]
                           or w["target_path"] != pair[1]
                           or w["source_sha256"] != hashes[pair[0]]
                           or type(w["line"]) is not int or w["line"] < 1
                           for w in edge["import_witnesses"])):
                raise RuntimeEdgeCorrelationError("unbound static import witness")
        if pairs:
            if observation is None:
                raise RuntimeEdgeCorrelationError("missing bounded runtime observation")
            observed = {(p["source_path"], p["target_path"]): p
                        for p in observation["observed_pairs"]}
            tests = {t["test_id"]: t["outcome"]
                     for t in observation["executed_tests"]}
            if (
                observation["schema_version"] != "0.1"
                or not _authentic(observation, "observation_id")
                or observation["source_identity"]["snapshot_sha_claim"] != head
                or observation["source_identity"]["source_sha256"] != hashes
                or observation["static_import_edge_traversal"] != "NOT_EVALUATED"
                or observation["decision"] != "NOT_EVALUATED"
                or observation["evidence_class"] != "LOCAL_PYTHON_FRAME_CALL_UNATTESTED"
                or observation["suite_was_successful"] is not True
                or type(observation["tests_run"]) is not int
                or observation["tests_run"] < 1
                or len(tests) != len(observation["executed_tests"])
                or len(tests) != observation["tests_run"]
                or any(v not in ("PASSED", "SKIPPED", "EXPECTED_FAILURE")
                       for v in tests.values())
                or len(observed) != len(observation["observed_pairs"])
                or set(observed) != set(pairs)
            ):
                raise RuntimeEdgeCorrelationError("untrusted runtime observation")
            for record in observed.values():
                count = record["observed_direct_python_calls"]
                witnesses = record["call_witnesses"]
                if (type(count) is not int or count < 0
                        or not isinstance(witnesses, list)
                        or len(witnesses) > count
                        or record["witnesses_truncated"] is not (count > len(witnesses))
                        or any(w["test_id"] not in tests
                               or tests[w["test_id"]] == "SKIPPED"
                               or type(w["caller_line"]) is not int
                               or w["caller_line"] < 1
                               or type(w["callee_first_line"]) is not int
                               or w["callee_first_line"] < 1
                               for w in witnesses)):
                    raise RuntimeEdgeCorrelationError("unbound call witness/count")
        else:
            if observation is not None:
                raise RuntimeEdgeCorrelationError("unexpected runtime observation for zero pairs")
            observed, tests = {}, {}

        by_role: dict[str, dict[str, int]] = defaultdict(
            lambda: {"static_pairs": 0, "direct_call_observed_pairs": 0, "direct_calls": 0}
        )
        records = []
        for source, target in sorted(pairs):
            edge = edges[(source, target)]
            calls = (observed[(source, target)]["observed_direct_python_calls"]
                     if observation is not None else 0)
            witnesses = (observed[(source, target)]["call_witnesses"]
                         if observation is not None else [])
            role = edge["target_role"]
            by_role[role]["static_pairs"] += 1
            by_role[role]["direct_call_observed_pairs"] += int(calls > 0)
            by_role[role]["direct_calls"] += calls
            records.append({
                "source_path": source,
                "target_path": target,
                "source_role": edge["source_role"],
                "target_role": role,
                "declared_policy_direction": edge["declared_policy_direction"],
                "import_witnesses": edge["import_witnesses"],
                "direct_python_calls": calls,
                "call_witnesses": witnesses,
                "witnesses_truncated": (
                    observed[(source, target)]["witnesses_truncated"]
                    if observation is not None else False
                ),
                "runtime_observation": (
                    "OBSERVED_DIRECT_PYTHON_CALL" if calls else "NOT_OBSERVED_IN_SAMPLE"
                ),
                "static_import_edge_traversal": "NOT_EVALUATED",
                "semantic_ownership": "NOT_EVALUATED",
            })
        total_observed = sum(v["direct_call_observed_pairs"] for v in by_role.values())
        result = {
            "schema_version": "0.1",
            "source_identity": identity,
            "selection_id": selection["selection_id"],
            "observation_id": observation["observation_id"] if observation else None,
            "static_pairs": len(pairs),
            "direct_call_observed_pairs": total_observed,
            "not_observed_in_sample_pairs": len(pairs) - total_observed,
            "direct_python_calls": sum(v["direct_calls"] for v in by_role.values()),
            "executed_tests": len(tests),
            "by_target_role": dict(sorted(by_role.items())),
            "edges": records,
            "static_import_edge_traversal": "NOT_EVALUATED",
            "semantic_ownership": "NOT_EVALUATED",
            "external_consumers": "NOT_EVALUATED",
            "public_api_compatibility": "NOT_EVALUATED",
            "decision": "NOT_EVALUATED",
            "limitations": [
                "a direct Python call does not prove execution of the static import witness",
                "a zero call count is not evidence of a dead dependency or bad ownership",
                "role policy direction is not a semantic responsibility decision",
                "sampled test execution does not cover all tests, threads or native calls",
                "external/dynamic consumers and public API compatibility are NOT_EVALUATED",
            ],
        }
        result["correlation_id"] = _digest(result)
        return result
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        raise RuntimeEdgeCorrelationError("invalid B8 runtime correlation inputs") from exc
