from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import Interface
from graphene.types.interface import InterfaceOptions

from infrahub.graphql.constants import KIND_GRAPHQL_FIELD_NAME

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.graphql.initialization import GraphqlContext
    from infrahub.graphql.types import InfrahubObject


class InfrahubInterfaceOptions(InterfaceOptions):
    schema = None


class InfrahubInterface(Interface):
    @classmethod
    def resolve_type(cls, instance: dict[str, Any], info: GraphQLResolveInfo) -> InfrahubObject:
        graphql_context: GraphqlContext = info.context
        if KIND_GRAPHQL_FIELD_NAME in instance:
            return graphql_context.types[instance[KIND_GRAPHQL_FIELD_NAME]]

        raise ValueError("Unable to identify the type of the instance.")
