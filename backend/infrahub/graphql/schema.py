from __future__ import annotations

from typing import TYPE_CHECKING

from graphene import ObjectType
from infrahub_sdk.utils import extract_fields

from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.exceptions import NodeNotFoundError

from .mutations import (
    BranchCreate,
    BranchDelete,
    BranchMerge,
    BranchRebase,
    BranchUpdate,
    BranchValidate,
    CoreAccountSelfUpdate,
    CoreAccountTokenCreate,
    ProposedChangeRequestRunCheck,
    RelationshipAdd,
    RelationshipRemove,
    SchemaDropdownAdd,
    SchemaDropdownRemove,
    SchemaEnumAdd,
    SchemaEnumRemove,
    TaskCreate,
    TaskUpdate,
)
from .parser import extract_selection_set_fields
from .queries import BranchQueryList, DiffSummary, DiffSummaryOld, InfrahubInfo, InfrahubStatus, Relationship, Task

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from . import GraphqlContext


# pylint: disable=unused-argument


async def default_paginated_list_resolver(root: dict, info: GraphQLResolveInfo, **kwargs):
    fields = extract_selection_set_fields(info.field_nodes[0])

    return await info.return_type.graphene_type.get_paginated_list(**kwargs, fields=fields, context=info.context)


async def account_resolver(root, info: GraphQLResolveInfo):
    fields = await extract_fields(info.field_nodes[0].selection_set)
    context: GraphqlContext = info.context

    async with context.db.start_session() as db:
        results = await NodeManager.query(
            schema=InfrahubKind.ACCOUNT, filters={"ids": [context.account_session.account_id]}, fields=fields, db=db
        )
        if results:
            account_profile = await results[0].to_graphql(db=db, fields=fields)
            return account_profile

        raise NodeNotFoundError(
            node_type=InfrahubKind.ACCOUNT,
            identifier=context.account_session.account_id,
        )


class InfrahubBaseQuery(ObjectType):
    Branch = BranchQueryList

    DiffSummary = DiffSummary
    DiffSummaryOld = DiffSummaryOld

    Relationship = Relationship

    InfrahubInfo = InfrahubInfo
    InfrahubStatus = InfrahubStatus

    InfrahubTask = Task


class InfrahubBaseMutation(ObjectType):
    CoreAccountTokenCreate = CoreAccountTokenCreate.Field()
    CoreAccountSelfUpdate = CoreAccountSelfUpdate.Field()
    CoreProposedChangeRunCheck = ProposedChangeRequestRunCheck.Field()

    BranchCreate = BranchCreate.Field()
    BranchDelete = BranchDelete.Field()
    BranchRebase = BranchRebase.Field()
    BranchMerge = BranchMerge.Field()
    BranchUpdate = BranchUpdate.Field()
    BranchValidate = BranchValidate.Field()
    InfrahubTaskCreate = TaskCreate.Field()
    InfrahubTaskUpdate = TaskUpdate.Field()

    RelationshipAdd = RelationshipAdd.Field()
    RelationshipRemove = RelationshipRemove.Field()
    SchemaDropdownAdd = SchemaDropdownAdd.Field()
    SchemaDropdownRemove = SchemaDropdownRemove.Field()
    SchemaEnumAdd = SchemaEnumAdd.Field()
    SchemaEnumRemove = SchemaEnumRemove.Field()
