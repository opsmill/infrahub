from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub.core.constants import RepositoryGitCondition, RepositoryGitUnavailableReason

if TYPE_CHECKING:
    from datetime import datetime

    from infrahub.core.constants import RepositoryCommitState


@dataclass(frozen=True)
class CommitEntry:
    hash: str
    """Full commit hash."""

    message: str
    """Full commit message."""

    author_name: str

    authored_at: datetime
    """Timezone-aware."""

    committed_at: datetime
    """Timezone-aware."""

    state: RepositoryCommitState

    @property
    def short_hash(self) -> str:
        """First 7 characters of the hash."""
        return self.hash[:7]

    @property
    def summary(self) -> str:
        """First line of the commit message."""
        return self.message.split("\n", 1)[0]


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
    """Left None when the count was not requested, as well as when no count applies."""

    def __post_init__(self) -> None:
        """Reject a measurement the worker could not have taken.

        Raises:
            ValueError: When a field is set that the measurement order leaves unreachable.

        """
        if self.imported is None and self.imported_resolvable is not None:
            raise ValueError("imported_resolvable cannot be measured without an imported commit")
        if self.imported_resolvable is False and self.imported_is_ancestor_of_head is not None:
            raise ValueError("An unresolvable imported commit cannot be tested for ancestry")


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


def _raise_unless_unavailable_fields_agree(
    unavailable_reason: RepositoryGitUnavailableReason | None,
    warm_up_task_id: str | None,
    error_message: str | None,
) -> None:
    """Reject a result whose unavailable fields contradict the reason it carries.

    Raises:
        ValueError: When a field belonging to the unavailable path is set without it.

    """
    if unavailable_reason is None:
        if warm_up_task_id is not None:
            raise ValueError("A warm_up_task_id belongs to an unavailable result")
        if error_message is not None:
            raise ValueError("An error_message belongs to an unavailable result")
    elif warm_up_task_id is not None and unavailable_reason is not RepositoryGitUnavailableReason.NOT_CLONED:
        raise ValueError(f"A warm-up is only started for NOT_CLONED, not {unavailable_reason.name}")


@dataclass(frozen=True)
class CommitLogResult:
    condition: RepositoryGitCondition
    remote_head: str | None = None
    imported_commit: str | None = None
    """The imported hash as the answering worker resolved it, when it resolved one."""

    pending_count: int | None = None
    commits: tuple[CommitEntry, ...] = ()
    fetched_at: datetime | None = None
    unavailable_reason: RepositoryGitUnavailableReason | None = None
    warm_up_task_id: str | None = None
    error_message: str | None = None
    """Display-safe explanation, set whenever no git-derived answer was produced."""

    def __post_init__(self) -> None:
        """Reject a result whose condition and unavailable reason disagree.

        Raises:
            ValueError: When only one of the two is set.

        """
        is_unavailable = self.condition is RepositoryGitCondition.UNAVAILABLE
        if is_unavailable and self.unavailable_reason is None:
            raise ValueError("A result with condition UNAVAILABLE must carry an unavailable_reason")
        if not is_unavailable and self.unavailable_reason is not None:
            raise ValueError(
                f"A result carrying an unavailable_reason must have condition UNAVAILABLE, not {self.condition.name}"
            )
        _raise_unless_unavailable_fields_agree(
            unavailable_reason=self.unavailable_reason,
            warm_up_task_id=self.warm_up_task_id,
            error_message=self.error_message,
        )


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

    def __post_init__(self) -> None:
        """Reject a result whose unavailable fields contradict the reason it carries.

        The rows are graph-resolved, so this result carries them alongside an unavailable column
        rather than instead of it.

        Raises:
            ValueError: When a field belonging to the unavailable path is set without it.

        """
        _raise_unless_unavailable_fields_agree(
            unavailable_reason=self.unavailable_reason,
            warm_up_task_id=self.warm_up_task_id,
            error_message=self.error_message,
        )
