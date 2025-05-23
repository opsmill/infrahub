from __future__ import annotations

import sys
from typing import Self

from pydantic import ConfigDict, Field, model_validator

from infrahub.core.constants.schema import UpdateSupport
from infrahub.core.models import HashableModel


def get_attribute_parameters_class_for_kind(kind: str) -> type[AttributeParameters]:
    param_classes: dict[str, type[AttributeParameters]] = {
        "NumberPool": NumberPoolParameters,
        "Text": TextAttributeParameters,
        "TextArea": TextAttributeParameters,
    }
    return param_classes.get(kind, AttributeParameters)


class AttributeParameters(HashableModel):
    model_config = ConfigDict(extra="forbid")


class NumberPoolParameters(AttributeParameters):
    end_range: int = Field(
        default=sys.maxsize,
        description="End range for numbers for the associated NumberPool",
        json_schema_extra={"update": UpdateSupport.VALIDATE_CONSTRAINT.value},
    )
    start_range: int = Field(
        default=1,
        description="Start range for numbers for the associated NumberPool",
        json_schema_extra={"update": UpdateSupport.VALIDATE_CONSTRAINT.value},
    )
    number_pool_id: str | None = Field(
        default=None,
        description="The ID of the numberpool associated with this attribute",
        json_schema_extra={"update": UpdateSupport.NOT_SUPPORTED.value},
    )

    @model_validator(mode="after")
    def validate_ranges(self) -> Self:
        if self.start_range > self.end_range:
            raise ValueError("start_range can't be less than end_range")
        return self


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
