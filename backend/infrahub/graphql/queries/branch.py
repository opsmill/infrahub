from __future__ import annotations

from typing import TYPE_CHECKING

from graphene import ID, Field, List, String
from infrahub_sdk.utils import extract_fields

from infrahub.graphql.types import BranchType

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo


async def branch_resolver(root: dict, info: GraphQLResolveInfo, **kwargs):  # pylint: disable=unused-argument
    fields = await extract_fields(info.field_nodes[0].selection_set)
    return await BranchType.get_list(context=info.context, fields=fields, **kwargs)


BranchQueryList = Field(
    List(BranchType),
    ids=List(ID),
    name=String(),
    resolver=branch_resolver,
)
