from __future__ import annotations

import sys
from typing import Self

from pydantic import ConfigDict, Field, model_validator

from infrahub import config
from infrahub.core.constants.schema import UpdateSupport
from infrahub.core.models import HashableModel


def get_attribute_parameters_class_for_kind(kind: str) -> type[AttributeParameters]:
    param_classes: dict[str, type[AttributeParameters]] = {
        "NumberPool": NumberPoolParameters,
        "Text": TextAttributeParameters,
        "TextArea": TextAttributeParameters,
        "Number": NumberAttributeParameters,
    }
    return param_classes.get(kind, AttributeParameters)


class AttributeParameters(HashableModel):
    model_config = ConfigDict(extra="forbid")


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

    @model_validator(mode="after")
    def validate_min_max(self) -> Self:
        if (
            config.SETTINGS.initialized
            and config.SETTINGS.main.schema_strict_mode
            and self.min_length is not None
            and self.max_length is not None
        ):
            if self.min_length > self.max_length:
                raise ValueError(
                    "`max_length` can't be less than `min_length` when the schema is configured with strict mode"
                )

        return self


class NumberAttributeParameters(AttributeParameters):
    min_value: int | None = Field(
        default=None,
        description="Set a minimum value allowed.",
        json_schema_extra={"update": UpdateSupport.VALIDATE_CONSTRAINT.value},
    )
    max_value: int | None = Field(
        default=None,
        description="Set a maximum value allowed.",
        json_schema_extra={"update": UpdateSupport.VALIDATE_CONSTRAINT.value},
    )
    excluded_values: str | None = Field(
        default=None,
        description="List of values or range of values not allowed for the attribute, format is: '100,150-200,280,300-400'",
        pattern=r"^(\d+(?:-\d+)?)(?:,\d+(?:-\d+)?)*$",
        json_schema_extra={"update": UpdateSupport.VALIDATE_CONSTRAINT.value},
    )

    @model_validator(mode="after")
    def validate_ranges(self) -> Self:
        ranges = self.get_excluded_ranges()
        for i, (start_range_1, end_range_1) in enumerate(ranges):
            if start_range_1 > end_range_1:
                raise ValueError("`start_range` can't be less than `end_range`")

            # Check for overlapping ranges
            for start_range_2, end_range_2 in ranges[i + 1 :]:
                if not (end_range_1 < start_range_2 or start_range_1 > end_range_2):
                    raise ValueError("Excluded ranges cannot overlap")

        return self

    @model_validator(mode="after")
    def validate_min_max(self) -> Self:
        if (
            config.SETTINGS.initialized
            and config.SETTINGS.main.schema_strict_mode
            and self.min_value is not None
            and self.max_value is not None
        ):
            if self.min_value > self.max_value:
                raise ValueError(
                    "`max_value` can't be less than `min_value` when the schema is configured with strict mode"
                )

        return self

    def get_excluded_single_values(self) -> list[int]:
        if not self.excluded_values:
            return []

        results = [int(value) for value in self.excluded_values.split(",") if "-" not in value]
        return results

    def get_excluded_ranges(self) -> list[tuple[int, int]]:
        if not self.excluded_values:
            return []

        ranges = []
        for value in self.excluded_values.split(","):
            if "-" in value:
                start, end = map(int, value.split("-"))
                ranges.append((start, end))

        return ranges

    def is_valid_value(self, value: int) -> bool:
        if self.min_value is not None and value < self.min_value:
            return False
        if self.max_value is not None and value > self.max_value:
            return False
        if value in self.get_excluded_single_values():
            return False
        for start, end in self.get_excluded_ranges():
            if start <= value <= end:
                return False
        return True


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
            raise ValueError("`start_range` can't be less than `end_range`")
        return self
