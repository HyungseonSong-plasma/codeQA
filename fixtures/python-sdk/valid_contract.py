"""Pinned SDK positive type conformance against actual Pydantic 2.13.5 types."""
from typing import Any, Protocol

from pydantic import BaseModel, Field


class Payload(BaseModel):
    item_id: int = Field(validation_alias="legacyId", serialization_alias="itemId")
    quantity: int


class PayloadEncoder(Protocol):
    def encode(self, item: Payload) -> dict[str, Any]: ...


class PydanticEncoder:
    def encode(self, item: Payload) -> dict[str, Any]:
        return item.model_dump(mode="json", by_alias=True)


def encode_checked(encoder: PayloadEncoder, raw: dict[str, Any]) -> dict[str, Any]:
    return encoder.encode(Payload.model_validate(raw))


encoder: PayloadEncoder = PydanticEncoder()
example: dict[str, Any] = encode_checked(
    encoder, {"legacyId": 4, "quantity": 2}
)
