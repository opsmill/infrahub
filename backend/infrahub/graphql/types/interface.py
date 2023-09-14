from __future__ import annotations

from graphene import Interface
from graphene.types.interface import InterfaceOptions

from infrahub.core import registry

from .mixin import GetListMixin


class InfrahubInterfaceOptions(InterfaceOptions):
    schema = None


class InfrahubInterface(Interface, GetListMixin):
    @classmethod
    def resolve_type(cls, instance, info):
        branch = info.context["infrahub_branch"]

        if "type" in instance:
            return registry.get_graphql_type(name=instance["type"], branch=branch)

        raise ValueError("Unable to identify the type of the instance.")
