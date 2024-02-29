from __future__ import annotations

import importlib
import typing
from typing import TYPE_CHECKING, Dict, Type

import graphene
from graphene.types.generic import GenericScalar

from infrahub.core import registry

if TYPE_CHECKING:
    from infrahub.core.attribute import BaseAttribute
    from infrahub.graphql.mutations.attribute import BaseAttributeInput
    from infrahub.graphql.types.attribute import BaseAttribute as BaseAttributeType

DEFAULT_MODULE_ATTRIBUTE = "infrahub.core.attribute"
DEFAULT_MODULE_GRAPHQL_INPUT = "infrahub.graphql.mutations"
DEFAULT_MODULE_GRAPHQL_QUERY = "infrahub.graphql.types"


class InfrahubDataType:
    label: str
    graphql_query: str
    graphql_input: str
    graphql_filter: type
    graphql: type
    infrahub: str

    @classmethod
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        registry.data_type[cls.label] = cls

    def __str__(self):
        return self.label

    @classmethod
    def get_infrahub_class(cls) -> Type[BaseAttribute]:
        if not isinstance(cls.infrahub, str):
            return cls.infrahub
        module = importlib.import_module(DEFAULT_MODULE_ATTRIBUTE)
        return getattr(module, cls.infrahub)

    @classmethod
    def get_graphql_input(cls) -> Type[BaseAttributeInput]:
        if not isinstance(cls.graphql_input, str):
            return cls.graphql_input
        module = importlib.import_module(DEFAULT_MODULE_GRAPHQL_INPUT)
        return getattr(module, cls.graphql_input)

    @classmethod
    def get_graphql_type(cls) -> Type[BaseAttributeType]:
        if not isinstance(cls.graphql_query, str):
            return cls.graphql_query
        module = importlib.import_module(DEFAULT_MODULE_GRAPHQL_QUERY)
        return getattr(module, cls.graphql_query)

    @classmethod
    def get_graphql_type_name(cls) -> str:
        return cls.get_graphql_type().__name__

    @classmethod
    def get_graphql_filters(cls, name: str, include_properties: bool = True) -> Dict[str, typing.Any]:
        filters: Dict[str, typing.Any] = {}
        attr_class = cls.get_infrahub_class()
        filters[f"{name}__value"] = cls.graphql_filter()
        filters[f"{name}__values"] = graphene.List(cls.graphql_filter)

        if not include_properties:
            return filters

        for node_prop in attr_class._node_properties:
            filters[f"{name}__{node_prop}__id"] = graphene.ID()

        for flag_prop in attr_class._flag_properties:
            filters[f"{name}__{flag_prop}"] = graphene.Boolean()

        return filters


class Default(InfrahubDataType):
    label: str = "Default"
    graphql = graphene.String
    graphql_query = "BaseAttribute"
    graphql_input = "BaseAttributeInput"
    graphql_filter = graphene.String
    infrahub = "BaseAttribute"


class ID(InfrahubDataType):
    label: str = "ID"
    graphql = graphene.ID
    graphql_query = "TextAttributeType"
    graphql_input = "TextAttributeInput"
    graphql_filter = graphene.String
    infrahub = "String"


class Text(InfrahubDataType):
    label: str = "Text"
    graphql = graphene.String
    graphql_query = "TextAttributeType"
    graphql_input = "TextAttributeInput"
    graphql_filter = graphene.String
    infrahub = "String"


class TextArea(Text):
    label: str = "TextArea"
    graphql = graphene.String
    graphql_query = "TextAttributeType"
    graphql_input = "TextAttributeInput"
    graphql_filter = graphene.String
    infrahub = "String"


class DateTime(InfrahubDataType):
    label: str = "DateTime"
    graphql = graphene.String
    graphql_query = "TextAttributeType"
    graphql_input = "TextAttributeInput"
    graphql_filter = graphene.String
    infrahub = "String"


class Email(InfrahubDataType):
    label: str = "Email"
    graphql = graphene.String
    graphql_query = "TextAttributeType"
    graphql_input = "TextAttributeInput"
    graphql_filter = graphene.String
    infrahub = "String"


class Password(InfrahubDataType):
    label: str = "Password"
    graphql = graphene.String
    graphql_query = "TextAttributeType"
    graphql_input = "TextAttributeInput"
    graphql_filter = graphene.String
    infrahub = "String"


class HashedPassword(InfrahubDataType):
    label: str = "Password"
    graphql = graphene.String
    graphql_query = "TextAttributeType"
    graphql_input = "TextAttributeInput"
    graphql_filter = graphene.String
    infrahub = "HashedPassword"


class URL(InfrahubDataType):
    label: str = "URL"
    graphql = graphene.String
    graphql_query = "TextAttributeType"
    graphql_input = "TextAttributeInput"
    graphql_filter = graphene.String
    infrahub = "URL"


class File(InfrahubDataType):
    label: str = "File"
    graphql = graphene.String
    graphql_query = "TextAttributeType"
    graphql_input = "TextAttributeInput"
    graphql_filter = graphene.String
    infrahub = "String"


class MacAddress(InfrahubDataType):
    label: str = "MacAddress"
    graphql = graphene.String
    graphql_query = "TextAttributeType"
    graphql_input = "TextAttributeInput"
    graphql_filter = graphene.String
    infrahub = "String"


class Color(InfrahubDataType):
    label: str = "Color"
    graphql = graphene.String
    graphql_query = "TextAttributeType"
    graphql_input = "TextAttributeInput"
    graphql_filter = graphene.String
    infrahub = "String"


class Dropdown(InfrahubDataType):
    label: str = "Dropdown"
    graphql = graphene.String
    graphql_query = "DropdownType"
    graphql_input = "TextAttributeInput"
    graphql_filter = graphene.String
    infrahub = "Dropdown"


class Number(InfrahubDataType):
    label: str = "Number"
    graphql = graphene.Int
    graphql_query = "NumberAttributeType"
    graphql_input = "NumberAttributeInput"
    graphql_filter = graphene.Int
    infrahub = "Integer"


class Bandwidth(InfrahubDataType):
    label: str = "Bandwidth"
    graphql = graphene.Int
    graphql_query = "NumberAttributeType"
    graphql_input = "NumberAttributeInput"
    graphql_filter = graphene.Int
    infrahub = "Integer"


class IPHost(InfrahubDataType):
    label: str = "IPHost"
    graphql = graphene.String
    graphql_query = "IPHostType"
    graphql_input = "TextAttributeInput"
    graphql_filter = graphene.String
    infrahub = "IPHost"


class IPNetwork(InfrahubDataType):
    label: str = "IPNetwork"
    graphql = graphene.String
    graphql_query = "IPNetworkType"
    graphql_input = "TextAttributeInput"
    graphql_filter = graphene.String
    infrahub = "IPNetwork"


class Checkbox(InfrahubDataType):
    label: str = "Checkbox"
    graphql = graphene.Boolean
    graphql_query = "CheckboxAttributeType"
    graphql_input = "CheckboxAttributeInput"
    graphql_filter = graphene.Boolean
    infrahub = "Boolean"


class List(InfrahubDataType):
    label: str = "List"
    graphql = GenericScalar
    graphql_query = "ListAttributeType"
    graphql_input = "ListAttributeInput"
    graphql_filter = GenericScalar
    infrahub = "ListAttribute"


class JSON(InfrahubDataType):
    label: str = "JSON"
    graphql = GenericScalar
    graphql_query = "JSONAttributeType"
    graphql_input = "JSONAttributeInput"
    graphql_filter = GenericScalar
    infrahub = "JSONAttribute"


class Any(InfrahubDataType):
    label: str = "Any"
    graphql = GenericScalar
    graphql_query = "AnyAttributeType"
    graphql_input = "AnyAttributeInput"
    graphql_filter = GenericScalar
    infrahub = "AnyAttribute"


# ------------------------------------------
# Deprecated
# ------------------------------------------
class String(InfrahubDataType):
    label: str = "String"
    graphql = graphene.String
    graphql_query = "TextAttributeType"
    graphql_input = "TextAttributeInput"
    graphql_filter = graphene.String
    infrahub = "String"


class Integer(InfrahubDataType):
    label: str = "Integer"
    graphql = graphene.Int
    graphql_query = "NumberAttributeType"
    graphql_input = "NumberAttributeInput"
    graphql_filter = graphene.Int
    infrahub = "Integer"


class Boolean(InfrahubDataType):
    label: str = "Boolean"
    graphql = graphene.Boolean
    graphql_query = "CheckboxAttributeType"
    graphql_input = "CheckboxAttributeInput"
    graphql_filter = graphene.Boolean
    infrahub = "Boolean"


ATTRIBUTE_TYPES: Dict[str, Type[InfrahubDataType]] = {
    "ID": ID,
    "Dropdown": Dropdown,
    "Text": Text,
    "TextArea": TextArea,
    "DateTime": DateTime,
    "Email": Email,
    "Password": Password,
    "HashedPassword": HashedPassword,
    "URL": URL,
    "File": File,
    "MacAddress": MacAddress,
    "Color": Color,
    "Number": Number,
    "Bandwidth": Bandwidth,
    "IPHost": IPHost,
    "IPNetwork": IPNetwork,
    "Checkbox": Checkbox,
    "List": List,
    "JSON": JSON,
    "Any": Any,
    "String": String,
    "Integer": Integer,
    "Boolean": Boolean,
}

ATTRIBUTE_KIND_LABELS = list(ATTRIBUTE_TYPES.keys())


def get_attribute_type(kind: str = "Default") -> Type[InfrahubDataType]:
    """Return an InfrahubDataType object for a given kind
    If no kind is provided, return the default one."""
    return ATTRIBUTE_TYPES.get(kind, Default)
