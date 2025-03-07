from pydantic import Field

from infrahub.context import InfrahubContext
from infrahub.message_bus import InfrahubMessage


class FinalizeValidatorExecution(InfrahubMessage):
    """Update the status of a validator after all checks have been completed."""

    validator_id: str = Field(..., description="The id of the validator associated with this check")
    validator_execution_id: str = Field(..., description="The id of current execution of the associated validator")
    start_time: str = Field(..., description="Start time when the message was first created")
    validator_type: str = Field(..., description="The type of validator to complete")
    context: InfrahubContext = Field(..., description="The Infrahub context")
    proposed_change: str = Field(..., description="The ID of the proposed change")
