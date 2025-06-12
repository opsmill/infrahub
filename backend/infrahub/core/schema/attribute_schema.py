from __future__ import annotations

import enum
from enum import Enum
from typing import TYPE_CHECKING, Any, Self

from pydantic import Field, ValidationInfo, field_validator, model_validator

from infrahub import config
from infrahub.core.constants.schema import UpdateSupport
from infrahub.core.enums import generate_python_enum
from infrahub.core.query.attribute import default_attribute_query_filter
from infrahub.types import ATTRIBUTE_KIND_LABELS, ATTRIBUTE_TYPES

from .attribute_parameters import (
    AttributeParameters,
    NumberAttributeParameters,
    NumberPoolParameters,
    TextAttributeParameters,
    get_attribute_parameters_class_for_kind,
)
from .generated.attribute_schema import GeneratedAttributeSchema

if TYPE_CHECKING:
    from infrahub.core.attribute import BaseAttribute
    from infrahub.core.branch import Branch
    from infrahub.core.constants import BranchSupportType
    from infrahub.core.query import QueryElement
    from infrahub.database import InfrahubDatabase


def get_attribute_schema_class_for_kind(kind: str) -> type[AttributeSchema]:
    return attribute_schema_class_by_kind.get(kind, AttributeSchema)


class AttributeSchema(GeneratedAttributeSchema):
    _sort_by: list[str] = ["name"]
    _enum_class: type[enum.Enum] | None = None

    @classmethod
    def model_json_schema(cls, *args: Any, **kwargs: Any) -> dict[str, Any]:
        schema = super().model_json_schema(*args, **kwargs)

        # Build conditional schema based on attribute_schema_class_by_kind mapping
        # This override allows people using the Yaml language server to get the correct mappings
        # for the parameters when selecting the appropriate kind
        schema["allOf"] = []
        for kind, schema_class in attribute_schema_class_by_kind.items():
            schema["allOf"].append(
                {
                    "if": {"properties": {"kind": {"const": kind}}},
                    "then": {"properties": {"parameters": {"$ref": f"#/definitions/{schema_class.__name__}"}}},
                }
            )

        return schema

    @property
    def is_attribute(self) -> bool:
        return True

    @property
    def is_relationship(self) -> bool:
        return False

    @property
    def is_deprecated(self) -> bool:
        return bool(self.deprecation)

    def to_dict(self) -> dict:
        data = self.model_dump(exclude_unset=True, exclude_none=True)
        for field_name, value in data.items():
            if isinstance(value, Enum):
                data[field_name] = value.value
        return data

    @field_validator("kind")
    @classmethod
    def kind_options(cls, v: str) -> str:
        if v not in ATTRIBUTE_KIND_LABELS:
            raise ValueError(f"Only valid Attribute Kind are : {ATTRIBUTE_KIND_LABELS} ")
        return v

    @model_validator(mode="before")
    @classmethod
    def validate_dropdown_choices(cls, values: Any) -> Any:
        """Validate that choices are defined for a dropdown but not for other kinds."""
        if isinstance(values, dict):
            kind = values.get("kind")
            choices = values.get("choices")
        elif isinstance(values, AttributeSchema):
            kind = values.kind
            choices = values.choices
        else:
            return values
        if kind != "Dropdown" and choices:
            raise ValueError(f"Can only specify 'choices' for kind=Dropdown: {kind}")

        if kind == "Dropdown" and not choices:
            raise ValueError("The property 'choices' is required for kind=Dropdown")

        return values

    @field_validator("parameters", mode="before")
    @classmethod
    def set_parameters_type(cls, value: Any, info: ValidationInfo) -> Any:
        """Override parameters class if using base AttributeParameters class and should be using a subclass"""
        kind = info.data["kind"]
        expected_parameters_class = get_attribute_parameters_class_for_kind(kind=kind)
        if value is None:
            return expected_parameters_class()
        if not isinstance(value, expected_parameters_class) and isinstance(value, AttributeParameters):
            return expected_parameters_class(**value.model_dump())
        return value

    @model_validator(mode="after")
    def validate_parameters(self) -> Self:
        if isinstance(self.parameters, NumberPoolParameters) and not self.kind == "NumberPool":
            raise ValueError(f"NumberPoolParameters can't be used as parameters for {self.kind}")

        if isinstance(self.parameters, TextAttributeParameters) and self.kind not in ["Text", "TextArea"]:
            raise ValueError(f"TextAttributeParameters can't be used as parameters for {self.kind}")

        return self

    def get_class(self) -> type[BaseAttribute]:
        return ATTRIBUTE_TYPES[self.kind].get_infrahub_class()

    @property
    def uses_enum_class(self) -> bool:
        return bool(self.enum) and config.SETTINGS.experimental_features.graphql_enums

    def get_branch(self) -> BranchSupportType:
        if not self.branch:
            raise ValueError("branch hasn't been defined yet")
        return self.branch

    def get_enum_class(self) -> type[enum.Enum]:
        if not self.enum:
            raise ValueError(f"{self.name} is not an Enum")
        if not self._enum_class:
            self._enum_class = generate_python_enum(name=f"{self.name.title()}Enum", options=self.enum)
        return self._enum_class

    def convert_value_to_enum(self, value: Any) -> enum.Enum | None:
        if isinstance(value, enum.Enum) or value is None:
            return value
        enum_class = self.get_enum_class()
        return enum_class(value)

    def convert_enum_to_value(self, data: Any) -> Any:
        if isinstance(data, list):
            value = [self.convert_enum_to_value(element) for element in data]
            return [element.value if isinstance(element, enum.Enum) else element for element in value]
        if isinstance(data, enum.Enum):
            return data.value
        return data

    def update_from_generic(self, other: AttributeSchema) -> None:
        fields_to_exclude = ("id", "order_weight", "branch", "inherited")
        for name in self.model_fields:
            if name in fields_to_exclude:
                continue
            if getattr(self, name) != getattr(other, name):
                setattr(self, name, getattr(other, name))

    def to_node(self) -> dict[str, Any]:
        fields_to_exclude = {"id", "state", "filters"}
        fields_to_json = {"computed_attribute", "parameters"}
        data = self.model_dump(exclude=fields_to_exclude | fields_to_json)

        for field_name in fields_to_json:
            if field := getattr(self, field_name):
                data[field_name] = {"value": field.model_dump()}
            else:
                data[field_name] = None

        return data

    def get_regex(self) -> str | None:
        return self.regex

    def get_min_length(self) -> int | None:
        return self.min_length

    def get_max_length(self) -> int | None:
        return self.max_length

    async def get_query_filter(
        self,
        name: str,
        filter_name: str,
        branch: Branch | None = None,
        filter_value: str | int | bool | list | None = None,
        include_match: bool = True,
        param_prefix: str | None = None,
        db: InfrahubDatabase | None = None,
        partial_match: bool = False,
        support_profiles: bool = False,
    ) -> tuple[list[QueryElement], dict[str, Any], list[str]]:
        if self.enum:
            filter_value = self.convert_enum_to_value(filter_value)

        return await default_attribute_query_filter(
            name=name,
            attribute_kind=self.kind,
            filter_name=filter_name,
            branch=branch,
            filter_value=filter_value,
            include_match=include_match,
            param_prefix=param_prefix,
            db=db,
            partial_match=partial_match,
            support_profiles=support_profiles,
        )


class NumberPoolSchema(AttributeSchema):
    parameters: NumberPoolParameters = Field(
        default_factory=NumberPoolParameters,
        description="Extra parameters specific to NumberPool attributes",
        json_schema_extra={"update": UpdateSupport.VALIDATE_CONSTRAINT.value},
    )


class TextAttributeSchema(AttributeSchema):
    parameters: TextAttributeParameters = Field(
        default_factory=TextAttributeParameters,
        description="Extra parameters specific to text attributes",
        json_schema_extra={"update": UpdateSupport.VALIDATE_CONSTRAINT.value},
    )

    @model_validator(mode="after")
    def reconcile_parameters(self) -> Self:
        if self.regex != self.parameters.regex:
            final_regex = self.parameters.regex if self.parameters.regex is not None else self.regex
            self.regex = self.parameters.regex = final_regex
        if self.min_length != self.parameters.min_length:
            final_min_length = self.parameters.min_length if self.parameters.min_length is not None else self.min_length
            self.min_length = self.parameters.min_length = final_min_length
        if self.max_length != self.parameters.max_length:
            final_max_length = self.parameters.max_length if self.parameters.max_length is not None else self.max_length
            self.max_length = self.parameters.max_length = final_max_length
        return self

    def get_regex(self) -> str | None:
        return self.parameters.regex

    def get_min_length(self) -> int | None:
        return self.parameters.min_length

    def get_max_length(self) -> int | None:
        return self.parameters.max_length


class NumberAttributeSchema(AttributeSchema):
    parameters: NumberAttributeParameters = Field(
        default_factory=NumberAttributeParameters,
        description="Extra parameters specific to number attributes",
        json_schema_extra={"update": UpdateSupport.VALIDATE_CONSTRAINT.value},
    )


attribute_schema_class_by_kind: dict[str, type[AttributeSchema]] = {
    "NumberPool": NumberPoolSchema,
    "Text": TextAttributeSchema,
    "TextArea": TextAttributeSchema,
    "Number": NumberAttributeSchema,
}
