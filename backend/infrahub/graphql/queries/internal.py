from __future__ import annotations

from typing import TYPE_CHECKING

from graphene import Field, ObjectType, String

from infrahub import __version__
from infrahub.core import registry

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo


class Info(ObjectType):
    deployment_id = String(required=True)
    version = String(required=True)

    @staticmethod
    async def resolve(
        root: dict,  # pylint: disable=unused-argument
        info: GraphQLResolveInfo,  # pylint: disable=unused-argument
    ):
        return {"deployment_id": str(registry.id), "version": __version__}


InfrahubInfo = Field(Info, resolver=Info.resolve)
