from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from graphene import ID, Boolean, Field, List, ObjectType, String

from infrahub import config
from infrahub.core.manager import NodeManager
from infrahub.exceptions import NodeNotFound

from .mutations import (
    BranchCreate,
    BranchDelete,
    BranchMerge,
    BranchRebase,
    BranchValidate,
    CoreAccountTokenCreate,
    RelationshipAdd,
    RelationshipRemove,
)
from .types import BranchDiffType, BranchType
from .utils import extract_fields

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo  # pylint: disable=no-name-in-module

    from infrahub.auth import AccountSession

# pylint: disable=unused-argument


async def default_list_resolver(root: dict, info: GraphQLResolveInfo, **kwargs):
    fields = await extract_fields(info.field_nodes[0].selection_set)
    return await info.return_type.of_type.graphene_type.get_list(**kwargs, fields=fields, context=info.context)


async def default_paginated_list_resolver(root: dict, info: GraphQLResolveInfo, **kwargs):
    fields = await extract_fields(info.field_nodes[0].selection_set)
    return await info.return_type.graphene_type.get_paginated_list(**kwargs, fields=fields, context=info.context)


async def account_resolver(root, info: GraphQLResolveInfo):
    account_session: AccountSession = info.context.get("account_session")
    fields = await extract_fields(info.field_nodes[0].selection_set)

    db = info.context.get("infrahub_database")
    async with db.session(database=config.SETTINGS.database.database) as session:
        results = await NodeManager.query(
            schema="CoreAccount", filters={"ids": [account_session.account_id]}, fields=fields, session=session
        )
        if results:
            account_profile = await results[0].to_graphql(session=session, fields=fields)
            return account_profile

    raise NodeNotFound(
        branch_name=config.SETTINGS.main.default_branch, node_type="CoreAccount", identifier=account_session.account_id
    )


class InfrahubBaseQuery(ObjectType):
    branch = List(BranchType, ids=List(ID), name=String())

    diff = Field(
        BranchDiffType,
        branch=String(required=True, description="Name of the branch to use to calculate the diff."),
        time_from=String(required=False),
        time_to=String(required=False),
        branch_only=Boolean(required=False, default_value=False),
    )

    @staticmethod
    async def resolve_branch(root: dict, info: GraphQLResolveInfo, **kwargs):
        fields = await extract_fields(info.field_nodes[0].selection_set)
        return await BranchType.get_list(fields=fields, context=info.context, **kwargs)

    @staticmethod
    async def resolve_diff(
        root: dict,
        info: GraphQLResolveInfo,
        branch: str,
        branch_only: bool,
        time_from: Optional[str] = None,
        time_to: Optional[str] = None,
        **kwargs,
    ):
        fields = await extract_fields(info.field_nodes[0].selection_set)
        return await BranchDiffType.get_diff(
            fields=fields,
            context=info.context,
            branch_only=branch_only,
            diff_from=time_from or None,
            diff_to=time_to or None,
            branch=branch,
        )


class InfrahubBaseMutation(ObjectType):
    CoreAccountTokenCreate = CoreAccountTokenCreate.Field()

    BranchCreate = BranchCreate.Field()
    BranchDelete = BranchDelete.Field()
    BranchRebase = BranchRebase.Field()
    BranchMerge = BranchMerge.Field()
    BranchValidate = BranchValidate.Field()

    RelationshipAdd = RelationshipAdd.Field()
    RelationshipRemove = RelationshipRemove.Field()
