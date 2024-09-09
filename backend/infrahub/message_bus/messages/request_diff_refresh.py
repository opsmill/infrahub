from pydantic import Field

from infrahub.message_bus import InfrahubMessage


class RequestDiffRefresh(InfrahubMessage):
    """Request diff be recalculated from scratch."""

    branch_name: str = Field(..., description="The branch associated with the diff")
    diff_id: str = Field(..., description="The id for this diff")
