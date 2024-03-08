from __future__ import annotations

import enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

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
    _sort_by: List[str] = ["name"]

    @property
    def is_attribute(self) -> bool:
        return True

    @property
    def is_relationship(self) -> bool:
        return False

    @field_validator("kind")
    @classmethod
    def kind_options(cls, v: str) -> str:
        if v not in ATTRIBUTE_KIND_LABELS:
            raise ValueError(f"Only valid Attribute Kind are : {ATTRIBUTE_KIND_LABELS} ")
        return v

    @model_validator(mode="before")
    @classmethod
    def validate_dropdown_choices(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that choices are defined for a dropdown but not for other kinds."""
        if values.get("kind") != "Dropdown" and values.get("choices"):
            raise ValueError(f"Can only specify 'choices' for kind=Dropdown: {values['kind'] }")

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

    def get_attribute_enum_class(self) -> Optional[enum.EnumType]:
        if not self.uses_enum_class:
            return None
        return generate_python_enum(f"{self.name.title()}Enum", {v: v for v in self.enum})

    def convert_to_attribute_enum(self, value: Any) -> Any:
        if not self.uses_enum_class or not value:
            return value
        attribute_enum_class = self.get_attribute_enum_class()
        if isinstance(value, attribute_enum_class):
            return value
        if isinstance(value, enum.Enum):
            value = value.value
        return attribute_enum_class(value)

    def convert_to_enum_value(self, value: Any) -> Any:
        if not self.uses_enum_class:
            return value
        if isinstance(value, list):
            value = [self.convert_to_attribute_enum(element) for element in value]
            return [element.value if isinstance(element, enum.Enum) else element for element in value]
        value = self.convert_to_attribute_enum(value)
        return value.value if isinstance(value, enum.Enum) else value

    async def get_query_filter(
        self,
        name: str,
        filter_name: str,
        branch: Optional[Branch] = None,
        filter_value: Optional[Union[str, int, bool, list, enum.Enum]] = None,
        include_match: bool = True,
        param_prefix: Optional[str] = None,
        db: Optional[InfrahubDatabase] = None,
        partial_match: bool = False,
    ) -> Tuple[List[QueryElement], Dict[str, Any], List[str]]:
        filter_value = self.convert_to_enum_value(filter_value)
        return await default_attribute_query_filter(
            name=name,
            filter_name=filter_name,
            branch=branch,
            filter_value=filter_value,
            include_match=include_match,
            param_prefix=param_prefix,
            db=db,
            partial_match=partial_match,
        )
