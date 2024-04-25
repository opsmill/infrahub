from pydantic import Field

from infrahub.message_bus import InfrahubMessage


class TriggerGeneratorDefinitionRun(InfrahubMessage):
    """Triggers all Generators to run on the desired branch."""

    branch: str = Field(..., description="The branch to run the Generators in")
