"""Exact-source candidate test assertions for observed architecture edges.

An import and a call/assert in one test are static proximity, not proof that
any downstream dependency edge is exercised or semantically well owned.
"""
from __future__ import annotations

import ast
from collections.abc import Mapping
from hashlib import sha256
import json
from typing import Any


class TestBehaviorCandidateError(ValueError):
    """Source, import witness or report identity is not trustworthy."""


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _root_name(node: ast.AST) -> str | None:
    while isinstance(node, ast.Attribute):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _candidate_sites(text: str, import_lines: set[int]) -> tuple[list[dict[str, Any]], str]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return [], "PARSE_FAILED"
    aliases: set[str] = set()
    for node in ast.walk(tree):
        if getattr(node, "lineno", None) not in import_lines:
            continue
        if isinstance(node, ast.ImportFrom):
            aliases.update(a.asname or a.name for a in node.names if a.name != "*")
        elif isinstance(node, ast.Import):
            # Unaliased imports bind a package root, not an unambiguous module.
            aliases.update(a.asname for a in node.names if a.asname)
    if not aliases:
        return [], "NO_UNAMBIGUOUS_IMPORT_BINDING"
    results = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or not node.name.startswith("test_"):
            continue
        calls: set[int] = set()
        assertions: set[int] = set()
        for item in ast.walk(node):
            if isinstance(item, ast.Call):
                if _root_name(item.func) in aliases:
                    calls.add(item.lineno)
                if (isinstance(item.func, ast.Attribute)
                        and item.func.attr.startswith("assert")
                        and _root_name(item.func) == "self"):
                    assertions.add(item.lineno)
            elif isinstance(item, ast.Assert):
                assertions.add(item.lineno)
        if calls and assertions:
            results.append({
                "test_function": node.name,
                "test_function_line": node.lineno,
                "candidate_call_lines": sorted(calls),
                "assertion_lines": sorted(assertions),
                "evidence_class": "STATIC_CANDIDATE_NOT_BEHAVIORAL_COVERAGE",
            })
    return sorted(results, key=lambda x: (x["test_function_line"], x["test_function"])), "PARSED"


def census_test_behavior_candidates(
    inventory: Mapping[str, Any],
    responsibility: Mapping[str, Any],
    test_sources: Mapping[str, bytes | str],
) -> dict[str, Any]:
    """Join authenticated test import sites to nearby static test call/assert sites.

    The caller reads exact HEAD Git blobs; every supplied byte string must match
    the B1 inventory SHA-256. No working-tree reads occur in this evaluator.
    """
    try:
        identity = inventory["source_identity"]
        source_sha = identity["repository_commit_sha"]
        if (inventory["schema_version"] != "0.1"
                or responsibility["schema_version"] != "0.1"
                or inventory["inventory_id"] != _digest({
                    k: v for k, v in inventory.items() if k != "inventory_id"
                })
                or responsibility["responsibility_id"] != _digest({
                    k: v for k, v in responsibility.items() if k != "responsibility_id"
                })
                or responsibility["source_identity"]["snapshot_sha"] != source_sha
                or responsibility["source_identity"]["inventory_id"] != inventory["inventory_id"]
                or responsibility["decision"] != "NOT_EVALUATED"
                or responsibility["observed_cross_role_pairs"] != len(responsibility["edges"])
                or responsibility["test_behavior_coverage"] != "NOT_EVALUATED"):
            raise TestBehaviorCandidateError("report/source identity mismatch")
        files = {item["path"]: item for item in inventory["files"]}
        if len(files) != len(inventory["files"]):
            raise TestBehaviorCandidateError("duplicate inventory path")
        expected: dict[str, set[int]] = {}
        edges = responsibility["edges"]
        keys = {(e["signal_id"], e["source_path"], e["target_path"]) for e in edges}
        if len(keys) != len(edges):
            raise TestBehaviorCandidateError("duplicate measured edge")
        for edge in edges:
            for witness in edge["known_test_path_importers"]:
                path = witness["source_path"]
                if (not path.startswith("tests/") or not path.endswith(".py")
                        or witness["target_path"] != edge["source_path"]
                        or path not in files or files[path]["read_state"] != "READ"
                        or witness["source_sha256"] != files[path]["source_sha256"]
                        or type(witness["line"]) is not int or witness["line"] < 1):
                    raise TestBehaviorCandidateError("unbound test import witness")
                expected.setdefault(path, set()).add(witness["line"])
        if set(test_sources) != set(expected):
            raise TestBehaviorCandidateError("missing or unrelated test source")
        decoded: dict[str, str | None] = {}
        for path, raw in test_sources.items():
            if not isinstance(raw, (bytes, str)):
                raise TestBehaviorCandidateError("invalid test source bytes")
            raw_bytes = raw.encode("utf-8") if isinstance(raw, str) else raw
            if sha256(raw_bytes).hexdigest() != files[path]["source_sha256"]:
                raise TestBehaviorCandidateError("test source SHA-256 mismatch")
            try:
                decoded[path] = raw_bytes.decode("utf-8")
            except UnicodeDecodeError:
                decoded[path] = None
        records = []
        total = 0
        for edge in edges:
            by_path: dict[str, set[int]] = {}
            for w in edge["known_test_path_importers"]:
                by_path.setdefault(w["source_path"], set()).add(w["line"])
            sites = []
            for path, lines in sorted(by_path.items()):
                if decoded[path] is None:
                    candidates, parse_status = [], "DECODE_FAILED"
                else:
                    candidates, parse_status = _candidate_sites(decoded[path], lines)
                total += len(candidates)
                sites.append({
                    "test_path": path,
                    "test_source_sha256": files[path]["source_sha256"],
                    "import_lines": sorted(lines),
                    "parse_status": parse_status,
                    "candidate_tests": candidates,
                })
            records.append({
                "signal_id": edge["signal_id"],
                "source_path": edge["source_path"],
                "target_path": edge["target_path"],
                "candidate_test_paths": sites,
                "behavioral_edge_coverage": "NOT_EVALUATED",
                "semantic_ownership": "NOT_EVALUATED",
            })
        result: dict[str, Any] = {
            "schema_version": "0.1",
            "source_identity": {
                "snapshot_sha": source_sha,
                "inventory_id": inventory["inventory_id"],
                "responsibility_id": responsibility["responsibility_id"],
            },
            "observed_cross_role_pairs": len(records),
            "candidate_test_functions_across_edges": total,
            "edges": records,
            "decision": "NOT_EVALUATED",
            "limitations": [
                "test import, call and assertion in one function are static proximity only",
                "test assertions may not inspect the imported call result or downstream edge",
                "module import may be indirect, mocked, shadowed, or never executed",
                "no candidate does not establish absent behavioral coverage",
                "runtime, external consumers, semantic ownership and compatibility remain NOT_EVALUATED",
            ],
        }
        result["candidate_id"] = _digest(result)
        return result
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        raise TestBehaviorCandidateError("untrustworthy test behavior candidates") from exc


def render_test_behavior_candidates_markdown(report: Mapping[str, Any]) -> str:
    """Render review candidates without promoting them to verified behavior."""
    try:
        if (report["candidate_id"] != _digest({
                k: v for k, v in report.items() if k != "candidate_id"
            }) or report["decision"] != "NOT_EVALUATED"
                or report["observed_cross_role_pairs"] != len(report["edges"])):
            raise TestBehaviorCandidateError("modified candidate report")
        lines = [
            "## Candidate behavioral test witnesses (static only)", "",
            "Source HEAD: " + report["source_identity"]["snapshot_sha"],
            "Observed cross-role pairs: " + str(report["observed_cross_role_pairs"]),
            "Candidate test functions across edges: "
            + str(report["candidate_test_functions_across_edges"]),
            "Call/assert proximity is NOT behavioral coverage or semantic ownership.",
        ]
        for edge in report["edges"]:
            for path in edge["candidate_test_paths"]:
                for test in path["candidate_tests"]:
                    lines.append(
                        "- `" + edge["source_path"] + "` -> `" + edge["target_path"]
                        + "`: `" + path["test_path"] + ":"
                        + str(test["test_function_line"]) + "` "
                        + test["test_function"] + " (call="
                        + str(test["candidate_call_lines"]) + ", assertion="
                        + str(test["assertion_lines"]) + "; candidate only)"
                    )
        lines.extend(["", "Behavioral edge coverage, external callers and runtime/API compatibility: NOT_EVALUATED.", ""])
        return "\n".join(lines)
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        raise TestBehaviorCandidateError("untrustworthy candidate renderer") from exc
