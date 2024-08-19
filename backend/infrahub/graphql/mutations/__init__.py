from .account import InfrahubAccountSelfUpdate, InfrahubAccountTokenCreate, InfrahubAccountTokenDelete
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
from .diff import DiffUpdateMutation
from .diff_conflict import ResolveDiffConflict
from .ipam import InfrahubIPAddressMutation, InfrahubIPNamespaceMutation, InfrahubIPPrefixMutation
from .main import InfrahubMutation, InfrahubMutationMixin, InfrahubMutationOptions
from .proposed_change import (
    InfrahubProposedChangeMutation,
    ProposedChangeRequestRunCheck,
)
from .relationship import RelationshipAdd, RelationshipRemove
from .repository import InfrahubRepositoryMutation, ProcessRepository, ValidateRepositoryConnectivity
from .resource_manager import InfrahubNumberPoolMutation, IPAddressPoolGetResource, IPPrefixPoolGetResource
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
    "DiffUpdateMutation",
    "InfrahubAccountSelfUpdate",
    "InfrahubAccountTokenCreate",
    "InfrahubAccountTokenDelete",
    "IPPrefixPoolGetResource",
    "IPAddressPoolGetResource",
    "InfrahubArtifactDefinitionMutation",
    "InfrahubNumberPoolMutation",
    "InfrahubIPAddressMutation",
    "InfrahubIPNamespaceMutation",
    "InfrahubIPPrefixMutation",
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
    "ProcessRepository",
    "RelationshipAdd",
    "RelationshipRemove",
    "ResolveDiffConflict",
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
    "ValidateRepositoryConnectivity",
]
