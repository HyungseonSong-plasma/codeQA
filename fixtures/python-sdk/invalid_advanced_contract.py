"""Controlled negative Pyright witnesses; diagnostics must be observed, not invented."""
from typing import Callable, TypeVar, overload

from public_sdk import ExportedModel


class Payload(ExportedModel):
    value: int

    # Incompatible with the real Pydantic BaseModel.model_dump signature.
    def model_dump(self, *, mode: int = 0) -> dict[str, object]:
        return {}


class BaseMixin:
    def convert(self, value: int) -> int:
        return value


class BrokenMixin(BaseMixin):
    def convert(self, value: str) -> str:
        return value


class ServiceMeta(type):
    contract_revision: str = "fixture-v1"


class Service(metaclass=ServiceMeta):
    pass


@overload
def normalize(value: int) -> int: ...


@overload
def normalize(value: str) -> str: ...


def normalize(value: int | str) -> int | str:
    return value


# Must be rejected: no overload accepts a list.
bad_overload = normalize([1, 2])
bad_metaclass_assignment: int = Service.contract_revision


F = TypeVar("F", bound=Callable[..., object])


def preserve_signature(fn: F) -> F:
    return fn


registered = preserve_signature


@registered
def callback(value: int) -> int:
    return value


# Must be rejected: the aliased decorator preserves an int return type.
bad_callback_assignment: str = callback(1)
