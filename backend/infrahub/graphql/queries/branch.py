from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import ID, Field, List, String
from infrahub_sdk.utils import extract_fields_first_node

from infrahub.graphql.types import BranchType

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo


async def branch_resolver(
    root: dict,  # pylint: disable=unused-argument
    info: GraphQLResolveInfo,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    fields = await extract_fields_first_node(info)
    return await BranchType.get_list(context=info.context, fields=fields, **kwargs)


BranchQueryList = Field(
    List(BranchType),
    ids=List(ID),
    name=String(),
    resolver=branch_resolver,
)
