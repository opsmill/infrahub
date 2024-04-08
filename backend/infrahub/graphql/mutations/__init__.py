from .account import CoreAccountSelfUpdate, CoreAccountTokenCreate
from .artifact_definition import InfrahubArtifactDefinitionMutation
from .attribute import (
    AnyAttributeCreate,
    AnyAttributeUpdate,
    BoolAttributeCreate,
    BoolAttributeUpdate,
    CheckboxAttributeCreate,
    CheckboxAttributeUpdate,
    JSONAttributeCreate,
    JSONAttributeUpdate,
    ListAttributeCreate,
    ListAttributeUpdate,
    NumberAttributeCreate,
    NumberAttributeUpdate,
    StringAttributeCreate,
    StringAttributeUpdate,
    TextAttributeCreate,
    TextAttributeUpdate,
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
    ProposedChangeRequestRunCheck,
)
from .relationship import RelationshipAdd, RelationshipRemove
from .repository import InfrahubRepositoryMutation
from .schema import SchemaDropdownAdd, SchemaDropdownRemove, SchemaEnumAdd, SchemaEnumRemove
from .task import TaskCreate, TaskUpdate

__all__ = [
    "AnyAttributeCreate",
    "AnyAttributeUpdate",
    "BoolAttributeCreate",
    "BoolAttributeUpdate",
    "BranchCreate",
    "BranchCreateInput",
    "BranchRebase",
    "BranchValidate",
    "BranchDelete",
    "BranchMerge",
    "BranchNameInput",
    "BranchUpdate",
    "CheckboxAttributeCreate",
    "CheckboxAttributeUpdate",
    "CoreAccountSelfUpdate",
    "CoreAccountTokenCreate",
    "InfrahubArtifactDefinitionMutation",
    "InfrahubRepositoryMutation",
    "InfrahubMutationOptions",
    "InfrahubMutation",
    "InfrahubMutationMixin",
    "InfrahubProposedChangeMutation",
    "JSONAttributeCreate",
    "JSONAttributeUpdate",
    "ListAttributeCreate",
    "ListAttributeUpdate",
    "NumberAttributeCreate",
    "NumberAttributeUpdate",
    "ProposedChangeRequestRunCheck",
    "RelationshipAdd",
    "RelationshipRemove",
    "StringAttributeCreate",
    "StringAttributeUpdate",
    "TextAttributeCreate",
    "TextAttributeUpdate",
    "SchemaDropdownAdd",
    "SchemaDropdownRemove",
    "SchemaEnumAdd",
    "SchemaEnumRemove",
    "TaskCreate",
    "TaskUpdate",
]
