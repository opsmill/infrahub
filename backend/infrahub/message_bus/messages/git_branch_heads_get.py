from datetime import datetime

from pydantic import BaseModel, Field

from infrahub.core.constants import RepositoryGitCondition, RepositoryGitUnavailableReason
from infrahub.message_bus import InfrahubMessage, InfrahubResponse, InfrahubResponseData

ROUTING_KEY = "git.branch_heads.get"


class BranchRefInput(BaseModel):
    branch_name: str = Field(..., description="Infrahub branch the row is reported for")
    git_ref: str = Field(..., description="Remote branch or read-only ref the branch is compared against")
    tracked_commit: str | None = Field(default=None, description="Commit imported on the Infrahub branch")


class GitBranchHeadsGet(InfrahubMessage):
    """Read the remote head of every branch of a repository from a worker's local clone."""

    repository_id: str = Field(..., description="The unique ID of the Repository")
    repository_name: str = Field(..., description="The name of the repository")
    repository_kind: str = Field(..., description="The kind of the repository")
    location: str = Field(..., description="The external URL of the repository")
    branches: list[BranchRefInput] = Field(..., description="The branches whose remote heads are read")


class GitBranchDriftRow(BaseModel):
    branch_name: str
    git_ref: str
    # A reply is serialised without its null fields, so each nullable field needs a default to parse again.
    tracked_commit: str | None = None
    remote_head: str | None = None
    condition: RepositoryGitCondition


class GitBranchHeadsGetResponseData(InfrahubResponseData):
    # Every field has a default so an error reply, which carries no data, still parses.
    fetched_at: datetime | None = None
    unavailable_reason: RepositoryGitUnavailableReason | None = None
    warm_up_task_id: str | None = None
    branches: list[GitBranchDriftRow] = Field(default_factory=list)
    error_message: str | None = None


class GitBranchHeadsGetResponse(InfrahubResponse):
    routing_key: str = ROUTING_KEY
    data: GitBranchHeadsGetResponseData
