from __future__ import annotations

import importlib
import typing
from datetime import datetime
from typing import TYPE_CHECKING

import graphene
from graphene.types.generic import GenericScalar
from pydantic import EmailStr, HttpUrl, IPvAnyAddress, Json

from infrahub.core import registry

if TYPE_CHECKING:
    from infrahub.core.attribute import BaseAttribute
    from infrahub.graphql.mutations.attribute import BaseAttributeCreate, BaseAttributeUpdate
    from infrahub.graphql.types.attribute import BaseAttribute as BaseAttributeType

DEFAULT_MODULE_ATTRIBUTE = "infrahub.core.attribute"
DEFAULT_MODULE_GRAPHQL_INPUT = "infrahub.graphql.mutations.attribute"
DEFAULT_MODULE_GRAPHQL_QUERY = "infrahub.graphql.types"


class InfrahubDataType:
    label: str
    graphql_query: str
    graphql_create: str
    graphql_update: str
    graphql_filter: type
    graphql: type
    infrahub: str
    pydantic: type

    @classmethod
    def __init_subclass__(cls, **kwargs: typing.Any) -> None:
        super().__init_subclass__(**kwargs)
        registry.data_type[cls.label] = cls

    def __str__(self) -> str:
        return self.label

    @classmethod
    def get_infrahub_class(cls) -> type[BaseAttribute]:
        if not isinstance(cls.infrahub, str):
            return cls.infrahub
        module = importlib.import_module(DEFAULT_MODULE_ATTRIBUTE)
        return getattr(module, cls.infrahub)

    @classmethod
    def get_graphql_create(cls) -> type[BaseAttributeCreate]:
        if not isinstance(cls.graphql_create, str):
            return cls.graphql_create
        module = importlib.import_module(DEFAULT_MODULE_GRAPHQL_INPUT)
        return getattr(module, cls.graphql_create)

    @classmethod
    def get_graphql_update(cls) -> type[BaseAttributeUpdate]:
        if not isinstance(cls.graphql_update, str):
            return cls.graphql_update
        module = importlib.import_module(DEFAULT_MODULE_GRAPHQL_INPUT)
        return getattr(module, cls.graphql_update)

    @classmethod
    def get_graphql_type(cls) -> type[BaseAttributeType]:
        if not isinstance(cls.graphql_query, str):
            return cls.graphql_query
        module = importlib.import_module(DEFAULT_MODULE_GRAPHQL_QUERY)
        return getattr(module, cls.graphql_query)

    @classmethod
    def get_graphql_type_name(cls) -> str:
        return cls.get_graphql_type().__name__

    @classmethod
    def get_graphql_filters(
        cls, name: str, include_properties: bool = True, include_isnull: bool = False
    ) -> dict[str, typing.Any]:
        filters: dict[str, typing.Any] = {}
        attr_class = cls.get_infrahub_class()
        filters[f"{name}__value"] = cls.graphql_filter()
        filters[f"{name}__values"] = graphene.List(cls.graphql_filter)
        if include_isnull:
            filters[f"{name}__isnull"] = graphene.Boolean()

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
    graphql_create = "BaseAttributeCreate"
    graphql_update = "BaseAttributeUpdate"
    graphql_filter = graphene.String
    infrahub = "BaseAttribute"


class ID(InfrahubDataType):
    label: str = "ID"
    graphql = graphene.ID
    graphql_query = "TextAttributeType"
    graphql_create = "TextAttributeCreate"
    graphql_update = "TextAttributeUpdate"
    graphql_filter = graphene.String
    infrahub = "String"


class Text(InfrahubDataType):
    label: str = "Text"
    graphql = graphene.String
    graphql_query = "TextAttributeType"
    graphql_create = "TextAttributeCreate"
    graphql_update = "TextAttributeUpdate"
    graphql_filter = graphene.String
    infrahub = "String"


class TextArea(Text):
    label: str = "TextArea"
    graphql = graphene.String
    graphql_query = "TextAttributeType"
    graphql_create = "TextAttributeCreate"
    graphql_update = "TextAttributeUpdate"
    graphql_filter = graphene.String
    infrahub = "String"


class DateTime(InfrahubDataType):
    label: str = "DateTime"
    graphql = graphene.DateTime
    graphql_query = "TextAttributeType"
    graphql_create = "TextAttributeCreate"
    graphql_update = "TextAttributeUpdate"
    graphql_filter = graphene.DateTime
    infrahub = "DateTime"


class Email(InfrahubDataType):
    label: str = "Email"
    graphql = graphene.String
    graphql_query = "TextAttributeType"
    graphql_create = "TextAttributeCreate"
    graphql_update = "TextAttributeUpdate"
    graphql_filter = graphene.String
    infrahub = "String"


class Password(InfrahubDataType):
    label: str = "Password"
    graphql = graphene.String
    graphql_query = "TextAttributeType"
    graphql_create = "TextAttributeCreate"
    graphql_update = "TextAttributeUpdate"
    graphql_filter = graphene.String
    infrahub = "String"
    pydantic = str


class HashedPassword(InfrahubDataType):
    label: str = "Password"
    graphql = graphene.String
    graphql_query = "TextAttributeType"
    graphql_create = "TextAttributeCreate"
    graphql_update = "TextAttributeUpdate"
    graphql_filter = graphene.String
    infrahub = "HashedPassword"


class URL(InfrahubDataType):
    label: str = "URL"
    graphql = graphene.String
    graphql_query = "TextAttributeType"
    graphql_create = "TextAttributeCreate"
    graphql_update = "TextAttributeUpdate"
    graphql_filter = graphene.String
    infrahub = "URL"


class File(InfrahubDataType):
    label: str = "File"
    graphql = graphene.String
    graphql_query = "TextAttributeType"
    graphql_create = "TextAttributeCreate"
    graphql_update = "TextAttributeUpdate"
    graphql_filter = graphene.String
    infrahub = "String"


class MacAddress(InfrahubDataType):
    label: str = "MacAddress"
    graphql = graphene.String
    graphql_query = "MacAddressType"
    graphql_create = "TextAttributeCreate"
    graphql_update = "TextAttributeUpdate"
    graphql_filter = graphene.String
    infrahub = "MacAddress"


class Color(InfrahubDataType):
    label: str = "Color"
    graphql = graphene.String
    graphql_query = "TextAttributeType"
    graphql_create = "TextAttributeCreate"
    graphql_update = "TextAttributeUpdate"
    graphql_filter = graphene.String
    infrahub = "String"


class Dropdown(InfrahubDataType):
    label: str = "Dropdown"
    graphql = graphene.String
    graphql_query = "DropdownType"
    graphql_create = "TextAttributeCreate"
    graphql_update = "TextAttributeUpdate"
    graphql_filter = graphene.String
    infrahub = "Dropdown"


class Number(InfrahubDataType):
    label: str = "Number"
    graphql = graphene.BigInt
    graphql_query = "NumberAttributeType"
    graphql_create = "NumberAttributeCreate"
    graphql_update = "NumberAttributeUpdate"
    graphql_filter = graphene.BigInt
    infrahub = "Integer"


class Bandwidth(InfrahubDataType):
    label: str = "Bandwidth"
    graphql = graphene.Int
    graphql_query = "NumberAttributeType"
    graphql_create = "NumberAttributeCreate"
    graphql_update = "NumberAttributeUpdate"
    graphql_filter = graphene.Int
    infrahub = "Integer"


class IPHost(InfrahubDataType):
    label: str = "IPHost"
    graphql = graphene.String
    graphql_query = "IPHostType"
    graphql_create = "TextAttributeCreate"
    graphql_update = "TextAttributeUpdate"
    graphql_filter = graphene.String
    infrahub = "IPHost"


class IPNetwork(InfrahubDataType):
    label: str = "IPNetwork"
    graphql = graphene.String
    graphql_query = "IPNetworkType"
    graphql_create = "TextAttributeCreate"
    graphql_update = "TextAttributeUpdate"
    graphql_filter = graphene.String
    infrahub = "IPNetwork"


class Boolean(InfrahubDataType):
    label: str = "Boolean"
    graphql = graphene.Boolean
    graphql_query = "CheckboxAttributeType"
    graphql_create = "CheckboxAttributeCreate"
    graphql_update = "CheckboxAttributeUpdate"
    graphql_filter = graphene.Boolean
    infrahub = "Boolean"


class Checkbox(InfrahubDataType):
    label: str = "Checkbox"
    graphql = graphene.Boolean
    graphql_query = "CheckboxAttributeType"
    graphql_create = "CheckboxAttributeCreate"
    graphql_update = "CheckboxAttributeUpdate"
    graphql_filter = graphene.Boolean
    infrahub = "Boolean"


class List(InfrahubDataType):
    label: str = "List"
    graphql = GenericScalar
    graphql_query = "ListAttributeType"
    graphql_create = "ListAttributeCreate"
    graphql_update = "ListAttributeUpdate"
    graphql_filter = GenericScalar
    infrahub = "ListAttribute"


class JSON(InfrahubDataType):
    label: str = "JSON"
    graphql = GenericScalar
    graphql_query = "JSONAttributeType"
    graphql_create = "JSONAttributeCreate"
    graphql_update = "JSONAttributeUpdate"
    graphql_filter = GenericScalar
    infrahub = "JSONAttribute"


class Any(InfrahubDataType):
    label: str = "Any"
    graphql = GenericScalar
    graphql_query = "AnyAttributeType"
    graphql_create = "AnyAttributeCreate"
    graphql_update = "AnyAttributeUpdate"
    graphql_filter = GenericScalar
    infrahub = "AnyAttribute"


ATTRIBUTE_TYPES: dict[str, type[InfrahubDataType]] = {
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
    "Boolean": Boolean,
    "Checkbox": Checkbox,
    "List": List,
    "JSON": JSON,
    "Any": Any,
}

ATTRIBUTE_PYTHON_TYPES: dict[str, type] = {
    "ID": int,  # Assuming IDs are integers
    "Dropdown": str,  # Dropdowns can be represented as strings
    "Text": str,
    "TextArea": str,
    "DateTime": datetime,
    "Email": EmailStr,
    "Password": str,  # Passwords can be any string
    "HashedPassword": str,  # Hashed passwords are also strings
    "URL": HttpUrl,
    "File": str,  # File paths or identifiers as strings
    "MacAddress": str,  # MAC addresses can be straightforward strings
    "Color": str,  # Colors often represented as hex strings
    "Number": float,  # Numbers can be floats for general use
    "Bandwidth": float,  # Bandwidth in some units, represented as a float
    "IPHost": IPvAnyAddress,  # type: ignore[dict-item]
    "IPNetwork": str,
    "Boolean": bool,
    "Checkbox": bool,  # Checkboxes represent boolean values
    "List": list[Any],  # Lists can contain any type of items
    "JSON": Json,  # Pydantic's Json type handles arbitrary JSON objects
    "Any": Any,  # Any type allowed
}

ATTRIBUTE_KIND_LABELS = list(ATTRIBUTE_TYPES.keys())

# Data types supporting large values, which can therefore not be indexed in neo4j.
LARGE_ATTRIBUTE_TYPES = [TextArea, JSON, List]


def get_attribute_type(kind: str = "Default") -> type[InfrahubDataType]:
    """Return an InfrahubDataType object for a given kind
    If no kind is provided, return the default one."""
    return ATTRIBUTE_TYPES.get(kind, Default)
