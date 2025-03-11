from pydantic import ConfigDict, Field

from infrahub.context import InfrahubContext
from infrahub.generators.models import ProposedChangeGeneratorDefinition
from infrahub.message_bus import InfrahubMessage
from infrahub.message_bus.types import ProposedChangeBranchDiff


class RequestGeneratorDefinitionCheck(InfrahubMessage):
    """Sent to trigger Generators to run for a proposed change."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    generator_definition: ProposedChangeGeneratorDefinition = Field(..., description="The Generator Definition")
    branch_diff: ProposedChangeBranchDiff = Field(..., description="The calculated diff between the two branches")
    proposed_change: str = Field(..., description="The unique ID of the Proposed Change")
    source_branch: str = Field(..., description="The source branch")
    source_branch_sync_with_git: bool = Field(..., description="Indicates if the source branch should sync with git")
    destination_branch: str = Field(..., description="The target branch")
    context: InfrahubContext = Field(..., description="The Infrahub context")
