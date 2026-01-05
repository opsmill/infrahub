from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import ID, Field, Int, List, NonNull, String

from infrahub.core.registry import registry
from infrahub.exceptions import ValidationError
from infrahub.graphql.field_extractor import extract_graphql_fields
from infrahub.graphql.types import BranchType, InfrahubBranch, InfrahubBranchType

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo


async def branch_resolver(
    root: dict,  # noqa: ARG001
    info: GraphQLResolveInfo,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    fields = extract_graphql_fields(info)
    return await BranchType.get_list(graphql_context=info.context, fields=fields, exclude_global=True, **kwargs)


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
    name__value: str | None = None,
    ids: list[str] | None = None,
) -> dict[str, Any]:
    if isinstance(limit, int) and limit < 1:
        raise ValidationError("limit must be >= 1")
    if isinstance(offset, int) and offset < 0:
        raise ValidationError("offset must be >= 0")

    fields = extract_graphql_fields(info)
    result: dict[str, Any] = {}
    if "edges" in fields:
        branches = await InfrahubBranch.get_list(
            graphql_context=info.context,
            fields=fields.get("edges", {}).get("node", {}),
            limit=limit,
            offset=offset,
            name=name__value,
            ids=ids,
            exclude_global=True,
        )
        result["edges"] = [{"node": branch} for branch in branches]
    if "count" in fields:
        result["count"] = await InfrahubBranchType.get_list_count(
            graphql_context=info.context, name=name__value, ids=ids
        )

    if "default_branch" in fields:
        result["default_branch"] = await InfrahubBranch.get_by_name(
            graphql_context=info.context,
            fields=fields["default_branch"],
            name=registry.default_branch,
        )

    return result


InfrahubBranchQueryList = Field(
    InfrahubBranchType,
    offset=Int(),
    limit=Int(),
    name__value=String(),
    ids=List(ID),
    description="Retrieve paginated information about active branches.",
    resolver=infrahub_branch_resolver,
    required=True,
)
