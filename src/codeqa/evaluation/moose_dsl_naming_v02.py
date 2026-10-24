"""Conservative MOOSE DSL spelling evidence, not a full parser (#73)."""
from __future__ import annotations

from collections.abc import Mapping


class MooseNamingContractError(ValueError):
    pass


def classify_moose_identifier(profile: Mapping[str, object], identifier: str) -> str:
    """Never case-normalize an unverified framework DSL keyword."""
    if (not isinstance(profile, Mapping) or profile.get("schema_version") != "0.2-draft"
            or profile.get("cpp_parser_status") != "NOT_EVALUATED"
            or profile.get("moose_grammar_status") != "NOT_EVALUATED"
            or profile.get("moose_framework_revision_status") != "NOT_EVALUATED"
            or profile.get("automatic_rename") is not False):
        raise MooseNamingContractError("verified immutable capability envelope required")
    reserved = profile.get("reserved_moose_blocks")
    custom = profile.get("custom_application_identifiers")
    if not isinstance(reserved, list) or not isinstance(custom, list):
        raise MooseNamingContractError("declared source namespaces required")
    if not all(isinstance(x, str) and x for x in reserved + custom):
        raise MooseNamingContractError("invalid DSL identifier")
    if len(set(reserved + custom)) != len(reserved) + len(custom):
        raise MooseNamingContractError("framework namespace conflict")
    if not isinstance(identifier, str) or not identifier:
        raise MooseNamingContractError("identifier required")
    if identifier in reserved:
        return "PRESERVE_DECLARED_RESERVED_KEY"
    if identifier in custom:
        return "APPLICATION_IDENTIFIER_REVIEW_CANDIDATE"
    return "NOT_EVALUATED"
