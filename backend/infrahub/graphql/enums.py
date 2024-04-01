import re
from typing import Any, List

import graphene

from infrahub.core.enums import generate_python_enum
from infrahub.core.schema import AttributeSchema, MainSchemaTypes

ENUM_NAME_REGEX = re.compile("[_a-zA-Z0-9]+")


def get_enum_attribute_type_name(node_schema: MainSchemaTypes, attr_schema: AttributeSchema) -> str:
    return f"{node_schema.kind}{attr_schema.name.title()}"


def generate_graphql_enum(name: str, options: List[Any]) -> graphene.Enum:
    def description_func(value: Any) -> str:
        if value:
            return value.value
        return f"Enum for {name}"

    py_enum = generate_python_enum(name=name, options=options)
    return graphene.Enum.from_enum(enum=py_enum, description=description_func)
