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
from .mutations.computed_attribute import UpdateComputedAttribute
from .mutations.diff import DiffUpdateMutation
from .mutations.diff_conflict import ResolveDiffConflict
from .mutations.generator import GeneratorDefinitionRequestRun
from .mutations.proposed_change import ProposedChangeMerge, ProposedChangeRequestRunCheck
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
from .queries import (
    AccountPermissions,
    AccountToken,
    BranchQueryList,
    InfrahubInfo,
    InfrahubIPAddressGetNextAvailable,
    InfrahubIPPrefixGetNextAvailable,
    InfrahubResourcePoolAllocated,
    InfrahubResourcePoolUtilization,
    InfrahubSearchAnywhere,
    InfrahubStatus,
    Relationship,
)
from .queries.diff.tree import DiffTreeQuery, DiffTreeSummaryQuery
from .queries.event import Event
from .queries.task import Task, TaskBranchStatus


class InfrahubBaseQuery(ObjectType):
    Branch = BranchQueryList
    InfrahubAccountToken = AccountToken
    InfrahubPermissions = AccountPermissions

    DiffTree = DiffTreeQuery
    DiffTreeSummary = DiffTreeSummaryQuery

    Relationship = Relationship

    InfrahubInfo = InfrahubInfo
    InfrahubStatus = InfrahubStatus

    InfrahubSearchAnywhere = InfrahubSearchAnywhere

    InfrahubTask = Task
    InfrahubEvent = Event
    InfrahubTaskBranchStatus = TaskBranchStatus

    IPAddressGetNextAvailable = InfrahubIPAddressGetNextAvailable
    IPPrefixGetNextAvailable = InfrahubIPPrefixGetNextAvailable
    InfrahubResourcePoolAllocated = InfrahubResourcePoolAllocated
    InfrahubResourcePoolUtilization = InfrahubResourcePoolUtilization


class InfrahubBaseMutation(ObjectType):
    InfrahubAccountTokenCreate = InfrahubAccountTokenCreate.Field()
    InfrahubAccountSelfUpdate = InfrahubAccountSelfUpdate.Field()
    InfrahubAccountTokenDelete = InfrahubAccountTokenDelete.Field()
    CoreProposedChangeRunCheck = ProposedChangeRequestRunCheck.Field()
    CoreProposedChangeMerge = ProposedChangeMerge.Field()
    CoreGeneratorDefinitionRun = GeneratorDefinitionRequestRun.Field()

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
    InfrahubUpdateComputedAttribute = UpdateComputedAttribute.Field()

    RelationshipAdd = RelationshipAdd.Field()
    RelationshipRemove = RelationshipRemove.Field()
    SchemaDropdownAdd = SchemaDropdownAdd.Field()
    SchemaDropdownRemove = SchemaDropdownRemove.Field()
    SchemaEnumAdd = SchemaEnumAdd.Field()
    SchemaEnumRemove = SchemaEnumRemove.Field()
    ResolveDiffConflict = ResolveDiffConflict.Field()
