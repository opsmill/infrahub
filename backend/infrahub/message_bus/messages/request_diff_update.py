from pydantic import Field

from infrahub.message_bus import InfrahubMessage


class RequestDiffUpdate(InfrahubMessage):
    """Request diff to be updated."""

    branch_name: str = Field(..., description="The branch associated with the diff")
    name: str | None = None
    from_time: str | None = None
    to_time: str | None = None
