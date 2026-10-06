from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence
    from datetime import datetime

    from infrahub.git.writeback.models import (
        AbandonmentRecord,
        Actor,
        DeliveryFailure,
        HeldRegeneration,
        HoldReceipt,
        PendingMerge,
        ReleaseLease,
        RevertedDelivery,
        WritebackIntent,
    )


@dataclass(frozen=True)
class RepositoryRef:
    """The repository whose merges a delivery pushes to its remote."""

    id: str
    name: str
    destination_git_branch: str
    """The remote branch that Infrahub maps onto its default branch, which receives the merges."""


@dataclass(frozen=True)
class ReplayResult:
    """The worktree head after a replay of merges, and the commit whose merge conflicted, if one did."""

    head: str
    """The base of the replay when a merge conflicted, because the replay then resets to it."""
    conflicting_commit: str | None = None


type Clock = Callable[[], datetime]
"""Return the current time, timezone-aware."""


class DeliveryStatePort(Protocol):
    """The delivery state of each repository, read and written on the default branch only.

    Every method except the three reads runs under the lock of the delivery state. Every method that
    takes or clears a release lease also trims the expired leases in the same save.
    """

    async def read(self, *, repository_id: str) -> WritebackIntent:
        """Return one consistent snapshot of the delivery state of the repository."""

    async def pending_repository_ids(self) -> frozenset[str]:
        """Return the id of every repository whose delivery status is not `none`."""

    async def references_source_branch(self, *, repository_id: str, git_branch: str) -> bool:
        """Return whether a pending merge of the repository comes from this remote branch."""

    async def enqueue(self, *, repository_id: str, entry: PendingMerge, widen: bool) -> WritebackIntent:
        """Append the merge, unless its id is queued, was removed, or was in the last abandonment.

        Args:
            widen: When the merge is appended, hold a full regeneration of the repository in the same save.

        """

    async def start_attempt(self, *, repository_id: str) -> WritebackIntent:
        """Stamp the start of a delivery attempt, and return the snapshot that the attempt works from."""

    async def record_failure(
        self, *, repository_id: str, failure: DeliveryFailure, final: bool, retry_due_at: datetime | None
    ) -> None:
        """Record the failure; a final one sets `action-required` only when merges are still queued."""

    async def owe_import(self, *, repository_id: str, commit: str) -> None:
        """Record that an import of the repository objects at the commit is owed."""

    async def settle_import(self, *, repository_id: str, commit: str, snapshot: WritebackIntent) -> bool:
        """Clear the owed import of the commit, and return whether it did.

        Keeps the owed import when another commit is owed, or when the queue grew past the snapshot.
        """

    async def request_branch_deletion(self, *, repository_id: str, git_branch: str) -> bool:
        """Flag each pending merge from the remote branch to delete that branch once delivered.

        Returns whether any pending merge comes from the branch.
        """

    async def progress(self, *, repository_id: str) -> None:
        """Move the time of the last progress at a step boundary of an attempt, and leave the queue untouched."""

    async def hold(self, *, repository_id: str, held: HeldRegeneration) -> HoldReceipt | None:
        """Hold the items under the next sequence, or return None and write nothing when the queue is empty."""

    async def settle_delivery(
        self, *, repository_id: str, snapshot: WritebackIntent, delivered_commit: str | None
    ) -> ReleaseLease | None:
        """Remove the merges of the snapshot, and lease the uncovered held items up to the snapshot's sequence.

        Returns None when no held item is left to lease.
        """

    async def abandon(
        self, *, repository_id: str, queue_version: int, record: AbandonmentRecord, actor: Actor
    ) -> tuple[WritebackIntent, ReleaseLease | None]:
        """Move every pending merge and the owed import into the record, and lease every uncovered held item.

        Both happen in one save, made as the actor.

        Raises:
            DeliveryQueueChangedError: The queue is no longer at `queue_version`.
            NothingPendingError: The queue is empty.

        """

    async def lease_owed_release(self, *, repository_id: str) -> ReleaseLease | None:
        """Lease every held item that no live lease covers.

        Returns None and writes nothing while merges are queued, or when no such item is held.
        """

    async def renew_lease(self, *, repository_id: str, lease_id: str) -> None:
        """Move the expiry of the lease."""

    async def expire_lease(self, *, repository_id: str, lease_id: str) -> None:
        """Expire the lease now and keep its items held for the next lease; does nothing when the lease is gone."""

    async def clear_released(self, *, repository_id: str, lease_id: str) -> None:
        """Remove each item of the lease that keeps its named sequence, then the lease; does nothing when it is gone."""

    async def touch(self, *, repository_id: str) -> None:
        """Move the time of the last progress after a recovery submission, as at a step boundary of an attempt."""

    async def record_reverted(self, *, repository_id: str, reverted: RevertedDelivery) -> None:
        """Replace the record of the delivered commit that a rewrite of the remote discarded."""


class DeliveryGitPort(Protocol):
    """The Git work of a delivery, on the clone of one repository and its destination worktree.

    Each Git command that a method runs is bounded in time.
    """

    async def fetch(self) -> None:
        """Fetch from the remote.

        Raises:
            RepositoryError: The clone has no `origin` remote.

        """

    def remote_head(self, *, git_branch: str) -> str | None:
        """Return the commit of the remote branch as last fetched, or None when the remote has no such branch."""

    def is_ancestor(self, *, ancestor: str, descendant: str) -> bool:
        """Return whether `ancestor` is `descendant` or one of its ancestors; a commit missing locally gives False.

        Raises:
            RepositoryError: Git failed for another reason.

        """

    def replay(self, *, base: str, commits: Sequence[str]) -> ReplayResult:
        """Reset the worktree to `base` and merge each commit in order; a conflict aborts and resets to `base`."""

    async def push(self) -> None:
        """Push the worktree head to the destination branch of the remote."""

    def reset(self, *, commit: str) -> None:
        """Reset the worktree to the commit. Never raises."""

    async def record(self, *, commit: str) -> None:
        """Make the commit the one that Infrahub tracks for the repository."""

    async def import_at(self, *, commit: str) -> None:
        """Import the repository objects at the commit on the default branch, with no time bound."""

    async def broadcast(self, *, commit: str) -> None:
        """Ask every worker to fetch the commit."""

    async def delete_remote_branch(self, *, git_branch: str) -> None:
        """Delete the branch on the remote; a branch that is already gone counts as deleted."""

    async def notify_branch_deleted(self, *, git_branch: str) -> None:
        """Tell every worker that the remote branch is gone, without deleting it."""


class RegenerationReleasePort(Protocol):
    async def release(
        self, *, repository_id: str, held: HeldRegeneration, renew: Callable[[], Awaitable[None]]
    ) -> None:
        """Dispatch the held regeneration of one lease, and call `renew` after each awaited step.

        Args:
            held: The items that the lease names, each at its named sequence.
            renew: Moves the expiry of the lease.

        """


class DeliveryRunQuery(Protocol):
    async def has_queued_run(self, *, repository_id: str) -> bool:
        """Return whether a delivery run of the repository waits to start; raises when the orchestrator fails."""
