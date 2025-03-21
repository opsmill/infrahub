from __future__ import annotations

import enum
from enum import Enum
from typing import TYPE_CHECKING, Any

from pydantic import field_validator, model_validator

from infrahub import config
from infrahub.core.enums import generate_python_enum
from infrahub.core.query.attribute import default_attribute_query_filter
from infrahub.types import ATTRIBUTE_KIND_LABELS, ATTRIBUTE_TYPES

from .generated.attribute_schema import GeneratedAttributeSchema

if TYPE_CHECKING:
    from infrahub.core.attribute import BaseAttribute
    from infrahub.core.branch import Branch
    from infrahub.core.constants import BranchSupportType
    from infrahub.core.query import QueryElement
    from infrahub.database import InfrahubDatabase


class AttributeSchema(GeneratedAttributeSchema):
    _sort_by: list[str] = ["name"]
    _enum_class: type[enum.Enum] | None = None

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
    def validate_dropdown_choices(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Validate that choices are defined for a dropdown but not for other kinds."""
        if values.get("kind") != "Dropdown" and values.get("choices"):
            raise ValueError(f"Can only specify 'choices' for kind=Dropdown: {values['kind']}")

        if values.get("kind") == "Dropdown" and not values.get("choices"):
            raise ValueError("The property 'choices' is required for kind=Dropdown")

        return values

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
        fields_to_json = {"computed_attribute"}
        data = self.model_dump(exclude=fields_to_exclude | fields_to_json)

        for field_name in fields_to_json:
            if field := getattr(self, field_name):
                data[field_name] = {"value": field.model_dump()}
            else:
                data[field_name] = None

        return data

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
