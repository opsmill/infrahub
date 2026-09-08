from __future__ import annotations

from graphene import Boolean, Field, Int, List, NonNull, ObjectType, String

from .attribute import DropdownType, TextAttributeType
from .enums import InfrahubBranchStatus


class InfrahubRepositoryBranchStatusNode(ObjectType):
    name = String(required=True, description="Branch name; joins the repository's per-branch attribute edges")
    status = InfrahubBranchStatus(required=True)
    is_default = Boolean(required=True)
    sync_with_git = Boolean(
        required=True,
        description="Always true on CoreRepository, which selects on it; varies per row on CoreReadOnlyRepository, whose row set is every branch",
    )
    branched_from = String(
        required=True, description="Fork point from the default branch; inherited rows resolve as of this time"
    )
    commit = Field(TextAttributeType, description="Imported commit as this branch resolves it")
    sync_status = Field(
        DropdownType,
        description="Import status as this branch resolves it (defined on CoreGenericRepository, present for both kinds)",
    )
    internal_status = Field(DropdownType, description="Defined on CoreGenericRepository, present for both kinds")
    ref = Field(TextAttributeType, description="CoreReadOnlyRepository only; null for CoreRepository")

    class Meta:
        name = "InfrahubRepositoryBranchStatus"


class InfrahubRepositoryBranchStatusEdge(ObjectType):
    node = Field(InfrahubRepositoryBranchStatusNode, required=True)


class InfrahubRepositoryBranchStatusType(ObjectType):
    count = Int(required=True, description="Number of rows after all filters, before limit and offset")
    edges = List(NonNull(InfrahubRepositoryBranchStatusEdge), required=True)
