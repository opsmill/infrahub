import enum
import re
from typing import Iterable, Union

import graphene

from infrahub.core import registry
from infrahub.core.attribute import String
from infrahub.core.branch import Branch
from infrahub.core.schema import AttributeSchema, GenericSchema, GroupSchema, NodeSchema
from infrahub.graphql.mutations.attribute import BaseAttributeInput
from infrahub.graphql.types.attribute import AttributeInterface
from infrahub.types import ATTRIBUTE_TYPES, InfrahubDataType

from .types.attribute import BaseAttribute

ENUM_NAME_REGEX = re.compile("[_a-zA-Z0-9]+")


def get_enum_attribute_type_name(node_schema: NodeSchema, attr_schema: AttributeSchema) -> str:
    return f"{node_schema.kind}{attr_schema.name.title()}"


def generate_graphql_enum(name, options):
    def description_func(value):
        if value:
            return value.value
        return f"Enum for {name}"

    main_attrs = {}
    for option in options:
        enum_name = "_".join(re.findall(ENUM_NAME_REGEX, option)).upper()
        main_attrs[enum_name] = option
    py_enum = enum.Enum(name, main_attrs)
    return graphene.Enum.from_enum(enum=py_enum, description=description_func)


def load_all_enum_types_in_registry(
    node_schemas: Iterable[Union[NodeSchema, GenericSchema, GroupSchema]], branch: Branch
) -> None:
    for node_schema in node_schemas:
        load_enum_type_in_registry(node_schema, branch)


def load_enum_type_in_registry(node_schema: Union[NodeSchema, GenericSchema, GroupSchema], branch: Branch) -> None:
    for attr_schema in node_schema.attributes:
        if not attr_schema.enum:
            continue
        base_enum_name = get_enum_attribute_type_name(node_schema, attr_schema)
        enum_value_name = f"{base_enum_name}Value"
        input_class_name = f"{base_enum_name}AttributeInput"
        attribute_name = f"{base_enum_name}Attribute"
        attribute_type_class_name = f"{base_enum_name}AttributeType"
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
        attribute_type_metaclass = type(
            "Meta",
            (),
            {
                "description": f"Attribute of type {attribute_name}",
                "name": attribute_name,
                "interfaces": {AttributeInterface},
            },
        )
        attribute_type_class = type(
            attribute_type_class_name, (BaseAttribute,), {"value": graphene_field, "Meta": attribute_type_metaclass}
        )
        data_type_class = type(
            data_type_class_name,
            (InfrahubDataType,),
            {
                "label": data_type_class_name,
                "graphql": graphene.String,
                "graphql_query": attribute_type_class,
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
