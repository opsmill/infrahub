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
    page = kwargs.pop("page", 1)
    limit = kwargs.pop("limit", 100)
    offset = (page - 1) * limit
    fields = {"id": None, "name": None}  # extract_graphql_fields(info)

    branches = await BranchType.get_list(
        fields=fields, graphql_context=info.context, limit=limit, offset=offset, **kwargs
    )
    total_count = 100  # await BranchType.get_list_total_count(graphql_context=info.context, **kwargs)

    total_pages = (total_count + limit - 1) // limit

    # return InfrahubBranchType(
    #     total_count=total_count,
    #     total_pages=total_pages,
    #     current_page=page,
    #     per_page=limit,
    #     branches=[BranchType(**branch) for branch in branches],
    # )

    return {
        "total_count": total_count,
        "total_pages": total_pages,
        "current_page": page,
        "per_page": limit,
        "branches": branches,
    }


InfrahubBranchQueryList = Field(
    InfrahubBranchType,
    ids=List(ID),
    name=String(),
    page=Int(default_value=1),
    limit=Int(default_value=100),
    description="Retrieve paginated information about active branches.",
    resolver=infrahub_branch_resolver,
    required=True,
)
