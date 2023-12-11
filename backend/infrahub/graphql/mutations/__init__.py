from .account import CoreAccountSelfUpdate, CoreAccountTokenCreate
from .artifact_definition import InfrahubArtifactDefinitionMutation
from .attribute import (
    AnyAttributeInput,
    BoolAttributeInput,
    CheckboxAttributeInput,
    JSONAttributeInput,
    ListAttributeInput,
    NumberAttributeInput,
    StringAttributeInput,
    TextAttributeInput,
)
from .branch import (
    BranchCreate,
    BranchCreateInput,
    BranchDelete,
    BranchMerge,
    BranchNameInput,
    BranchRebase,
    BranchUpdate,
    BranchValidate,
)
from .main import InfrahubMutation, InfrahubMutationMixin, InfrahubMutationOptions
from .proposed_change import (
    InfrahubProposedChangeMutation,
    ProposedChangeRequestRefreshArtifacts,
    ProposedChangeRequestRunCheck,
)
from .relationship import RelationshipAdd, RelationshipRemove
from .repository import InfrahubRepositoryMutation
from .schema import SchemaDropdownAdd, SchemaDropdownRemove, SchemaEnumAdd, SchemaEnumRemove

__all__ = [
    "AnyAttributeInput",
    "BoolAttributeInput",
    "BranchCreate",
    "BranchCreateInput",
    "BranchRebase",
    "BranchValidate",
    "BranchDelete",
    "BranchMerge",
    "BranchNameInput",
    "BranchUpdate",
    "CheckboxAttributeInput",
    "CoreAccountSelfUpdate",
    "CoreAccountTokenCreate",
    "InfrahubArtifactDefinitionMutation",
    "InfrahubRepositoryMutation",
    "InfrahubMutationOptions",
    "InfrahubMutation",
    "InfrahubMutationMixin",
    "InfrahubProposedChangeMutation",
    "JSONAttributeInput",
    "ListAttributeInput",
    "NumberAttributeInput",
    "ProposedChangeRequestRefreshArtifacts",
    "ProposedChangeRequestRunCheck",
    "RelationshipAdd",
    "RelationshipRemove",
    "StringAttributeInput",
    "TextAttributeInput",
    "SchemaDropdownAdd",
    "SchemaDropdownRemove",
    "SchemaEnumAdd",
    "SchemaEnumRemove",
]
