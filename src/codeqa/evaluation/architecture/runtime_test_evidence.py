"""Opt-in unittest execution receipts for Architecture QA review.

Execution of a test is not proof that an import edge was traversed. The caller
must choose the suite and supply source identity from a separately verified Git
snapshot. This module does not discover or run repository tests implicitly.
"""
from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
import json
import re
import unittest
from typing import Any


class RuntimeTestEvidenceError(ValueError):
    """A receipt or its declared source identity is inconsistent."""


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class _ReceiptResult(unittest.TestResult):
    def __init__(self) -> None:
        super().__init__()
        self.outcomes: dict[str, str] = {}

    def startTest(self, test: unittest.case.TestCase) -> None:
        identifier = test.id()
        if identifier in self.outcomes:
            raise RuntimeTestEvidenceError("duplicate executed test identifier")
        self.outcomes[identifier] = "STARTED"
        super().startTest(test)

    def addSuccess(self, test: unittest.case.TestCase) -> None:
        super().addSuccess(test)
        self.outcomes[test.id()] = "PASSED"

    def addFailure(self, test: unittest.case.TestCase, err: Any) -> None:
        super().addFailure(test, err)
        # A test can error in its body and then fail in tearDown. Retain
        # the more severe result while preserving unittest's own accounting.
        if test.id() in self.outcomes and self.outcomes[test.id()] != "ERROR":
            self.outcomes[test.id()] = "FAILED"

    def addError(self, test: unittest.case.TestCase, err: Any) -> None:
        super().addError(test, err)
        # unittest uses synthetic _ErrorHolder objects for setUpClass/tearDownClass
        # failures. They are suite errors, not executed test methods.
        if test.id() in self.outcomes:
            self.outcomes[test.id()] = "ERROR"

    def addSubTest(
        self, test: unittest.case.TestCase, subtest: unittest.case.TestCase,
        err: Any,
    ) -> None:
        # unittest reports failed subtests here, not through addFailure.
        # Without this hook a failed method remains misleadingly STARTED.
        super().addSubTest(test, subtest, err)
        if err is not None:
            status = ("FAILED" if issubclass(err[0], test.failureException)
                      else "ERROR")
            # A later assertion failure must not mask an earlier subtest error.
            if test.id() in self.outcomes and self.outcomes[test.id()] != "ERROR":
                self.outcomes[test.id()] = status

    def addSkip(self, test: unittest.case.TestCase, reason: str) -> None:
        super().addSkip(test, reason)
        # A skip raised during tearDown must not hide an earlier error/failure.
        if test.id() in self.outcomes and self.outcomes[test.id()] not in {"ERROR", "FAILED"}:
            self.outcomes[test.id()] = "SKIPPED"

    def addExpectedFailure(self, test: unittest.case.TestCase, err: Any) -> None:
        super().addExpectedFailure(test, err)
        self.outcomes[test.id()] = "EXPECTED_FAILURE"

    def addUnexpectedSuccess(self, test: unittest.case.TestCase) -> None:
        super().addUnexpectedSuccess(test)
        self.outcomes[test.id()] = "UNEXPECTED_SUCCESS"


def capture_unittest_execution(
    suite: unittest.TestSuite,
    *,
    snapshot_sha: str,
    test_path: str,
    test_source: bytes,
    expected_source_sha256: str,
) -> dict[str, Any]:
    """Execute an explicitly provided suite and return bounded local outcomes.

    snapshot_sha is a caller-supplied claim, NOT Git/CI attestation.
    test_source is checked against a caller-supplied inventory hash, but
    this cannot establish that the interpreter loaded those exact bytes.
    """
    if (not isinstance(suite, unittest.TestSuite)
            or not isinstance(snapshot_sha, str)
            or re.fullmatch(r"[0-9a-f]{40}", snapshot_sha) is None
            or not isinstance(test_path, str)
            or not test_path.startswith("tests/") or not test_path.endswith(".py")
            or any(part in ("", ".", "..") for part in test_path.split("/"))
            or "\\" in test_path
            or not isinstance(test_source, bytes)
            or not isinstance(expected_source_sha256, str)
            or sha256(test_source).hexdigest() != expected_source_sha256):
        raise RuntimeTestEvidenceError("invalid or mismatched source identity")
    result = _ReceiptResult()
    suite.run(result)
    outcomes = [
        {"test_id": name, "outcome": status}
        for name, status in sorted(result.outcomes.items())
    ]
    receipt: dict[str, Any] = {
        "schema_version": "0.1",
        "source_identity": {
            "snapshot_sha_claim": snapshot_sha,
            "test_path": test_path,
            "test_source_sha256": expected_source_sha256,
        },
        "executed_tests": outcomes,
        "tests_run": result.testsRun,
        "suite_was_successful": result.wasSuccessful(),
        "all_passed": (result.wasSuccessful() and bool(outcomes)
                       and result.testsRun == len(outcomes)
                       and all(x["outcome"] == "PASSED" for x in outcomes)),
        "evidence_class": "LOCAL_UNITTEST_EXECUTION_UNATTESTED",
        "edge_traversal": "NOT_EVALUATED",
        "semantic_ownership": "NOT_EVALUATED",
        "limitations": [
            "snapshot identity and loaded test bytes are not independently attested",
            "unittest execution does not prove any observed import edge was traversed",
            "mocks, dynamic imports, external consumers and public API compatibility remain NOT_EVALUATED",
        ],
    }
    receipt["receipt_id"] = _digest(receipt)
    return receipt


def _test_id_belongs_to_path(test_id: str, test_path: str) -> bool:
    """Fail closed on a same-named test from a different Python module.

    unittest IDs use module.Class.method. Discovery may import a test module
    with or without its leading tests package; arbitrary module suffixes are
    not accepted. This is only a lexical binding, NOT loaded-byte attestation.
    """
    if not isinstance(test_id, str) or not isinstance(test_path, str):
        return False
    parts = test_id.split(".")
    if len(parts) < 3:
        return False
    expected = test_path.removeprefix("tests/").removesuffix(".py").replace("/", ".")
    module = ".".join(parts[:-2])
    return module in (expected, "tests." + expected)


def correlate_runtime_test_candidates(
    candidates: Mapping[str, Any], receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Associate a local unittest result with static candidates, never edge PASS.

    A method name must match exactly one executed test ID. Duplicate class
    methods or an unexecuted test remain ambiguous or unmatched, respectively.
    """
    try:
        if (candidates["candidate_id"] != _digest({
                k: v for k, v in candidates.items() if k != "candidate_id"
            }) or receipt["receipt_id"] != _digest({
                k: v for k, v in receipt.items() if k != "receipt_id"
            }) or candidates["decision"] != "NOT_EVALUATED"
                or receipt["schema_version"] != "0.1"
                or receipt["evidence_class"] != "LOCAL_UNITTEST_EXECUTION_UNATTESTED"
                or receipt["edge_traversal"] != "NOT_EVALUATED"
                or receipt["semantic_ownership"] != "NOT_EVALUATED"
                or candidates["source_identity"]["snapshot_sha"] != receipt["source_identity"]["snapshot_sha_claim"]
                or receipt["tests_run"] != len(receipt["executed_tests"])):
            raise RuntimeTestEvidenceError("receipt/candidate identity mismatch")
        path = receipt["source_identity"]["test_path"]
        source_hash = receipt["source_identity"]["test_source_sha256"]
        # Correlation accepts untrusted, caller-rehashed receipts. The digest
        # is not an attestation: revalidate the same bounded source-identity
        # shape required when the receipt was originally captured.
        snapshot_claim = receipt["source_identity"]["snapshot_sha_claim"]
        if (not isinstance(snapshot_claim, str)
                or re.fullmatch(r"[0-9a-f]{40}", snapshot_claim) is None
                or not isinstance(path, str)
                or not path.startswith("tests/")
                or not path.endswith(".py")
                or "\\" in path
                or any(part in ("", ".", "..") for part in path.split("/"))
                or not isinstance(source_hash, str)
                or re.fullmatch(r"[0-9a-f]{64}", source_hash) is None):
            raise RuntimeTestEvidenceError("invalid runtime receipt source identity")
        outcomes = receipt["executed_tests"]
        # A digest is only an integrity checksum, not a trusted signature.
        # Reject internally impossible unittest claims even when a caller
        # recomputes receipt_id after modifying the payload.
        valid_outcomes = {
            "STARTED", "PASSED", "FAILED", "ERROR", "SKIPPED",
            "EXPECTED_FAILURE", "UNEXPECTED_SUCCESS",
        }
        if (not isinstance(outcomes, list)
                or type(receipt["tests_run"]) is not int
                or type(receipt["all_passed"]) is not bool
                or type(receipt["suite_was_successful"]) is not bool
                or any(
                    not isinstance(row, Mapping)
                    or not isinstance(row.get("test_id"), str)
                    or not row["test_id"]
                    or not isinstance(row.get("outcome"), str)
                    or row["outcome"] not in valid_outcomes
                    for row in outcomes
                )
                # unittest.TestResult.wasSuccessful() is false when a test
                # fails, errors, or unexpectedly succeeds. A caller can
                # recompute receipt_id, so the summary must agree with rows.
                or (receipt["suite_was_successful"] and any(
                    row["outcome"] in {"FAILED", "ERROR", "UNEXPECTED_SUCCESS"}
                    for row in outcomes
                ))
                or receipt["all_passed"] != (
                    receipt["suite_was_successful"]
                    and bool(outcomes)
                    and all(row["outcome"] == "PASSED" for row in outcomes)
                )):
            raise RuntimeTestEvidenceError("inconsistent unittest outcomes")
        if len({r["test_id"] for r in outcomes}) != len(outcomes):
            raise RuntimeTestEvidenceError("duplicate executed test ID")
        matches = []
        for edge in candidates["edges"]:
            for site in edge["candidate_test_paths"]:
                if site["test_path"] != path:
                    continue
                if site["test_source_sha256"] != source_hash:
                    raise RuntimeTestEvidenceError("test source mismatch")
                for candidate in site["candidate_tests"]:
                    name = candidate["test_function"]
                    matching = [
                        r for r in outcomes
                        if r["test_id"].endswith("." + name)
                        and _test_id_belongs_to_path(r["test_id"], path)
                    ]
                    matches.append({
                        "source_path": edge["source_path"],
                        "target_path": edge["target_path"],
                        "test_function": name,
                        "match_state": "UNIQUE" if len(matching) == 1 else (
                            "AMBIGUOUS" if matching else "NOT_EXECUTED"
                        ),
                        "unittest_outcome": matching[0]["outcome"] if len(matching) == 1 else None,
                        "edge_traversal": "NOT_EVALUATED",
                    })
        output = {
            "schema_version": "0.1",
            "candidate_id": candidates["candidate_id"],
            "receipt_id": receipt["receipt_id"],
            "matched_candidates": matches,
            "decision": "NOT_EVALUATED",
            "limitations": [
                "test module-name binding is not proof of loaded test bytes or import edge",
                "runtime edge traversal and semantic ownership remain NOT_EVALUATED",
            ],
        }
        output["correlation_id"] = _digest(output)
        return output
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        raise RuntimeTestEvidenceError("untrustworthy runtime correlation") from exc
