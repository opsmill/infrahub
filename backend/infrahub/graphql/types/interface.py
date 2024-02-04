from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

from graphene import Interface
from graphene.types.interface import InterfaceOptions

from .mixin import GetListMixin

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.graphql import GraphqlContext
    from infrahub.graphql.types import InfrahubObject


class InfrahubInterfaceOptions(InterfaceOptions):
    schema = None


class InfrahubInterface(Interface, GetListMixin):
    @classmethod
    def resolve_type(cls, instance: Dict[str, Any], info: GraphQLResolveInfo) -> InfrahubObject:
        context: GraphqlContext = info.context
        if "type" in instance:
            return context.types[instance["type"]]

        raise ValueError("Unable to identify the type of the instance.")
