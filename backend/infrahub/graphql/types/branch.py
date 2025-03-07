from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import Boolean, Field, String

from infrahub.core.branch import Branch
from infrahub.core.constants import GLOBAL_BRANCH_NAME

from .standard_node import InfrahubObjectType

if TYPE_CHECKING:
    from infrahub.graphql.initialization import GraphqlContext


class BranchType(InfrahubObjectType):
    id = String(required=True)
    name = String(required=True)
    description = String(required=False)
    origin_branch = String(required=False)
    branched_from = String(required=False)
    created_at = String(required=False)
    sync_with_git = Boolean(required=False)
    is_default = Boolean(required=False)
    is_isolated = Field(Boolean(required=False), deprecation_reason="non isolated mode is not supported anymore")
    has_schema_changes = Boolean(required=False)

    class Meta:
        description = "Branch"
        name = "Branch"
        model = Branch

    @classmethod
    async def get_list(
        cls,
        fields: dict,
        graphql_context: GraphqlContext,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        async with graphql_context.db.start_session() as db:
            objs = await Branch.get_list(db=db, **kwargs)

            if not objs:
                return []

            return [await obj.to_graphql(fields=fields) for obj in objs if obj.name != GLOBAL_BRANCH_NAME]
