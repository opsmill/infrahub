from pydantic import Field

from infrahub.message_bus import InfrahubBaseMessage


class RequestGitCreateBranch(InfrahubBaseMessage):
    """Sent to trigger the creation of a branch in git repositories."""

    branch: str = Field(..., description="The branch to target")
