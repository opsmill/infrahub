from pydantic import Field

from infrahub.message_bus import InfrahubMessage


class RequestDiffRefresh(InfrahubMessage):
    """Request diff be recalculated from scratch."""

    branch_name: str = Field(..., description="The branch associated with the diff")
    tracking_id_str: str = Field(..., description="The serialized tracking_id for this diff")
