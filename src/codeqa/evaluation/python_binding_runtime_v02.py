"""Opt-in Python override/callback *shape* evidence (#70).

Runtime reflection on controlled objects is not proof of a pinned external SDK,
typechecker verification, or framework callback invocation.
"""
from __future__ import annotations

from dataclasses import dataclass
import inspect
from typing import Any


@dataclass(frozen=True, slots=True)
class BindingObservation:
    kind: str
    name: str
    status: str
    owner: str | None
    provenance: str
    sdk_status: str = "NOT_EVALUATED"
    typechecker_status: str = "NOT_EVALUATED"
    framework_runtime_status: str = "NOT_EVALUATED"
    override_marker_is_intent_only: bool = True


class BindingEvidenceError(ValueError):
    pass


def _shape_compatibility(parent: Any, implementation: Any, call_shapes: tuple) -> str:
    if not isinstance(call_shapes, tuple) or not call_shapes:
        return "UNRESOLVED"
    try:
        required = inspect.signature(parent)
        proposed = inspect.signature(implementation)
    except (TypeError, ValueError):
        return "UNRESOLVED"
    for entry in call_shapes:
        if (not isinstance(entry, tuple) or len(entry) != 2
                or not isinstance(entry[0], tuple)
                or not isinstance(entry[1], dict)):
            raise BindingEvidenceError("explicit call shapes must be (args, kwargs)")
        args, kwargs = entry
        try:
            required.bind(*args, **kwargs)
        except TypeError as exc:
            raise BindingEvidenceError("supplied call shape contradicts required contract") from exc
        try:
            proposed.bind(*args, **kwargs)
        except TypeError:
            return "INCOMPATIBLE_SIGNATURE"
    return "SIGNATURE_SHAPE_CANDIDATE"


def inspect_override(
    subclass: type, member: str, *,
    call_shapes: tuple,
) -> BindingObservation:
    if not isinstance(subclass, type) or not isinstance(member, str) or not member:
        raise BindingEvidenceError("class and exact member required")
    local = vars(subclass).get(member)
    if local is None:
        return BindingObservation("override", member, "UNRESOLVED", None,
                                  "no local override declaration")
    found = None
    for base in subclass.__mro__[1:]:
        if member in vars(base):
            found = base
            break
    if found is None:
        return BindingObservation("override", member, "UNRESOLVED", None,
                                  "no exact ancestor member in Python MRO")
    result = _shape_compatibility(vars(found)[member], local, call_shapes)
    return BindingObservation(
        "override", member, result,
        f"{found.__module__}.{found.__qualname__}",
        "CONTROLLED_RUNTIME_MRO_AND_INSPECT_SIGNATURE_ONLY")


def inspect_callback(
    contract: Any, callback: Any, *, name: str, call_shapes: tuple,
) -> BindingObservation:
    if not isinstance(name, str) or not name:
        raise BindingEvidenceError("declared callback name required")
    result = _shape_compatibility(contract, callback, call_shapes)
    return BindingObservation(
        "callback", name, result, None,
        "CALLER_DECLARED_CALLBACK_SIGNATURE_ONLY")
