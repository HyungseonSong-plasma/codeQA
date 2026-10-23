"""Pure opt-in external ancestor name checks, intentionally not runtime dispatch."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from codeqa.core.naming import NamingEvidence
from codeqa.core.naming_ancestor import (
    ExternalAncestorError, ExternalAncestorEvidence, ExternalAncestorProfile,
)


@dataclass(frozen=True, slots=True)
class AncestorNameFinding:
    path: str
    owner: str
    name: str
    line: int
    column: int
    ancestor: str
    ancestor_source_sha256: str
    ancestor_declaration_line: int | None
    verdict: str
    limitation: str


@dataclass(frozen=True, slots=True)
class AncestorNameReport:
    schema_version: str
    snapshot_id: str
    profile_fingerprint: str
    findings: tuple[AncestorNameFinding, ...]
    matched_direct_declarations: int
    absent_in_pinned_declarations: int
    status: str
    interpretation: str = "EXACT_PINNED_NAME_NOT_SIGNATURE_RUNTIME_OR_MRO_PROOF"

    def to_document(self) -> dict[str, Any]:
        def serial(value: Any) -> Any:
            if isinstance(value, (tuple, list)):
                return [serial(x) for x in value]
            if isinstance(value, dict):
                return {key: serial(x) for key, x in value.items()}
            return value
        return serial(asdict(self))


def evaluate_pinned_ancestor_names(
    naming: NamingEvidence,
    evidence: ExternalAncestorEvidence,
    profile: ExternalAncestorProfile,
) -> AncestorNameReport:
    if (not isinstance(naming, NamingEvidence)
            or not isinstance(evidence, ExternalAncestorEvidence)
            or not isinstance(profile, ExternalAncestorProfile)
            or naming.producer != "python-ast-naming-safe-v0.1"
            or evidence.producer != "python-ast-pinned-ancestor-v0.1"
            or naming.snapshot_id != evidence.snapshot_id
            or naming.source_sha256 != evidence.source_sha256
            or evidence.profile_fingerprint != profile.fingerprint()):
        raise ExternalAncestorError("naming/ancestor evidence or profile mismatch")
    if tuple(sorted((p.source_path, p.source_sha256) for p in profile.providers)) != evidence.provider_sha256:
        raise ExternalAncestorError("external provider identity differs from pinned source evidence")
    found = {(x.path, x.owner, x.name, x.line, x.column): x
             for x in naming.symbols if x.kind == "method"}
    if len(found) != sum(x.kind == "method" for x in naming.symbols):
        raise ExternalAncestorError("ambiguous method identifiers")
    providers = {p.qualified_class:p for p in profile.providers}
    results = []
    positions = set()
    for witness in evidence.witnesses:
        key = (witness.path, witness.owner, witness.name, witness.line, witness.column)
        if key in positions or key not in found or witness.ancestor not in providers:
            raise ExternalAncestorError("forged, duplicate or ungrounded derived method")
        positions.add(key)
        symbol = found[key]
        if (symbol.relation != "EXTERNAL_BASE_UNRESOLVED"
                or witness.external_source_sha256 != providers[witness.ancestor].source_sha256
                or witness.explanation != "exact_source_declaration_only_not_runtime_override"):
            raise ExternalAncestorError("ancestor witness contradicted Python naming evidence")
        if (witness.state == "PINNED_MEMBER_DECLARED"
                and type(witness.external_declaration_line) is int
                and witness.external_declaration_line > 0):
            verdict = "EXEMPT_BY_PINNED_DECLARATION"
        elif witness.state == "PINNED_MEMBER_NOT_DECLARED" and witness.external_declaration_line is None:
            verdict = "NOT_EVALUATED"
        else:
            raise ExternalAncestorError("invented external parent signature or line")
        results.append(AncestorNameFinding(
            witness.path,witness.owner,witness.name,witness.line,witness.column,
            witness.ancestor,witness.external_source_sha256,
            witness.external_declaration_line, verdict,
            "external_stub_declaration_does_not_verify_installed_runtime_or_signature",
        ))
    count = sum(x.verdict == "EXEMPT_BY_PINNED_DECLARATION" for x in results)
    return AncestorNameReport(
        schema_version="0.1",snapshot_id=evidence.snapshot_id,
        profile_fingerprint=profile.fingerprint(),
        findings=tuple(results),
        matched_direct_declarations=count,
        absent_in_pinned_declarations=len(results)-count,
        status="PARTIAL" if any(x.verdict == "NOT_EVALUATED" for x in results)
               else "OBSERVED_PINNED_NAMES" if count else "NOT_EVALUATED",
    )
