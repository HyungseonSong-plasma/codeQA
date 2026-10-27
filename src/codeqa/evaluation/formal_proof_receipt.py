"""Source-only, fail-closed Dafny proof receipt assessment (#102).

A source verifier receipt is not a proof of compiler correctness, generated
program semantics, a deployed binary or a human requirement.  All outputs
explicitly prohibit implementation/merge authorization.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from typing import Literal

from codeqa.core.external_evidence import (
    ExternalEvidence, FormalProof, ToolIdentity, assess_external_evidence,
)


_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_DAFNY_SUMMARY = re.compile(
    r"^\s*Dafny program verifier finished with (\d+) verified, (\d+) errors?\s*$",
    re.MULTILINE,
)


@dataclass(frozen=True, slots=True)
class SolverIdentity:
    """Caller-asserted solver provenance; NOT authenticated by this class."""
    name: str
    version: str
    binary_sha256: str

    def __post_init__(self) -> None:
        if (not isinstance(self.name, str) or not self.name.strip()
                or not isinstance(self.version, str) or not self.version.strip()
                or not isinstance(self.binary_sha256, str)
                or not _SHA256.fullmatch(self.binary_sha256)):
            raise ValueError("complete, exact solver identity required")


@dataclass(frozen=True, slots=True)
class FormalProofEvidence:
    schema_version: Literal["0.1"]
    evidence_scope: Literal["VERIFIED_SPECIFICATION_ONLY"]
    snapshot_id: str
    specification_path: str
    specification_sha256: str
    verifier_name: str
    verifier_version: str
    verifier_exit_classifier: str
    solver: SolverIdentity | None
    obligation_ids: tuple[str, ...]
    accepted_assumptions: tuple[str, ...]
    raw_verifier_log_sha256: str | None
    status: Literal["SOURCE_RECEIPT_CONSISTENT", "NOT_EVALUATED", "BLOCK"]
    reasons: tuple[str, ...]
    implementation_authorization: Literal["BLOCK"]

    def to_document(self) -> dict[str, object]:
        return asdict(self)

    def canonical_json(self) -> str:
        return json.dumps(self.to_document(), sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False)


def assess_formal_proof_evidence(
    evidence: ExternalEvidence,
    *,
    expected_snapshot_id: str,
    expected_specification_path: str,
    expected_specification_sha256: str,
    expected_tool: ToolIdentity,
    expected_rules: tuple[str, ...],
    required_obligations: tuple[str, ...],
    accepted_assumptions: tuple[str, ...],
    raw_verifier_log: bytes | None,
    observed_solver: SolverIdentity | None,
    expected_solver: SolverIdentity | None,
) -> FormalProofEvidence:
    """Assess pinned *source proof* completeness, never implementation truth.

    Independent caller expectations are mandatory. Solver identity supplied
    here is a declaration, not authenticated process attestation. A missing
    solver stays NOT_EVALUATED even if Dafny's source verification succeeded.
    """
    if not isinstance(evidence, ExternalEvidence):
        raise TypeError("parsed external evidence required")
    if not isinstance(expected_tool, ToolIdentity):
        raise TypeError("typed expected tool required")
    if observed_solver is not None and not isinstance(observed_solver, SolverIdentity):
        raise TypeError("typed observed solver required")
    if expected_solver is not None and not isinstance(expected_solver, SolverIdentity):
        raise TypeError("typed expected solver required")
    invalid: set[str] = set()
    unknown: set[str] = set()
    if (not isinstance(expected_specification_path, str)
            or not re.fullmatch(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*\.dfy",
                                expected_specification_path)
            or any(part in (".", "..")
                   for part in expected_specification_path.split("/"))
            or not isinstance(expected_specification_sha256, str)
            or not _SHA256.fullmatch(expected_specification_sha256)):
        raise ValueError("independently pinned safe Dafny source path/hash required")
    if (not required_obligations or len(set(required_obligations)) != len(required_obligations)
            or any(not isinstance(x, str) or not x for x in required_obligations)):
        raise ValueError("unique nonempty required obligation identities required")
    if (not expected_rules or len(set(expected_rules)) != len(expected_rules)
            or any(not isinstance(x, str) or not x for x in expected_rules)):
        raise ValueError("unique nonempty expected rules required")
    if (not accepted_assumptions or len(set(accepted_assumptions)) != len(accepted_assumptions)
            or any(not isinstance(x, str) or not x for x in accepted_assumptions)):
        raise ValueError("explicit unique accepted assumptions required")
    if expected_tool.name != "Dafny":
        invalid.add("UNSUPPORTED_VERIFIER")
    admitted = assess_external_evidence(
        evidence, expected_snapshot_id=expected_snapshot_id,
        expected_files={expected_specification_path: expected_specification_sha256},
        expected_tool=expected_tool, expected_rules=expected_rules,
        raw_artifact=raw_verifier_log, purpose="SOURCE_ANALYSIS",
    )
    if admitted.status == "INADMISSIBLE":
        invalid.add("EXTERNAL_EVIDENCE_INADMISSIBLE")
    elif admitted.status != "ADMISSIBLE":
        unknown.add("EXTERNAL_EVIDENCE_INDETERMINATE")
    if evidence.execution.state != "COMPLETED" or evidence.execution.exit_code != 0:
        invalid.add("VERIFIER_EXIT_NOT_SUCCESS")
    if evidence.execution.exit_classification != "VALID_RESULT":
        invalid.add("VERIFIER_EXIT_CLASSIFICATION_UNVERIFIED")
    if raw_verifier_log is None:
        unknown.add("RAW_VERIFIER_LOG_MISSING")
    elif type(raw_verifier_log) is not bytes:
        invalid.add("RAW_VERIFIER_LOG_NOT_BYTES")
    else:
        summaries = _DAFNY_SUMMARY.findall(raw_verifier_log.decode("utf-8", errors="replace"))
        if len(summaries) != 1 or int(summaries[0][0]) < 1 or int(summaries[0][1]) != 0:
            invalid.add("VERIFIER_SUMMARY_NOT_UNAMBIGUOUS_SUCCESS")
    observations = evidence.observations
    if (len(observations) != len(required_obligations)
            or any(not isinstance(item, FormalProof) for item in observations)
            or {item.obligation_id for item in observations} != set(required_obligations)):
        invalid.add("PROOF_OBLIGATION_COVERAGE_MISMATCH")
    for item in observations:
        if not isinstance(item, FormalProof):
            continue
        if (item.path != expected_specification_path
                or item.source_sha256 != expected_specification_sha256
                or item.native_status != "VERIFIED"
                or item.counterexample_sha256 is not None):
            invalid.add("PROOF_STATUS_OR_SOURCE_MISMATCH")
        if tuple(sorted(item.assumptions)) != tuple(sorted(accepted_assumptions)):
            invalid.add("UNREVIEWED_PROOF_ASSUMPTIONS")
    if observed_solver is None:
        unknown.add("SOLVER_PROVENANCE_NOT_EVALUATED")
    elif expected_solver is None:
        unknown.add("INDEPENDENT_SOLVER_EXPECTATION_MISSING")
    elif observed_solver != expected_solver:
        invalid.add("SOLVER_IDENTITY_MISMATCH")
    status: Literal["SOURCE_RECEIPT_CONSISTENT", "NOT_EVALUATED", "BLOCK"]
    status = "BLOCK" if invalid else ("NOT_EVALUATED" if unknown else "SOURCE_RECEIPT_CONSISTENT")
    return FormalProofEvidence(
        schema_version="0.1", evidence_scope="VERIFIED_SPECIFICATION_ONLY",
        snapshot_id=evidence.snapshot_id,
        specification_path=expected_specification_path,
        specification_sha256=expected_specification_sha256,
        verifier_name=evidence.tool.name, verifier_version=evidence.tool.version,
        verifier_exit_classifier=evidence.tool.exit_classifier,
        solver=observed_solver,
        obligation_ids=tuple(sorted(required_obligations)),
        accepted_assumptions=tuple(sorted(accepted_assumptions)),
        raw_verifier_log_sha256=(sha256(raw_verifier_log).hexdigest()
                                  if type(raw_verifier_log) is bytes else None),
        status=status, reasons=tuple(sorted(invalid | unknown)),
        implementation_authorization="BLOCK",
    )
