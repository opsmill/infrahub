from __future__ import annotations

from graphene import Field, Int, List, NonNull, ObjectType

from .attribute import DropdownType, TextAttributeType
from .branch import (
    NonRequiredBooleanValueField,
    NonRequiredStringValueField,
    RequiredStringValueField,
    StatusField,
)
from .metadata import InfrahubStandardNodeMetaData


class InfrahubRepositoryBranchStatusNode(ObjectType):
    """One branch's view of a repository.

    The branch fields carry the same value-field wrappers and nullability as the branch query, so a
    client reads `name.value` and `commit.value` through one access pattern across the whole row.
    """

    name = Field(
        RequiredStringValueField,
        required=True,
        description="Branch name; joins the repository's per-branch attribute edges",
    )
    status = Field(StatusField, required=True)
    is_default = Field(NonRequiredBooleanValueField, required=False)
    sync_with_git = Field(
        NonRequiredBooleanValueField,
        required=False,
        description="Always true on CoreRepository, which selects on it; varies per row on CoreReadOnlyRepository, whose row set is every branch",
    )
    branched_from = Field(
        NonRequiredStringValueField,
        required=False,
        description="Fork point from the default branch; inherited rows resolve as of this time",
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
    node_metadata = Field(InfrahubStandardNodeMetaData, required=True)


class InfrahubRepositoryBranchStatusType(ObjectType):
    count = Int(required=True, description="Number of rows after all filters, before limit and offset")
    edges = List(NonNull(InfrahubRepositoryBranchStatusEdge), required=True)
