from __future__ import annotations

from pydantic import Field

from infrahub.core.constants.schema import UpdateSupport
from infrahub.core.models import HashableModel


def get_attribute_parameters_class_for_kind(kind: str) -> type[AttributeParameters]:
    return {
        "Text": TextAttributeParameters,
        "TextArea": TextAttributeParameters,
    }.get(kind, AttributeParameters)


class AttributeParameters(HashableModel):
    class Config:
        extra = "forbid"


class TextAttributeParameters(AttributeParameters):
    regex: str | None = Field(
        default=None,
        description="Regular expression that attribute value must match if defined",
        json_schema_extra={"update": UpdateSupport.VALIDATE_CONSTRAINT.value},
    )
    min_length: int | None = Field(
        default=None,
        description="Set a minimum number of characters allowed.",
        json_schema_extra={"update": UpdateSupport.VALIDATE_CONSTRAINT.value},
    )
    max_length: int | None = Field(
        default=None,
        description="Set a maximum number of characters allowed.",
        json_schema_extra={"update": UpdateSupport.VALIDATE_CONSTRAINT.value},
    )
