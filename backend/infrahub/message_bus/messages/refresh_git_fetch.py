from typing import Self

from pydantic import BaseModel, Field, model_validator

from infrahub.message_bus import InfrahubMessage


class BranchCommitPair(BaseModel):
    """One branch a worker converges, and the commit its worktree is reset to."""

    infrahub_branch_name: str = Field(..., description="Infrahub branch whose worktree is reset")
    infrahub_branch_id: str = Field(..., description="Id of the Infrahub branch, used to create a missing worktree")
    commit: str = Field(..., description="Commit SHA the worktree is reset to")


class RefreshGitFetch(InfrahubMessage):
    """Fetch a repository remote changes."""

    location: str = Field(..., description="The external URL of the repository")
    repository_id: str = Field(..., description="The unique ID of the repository")
    repository_name: str = Field(..., description="The name of the repository")
    repository_kind: str = Field(..., description="The type of repository")
    infrahub_branch_name: str = Field(..., description="Infrahub branch on which to sync the remote repository")
    infrahub_branch_id: str = Field(..., description="Id of the Infrahub branch on which to sync the remote repository")
    commit: str | None = Field(
        default=None,
        description="Commit SHA to check out, pinned by the sync orchestrator instead of pulling the latest upstream HEAD",
    )
    branches: tuple[BranchCommitPair, ...] | None = Field(
        default=None,
        description="Every branch to converge with its pinned commit, the first one repeating the single-branch fields",
    )

    @model_validator(mode="after")
    def validate_first_branch_matches_single_branch_fields(self) -> Self:
        """A worker that reads only the single-branch fields must converge the branch the list starts with.

        Raises:
            ValueError: When ``branches`` is empty, or its first entry differs from the single-branch fields.

        """
        if self.branches is None:
            return self
        if not self.branches:
            raise ValueError("branches must hold at least one branch when it is set")
        first = self.branches[0]
        if (first.infrahub_branch_name, first.infrahub_branch_id, first.commit) != (
            self.infrahub_branch_name,
            self.infrahub_branch_id,
            self.commit,
        ):
            raise ValueError(
                f"The first entry of branches ({first.infrahub_branch_name}, {first.infrahub_branch_id}, "
                f"{first.commit}) differs from the single-branch fields ({self.infrahub_branch_name}, "
                f"{self.infrahub_branch_id}, {self.commit})"
            )
        return self
