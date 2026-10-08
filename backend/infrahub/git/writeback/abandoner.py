from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.git.writeback.models import AbandonmentRecord
from infrahub.git.writeback.service import REPOSITORY_LOCK_NAMESPACE
from infrahub.log import get_run_logger

if TYPE_CHECKING:
    from infrahub.git.writeback.models import Actor, ReleaseLease
    from infrahub.git.writeback.ports import (
        Clock,
        DeliveryGitPort,
        DeliveryStatePort,
        RegenerationReleasePort,
        RepositoryRef,
    )
    from infrahub.lock import InfrahubLockRegistry

log = get_run_logger()


class WritebackAbandoner:
    """Drop the queued merges of one repository at a user's request, then release the regeneration held for them."""

    def __init__(
        self,
        repository: RepositoryRef,
        state: DeliveryStatePort,
        git: DeliveryGitPort,
        releaser: RegenerationReleasePort,
        lock_registry: InfrahubLockRegistry,
        clock: Clock,
    ) -> None:
        self.repository = repository
        self.state = state
        self.git = git
        self.releaser = releaser
        self.lock_registry = lock_registry
        self.clock = clock

    async def abandon(self, *, queue_version: int, actor: Actor) -> AbandonmentRecord:
        """Remove every queued merge and the owed import of the repository, and return the record that names them.

        It pushes nothing, deletes no remote branch and imports nothing. It tells the workers that each source
        branch flagged for deletion is gone, so they drop their local copy.

        Raises:
            DeliveryQueueChangedError: The queue is no longer at `queue_version`.
            NothingPendingError: The queue is empty.
            DeliveryStateUnavailableError: The lock of the delivery state was not acquired in time.
            RuntimeError: The state saved no record of the abandonment.
            Exception: The release of the held regeneration failed after the abandonment was saved; the items stay
                held, and a later delivery run of the repository releases them.

        """
        async with self.lock_registry.get(name=self.repository.name, namespace=REPOSITORY_LOCK_NAMESPACE):
            recorded = await self.git.recorded_commit()
            abandoned, lease = await self.state.abandon(
                repository_id=self.repository.id,
                queue_version=queue_version,
                record=AbandonmentRecord(
                    abandoned_at=self.clock(),
                    account_id=actor.account_id,
                    account_name=actor.account_name,
                    queue_version=queue_version,
                    # A repository that records no commit can still queue merges, and a user must be able to drop them.
                    recorded_commit=recorded or "",
                ),
                actor=actor,
            )
            record = abandoned.last_abandonment
            if record is None:
                raise RuntimeError(f"The abandonment of repository {self.repository.name} saved no record.")
            log.info(
                "%s abandoned the merges %s of repository %s, with the release lease %s.",
                actor.account_name,
                sorted(record.entry_ids),
                self.repository.name,
                lease.lease_id if lease else None,
            )
            await self._notify_deleted_branches(record=record)
        if lease is not None:
            try:
                # A release awaits generator runs, which take the repository lock to fetch a commit they lack.
                await self._release(lease=lease)
            except Exception:
                # The run fails with the error of the release, so this line tells the user that nothing is left to abandon.
                log.error(
                    "The merges %s of repository %s are abandoned, but the release of their held regeneration failed; "
                    "a later delivery run of the repository releases it.",
                    sorted(record.entry_ids),
                    self.repository.name,
                )
                raise
        return record

    async def _notify_deleted_branches(self, *, record: AbandonmentRecord) -> None:
        flagged = {entry.source_git_branch for entry in record.entries if entry.delete_source_git_branch}
        for git_branch in sorted(flagged):
            try:
                await self.git.notify_branch_deleted(git_branch=git_branch)
            except Exception:
                # The queue is already dropped, so a worker that missed the message keeps a local branch and nothing else.
                log.warning(
                    "Failed to tell the workers that the branch %s of repository %s is gone.",
                    git_branch,
                    self.repository.name,
                    exc_info=True,
                )

    async def _release(self, *, lease: ReleaseLease) -> None:
        repository_id = self.repository.id

        async def renew() -> None:
            await self.state.renew_lease(repository_id=repository_id, lease_id=lease.lease_id)

        try:
            await self.releaser.release(repository_id=repository_id, held=lease.window, renew=renew)
        except Exception:
            # Nothing cleared the items, so the next lease takes them and its run releases every one.
            await self._expire(lease=lease)
            raise
        await self.state.clear_released(repository_id=repository_id, lease_id=lease.lease_id)
        log.info("Released the held regeneration of lease %s for repository %s.", lease.lease_id, self.repository.name)

    async def _expire(self, *, lease: ReleaseLease) -> None:
        try:
            await self.state.expire_lease(repository_id=self.repository.id, lease_id=lease.lease_id)
        except Exception:
            # The lease then ends at its own expiry, and a later run leases its items again.
            log.warning(
                "Failed to end the release lease %s of repository %s.",
                lease.lease_id,
                self.repository.name,
                exc_info=True,
            )
