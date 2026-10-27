"""Source-bound formal verification provenance (#102), additive and fail closed.

Hash equality establishes artifact identity, not semantics preservation.
This module never declares a Dafny theorem to be proof of hand-written code.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
from collections.abc import Mapping
import json


class BindingContractError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class BoundArtifact:
    role: str
    path: str
    sha256: str


@dataclass(frozen=True, slots=True)
class FormalBinding:
    schema_version: str
    mode: str
    specification: BoundArtifact
    generated: BoundArtifact | None
    deployed: BoundArtifact
    toolchain_id: str
    toolchain_sha256: str
    build_configuration_sha256: str
    attestation_id: str
    attested_properties: tuple[str, ...]

    def canonical_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True, slots=True)
class BindingResult:
    status: str  # IDENTITY_MATCH | BINDING_BROKEN | NOT_EVALUATED
    reasons: tuple[str, ...]
    verified_properties: tuple[str, ...]


def parse_binding(document: Mapping[str, object]) -> FormalBinding:
    if not isinstance(document, Mapping):
        raise BindingContractError("binding must be a mapping")
    mandatory = {"schema_version", "mode", "specification", "generated",
                 "deployed", "toolchain_id", "toolchain_sha256",
                 "build_configuration_sha256", "attestation_id",
                 "attested_properties"}
    if set(document) != mandatory:
        raise BindingContractError("invalid exact binding contract")
    if document["schema_version"] != "0.1" or document["mode"] not in (
        "GENERATED_CODE_MATCH", "IN_SITU_VERIFICATION", "MANUAL_TRANSLATION_UNVERIFIED",
    ):
        raise BindingContractError("unsupported binding mode/version")
    def artifact(value, role):
        if not isinstance(value, Mapping) or set(value) != {"role", "path", "sha256"}:
            raise BindingContractError("invalid bound artifact")
        a = BoundArtifact(**value)
        # Reject noncanonical names before comparing immutable digests.
        # Byte identity does not establish the path/role of an artifact.
        if (a.role != role or not isinstance(a.path, str) or not a.path
                or any(part in ("", ".", "..") for part in a.path.split("/"))
                or "\\" in a.path
                or any(ord(ch) < 32 or ord(ch) == 127 for ch in a.path)
                or not _digest(a.sha256)):
            raise BindingContractError("invalid artifact role/path/digest")
        return a
    spec = artifact(document["specification"], "specification")
    generated = artifact(document["generated"], "generated") if document["generated"] is not None else None
    deployed = artifact(document["deployed"], "deployed")
    if document["mode"] == "GENERATED_CODE_MATCH" and generated is None:
        raise BindingContractError("generated-code mode requires generated artifact")
    if document["mode"] != "GENERATED_CODE_MATCH" and generated is not None:
        raise BindingContractError("generated artifact outside generated-code mode")
    if not all(isinstance(document[x], str) and document[x] for x in ("toolchain_id", "attestation_id")):
        raise BindingContractError("missing provenance")
    if not _digest(document["toolchain_sha256"]) or not _digest(document["build_configuration_sha256"]):
        raise BindingContractError("invalid toolchain/configuration digest")
    props = document["attested_properties"]
    if not isinstance(props, list) or not props or any(not isinstance(x,str) or not x for x in props) or len(props)!=len(set(props)):
        raise BindingContractError("properties must be explicitly enumerated")
    return FormalBinding("0.1",document["mode"],spec,generated,deployed,
                         document["toolchain_id"],document["toolchain_sha256"],
                         document["build_configuration_sha256"],document["attestation_id"],tuple(sorted(props)))


def _digest(value: object) -> bool:
    return isinstance(value,str) and len(value)==64 and all(c in "0123456789abcdef" for c in value)


def verify_binding(
    binding: FormalBinding, *,
    specification_bytes: bytes | None,
    generated_bytes: bytes | None,
    deployed_bytes: bytes | None,
    expected_toolchain_sha256: str | None,
    expected_build_configuration_sha256: str | None,
    expected_attestation_id: str | None,
    required_properties: tuple[str, ...],
) -> BindingResult:
    """Confirm byte identities only, not proof soundness or deployment semantics.

    Signed/genuinely independent transform attestation and verified proof result
    are NOT inputs in v0.1. A matching identity never authorizes a formal gate.
    """
    if not isinstance(binding, FormalBinding):
        raise TypeError("typed binding required")
    broken = set()
    unknown = set()
    for label, item, data in (("SPEC", binding.specification, specification_bytes),
                              ("DEPLOYED", binding.deployed, deployed_bytes),
                              ("GENERATED", binding.generated, generated_bytes)):
        if item is None:
            continue
        if data is None:
            unknown.add(label+"_BYTES_MISSING")
        elif not isinstance(data,bytes) or sha256(data).hexdigest()!=item.sha256:
            broken.add(label+"_HASH_MISMATCH")
    if expected_toolchain_sha256 is None or expected_build_configuration_sha256 is None or not expected_attestation_id:
        unknown.add("INDEPENDENT_PROVENANCE_MISSING")
    else:
        if expected_toolchain_sha256!=binding.toolchain_sha256 or expected_build_configuration_sha256!=binding.build_configuration_sha256 or expected_attestation_id!=binding.attestation_id:
            broken.add("PROVENANCE_MISMATCH")
    if set(required_properties)-set(binding.attested_properties) or not required_properties:
        unknown.add("REQUIRED_PROPERTIES_UNATTESTED")
    if binding.mode=="MANUAL_TRANSLATION_UNVERIFIED":
        unknown.add("MANUAL_TRANSLATION_UNVERIFIED")
    if binding.mode=="GENERATED_CODE_MATCH" and binding.generated is not None and binding.generated.sha256!=binding.deployed.sha256:
        broken.add("GENERATED_DEPLOYED_HASH_MISMATCH")
    if binding.mode=="IN_SITU_VERIFICATION" and binding.specification.sha256!=binding.deployed.sha256:
        unknown.add("IN_SITU_SOURCE_RELATION_UNVERIFIED")
    if broken:
        return BindingResult("BINDING_BROKEN",tuple(sorted(broken|unknown)),())
    if unknown:
        return BindingResult("NOT_EVALUATED",tuple(sorted(unknown)),())
    return BindingResult("IDENTITY_MATCH",("SEMANTIC_PRESERVATION_NOT_ESTABLISHED",),tuple(sorted(required_properties)))
