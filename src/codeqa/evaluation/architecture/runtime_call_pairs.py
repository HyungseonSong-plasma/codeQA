"""Opt-in, bounded Python call observations for Architecture QA.

A profiled Python frame-to-frame call is *not* evidence that a particular
static import was executed. The caller must supply an explicit test suite,
source snapshot claim, and a set of already measured source/target pairs.
This is local, current-thread execution, not independently attested CI.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
import unittest
from typing import Any


class RuntimeCallPairError(ValueError):
    """Invalid source identity, selected pair, or profiling precondition."""


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class _ObservedTests(unittest.TestResult):
    def __init__(self) -> None:
        super().__init__()
        self.current: str | None = None
        self.outcomes: dict[str, str] = {}

    def startTest(self, test: unittest.case.TestCase) -> None:
        test_id = test.id()
        if test_id in self.outcomes:
            raise RuntimeCallPairError("duplicate unittest identifier")
        self.current = test_id
        self.outcomes[test_id] = "STARTED"
        super().startTest(test)

    def stopTest(self, test: unittest.case.TestCase) -> None:
        super().stopTest(test)
        self.current = None

    def addSuccess(self, test: unittest.case.TestCase) -> None:
        super().addSuccess(test)
        self.outcomes[test.id()] = "PASSED"

    def addFailure(self, test: unittest.case.TestCase, err: Any) -> None:
        super().addFailure(test, err)
        self.outcomes[test.id()] = "FAILED"

    def addError(self, test: unittest.case.TestCase, err: Any) -> None:
        super().addError(test, err)
        self.outcomes[test.id()] = "ERROR"

    def addSkip(self, test: unittest.case.TestCase, reason: str) -> None:
        super().addSkip(test, reason)
        self.outcomes[test.id()] = "SKIPPED"

    def addExpectedFailure(self, test: unittest.case.TestCase, err: Any) -> None:
        super().addExpectedFailure(test, err)
        self.outcomes[test.id()] = "EXPECTED_FAILURE"

    def addUnexpectedSuccess(self, test: unittest.case.TestCase) -> None:
        super().addUnexpectedSuccess(test)
        self.outcomes[test.id()] = "UNEXPECTED_SUCCESS"


def capture_unittest_call_pairs(
    suite: unittest.TestSuite,
    *,
    snapshot_sha: str,
    repository_root: str | Path,
    source_sha256: Mapping[str, str],
    pairs: Sequence[tuple[str, str]],
    max_witnesses_per_pair: int = 8,
) -> dict[str, Any]:
    """Observe direct Python calls between selected source-file pairs.

    Files are checked against caller-supplied hashes before and after the suite.
    Python frame filenames and the Git SHA remain *claims*: neither the bytes
    actually loaded by the interpreter nor CI provenance are authenticated.
    Profiling covers the calling thread only, and may miss native/async paths.
    """
    if (not isinstance(suite, unittest.TestSuite)
            or not isinstance(snapshot_sha, str)
            or re.fullmatch(r"[0-9a-f]{40}", snapshot_sha) is None
            or not isinstance(source_sha256, Mapping)
            or not isinstance(pairs, (list, tuple))
            or type(max_witnesses_per_pair) is not int
            or not 1 <= max_witnesses_per_pair <= 100
            or sys.getprofile() is not None):
        raise RuntimeCallPairError("invalid execution/profile precondition")
    root = Path(repository_root).resolve()
    if not root.is_dir():
        raise RuntimeCallPairError("missing repository root")
    selected: dict[tuple[str, str], dict[str, Any]] = {}
    try:
        paths: set[str] = set()
        for pair in pairs:
            if (not isinstance(pair, (list, tuple)) or len(pair) != 2
                    or not all(isinstance(p, str) for p in pair)
                    or pair[0] == pair[1] or tuple(pair) in selected):
                raise RuntimeCallPairError("invalid or duplicate pair")
            selected[tuple(pair)] = {"count": 0, "witnesses": []}
            paths.update(pair)
        if not selected or set(source_sha256) != paths:
            raise RuntimeCallPairError("missing or extra source hashes")
        absolute: dict[str, str] = {}
        for relative in sorted(paths):
            parts = relative.split("/")
            if (not relative.startswith("src/") or not relative.endswith(".py")
                    or any(p in ("", ".", "..") for p in parts)):
                raise RuntimeCallPairError("unsafe source path")
            current = root
            for part in parts:
                current = current / part
                if current.is_symlink():
                    raise RuntimeCallPairError("symlinked source path")
            full = current.resolve()
            if not full.is_relative_to(root) or not full.is_file():
                raise RuntimeCallPairError("source escapes root or is absent")
            expected = source_sha256[relative]
            if (not isinstance(expected, str)
                    or re.fullmatch(r"[0-9a-f]{64}", expected) is None
                    or sha256(full.read_bytes()).hexdigest() != expected):
                raise RuntimeCallPairError("source hash mismatch")
            absolute[str(full)] = relative
    except (OSError, TypeError) as exc:
        raise RuntimeCallPairError("invalid source identity") from exc

    result = _ObservedTests()
    path_cache: dict[str, str | None] = {}

    def relative_path(filename: str) -> str | None:
        if filename not in path_cache:
            # Do not infer repository membership from an unqualified filename.
            path_cache[filename] = absolute.get(filename) if Path(filename).is_absolute() else None
        return path_cache[filename]

    def profile(frame: Any, event: str, arg: Any) -> None:
        if event != "call" or result.current is None or frame.f_back is None:
            return
        source = relative_path(frame.f_back.f_code.co_filename)
        target = relative_path(frame.f_code.co_filename)
        record = selected.get((source, target))
        if record is None:
            return
        record["count"] += 1
        if len(record["witnesses"]) < max_witnesses_per_pair:
            record["witnesses"].append({
                "test_id": result.current,
                "caller_line": frame.f_back.f_lineno,
                "callee_first_line": frame.f_code.co_firstlineno,
            })

    try:
        sys.setprofile(profile)
        suite.run(result)
    finally:
        sys.setprofile(None)
    try:
        for absolute_path, relative in absolute.items():
            if sha256(Path(absolute_path).read_bytes()).hexdigest() != source_sha256[relative]:
                raise RuntimeCallPairError("source changed during execution")
    except OSError as exc:
        raise RuntimeCallPairError("source unreadable after execution") from exc

    report = {
        "schema_version": "0.1",
        "source_identity": {
            "snapshot_sha_claim": snapshot_sha,
            "source_sha256": dict(sorted(source_sha256.items())),
        },
        "executed_tests": [
            {"test_id": name, "outcome": outcome}
            for name, outcome in sorted(result.outcomes.items())
        ],
        "tests_run": result.testsRun,
        "suite_was_successful": result.wasSuccessful(),
        "observed_pairs": [
            {"source_path": src, "target_path": dst,
             "observed_direct_python_calls": data["count"],
             "call_witnesses": data["witnesses"],
             "witnesses_truncated": data["count"] > len(data["witnesses"])}
            for (src, dst), data in sorted(selected.items())
        ],
        "evidence_class": "LOCAL_PYTHON_FRAME_CALL_UNATTESTED",
        "static_import_edge_traversal": "NOT_EVALUATED",
        "semantic_ownership": "NOT_EVALUATED",
        "public_api_compatibility": "NOT_EVALUATED",
        "decision": "NOT_EVALUATED",
        "limitations": [
            "direct frame calls do not prove the static import statement was executed",
            "frame filename and loaded code bytes are not independently attested",
            "only the current thread is profiled; native calls and other threads may be missed",
            "absence of a call is not evidence of absence of a dependency",
            "snapshot identity, external callers and semantic ownership are not attested",
        ],
    }
    report["observation_id"] = _digest(report)
    return report
