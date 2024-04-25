from pydantic import ConfigDict, Field

from infrahub.message_bus import InfrahubMessage
from infrahub.message_bus.types import ProposedChangeGeneratorDefinition


class RequestGeneratorDefinitionRun(InfrahubMessage):
    """Sent to trigger a Generator to run on a specific branch."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    generator_definition: ProposedChangeGeneratorDefinition = Field(..., description="The Generator Definition")
    branch: str = Field(..., description="The branch to target")
