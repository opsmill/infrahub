from __future__ import annotations

from typing import TYPE_CHECKING

from dependencies.registry import get_component_registry
from graphene import Boolean, String

from infrahub.core.branch import Branch
from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.core.to_graphql.aggregated import AggregatedToGraphQLTranslators
from infrahub.core.to_graphql.model import ToGraphQLRequest

from .standard_node import InfrahubObjectType

if TYPE_CHECKING:
    from infrahub.graphql import GraphqlContext


class BranchType(InfrahubObjectType):
    id = String(required=True)
    name = String(required=True)
    description = String(required=False)
    origin_branch = String(required=False)
    branched_from = String(required=False)
    created_at = String(required=False)
    is_data_only = Boolean(required=False)
    is_default = Boolean(required=False)

    class Meta:
        description = "Branch"
        name = "Branch"
        model = Branch

    @classmethod
    async def get_list(cls, fields: dict, context: GraphqlContext, *args, **kwargs):  # pylint: disable=unused-argument
        to_graphql_translator = get_component_registry().get_component(AggregatedToGraphQLTranslators)
        async with context.db.start_session() as db:
            objs = await Branch.get_list(db=db, **kwargs)

            if not objs:
                return []

            return [
                await to_graphql_translator.to_graphql(ToGraphQLRequest(obj=obj, db=context.db, fields=fields))
                for obj in objs
                if obj.name != GLOBAL_BRANCH_NAME
            ]
