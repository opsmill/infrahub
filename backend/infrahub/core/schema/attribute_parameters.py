from __future__ import annotations

from pydantic import BaseModel, Field


def get_attribute_parameters_class_for_kind(kind: str) -> type[AttributeParameters]:
    return {
        "Text": TextAttributeParameters,
        "TextArea": TextAttributeParameters,
    }.get(kind, AttributeParameters)


class AttributeParameters(BaseModel):
    class Config:
        extra = "forbid"


class TextAttributeParameters(AttributeParameters):
    regex: str | None = Field(default=None, description="Regular expression that attribute value must match if defined")
    min_length: int | None = Field(
        default=None,
        description="Set a minimum number of characters allowed.",
    )
    max_length: int | None = Field(
        default=None,
        description="Set a maximum number of characters allowed.",
    )
