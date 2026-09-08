from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from infrahub.core.constants import (
        RepositoryCommitState,
        RepositoryGitCondition,
        RepositoryGitUnavailableReason,
    )


@dataclass(frozen=True)
class CommitEntry:
    hash: str
    """Full commit hash."""

    short_hash: str
    """First 7 characters of the hash."""

    summary: str
    """First line of the commit message."""

    message: str
    """Full commit message."""

    author_name: str

    authored_at: datetime
    """Timezone-aware."""

    committed_at: datetime
    """Timezone-aware."""

    state: RepositoryCommitState


@dataclass(frozen=True)
class GitStateFacts:
    """What a worker measured on its local clone, before any of it is classified."""

    head: str | None = None
    """Head of the remote branch or tracked ref, as last fetched."""

    imported: str | None = None
    """Commit the graph records as imported on the request branch."""

    imported_resolvable: bool | None = None
    """Whether the imported hash names an object the clone holds.

    Measured before any ancestry call: an ancestry test against an unresolvable hash raises
    rather than answering.
    """

    imported_is_ancestor_of_head: bool | None = None

    pending_count: int | None = None

    tracked: bool = False
    """False when nothing is imported or inherited on this branch."""


@dataclass(frozen=True)
class BranchRef:
    """One branch of a repository and the remote ref it is compared against."""

    branch_name: str
    git_ref: str
    tracked_commit: str | None = None


@dataclass(frozen=True)
class CommitLogRequest:
    repository_id: str
    repository_name: str
    repository_kind: str
    location: str
    infrahub_branch_name: str
    git_ref: str
    imported_commit: str | None
    limit: int
    offset: int
    include_pending_count: bool


@dataclass(frozen=True)
class BranchHeadsRequest:
    repository_id: str
    repository_name: str
    repository_kind: str
    location: str
    branches: tuple[BranchRef, ...]


@dataclass(frozen=True)
class CommitLogResult:
    condition: RepositoryGitCondition
    remote_head: str | None = None
    imported_commit: str | None = None
    pending_count: int | None = None
    commits: tuple[CommitEntry, ...] = ()
    fetched_at: datetime | None = None
    unavailable_reason: RepositoryGitUnavailableReason | None = None
    warm_up_task_id: str | None = None
    error_message: str | None = None
    """Display-safe explanation, set whenever no git-derived answer was produced."""


@dataclass(frozen=True)
class BranchDriftRow:
    branch_name: str
    git_ref: str | None
    tracked_commit: str | None
    remote_head: str | None
    condition: RepositoryGitCondition


@dataclass(frozen=True)
class BranchDriftResult:
    branches: tuple[BranchDriftRow, ...] = ()
    fetched_at: datetime | None = None
    unavailable_reason: RepositoryGitUnavailableReason | None = None
    warm_up_task_id: str | None = None
    error_message: str | None = None
    """Display-safe explanation, set whenever no git-derived answer was produced."""
