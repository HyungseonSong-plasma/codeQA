"""Bounded cold-interpreter import-line entry evidence for Architecture QA.

Opt-in execution of caller-selected Python modules in a fresh isolated child.
Line entry is *not* proof of import completion, target binding or ownership.
"""
from __future__ import annotations

import ast
from collections.abc import Mapping
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


class ImportInitializationError(ValueError):
    """Invalid source selection, probe execution or evidence envelope."""


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


# The child starts with -I -B and installs tracing before importing selected
# modules. Source bytes are verified both before and after those imports.
_CHILD = r'''
import contextlib, hashlib, importlib, io, json, pathlib, sys
request = json.loads(sys.stdin.read())
root = pathlib.Path(request["root"])
paths = request["source_sha256"]
lines = request["lines"]
limit = request["limit"]

def verify():
    for rel, digest in paths.items():
        if hashlib.sha256((root / rel).read_bytes()).hexdigest() != digest:
            raise ValueError("source hash changed")

verify()
selected = {str((root / rel).resolve()): rel for rel in lines}
counts = {rel: {str(line): 0 for line in numbers} for rel, numbers in lines.items()}
truncated = False

def trace(frame, event, arg):
    global truncated
    if event == "call":
        return trace if frame.f_code.co_filename in selected else None
    if event == "line":
        rel = selected.get(frame.f_code.co_filename)
        if rel is not None:
            key = str(frame.f_lineno)
            if key in counts[rel]:
                if counts[rel][key] < limit:
                    counts[rel][key] += 1
                else:
                    truncated = True
    return trace

sys.path.insert(0, str(root / "src"))
statuses = {}
with contextlib.redirect_stdout(io.StringIO()):
    sys.settrace(trace)
    try:
        for module in request["modules"]:
            try:
                importlib.import_module(module)
            except Exception as exc:
                statuses[module] = "IMPORT_ERROR:" + type(exc).__name__
            else:
                statuses[module] = "IMPORTED"
    finally:
        sys.settrace(None)
verify()
print(json.dumps({"line_counts": counts, "module_statuses": statuses,
                  "truncated": truncated}, sort_keys=True))
'''


def capture_cold_import_line_entries(
    selection: Mapping[str, Any],
    responsibility: Mapping[str, Any],
    *,
    repository_root: str | Path,
    timeout_seconds: int = 25,
    max_line_visits: int = 1000,
) -> dict[str, Any]:
    """Trace selected import lines during fresh-interpreter module initialization.

    This executes selected repository code. Use only for trusted checked-out
    sources; the snapshot SHA and actual interpreter bytecode are not attested.
    """
    try:
        identity = selection["source_identity"]
        pairs = [tuple(p) for p in selection["pairs"]]
        edges = {(e["source_path"], e["target_path"]): e
                 for e in responsibility["edges"]}
        hashes = selection["source_sha256"]
        if (selection["schema_version"] != "0.1"
                or responsibility["schema_version"] != "0.1"
                or selection["selection_id"] != _digest({
                    k: v for k, v in selection.items() if k != "selection_id"})
                or responsibility["responsibility_id"] != _digest({
                    k: v for k, v in responsibility.items() if k != "responsibility_id"})
                or identity["snapshot_sha"] != responsibility["source_identity"]["snapshot_sha"]
                or identity["responsibility_id"] != responsibility["responsibility_id"]
                or selection["decision"] != "NOT_EVALUATED"
                or responsibility["decision"] != "NOT_EVALUATED"
                or len(pairs) != selection["observed_cross_role_pairs"]
                or len(edges) != responsibility["observed_cross_role_pairs"]
                or len(edges) != len(responsibility["edges"])
                or len(set(pairs)) != len(pairs)
                or set(pairs) != set(edges)
                or set(hashes) != {p for pair in pairs for p in pair}
                or type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 120
                or type(max_line_visits) is not int or not 1 <= max_line_visits <= 10000
                or re.fullmatch(r"[0-9a-f]{40}", identity["snapshot_sha"]) is None):
            raise ImportInitializationError("untrusted selection or denominator")
        root = Path(repository_root).resolve(strict=True)
        if not root.is_dir():
            raise ImportInitializationError("missing repository root")
        modules = {}
        for path, expected in hashes.items():
            parts = path.split("/")
            if (len(parts) < 3 or parts[0] != "src"
                    or not path.endswith(".py")
                    or any(re.fullmatch(r"[A-Za-z_]\w*", part) is None
                           for part in parts[1:-1])
                    or re.fullmatch(r"[A-Za-z_]\w*\.py", parts[-1]) is None
                    or re.fullmatch(r"[0-9a-f]{64}", expected) is None):
                raise ImportInitializationError("unsafe source path or digest")
            current = root
            for part in parts:
                current = current / part
                if current.is_symlink():
                    raise ImportInitializationError("symlinked source")
            if not current.is_file() or sha256(current.read_bytes()).hexdigest() != expected:
                raise ImportInitializationError("source differs from selected hash")
            if path in {p[0] for p in pairs}:
                modules[path] = ".".join(parts[1:-1] + [parts[-1][:-3]])
        line_map: dict[str, set[int]] = {path: set() for path in modules}
        for src, dst in pairs:
            witnesses = edges[(src, dst)]["import_witnesses"]
            if not witnesses:
                raise ImportInitializationError("missing import witness")
            for w in witnesses:
                if (w["source_path"] != src or w["target_path"] != dst
                        or w["source_sha256"] != hashes[src]
                        or type(w["line"]) is not int or w["line"] < 1):
                    raise ImportInitializationError("invalid import witness")
                line_map[src].add(w["line"])
        for src, lines in line_map.items():
            parsed = ast.parse((root / src).read_bytes(), filename=src)
            actual = {n.lineno for n in ast.walk(parsed)
                      if isinstance(n, (ast.Import, ast.ImportFrom))}
            if not lines <= actual:
                raise ImportInitializationError("witness line is not import AST")
        records = []
        if pairs:
            request = {"root": str(root), "source_sha256": hashes,
                       "lines": {k: sorted(v) for k, v in line_map.items()},
                       "modules": sorted(set(modules.values())), "limit": max_line_visits}
            completed = subprocess.run(
                [sys.executable, "-I", "-B", "-c", _CHILD],
                input=json.dumps(request), text=True, capture_output=True,
                cwd=root, timeout=timeout_seconds, check=False,
            )
            if completed.returncode or len(completed.stdout) > 1_000_000:
                raise ImportInitializationError("cold import probe failed")
            child = json.loads(completed.stdout)
            counts, statuses = child["line_counts"], child["module_statuses"]
            if (set(counts) != set(line_map)
                    or set(statuses) != set(modules.values())
                    or type(child["truncated"]) is not bool):
                raise ImportInitializationError("invalid child denominator")
            for src, lines in line_map.items():
                if (set(counts[src]) != {str(line) for line in lines}
                        or any(type(value) is not int or not 0 <= value <= max_line_visits
                               for value in counts[src].values())):
                    raise ImportInitializationError("invalid child line evidence")
            for path, expected in hashes.items():
                if sha256((root / path).read_bytes()).hexdigest() != expected:
                    raise ImportInitializationError("source changed during probe")
        else:
            counts, statuses, child = {}, {}, {"truncated": False}
        for src, dst in sorted(pairs):
            witnesses = sorted({w["line"] for w in edges[(src, dst)]["import_witnesses"]})
            visits = sum(counts[src][str(line)] for line in witnesses)
            records.append({"source_path": src, "target_path": dst,
                            "import_lines": witnesses, "line_entries": visits,
                            "module_status": statuses[modules[src]],
                            "import_target_resolution": "NOT_EVALUATED"})
        report = {
            "schema_version": "0.1", "source_identity": identity,
            "selection_id": selection["selection_id"],
            "responsibility_id": responsibility["responsibility_id"],
            "static_pairs": len(records),
            "pairs_with_line_entries": sum(r["line_entries"] > 0 for r in records),
            "records": records,
            "module_statuses": statuses,
            "line_visits_truncated": child["truncated"],
            "evidence_class": "COLD_INTERPRETER_LINE_ENTRY_UNATTESTED",
            "import_target_resolution": "NOT_EVALUATED",
            "semantic_ownership": "NOT_EVALUATED",
            "public_api_compatibility": "NOT_EVALUATED",
            "decision": "NOT_EVALUATED",
            "limitations": [
                "line entry occurs before import execution and does not prove target resolution",
                "selected modules execute code in a child; source SHA is a checkout claim",
                "import errors and optional imports can leave unobserved edges",
                "external/dynamic consumers, loaded bytecode and semantic ownership are unverified",
            ],
        }
        report["probe_id"] = _digest(report)
        return report
    except (OSError, TypeError, KeyError, AttributeError, ValueError,
            SyntaxError, subprocess.TimeoutExpired) as exc:
        raise ImportInitializationError("invalid cold import initialization evidence") from exc
