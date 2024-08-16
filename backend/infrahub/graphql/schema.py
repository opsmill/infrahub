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
    DiffUpdateMutation,
    InfrahubAccountSelfUpdate,
    InfrahubAccountTokenCreate,
    InfrahubAccountTokenDelete,
    IPAddressPoolGetResource,
    IPPrefixPoolGetResource,
    ProcessRepository,
    ProposedChangeRequestRunCheck,
    RelationshipAdd,
    RelationshipRemove,
    SchemaDropdownAdd,
    SchemaDropdownRemove,
    SchemaEnumAdd,
    SchemaEnumRemove,
    TaskCreate,
    TaskUpdate,
    ValidateRepositoryConnectivity,
)
from .parser import extract_selection
from .queries import (
    AccountToken,
    BranchQueryList,
    DiffSummary,
    InfrahubInfo,
    InfrahubIPAddressGetNextAvailable,
    InfrahubIPPrefixGetNextAvailable,
    InfrahubResourcePoolAllocated,
    InfrahubResourcePoolUtilization,
    InfrahubSearchAnywhere,
    InfrahubStatus,
    Relationship,
    Task,
)
from .queries.diff.tree import DiffTreeQuery, DiffTreeSummaryQuery

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from . import GraphqlContext


# pylint: disable=unused-argument


async def default_paginated_list_resolver(root: dict, info: GraphQLResolveInfo, **kwargs):
    fields = await extract_selection(info.field_nodes[0], schema=info.return_type.graphene_type._meta.schema)

    return await info.return_type.graphene_type.get_paginated_list(**kwargs, fields=fields, context=info.context)


async def account_resolver(root, info: GraphQLResolveInfo):
    fields = await extract_fields(info.field_nodes[0].selection_set)
    context: GraphqlContext = info.context

    async with context.db.start_session() as db:
        results = await NodeManager.query(
            schema=InfrahubKind.GENERICACCOUNT,
            filters={"ids": [context.account_session.account_id]},
            fields=fields,
            db=db,
        )
        if results:
            account_profile = await results[0].to_graphql(db=db, fields=fields)
            return account_profile

        raise NodeNotFoundError(node_type=InfrahubKind.GENERICACCOUNT, identifier=context.account_session.account_id)


class InfrahubBaseQuery(ObjectType):
    Branch = BranchQueryList
    InfrahubAccountToken = AccountToken

    DiffTree = DiffTreeQuery
    DiffTreeSummary = DiffTreeSummaryQuery
    DiffSummary = DiffSummary

    Relationship = Relationship

    InfrahubInfo = InfrahubInfo
    InfrahubStatus = InfrahubStatus

    InfrahubSearchAnywhere = InfrahubSearchAnywhere

    InfrahubTask = Task

    IPAddressGetNextAvailable = InfrahubIPAddressGetNextAvailable
    IPPrefixGetNextAvailable = InfrahubIPPrefixGetNextAvailable
    InfrahubResourcePoolAllocated = InfrahubResourcePoolAllocated
    InfrahubResourcePoolUtilization = InfrahubResourcePoolUtilization


class InfrahubBaseMutation(ObjectType):
    InfrahubAccountTokenCreate = InfrahubAccountTokenCreate.Field()
    InfrahubAccountSelfUpdate = InfrahubAccountSelfUpdate.Field()
    InfrahubAccountTokenDelete = InfrahubAccountTokenDelete.Field()
    CoreProposedChangeRunCheck = ProposedChangeRequestRunCheck.Field()

    IPPrefixPoolGetResource = IPPrefixPoolGetResource.Field()
    IPAddressPoolGetResource = IPAddressPoolGetResource.Field()

    BranchCreate = BranchCreate.Field()
    BranchDelete = BranchDelete.Field()
    BranchRebase = BranchRebase.Field()
    BranchMerge = BranchMerge.Field()
    BranchUpdate = BranchUpdate.Field()
    BranchValidate = BranchValidate.Field()

    DiffUpdate = DiffUpdateMutation.Field()

    InfrahubRepositoryProcess = ProcessRepository.Field()
    InfrahubRepositoryConnectivity = ValidateRepositoryConnectivity.Field()
    InfrahubTaskCreate = TaskCreate.Field()
    InfrahubTaskUpdate = TaskUpdate.Field()

    RelationshipAdd = RelationshipAdd.Field()
    RelationshipRemove = RelationshipRemove.Field()
    SchemaDropdownAdd = SchemaDropdownAdd.Field()
    SchemaDropdownRemove = SchemaDropdownRemove.Field()
    SchemaEnumAdd = SchemaEnumAdd.Field()
    SchemaEnumRemove = SchemaEnumRemove.Field()
