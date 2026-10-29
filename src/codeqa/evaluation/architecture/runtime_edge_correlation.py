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
            line_state = observation.get("import_line_observation", "NOT_EVALUATED")
            if line_state not in (
                "NOT_EVALUATED", "LOCAL_PYTHON_LINE_EVENT_UNATTESTED"
            ):
                raise RuntimeEdgeCorrelationError("untrusted import-line evidence class")
            line_mode = line_state == "LOCAL_PYTHON_LINE_EVENT_UNATTESTED"
            for pair, record in observed.items():
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
                if line_mode:
                    lines = sorted({w["line"] for w in edges[pair]["import_witnesses"]})
                    visits = record["import_line_visits"]
                    line_witnesses = record["import_line_witnesses"]
                    if (record["selected_import_lines"] != lines
                            or type(visits) is not int or visits < 0
                            or not isinstance(line_witnesses, list)
                            or len(line_witnesses) > visits
                            or record["import_lines_truncated"] is not (
                                visits > len(line_witnesses)
                            )
                            or any(w["test_id"] not in tests
                                   or tests[w["test_id"]] == "SKIPPED"
                                   or type(w["line"]) is not int
                                   or w["line"] not in lines
                                   for w in line_witnesses)):
                        raise RuntimeEdgeCorrelationError("unbound import-line witness")
                elif any(key in record for key in (
                    "import_line_visits", "import_line_witnesses",
                    "selected_import_lines", "import_lines_truncated"
                )):
                    raise RuntimeEdgeCorrelationError("unexpected import-line evidence")
        else:
            if observation is not None:
                raise RuntimeEdgeCorrelationError("unexpected runtime observation for zero pairs")
            observed, tests = {}, {}
            line_mode = False

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
                **({
                    "import_line_visits": observed[(source, target)]["import_line_visits"],
                    "import_line_witnesses": observed[(source, target)]["import_line_witnesses"],
                    "import_line_observation": (
                        "OBSERVED_IMPORT_LINE_ENTRY"
                        if observed[(source, target)]["import_line_visits"]
                        else "NOT_OBSERVED_IN_SAMPLE"
                    ),
                } if line_mode else {}),
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
                "an import-line event occurs before import execution and does not prove target resolution",
                "a zero call count is not evidence of a dead dependency or bad ownership",
                "role policy direction is not a semantic responsibility decision",
                "sampled test execution does not cover all tests, threads or native calls",
                "external/dynamic consumers and public API compatibility are NOT_EVALUATED",
            ],
        }
        if line_mode:
            result["import_line_visited_pairs"] = sum(
                edge["import_line_visits"] > 0 for edge in records
            )
            result["not_visited_import_line_pairs"] = (
                len(records) - result["import_line_visited_pairs"]
            )
            result["import_line_visits"] = sum(
                edge["import_line_visits"] for edge in records
            )
            result["import_line_observation"] = "LOCAL_PYTHON_LINE_EVENT_UNATTESTED"
        result["correlation_id"] = _digest(result)
        return result
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        raise RuntimeEdgeCorrelationError("invalid B8 runtime correlation inputs") from exc
