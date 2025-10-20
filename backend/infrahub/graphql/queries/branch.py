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
    **kwargs: Any,
) -> dict[str, Any]:
    limit = kwargs.pop("limit", 100)
    offset = kwargs.pop("offset", 0)
    fields = extract_graphql_fields(info)
    branches, count = await InfrahubBranchType.get_list_and_count(
        fields=fields.get("edges", {}).get("node", {}),
        graphql_context=info.context,
        limit=limit,
        offset=offset,
        **kwargs,
    )
    return {"count": count, "edges": {"node": branches}}


InfrahubBranchQueryList = Field(
    InfrahubBranchType,
    ids=List(ID),
    name=String(),
    offset=Int(default_value=0),
    limit=Int(default_value=100),
    description="Retrieve paginated information about active branches.",
    resolver=infrahub_branch_resolver,
    required=True,
)
