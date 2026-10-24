"""Strictly scoped Dafny-generated *fixture* Gate (#102), independent v0.1.

A PASS here means only that one pinned, source-backed verifier receipt and its
generated Python fixture tree meet a declared conformance policy. It is NOT a
proof of an unrelated implementation, compiler correctness or deploy safety.
The existing public Gate v0.1 remains intentionally UNKNOWN for formal claims.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from typing import Literal

from codeqa.core.external_evidence import (
    ExternalEvidence, FormalProof, ToolIdentity, assess_external_evidence,
)
from codeqa.evaluation.formal_binding import FormalBinding, verify_binding


def _digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def _json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _safe_path(path: str) -> bool:
    return (isinstance(path, str) and bool(path) and not path.startswith("/")
            and "\\" not in path and "\x00" not in path
            and all(part not in ("", ".", "..") for part in path.split("/")))


def python_tree_manifest(files: Mapping[str, bytes]) -> bytes:
    """Content-addressed and path-addressed all-file Python source manifest."""
    if not isinstance(files, Mapping) or not files:
        raise ValueError("nonempty generated-file mapping required")
    if not all(_safe_path(p) and p.endswith(".py") and type(data) is bytes
               for p, data in files.items()):
        raise ValueError("unsafe source tree or non-Python payload")
    return _json([{"path": path, "sha256": _digest(files[path])}
                  for path in sorted(files)])


@dataclass(frozen=True, slots=True)
class GeneratedFixturePolicy:
    version: Literal["0.1"]
    scope: Literal["CONTROLLED_GENERATED_PYTHON_FIXTURE"]
    snapshot_id: str
    specification_path: str
    specification_sha256: str
    required_properties: tuple[str, ...]
    required_rule_ids: tuple[str, ...]
    accepted_assumptions: tuple[str, ...]
    required_generated_paths: tuple[str, ...]
    tool: ToolIdentity
    expected_build_configuration_sha256: str
    attestation_id: str

    def fingerprint(self) -> str:
        return _digest(_json(asdict(self)))


@dataclass(frozen=True, slots=True)
class GeneratedFixtureDecision:
    version: str
    scope: str
    snapshot_id: str
    policy_fingerprint: str
    status: Literal["PASS", "UNKNOWN"]
    authorization: Literal["ALLOW_FIXTURE_ONLY", "BLOCK"]
    reasons: tuple[str, ...]
    evidence_artifact_sha256: str | None
    generated_manifest_sha256: str | None
    deployed_manifest_sha256: str | None
    requirement_ids: tuple[str, ...]

    def canonical_json(self) -> str:
        return _json(asdict(self)).decode("utf-8")


def parse_generated_fixture_policy(value: Mapping[str, object]) -> GeneratedFixturePolicy:
    """Exact data-only policy; cannot select a production/deployed source mode."""
    keys = {
        "version", "scope", "snapshot_id", "specification_path",
        "specification_sha256", "required_properties", "required_rule_ids", "accepted_assumptions",
        "required_generated_paths", "tool",
        "expected_build_configuration_sha256", "attestation_id",
    }
    if not isinstance(value, Mapping) or set(value) != keys:
        raise ValueError("unknown or incomplete generated fixture policy")
    if value["version"] != "0.1" or value["scope"] != "CONTROLLED_GENERATED_PYTHON_FIXTURE":
        raise ValueError("only explicit fixture scope supported")
    if not _safe_path(value["specification_path"]) or not value["specification_path"].endswith(".dfy"):
        raise ValueError("invalid Dafny fixture source path")
    digests = (value["specification_sha256"], value["expected_build_configuration_sha256"])
    if any(not isinstance(d, str) or not re.fullmatch(r"[0-9a-f]{64}", d) for d in digests):
        raise ValueError("invalid source/build digest")
    for name in ("snapshot_id", "attestation_id"):
        if not isinstance(value[name], str) or not value[name]:
            raise ValueError("invalid snapshot or provenance identity")
    for field in ("required_properties", "required_rule_ids", "accepted_assumptions", "required_generated_paths"):
        values = value[field]
        if not isinstance(values, list) or not values or any(
            not isinstance(x, str) or not x for x in values
        ) or len(set(values)) != len(values):
            raise ValueError("nonempty, unique policy requirements mandatory")
    if any(not _safe_path(p) or not p.endswith(".py")
           for p in value["required_generated_paths"]):
        raise ValueError("unsafe expected generated Python paths")
    tool_value = value["tool"]
    if not isinstance(tool_value, Mapping) or set(tool_value) != set(ToolIdentity.__dataclass_fields__):
        raise ValueError("pinned exact tool identity required")
    tool = ToolIdentity(**tool_value)
    if (tool.name != "Dafny" or
        any(not isinstance(getattr(tool, k), str) or not getattr(tool, k)
            for k in ToolIdentity.__dataclass_fields__)):
        raise ValueError("only pinned Dafny execution supported")
    for k in ("binary_sha256", "invocation_sha256", "ruleset_sha256"):
        if not re.fullmatch(r"[0-9a-f]{64}", getattr(tool, k)):
            raise ValueError("invalid tool fingerprint")
    return GeneratedFixturePolicy(
        version="0.1", scope="CONTROLLED_GENERATED_PYTHON_FIXTURE",
        snapshot_id=value["snapshot_id"],
        specification_path=value["specification_path"],
        specification_sha256=value["specification_sha256"],
        required_properties=tuple(sorted(value["required_properties"])),
        required_rule_ids=tuple(sorted(value["required_rule_ids"])),
        accepted_assumptions=tuple(sorted(value["accepted_assumptions"])),
        required_generated_paths=tuple(sorted(value["required_generated_paths"])),
        tool=tool,
        expected_build_configuration_sha256=value["expected_build_configuration_sha256"],
        attestation_id=value["attestation_id"],
    )


def evaluate_generated_fixture_gate(
    policy: GeneratedFixturePolicy, *,
    expected_policy_sha256: str | None,
    expected_snapshot_id: str | None,
    expected_tool: ToolIdentity | None,
    evidence: ExternalEvidence,
    raw_verifier_log: bytes | None,
    specification_bytes: bytes | None,
    generated_files: Mapping[str, bytes] | None,
    deployed_files: Mapping[str, bytes] | None,
    binding: FormalBinding | None,
) -> GeneratedFixtureDecision:
    """Conformance for one controlled *generated* fixture, never production.

    Source/tool/policy caller expectations must be independently selected,
    not derived from an untrusted evidence envelope. The real CI verifier
    adapter is responsible for attesting that it ran the exact pinned source.
    """
    if not isinstance(policy, GeneratedFixturePolicy):
        raise TypeError("parsed generated fixture policy required")
    reasons: set[str] = set()
    policy_digest = policy.fingerprint()
    if expected_policy_sha256 is None or expected_policy_sha256 != policy_digest:
        reasons.add("TRUSTED_POLICY_FINGERPRINT_UNVERIFIED")
    if not expected_snapshot_id or expected_snapshot_id != policy.snapshot_id:
        reasons.add("TRUSTED_SNAPSHOT_UNVERIFIED")
    if expected_tool is None or expected_tool != policy.tool:
        reasons.add("TRUSTED_TOOL_UNVERIFIED")
    if type(specification_bytes) is not bytes:
        reasons.add("SPECIFICATION_BYTES_MISSING")
    elif _digest(specification_bytes) != policy.specification_sha256:
        reasons.add("SPECIFICATION_BYTES_CHANGED")

    gen = dep = None
    for name, records in (("GENERATED", generated_files), ("DEPLOYED", deployed_files)):
        if records is None:
            reasons.add(name + "_FILES_MISSING")
            continue
        try:
            content = python_tree_manifest(records)
        except ValueError:
            reasons.add(name + "_FILES_INVALID")
            continue
        if set(records) != set(policy.required_generated_paths):
            reasons.add(name + "_FILE_COVERAGE_MISMATCH")
        if name == "GENERATED":
            gen = content
        else:
            dep = content
    if gen is not None and dep is not None and gen != dep:
        reasons.add("GENERATED_DEPLOYED_CONTENT_MISMATCH")

    if binding is None:
        reasons.add("IMPLEMENTATION_BINDING_MISSING")
    else:
        if binding.mode != "GENERATED_CODE_MATCH":
            reasons.add("UNSUPPORTED_IMPLEMENTATION_BINDING_MODE")
        if binding.specification.path != policy.specification_path:
            reasons.add("BINDING_SPECIFICATION_PATH_MISMATCH")
        if tuple(binding.attested_properties) != tuple(policy.required_properties):
            reasons.add("BINDING_PROPERTY_SCOPE_MISMATCH")
        checked = verify_binding(
            binding, specification_bytes=specification_bytes,
            generated_bytes=gen, deployed_bytes=dep,
            expected_toolchain_sha256=policy.tool.binary_sha256,
            expected_build_configuration_sha256=policy.expected_build_configuration_sha256,
            expected_attestation_id=policy.attestation_id,
            required_properties=policy.required_properties,
        )
        if checked.status != "IDENTITY_MATCH":
            reasons.add("BINDING_" + checked.status)
            reasons.update(checked.reasons)
        if "SEMANTIC_PRESERVATION_NOT_ESTABLISHED" not in checked.reasons:
            reasons.add("BINDING_TRUST_LIMIT_NOT_DECLARED")

    if not isinstance(evidence, ExternalEvidence):
        raise TypeError("parsed external evidence required")
    admitted = assess_external_evidence(
        evidence, expected_snapshot_id=policy.snapshot_id,
        expected_files={policy.specification_path: policy.specification_sha256},
        expected_tool=policy.tool,
        expected_rules=policy.required_rule_ids,
        raw_artifact=raw_verifier_log, purpose="SOURCE_ANALYSIS",
    )
    if admitted.status != "ADMISSIBLE":
        reasons.add("PROOF_EVIDENCE_NOT_ADMISSIBLE")
        reasons.update(admitted.reasons)

    if evidence.execution.exit_code != 0:
        reasons.add("VERIFIER_EXIT_NOT_ZERO")
    if raw_verifier_log is None:
        reasons.add("VERIFIER_OUTPUT_MISSING")
    else:
        log = raw_verifier_log.decode("utf-8", errors="replace")
        matches = re.findall(r"\b(\d+) verified,\s*(\d+) errors?\b", log, re.IGNORECASE)
        if len(matches) != 1 or int(matches[0][0]) < 1 or int(matches[0][1]) != 0:
            reasons.add("VERIFIER_SUCCESS_SUMMARY_MISSING")

    obligations = [p for p in evidence.observations if isinstance(p, FormalProof)]
    if len(obligations) != len(evidence.observations) or len(obligations) != len(policy.required_properties):
        reasons.add("PROOF_OBLIGATION_COVERAGE_MISMATCH")
    if {x.obligation_id for x in obligations} != set(policy.required_properties):
        reasons.add("REQUIRED_PROOF_OBLIGATIONS_MISSING")
    for proof in obligations:
        if (proof.path != policy.specification_path or
            proof.source_sha256 != policy.specification_sha256 or
            proof.native_status != "VERIFIED" or
            proof.counterexample_sha256 is not None):
            reasons.add("PROOF_STATUS_OR_SOURCE_MISMATCH")
        if tuple(sorted(proof.assumptions)) != policy.accepted_assumptions:
            reasons.add("PROOF_ASSUMPTIONS_UNACCEPTED")

    status: Literal["PASS", "UNKNOWN"] = "UNKNOWN" if reasons else "PASS"
    return GeneratedFixtureDecision(
        version="0.1", scope=policy.scope, snapshot_id=policy.snapshot_id,
        policy_fingerprint=policy_digest, status=status,
        authorization="ALLOW_FIXTURE_ONLY" if status == "PASS" else "BLOCK",
        reasons=tuple(sorted(reasons)),
        evidence_artifact_sha256=_digest(raw_verifier_log) if raw_verifier_log is not None else None,
        generated_manifest_sha256=_digest(gen) if gen is not None else None,
        deployed_manifest_sha256=_digest(dep) if dep is not None else None,
        requirement_ids=policy.required_properties,
    )
