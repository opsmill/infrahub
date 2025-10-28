from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import ID, Field, Int, List, NonNull, String

from infrahub.graphql.field_extractor import extract_graphql_fields
from infrahub.graphql.types import BranchType, InfrahubBranchType

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo


async def branch_resolver(
    root: dict,  # noqa: ARG001
    info: GraphQLResolveInfo,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    fields = extract_graphql_fields(info)
    return await BranchType.get_list(graphql_context=info.context, fields=fields, **kwargs)


BranchQueryList = Field(
    List(of_type=NonNull(BranchType)),
    ids=List(ID),
    name=String(),
    description="Retrieve information about active branches.",
    resolver=branch_resolver,
    required=True,
)


async def infrahub_branch_resolver(
    root: dict,  # noqa: ARG001
    info: GraphQLResolveInfo,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    fields = extract_graphql_fields(info)
    result = {}
    if "edges" in fields:
        result["edges"] = [
            {"node": branch}
            for branch in await BranchType.get_list(
                graphql_context=info.context, fields=fields.get("edges", {}).get("node", {}), limit=limit, offset=offset
            )
        ]
    if "count" in fields:
        result["count"] = await InfrahubBranchType.get_list_count(graphql_context=info.context)
    return result


InfrahubBranchQueryList = Field(
    InfrahubBranchType,
    ids=List(of_type=NonNull(ID)),
    name=String(),
    offset=Int(),
    limit=Int(),
    description="Retrieve paginated information about active branches.",
    resolver=infrahub_branch_resolver,
    required=True,
)
