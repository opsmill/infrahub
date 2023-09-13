from pydantic import Field

from infrahub.message_bus import InfrahubBaseMessage


class EventSchemaUpdate(InfrahubBaseMessage):
    """Sent when the schema on a branch has been updated."""

    branch: str = Field(..., description="The branch where the update occured")
