from __future__ import annotations

import sys
from typing import Any, Self

from pydantic import ConfigDict, Field, model_validator

from infrahub import config
from infrahub.core.constants.schema import UpdateSupport
from infrahub.core.models import HashableModel
from infrahub.exceptions import ValidationError


def get_attribute_parameters_class_for_kind(kind: str) -> type[AttributeParameters]:
    param_classes: dict[str, type[AttributeParameters]] = {
        "NumberPool": NumberPoolParameters,
        "Text": TextAttributeParameters,
        "TextArea": TextAttributeParameters,
        "List": ListAttributeParameters,
        "Number": NumberAttributeParameters,
    }
    return param_classes.get(kind, AttributeParameters)


class AttributeParameters(HashableModel):
    model_config = ConfigDict(extra="forbid")

    @classmethod
    def convert_from(cls, source: AttributeParameters) -> Self:
        """Convert from another AttributeParameters subclass.

        Args:
            source: The source AttributeParameters instance to convert from

        Returns:
            A new instance of the target class with compatible fields populated

        """
        source_data = source.model_dump()
        return cls.convert_from_dict(source_data=source_data)

    @classmethod
    def convert_from_dict(cls, source_data: dict[str, Any]) -> Self:
        """Convert from a dictionary to the target class.

        Args:
            source_data: The source dictionary to convert from

        Returns:
            A new instance of the target class with compatible fields populated

        """
        target_fields = set(cls.model_fields.keys())
        filtered_data = {k: v for k, v in source_data.items() if k in target_fields}
        return cls(**filtered_data)


class ListAttributeParameters(AttributeParameters):
    """Parameters for List attributes supporting regex validation on list items."""

    regex: str | None = Field(
        default=None,
        description="Regular expression that each list item value must match if defined",
        json_schema_extra={"update": UpdateSupport.VALIDATE_CONSTRAINT.value},
    )


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
            and self.min_length > self.max_length
        ):
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
            and self.min_value > self.max_value
        ):
            raise ValueError(
                "`max_value` can't be less than `min_value` when the schema is configured with strict mode"
            )

        return self

    def get_excluded_single_values(self) -> list[int]:
        if not self.excluded_values:
            return []

        return [int(value) for value in self.excluded_values.split(",") if "-" not in value]

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
        try:
            self.check_valid_value(value=value, name="UNUSED")
        except ValidationError:
            return False
        return True

    def check_valid_value(self, value: int, name: str) -> None:
        if self.min_value is not None and value < self.min_value:
            raise ValidationError({name: f"{value} is lower than the minimum allowed value {self.min_value!r}"})
        if self.max_value is not None and value > self.max_value:
            raise ValidationError({name: f"{value} is higher than the maximum allowed value {self.max_value!r}"})
        if value in self.get_excluded_single_values():
            raise ValidationError({name: f"{value} is in the excluded values"})
        for start, end in self.get_excluded_ranges():
            if start <= value <= end:
                raise ValidationError({name: f"{value} is in an the excluded range {start}-{end}"})


class NumberPoolRangeParameters(HashableModel):
    """One inclusive range of numbers declared for the NumberPool of an attribute."""

    start: int = Field(description="First number of the range")
    end: int = Field(description="Last number of the range")
    weight: int | None = Field(
        default=None,
        description="Ranges with a higher weight are allocated from first",
    )

    _sort_by: list[str] = ["start", "end"]

    @property
    def label(self) -> str:
        return f"{self.start}-{self.end}"

    @property
    def size(self) -> int:
        return self.end - self.start + 1

    def overlaps(self, other: NumberPoolRangeParameters) -> bool:
        return self.start <= other.end and other.start <= self.end


def _is_unset(value: int | list[NumberPoolRangeParameters] | None) -> bool:
    return value is None or value == []


# Unset range fields stay out of dumps so clients of an older published contract can load a dumped schema.
class NumberPoolParameters(AttributeParameters):
    end_range: int | None = Field(
        default=None,
        description=(
            "Deprecated, use ranges instead. End of the single range of the associated NumberPool, "
            "defaults to the largest supported number when only start_range is set"
        ),
        exclude_if=_is_unset,
        json_schema_extra={"update": UpdateSupport.VALIDATE_CONSTRAINT.value},
    )
    start_range: int | None = Field(
        default=None,
        description=(
            "Deprecated, use ranges instead. Start of the single range of the associated NumberPool, "
            "defaults to 1 when only end_range is set"
        ),
        exclude_if=_is_unset,
        json_schema_extra={"update": UpdateSupport.VALIDATE_CONSTRAINT.value},
    )
    ranges: list[NumberPoolRangeParameters] = Field(
        default_factory=list,
        description="Ranges of numbers the associated NumberPool allocates from, they must not overlap",
        exclude_if=_is_unset,
        json_schema_extra={"update": UpdateSupport.VALIDATE_CONSTRAINT.value},
    )
    number_pool_id: str | None = Field(
        default=None,
        description="The ID of the numberpool associated with this attribute. Only set after the number pool has been provisioned.",
        json_schema_extra={"update": UpdateSupport.NOT_SUPPORTED.value},
    )
    allocation_scope: list[str] | None = Field(
        default=None,
        description=(
            "Fields of the kind that divide the pool's space; "
            "allocation returns the lowest free number within the writer's division. "
            "Same notation as uniqueness constraints."
        ),
        json_schema_extra={"update": UpdateSupport.ALLOWED.value},
    )

    @property
    def has_shorthand(self) -> bool:
        return self.start_range is not None or self.end_range is not None

    def update(self, other: HashableModel) -> Self:
        # A declaration carrying either spelling replaces the previous ranges wholesale, a field-wise merge would
        # combine the two spellings or keep a previous bound the new shorthand leaves to its default.
        if isinstance(other, NumberPoolParameters):
            if other.has_shorthand:
                self.start_range = other.start_range
                self.end_range = other.end_range
                self.ranges = []
            elif other.ranges:
                self.start_range = None
                self.end_range = None
                self.ranges = list(other.ranges)
        return super().update(other)

    @model_validator(mode="after")
    def validate_ranges(self) -> Self:
        if self.has_shorthand and self.ranges:
            raise ValueError("start_range/end_range cannot be combined with ranges")

        if self.has_shorthand:
            shorthand = self._shorthand_range()
            if shorthand.start > shorthand.end:
                raise ValueError("`start_range` can't be less than `end_range`")
            return self

        ordered = sorted(self.ranges)
        for candidate in ordered:
            if candidate.end < candidate.start:
                raise ValueError(f"Range end ({candidate.end}) cannot be lower than start ({candidate.start})")
        for candidate in ordered:
            clashes = [other for other in ordered if other is not candidate and candidate.overlaps(other)]
            if clashes:
                raise ValueError(f"Range {candidate.label} overlaps {', '.join(clash.label for clash in clashes)}")
        return self

    def _shorthand_range(self) -> NumberPoolRangeParameters:
        start = self.start_range if self.start_range is not None else 1
        end = self.end_range if self.end_range is not None else sys.maxsize
        return NumberPoolRangeParameters(start=start, end=end)

    def effective_ranges(self) -> list[NumberPoolRangeParameters]:
        """Return the declared ranges ordered by start, whichever spelling declared them.

        A shorthand missing a bound resolves its start to 1 and its end to the largest supported number;
        a declaration using neither spelling has no range.
        """
        if self.has_shorthand:
            return [self._shorthand_range()]
        return sorted(self.ranges)

    def get_pool_size(self) -> int:
        """Returns the size of the pool based on the defined ranges."""
        return sum(pool_range.size for pool_range in self.effective_ranges())
