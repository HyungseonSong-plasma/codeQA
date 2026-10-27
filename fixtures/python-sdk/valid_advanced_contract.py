"""Controlled positive Pyright witnesses: re-export, mixin, metaclass, overload, decorator.

The imported BaseModel comes from the actual pinned Pydantic installation.
No external consumer compatibility or callback dispatch is inferred.
"""
from typing import Callable, Protocol, TypeVar, overload

from public_sdk import ExportedModel


class Payload(ExportedModel):
    value: int


class ServiceMeta(type):
    contract_revision: str = "fixture-v1"


class LabelMixin:
    def label(self) -> str:
        return "sample"


class Service(LabelMixin, metaclass=ServiceMeta):
    def encode(self, payload: Payload) -> str:
        return self.label() + str(payload.value)


@overload
def normalize(value: int) -> int: ...


@overload
def normalize(value: str) -> str: ...


def normalize(value: int | str) -> int | str:
    return value


F = TypeVar("F", bound=Callable[..., object])


def preserve_signature(fn: F) -> F:
    return fn


registered = preserve_signature


@registered
def callback(payload: Payload) -> str:
    return Service().encode(payload)


class CallbackContract(Protocol):
    def __call__(self, payload: Payload) -> str: ...


handler: CallbackContract = callback
integer_result: int = normalize(1)
string_result: str = normalize("ok")
payload = Payload.model_validate({"value": 4})
response: str = handler(payload)
