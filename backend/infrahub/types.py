import graphene

from infrahub.graphql.mutations import (
    BoolAttributeInput,
    IntAttributeInput,
    StringAttributeInput,
)
from infrahub.graphql.types import BoolAttributeType, IntAttributeType, StrAttributeType


class InfrahubDataType:
    label: str
    graphql_query: type
    graphql_input: type
    graphql: type

    def __str__(self):
        return self.label


class ID:
    label: str = "ID"
    graphql = graphene.ID
    # graphql_query = StrAttributeType
    # graphql_input = StringAttributeInput


class String:
    label: str = "String"
    graphql = graphene.String
    graphql_query = StrAttributeType
    graphql_input = StringAttributeInput


class Integer:
    label: str = "String"
    graphql = graphene.Int
    graphql_query = IntAttributeType
    graphql_input = IntAttributeInput


class Boolean:
    label: str = "Boolean"
    graphql = graphene.Boolean
    graphql_query = BoolAttributeType
    graphql_input = BoolAttributeInput


# TYPES_MAPPING_INFRAHUB_GRAPHQL = {
#     "String": StrAttributeType,
#     "Integer": IntAttributeType,
#     "Boolean": BoolAttributeType,
#     "List": ListAttributeType,
#     "Any": AnyAttributeType,
# }

# TYPES_MAPPING_INFRAHUB_GRAPHQL_STR = {
#     "String": "StrAttributeType",
#     "Integer": "IntAttributeType",
#     "Boolean": "BoolAttributeType",
#     "List": "ListAttributeType",
#     "Any": "AnyAttributeType",
# }

# INPUT_TYPES_MAPPING_INFRAHUB_GRAPHQL = {
#     "String": StringAttributeInput,
#     "Integer": IntAttributeInput,
#     "Boolean": BoolAttributeInput,
#     "List": ListAttributeInput,
#     "Any": AnyAttributeInput,
# }

# FILTER_TYPES_MAPPING_INFRAHUB_GRAPHQL = {
#     "String": graphene.String,
#     "Integer": graphene.Int,
#     "Boolean": graphene.Boolean,
#     "List": GenericScalar,
#     "Any": GenericScalar,
# }
