from datetime import datetime

from pydantic import BaseModel, Field

from infrahub.core.constants import RepositoryCommitState, RepositoryGitCondition, RepositoryGitUnavailableReason
from infrahub.message_bus import InfrahubMessage, InfrahubResponse, InfrahubResponseData

ROUTING_KEY = "git.commit_log.get"


class GitCommitLogGet(InfrahubMessage):
    """Read the commit log of a repository from a worker's local clone."""

    repository_id: str = Field(..., description="The unique ID of the Repository")
    repository_name: str = Field(..., description="The name of the repository")
    repository_kind: str = Field(..., description="The kind of the repository")
    location: str = Field(..., description="The external URL of the repository")
    infrahub_branch_name: str = Field(..., description="Infrahub branch the log is read for")
    git_ref: str = Field(..., description="Remote branch or read-only ref whose history is listed")
    imported_commit: str | None = Field(default=None, description="Commit imported on the Infrahub branch")
    limit: int = Field(..., ge=1, le=100, description="Number of commits to return")
    offset: int = Field(..., ge=0, description="Number of commits to skip from the head")
    include_pending_count: bool = Field(..., description="Whether to count the commits not yet imported")


class GitCommitLogEntry(BaseModel):
    hash: str
    message: str
    author_name: str
    authored_at: datetime
    committed_at: datetime
    state: RepositoryCommitState


class GitCommitLogGetResponseData(InfrahubResponseData):
    # Every field has a default so an error reply, which carries no data, still parses.
    condition: RepositoryGitCondition | None = None
    remote_head: str | None = None
    imported_commit: str | None = None
    pending_count: int | None = None
    fetched_at: datetime | None = None
    unavailable_reason: RepositoryGitUnavailableReason | None = None
    warm_up_task_id: str | None = None
    commits: list[GitCommitLogEntry] = Field(default_factory=list)
    error_message: str | None = None


class GitCommitLogGetResponse(InfrahubResponse):
    routing_key: str = ROUTING_KEY
    data: GitCommitLogGetResponseData
