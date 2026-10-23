"""Pure opt-in naming convention evaluator with fail-closed external interfaces.

A conformant spelling is only a local syntax finding; contracts, inheritance,
serializer behavior and full-repository quality are not inferred at runtime.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from hashlib import sha256
import re
from typing import Any

from codeqa.core.naming import (
    KINDS, RELATIONS, NamingContractError, NamingEvidence,
    NamingProfile, NamingSymbol,
)


@dataclass(frozen=True, slots=True)
class NamingFinding:
    path: str
    owner: str
    name: str
    kind: str
    line: int
    column: int
    status: str
    rule_id: str
    expected: str
    reason: str
    evidence_relation: str
    contract: str | None


@dataclass(frozen=True, slots=True)
class NamingReport:
    schema_version: str
    snapshot_id: str
    profile_id: str
    profile_fingerprint: str
    analyzed_paths: tuple[str, ...]
    unprocessed: tuple[tuple[str, str], ...]
    coverage_status: str
    eligible_declarations: int
    checked_declarations: int
    excluded_declarations: int
    unresolved_declarations: int
    findings: tuple[NamingFinding, ...]
    limitations: tuple[str, ...]
    status: str
    interpretation: str = "DECLARATION_NAME_STYLE_NOT_INTERFACE_OR_SEMANTIC_CORRECTNESS"

    def to_document(self) -> dict[str, Any]:
        def serial(v: Any) -> Any:
            if isinstance(v, (tuple, list)):
                return [serial(item) for item in v]
            if isinstance(v, dict):
                return {k: serial(value) for k, value in v.items()}
            return v
        return serial(asdict(self))


def _style_matches(name: str, style: str) -> bool:
    if style == "off":
        return True
    if not name.isascii():
        return False  # Explicitly unsupported Unicode policy; reviewed as ambiguous below.
    if style == "snake_case":
        return re.fullmatch(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*", name) is not None
    if style == "UPPER_SNAKE_CASE":
        return re.fullmatch(r"[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*", name) is not None
    if style == "PascalCase":
        return re.fullmatch(r"[A-Z][A-Za-z0-9]*", name) is not None and "_" not in name
    raise NamingContractError("unexpected style")


def _judge(symbol: NamingSymbol, profile: NamingProfile) -> NamingFinding:
    rules = dict(profile.rules)
    style = rules[symbol.kind]
    rule = f"{profile.profile_id}:{symbol.kind}"
    contract = next((c for c in profile.external_contracts if
                     (c.path, c.owner, c.name) == (
                         symbol.path, symbol.owner, symbol.name
                     ) and (
                         (c.kind in ("interface", "callback") and symbol.kind == "method")
                         or (c.kind == "field" and symbol.kind == "field")
                         or (c.kind == "import_alias" and symbol.kind == "import_alias")
                     )), None)
    if contract is not None:
        if (contract.kind == "field"
                and symbol.relation not in (
                    "DTO_DIRECT_FIELD_UNRESOLVED", "DTO_FIELD_MAPPING_UNRESOLVED",
                    "DTO_FIELD_ALIAS_DECLARED"
                )):
            raise NamingContractError("field contract does not identify a mapped field")
        if (contract.kind in ("interface", "callback") and symbol.relation not in (
                "EXTERNAL_BASE_UNRESOLVED", "DECORATED_EXTERNAL_UNRESOLVED",
                "LOCAL_OVERRIDE_MATCH"
        )):
            raise NamingContractError("claimed interface exemption lacks source ancestry")
        return NamingFinding(
            symbol.path, symbol.owner, symbol.name, symbol.kind,
            symbol.line, symbol.column, "EXEMPT_BY_DECLARED_CONTRACT", rule,
            style, "pinned_external_contract_attested_not_runtime_verified",
            symbol.relation, f"{contract.provider}@{contract.revision}:{contract.kind}",
        )
    if symbol.relation == "IMPORTED_ORIGINAL":
        return NamingFinding(
            symbol.path, symbol.owner, symbol.name, symbol.kind,
            symbol.line, symbol.column, "EXEMPT_BY_POLICY", rule, style,
            "external_import_spelling_preserved", symbol.relation, None,
        )
    if symbol.relation == "LOCAL_OVERRIDE_MATCH":
        return NamingFinding(
            symbol.path, symbol.owner, symbol.name, symbol.kind,
            symbol.line, symbol.column, "EXEMPT_BY_INTERFACE_CONTRACT",
            rule, style, "source_grounded_local_ancestor_member_spelling",
            symbol.relation, "in_repository_source",
        )
    if symbol.relation == "INVALID_OVERRIDE_INTENT":
        return NamingFinding(
            symbol.path, symbol.owner, symbol.name, symbol.kind,
            symbol.line, symbol.column, "REVIEW_REQUIRED", rule, style,
            "override_decorator_but_local_ancestor_member_missing",
            symbol.relation, None,
        )
    if symbol.relation in (
        "EXTERNAL_BASE_UNRESOLVED", "DECORATED_EXTERNAL_UNRESOLVED",
        "DTO_DIRECT_FIELD_UNRESOLVED", "DTO_FIELD_MAPPING_UNRESOLVED",
    ):
        return NamingFinding(
            symbol.path, symbol.owner, symbol.name, symbol.kind,
            symbol.line, symbol.column, "NOT_EVALUATED", rule, style,
            "external_interface_or_mapping_binding_unverified",
            symbol.relation, None,
        )
    if symbol.name.startswith("__") and symbol.name.endswith("__"):
        return NamingFinding(
            symbol.path, symbol.owner, symbol.name, symbol.kind,
            symbol.line, symbol.column, "EXEMPT_BY_POLICY", rule, style,
            "python_language_reserved_dunder_name",
            symbol.relation, None,
        )
    if symbol.name.startswith("_") and symbol.kind in ("method", "function", "field"):
        if not symbol.name.startswith("__") and _style_matches(symbol.name[1:], style):
            return NamingFinding(
                symbol.path, symbol.owner, symbol.name, symbol.kind,
                symbol.line, symbol.column, "CONFORMANT_WITH_APPLIED_RULE", rule, style,
                "private_prefix_allowed", symbol.relation, None,
            )
        if symbol.name.startswith("__") and _style_matches(symbol.name[2:], style):
            return NamingFinding(
                symbol.path, symbol.owner, symbol.name, symbol.kind,
                symbol.line, symbol.column, "CONFORMANT_WITH_APPLIED_RULE", rule, style,
                "private_name_mangling_allowed", symbol.relation, None,
            )
    if not symbol.name.isascii():
        return NamingFinding(
            symbol.path, symbol.owner, symbol.name, symbol.kind,
            symbol.line, symbol.column, "NOT_EVALUATED", rule, style,
            "unicode_identifier_normalization_not_defined", symbol.relation, None,
        )
    return NamingFinding(
        symbol.path, symbol.owner, symbol.name, symbol.kind,
        symbol.line, symbol.column,
        "CONFORMANT_WITH_APPLIED_RULE" if _style_matches(symbol.name, style)
        else "REVIEW_REQUIRED", rule, style,
        "pattern_matched" if _style_matches(symbol.name, style)
        else "observed_spelling_differs_from_effective_style",
        symbol.relation, None,
    )


def evaluate_naming(
    evidence: NamingEvidence, sources: Mapping[str, str],
    profile: NamingProfile,
) -> NamingReport:
    """Validate immutable adapter facts against exact caller bytes; never write."""
    if not isinstance(evidence, NamingEvidence) or not isinstance(profile, NamingProfile):
        raise TypeError("NamingEvidence and NamingProfile required")
    if not evidence.snapshot_id or evidence.producer != "python-ast-naming-safe-v0.1":
        raise NamingContractError("unknown source producer or snapshot")
    paths = set(evidence.analyzed_paths)
    unprocessed = {p for p, _ in evidence.unprocessed}
    actual = tuple(sorted(
        (p, sha256(s.encode("utf-8")).hexdigest()) for p, s in sources.items()
    ))
    if (len(paths) != len(evidence.analyzed_paths)
            or len(unprocessed) != len(evidence.unprocessed)
            or paths & unprocessed or
            set(sources) != paths | unprocessed
            or evidence.source_sha256 != actual
            or any(not isinstance(path, str) or not path or path.startswith("/")
                   or ".." in path.split("/") for path in sources)):
        raise NamingContractError("source scope or content hash differs from extracted evidence")
    seen: set[tuple[str, str, str, str, int, int]] = set()
    findings: list[NamingFinding] = []
    skipped = 0
    for symbol in evidence.symbols:
        identity = (symbol.path, symbol.owner, symbol.name, symbol.kind,
                    symbol.line, symbol.column)
        if (identity in seen or symbol.kind not in KINDS or
                symbol.relation not in RELATIONS or
                symbol.path not in paths or symbol.line < 1 or symbol.column < 0 or
                not isinstance(symbol.name, str) or not symbol.name or
                not isinstance(symbol.detail, str)):
            raise NamingContractError("invalid or duplicate declaration witness")
        if symbol.kind != "module":
            lines = sources[symbol.path].splitlines()
            if (symbol.line > len(lines)
                    or not lines[symbol.line - 1].encode("utf-8")[
                        symbol.column:
                    ].startswith(symbol.name.encode("utf-8"))):
                raise NamingContractError(
                    "identifier source position does not match original UTF-8 bytes"
                )
        seen.add(identity)
        if any(symbol.path.startswith(p) for p in profile.excluded_prefixes):
            skipped += 1
            continue
        findings.append(_judge(symbol, profile))
    limitations = []
    if evidence.unprocessed:
        limitations.append("unprocessed_or_unsupported_sources")
    if skipped:
        limitations.append("profile_excluded_declarations")
    if any(x.status == "NOT_EVALUATED" for x in findings):
        limitations.append("unresolved_contract_or_unsupported_naming_evidence")
    reviews = sum(x.status == "REVIEW_REQUIRED" for x in findings)
    checked = sum(x.status in (
        "CONFORMANT_WITH_APPLIED_RULE", "REVIEW_REQUIRED"
    ) for x in findings)
    unknowns = sum(x.status == "NOT_EVALUATED" for x in findings)
    return NamingReport(
        schema_version="0.1", snapshot_id=evidence.snapshot_id,
        profile_id=profile.profile_id, profile_fingerprint=profile.fingerprint(),
        analyzed_paths=tuple(sorted(paths)), unprocessed=evidence.unprocessed,
        coverage_status="partial" if paths and unprocessed else
                        "complete" if paths else "none",
        eligible_declarations=len(evidence.symbols),
        checked_declarations=checked, excluded_declarations=skipped,
        unresolved_declarations=unknowns,
        findings=tuple(sorted(findings, key=lambda x: (
            x.path, x.line, x.column, x.kind, x.name
        ))),
        limitations=tuple(limitations),
        status="REVIEW_REQUIRED" if reviews else
               "NOT_EVALUATED" if unknowns or evidence.unprocessed or skipped or not findings else
               "NO_VIOLATIONS_OBSERVED",
    )
