from pydantic import Field

from infrahub.message_bus import InfrahubMessage


class RequestGitCreateBranch(InfrahubMessage):
    """Sent to trigger the creation of a branch in git repositories."""

    branch: str = Field(..., description="The branch to target")
    branch_id: str = Field(..., description="The unique ID of the branch")
