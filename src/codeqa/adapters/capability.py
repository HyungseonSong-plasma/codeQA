"""Portable, data-only adapter capability validation (no Python parser dependency).

A capability declaration records supported evidence, never execution success or
an inferred source-code quality verdict.  The caller supplies the schema.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from jsonschema import Draft202012Validator


class AdapterCapabilityError(ValueError):
    """Malformed, ambiguous or contradictory adapter capability declaration."""


def validate_adapter_capability(
    document: Mapping[str, Any], schema: Mapping[str, Any],
) -> dict[str, Any]:
    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(document),
        key=lambda error: (tuple(str(item) for item in error.absolute_path), error.message),
    )
    if errors:
        raise AdapterCapabilityError("invalid adapter capability: " + errors[0].message)
    names = [item["name"] for item in document["features"]]
    if len(names) != len(set(names)):
        raise AdapterCapabilityError("duplicate adapter capability feature identity")
    supported = set(document["input"]["configuration"]["supported"])
    unsupported = set(document["input"]["configuration"]["unsupported"])
    if supported & unsupported:
        raise AdapterCapabilityError("configuration supported/unsupported overlap")
    if document["adapter"]["parser"]["execution"] == "executes_target":
        # Such adapters may be declared, but MUST NOT be classified as syntax-only.
        raise AdapterCapabilityError("v0.1 contract only accepts non-executing adapters")
    return dict(document)
