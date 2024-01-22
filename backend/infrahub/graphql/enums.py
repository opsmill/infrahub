import re
from typing import Iterable, Union

import graphene

from infrahub.core import registry
from infrahub.core.attribute import String
from infrahub.core.branch import Branch
from infrahub.core.enums import generate_python_enum
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema
from infrahub.graphql.mutations.attribute import BaseAttributeInput
from infrahub.types import ATTRIBUTE_TYPES, InfrahubDataType

from .types.attribute import TextAttributeType

ENUM_NAME_REGEX = re.compile("[_a-zA-Z0-9]+")


def get_enum_attribute_type_name(node_schema: NodeSchema, attr_schema: AttributeSchema) -> str:
    return f"{node_schema.kind}{attr_schema.name.title()}"


def generate_graphql_enum(name, options):
    def description_func(value):
        if value:
            return value.value
        return f"Enum for {name}"

    py_enum = generate_python_enum(name, options)
    return graphene.Enum.from_enum(enum=py_enum, description=description_func)


def load_all_enum_types_in_registry(node_schemas: Iterable[Union[NodeSchema, GenericSchema]], branch: Branch) -> None:
    for node_schema in node_schemas:
        load_enum_type_in_registry(node_schema, branch)


def load_enum_type_in_registry(node_schema: Union[NodeSchema, GenericSchema], branch: Branch) -> None:
    for attr_schema in node_schema.attributes:
        if not attr_schema.enum:
            continue
        base_enum_name = get_enum_attribute_type_name(node_schema, attr_schema)
        enum_value_name = f"{base_enum_name}Value"
        input_class_name = f"{base_enum_name}AttributeInput"
        data_type_class_name = f"{base_enum_name}EnumType"
        graphene_enum = generate_graphql_enum(enum_value_name, attr_schema.enum)
        default_value = None
        if attr_schema.default_value:
            for g_enum in graphene_enum:
                if g_enum.value == attr_schema.default_value:
                    default_value = g_enum.name
                    break
        graphene_field = graphene.Field(graphene_enum, default_value=default_value)
        input_class = type(input_class_name, (BaseAttributeInput,), {"value": graphene_field})
        data_type_class = type(
            data_type_class_name,
            (InfrahubDataType,),
            {
                "label": data_type_class_name,
                "graphql": graphene.String,
                "graphql_query": TextAttributeType,
                "graphql_input": input_class,
                "graphql_filter": graphene_enum,
                "infrahub": String,
            },
        )
        registry.set_graphql_type(
            name=data_type_class.get_graphql_type_name(),
            graphql_type=data_type_class.get_graphql_type(),
            branch=branch.name,
        )
        ATTRIBUTE_TYPES[base_enum_name] = data_type_class
