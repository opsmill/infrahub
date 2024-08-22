from pydantic import Field

from infrahub.message_bus import InfrahubMessage


class RequestDiffUpdate(InfrahubMessage):
    """
    Request diff to be updated.

    If the message only include a branch_name, it is assumed to be for updating the diff that tracks
    the lifetime changes of a branch
    """

    branch_name: str = Field(..., description="The branch associated with the diff")
    name: str | None = None
    from_time: str | None = None
    to_time: str | None = None
