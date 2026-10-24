"""Deliberate SDK type violations; real Pyright MUST reject these."""
from typing import Any, Protocol

from pydantic import BaseModel


class BadPayload(BaseModel):
    # Real Pydantic BaseModel.model_dump(mode: Literal["json", "python"] | str)
    # must NOT be overridden with an incompatible integer-only keyword.
    def model_dump(self, *, mode: int = 0) -> dict[str, Any]:
        return {}


class PayloadEncoder(Protocol):
    def encode(self, item: BadPayload) -> dict[str, Any]: ...


class InvalidEncoder:
    def encode(self, item: int) -> dict[str, Any]:
        return {}


encoder: PayloadEncoder = InvalidEncoder()
