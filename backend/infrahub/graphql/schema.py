from __future__ import annotations

from graphene import ObjectType

from .mutations.account import (
    InfrahubAccountSelfUpdate,
    InfrahubAccountTokenCreate,
    InfrahubAccountTokenDelete,
)
from .mutations.branch import (
    BranchCreate,
    BranchDelete,
    BranchMerge,
    BranchRebase,
    BranchUpdate,
    BranchValidate,
)
from .mutations.diff import DiffUpdateMutation
from .mutations.diff_conflict import ResolveDiffConflict
from .mutations.proposed_change import ProposedChangeRequestRunCheck
from .mutations.relationship import (
    RelationshipAdd,
    RelationshipRemove,
)
from .mutations.repository import (
    ProcessRepository,
    ValidateRepositoryConnectivity,
)
from .mutations.resource_manager import IPAddressPoolGetResource, IPPrefixPoolGetResource
from .mutations.schema import (
    SchemaDropdownAdd,
    SchemaDropdownRemove,
    SchemaEnumAdd,
    SchemaEnumRemove,
)
from .mutations.task import (
    TaskCreate,
    TaskUpdate,
)
from .queries import (
    AccountPermissions,
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


class InfrahubBaseQuery(ObjectType):
    Branch = BranchQueryList
    InfrahubAccountToken = AccountToken
    InfrahubPermissions = AccountPermissions

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
    ResolveDiffConflict = ResolveDiffConflict.Field()
