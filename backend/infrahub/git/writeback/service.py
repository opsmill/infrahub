from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, NoReturn

from infrahub.core.constants import RepositoryDeliveryFailureCause
from infrahub.exceptions import DeliveryStateUnavailableError, Error
from infrahub.git.writeback.classifier import classify_delivery_failure
from infrahub.git.writeback.models import DeliveryAttemptResult, DeliveryFailure, DeliveryOutcome, DeliveryStage
from infrahub.log import get_run_logger

if TYPE_CHECKING:
    from collections.abc import Iterator

    from infrahub.git.writeback.models import PendingMerge, ReleaseLease, WritebackIntent
    from infrahub.git.writeback.ports import (
        Clock,
        DeliveryGitPort,
        DeliveryStatePort,
        RegenerationReleasePort,
        RepositoryRef,
    )
    from infrahub.lock import InfrahubLockRegistry

log = get_run_logger()

REPOSITORY_LOCK_NAMESPACE = "repository"


class RetryableDeliveryError(Error):
    """A delivery attempt failed in a way that a later attempt can fix."""

    def __init__(self, failure: DeliveryFailure) -> None:
        self.failure = failure
        self.message = failure.message
        super().__init__(self.message)


class _StepFailedError(Exception):
    def __init__(self, *, stage: DeliveryStage, error: Exception) -> None:
        super().__init__(str(error))
        self.stage = stage
        self.error = error


class _AttemptStoppedError(Exception):
    """The attempt ends early with this result."""

    def __init__(self, *, result: DeliveryAttemptResult) -> None:
        super().__init__(result.outcome)
        self.result = result


@contextmanager
def _step(stage: DeliveryStage) -> Iterator[None]:
    try:
        yield
    except Exception as exc:
        raise _StepFailedError(stage=stage, error=exc) from exc


class RepositoryWritebackService:
    """Push the queued merges of one repository to its remote, then release the regeneration held for them."""

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

    async def deliver(self, *, final_attempt: bool, manual: bool, entry: PendingMerge | None) -> DeliveryAttemptResult:
        """Run one delivery attempt and return its result; a final failure of a step is also recorded on the repository.

        Args:
            final_attempt: No automatic retry follows, so a failure that a retry could fix is final.
            manual: A user asked for this attempt.
            entry: A merge to queue before the attempt, because the branch merge could not queue it.

        Raises:
            RetryableDeliveryError: A step failed in a way that a later attempt can fix, and the attempt is not the
                final one, or the delivery state was not available.

        """
        log.info(
            "Delivery attempt of repository %s starts (final attempt: %s, manual: %s).",
            self.repository.name,
            final_attempt,
            manual,
        )
        try:
            if entry is not None:
                await self._enqueue(entry=entry, final_attempt=final_attempt)
            return await self._deliver_queue(final_attempt=final_attempt)
        except _AttemptStoppedError as stopped:
            return stopped.result
        except DeliveryStateUnavailableError as exc:
            raise RetryableDeliveryError(
                failure=DeliveryFailure(cause=None, retryable=True, message=exc.message)
            ) from exc

    async def _enqueue(self, *, entry: PendingMerge, final_attempt: bool) -> None:
        try:
            queued = await self.state.enqueue(repository_id=self.repository.id, entry=entry, widen=True)
        except Exception as exc:
            failure = classify_delivery_failure(error=exc, stage=DeliveryStage.ENQUEUE)
            if not final_attempt:
                log.warning(
                    "The merge %s of branch %s was not queued for repository %s; the next attempt queues it.",
                    entry.entry_id,
                    entry.source_branch,
                    self.repository.name,
                    exc_info=True,
                )
                raise RetryableDeliveryError(failure=failure) from exc
            # The entry is in no queue, so this line is the only trace of the content that the remote lacks.
            log.exception(
                "The merge of branch %s at commit %s was not queued for repository %s after the last attempt; "
                "deliver it by hand.",
                entry.source_branch,
                entry.source_commit,
                self.repository.name,
            )
            raise _AttemptStoppedError(
                result=DeliveryAttemptResult(outcome=DeliveryOutcome.FAILED, failure=failure)
            ) from exc
        if any(queued_entry.entry_id == entry.entry_id for queued_entry in queued.queue.entries):
            log.info(
                "The queue of repository %s holds the merge %s of branch %s.",
                self.repository.name,
                entry.entry_id,
                entry.source_branch,
            )
        else:
            log.info(
                "Did not queue the merge %s for repository %s, because it left the queue.",
                entry.entry_id,
                self.repository.name,
            )

    async def _deliver_queue(self, *, final_attempt: bool) -> DeliveryAttemptResult:
        async with self.lock_registry.get(name=self.repository.name, namespace=REPOSITORY_LOCK_NAMESPACE):
            snapshot = await self.state.start_attempt(repository_id=self.repository.id)
            if not snapshot.has_work(now=self.clock()):
                log.info("Repository %s has no merge to deliver and no regeneration to release.", self.repository.name)
                return DeliveryAttemptResult(outcome=DeliveryOutcome.NOTHING_PENDING)
            if snapshot.queue.entries:
                result, lease = await self._deliver_entries(snapshot=snapshot, final_attempt=final_attempt)
            else:
                lease = await self.state.lease_owed_release(repository_id=self.repository.id)
                if lease is None:
                    log.info("A live release of repository %s covers every held regeneration.", self.repository.name)
                    return DeliveryAttemptResult(outcome=DeliveryOutcome.NOTHING_PENDING)
                result = DeliveryAttemptResult(outcome=DeliveryOutcome.RELEASED)
        if lease is None:
            return result
        # A release awaits generator runs, which take the repository lock to fetch a commit they lack.
        return await self._release(lease=lease, result=result, final_attempt=final_attempt)

    async def _deliver_entries(
        self, *, snapshot: WritebackIntent, final_attempt: bool
    ) -> tuple[DeliveryAttemptResult, ReleaseLease | None]:
        entry_ids = [entry.entry_id for entry in snapshot.queue.entries]
        log.info("Delivery attempt of repository %s works on the merges %s.", self.repository.name, entry_ids)

        head, recorded = await self._fetch(final_attempt=final_attempt)
        replayed = await self._check(snapshot=snapshot, head=head, recorded=recorded, final_attempt=final_attempt)
        # With no recorded commit, the remote head is the state of the worktree before the attempt.
        pre_attempt = recorded if recorded is not None else head
        commit = await self._replay(head=head, replayed=replayed, pre_attempt=pre_attempt, final_attempt=final_attempt)
        if replayed:
            await self._push(commit=commit, replayed=replayed, pre_attempt=pre_attempt, final_attempt=final_attempt)

        import_owed = head != recorded or snapshot.queue.import_owed_commit is not None
        if import_owed:
            # A crash before the record then leaves an import that the next attempt runs.
            await self.state.owe_import(repository_id=self.repository.id, commit=commit)
            log.info("An import of %s is owed for repository %s.", commit, self.repository.name)
        await self._record(commit=commit, pre_attempt=pre_attempt, final_attempt=final_attempt)
        if import_owed:
            await self._import(snapshot=snapshot, commit=commit, final_attempt=final_attempt)

        await self._broadcast(commit=commit)
        await self._delete_source_branches(snapshot=snapshot)

        lease = await self.state.settle_delivery(
            repository_id=self.repository.id, snapshot=snapshot, delivered_commit=commit if replayed else None
        )
        log.info(
            "Removed the merges %s from the queue of repository %s, with the release lease %s.",
            entry_ids,
            self.repository.name,
            lease.lease_id if lease else None,
        )
        outcome = DeliveryOutcome.DELIVERED if replayed else DeliveryOutcome.OBSERVED
        return DeliveryAttemptResult(outcome=outcome, commit=commit), lease

    async def _fetch(self, *, final_attempt: bool) -> tuple[str, str | None]:
        """Return the remote head of the destination and the commit that Infrahub records."""
        destination = self.repository.destination_git_branch
        try:
            with _step(DeliveryStage.FETCH):
                await self.git.fetch()
                head = self.git.remote_head(git_branch=destination)
            # Infrahub holds this commit, not the remote, so a failed read is retried as a failed record is.
            with _step(DeliveryStage.RECORD):
                recorded = await self.git.recorded_commit()
        except _StepFailedError as failed:
            await self._fail(failed=failed, final_attempt=final_attempt)
        await self.state.progress(repository_id=self.repository.id)
        log.info(
            "The remote branch %s of repository %s is at %s, and Infrahub records %s.",
            destination,
            self.repository.name,
            head,
            recorded,
        )
        if head is None:
            await self._refuse(
                cause=RepositoryDeliveryFailureCause.DESTINATION_REWRITTEN,
                message=(
                    f"The remote of repository {self.repository.name} has no branch {destination}, "
                    "so nothing was pushed."
                ),
            )
        return head, recorded

    async def _check(
        self, *, snapshot: WritebackIntent, head: str, recorded: str | None, final_attempt: bool
    ) -> tuple[PendingMerge, ...]:
        """Return the merges that the remote head lacks, after a check that a replay restores no discarded commit.

        A worker can still hold commits that the remote discarded, and a replay of them would push them again.
        """
        try:
            with _step(DeliveryStage.REPLAY):
                rewritten = recorded is not None and not self.git.is_ancestor(ancestor=recorded, descendant=head)
                replayed = tuple(
                    entry
                    for entry in snapshot.queue.entries
                    if not self.git.is_ancestor(ancestor=entry.source_commit, descendant=head)
                )
                discarded = self._discarded_source(entries=replayed)
        except _StepFailedError as failed:
            await self._fail(failed=failed, final_attempt=final_attempt)
        if rewritten:
            await self._refuse(
                cause=RepositoryDeliveryFailureCause.DESTINATION_REWRITTEN,
                message=(
                    f"The remote branch {self.repository.destination_git_branch} of repository {self.repository.name} "
                    f"is at {head}, which does not contain the commit {recorded} that Infrahub records, "
                    "so nothing was pushed."
                ),
            )
        if discarded is not None:
            await self._refuse(cause=RepositoryDeliveryFailureCause.SOURCE_DISCARDED, message=discarded)
        observed_ids = [entry.entry_id for entry in snapshot.queue.entries if entry not in replayed]
        if observed_ids:
            log.info("The remote of repository %s already holds the merges %s.", self.repository.name, observed_ids)
        return replayed

    def _discarded_source(self, *, entries: tuple[PendingMerge, ...]) -> str | None:
        """Return why the remote source branch of a merge no longer holds its commit, if one does not."""
        for entry in entries:
            branch_head = self.git.remote_head(git_branch=entry.source_git_branch)
            if branch_head is None:
                return (
                    f"The remote of repository {self.repository.name} has no branch {entry.source_git_branch}, "
                    f"which held the commit {entry.source_commit} of the merge {entry.entry_id} of branch "
                    f"{entry.source_branch}, so nothing was pushed."
                )
            if not self.git.is_ancestor(ancestor=entry.source_commit, descendant=branch_head):
                return (
                    f"The remote branch {entry.source_git_branch} of repository {self.repository.name} is at "
                    f"{branch_head}, which does not contain the commit {entry.source_commit} of the merge "
                    f"{entry.entry_id} of branch {entry.source_branch}, so nothing was pushed."
                )
        return None

    async def _replay(
        self, *, head: str, replayed: tuple[PendingMerge, ...], pre_attempt: str, final_attempt: bool
    ) -> str:
        """Return the worktree head after the merges are replayed on the remote head, or the remote head with no merge."""
        try:
            with _step(DeliveryStage.REPLAY):
                replay = self.git.replay(base=head, commits=[entry.source_commit for entry in replayed])
        except _StepFailedError as failed:
            self.git.reset(commit=pre_attempt)
            await self._fail(failed=failed, final_attempt=final_attempt)
        if replay.conflicting_commit is not None:
            self.git.reset(commit=pre_attempt)
            conflicting = next(entry for entry in replayed if entry.source_commit == replay.conflicting_commit)
            await self._refuse(
                cause=RepositoryDeliveryFailureCause.REPLAY_CONFLICT,
                message=(
                    f"The merge {conflicting.entry_id} of branch {conflicting.source_branch} at commit "
                    f"{conflicting.source_commit} conflicts with the remote branch "
                    f"{self.repository.destination_git_branch} of repository {self.repository.name} at {head}, "
                    "so nothing was pushed."
                ),
            )
        return replay.head

    async def _push(
        self, *, commit: str, replayed: tuple[PendingMerge, ...], pre_attempt: str, final_attempt: bool
    ) -> None:
        try:
            with _step(DeliveryStage.PUSH):
                await self.git.push()
        except _StepFailedError as failed:
            self.git.reset(commit=pre_attempt)
            await self._fail(failed=failed, final_attempt=final_attempt)
        await self.state.progress(repository_id=self.repository.id)
        log.info(
            "Pushed %s to the remote branch %s of repository %s with the merges %s.",
            commit,
            self.repository.destination_git_branch,
            self.repository.name,
            [entry.entry_id for entry in replayed],
        )

    async def _record(self, *, commit: str, pre_attempt: str, final_attempt: bool) -> None:
        try:
            with _step(DeliveryStage.RECORD):
                await self.git.record(commit=commit)
        except _StepFailedError as failed:
            # The remote holds the commit, so the next attempt observes the delivery and records it.
            self.git.reset(commit=pre_attempt)
            await self._fail(failed=failed, final_attempt=final_attempt, commit=commit)
        await self.state.progress(repository_id=self.repository.id)
        log.info("Recorded %s for repository %s.", commit, self.repository.name)

    async def _import(self, *, snapshot: WritebackIntent, commit: str, final_attempt: bool) -> None:
        await self.state.progress(repository_id=self.repository.id)
        try:
            with _step(DeliveryStage.IMPORT):
                await self.git.import_at(commit=commit)
        except _StepFailedError as failed:
            # The import stays owed, and the queued merges and the held regeneration wait for it.
            await self._fail(failed=failed, final_attempt=final_attempt, commit=commit)
        await self.state.progress(repository_id=self.repository.id)
        if await self.state.settle_import(repository_id=self.repository.id, commit=commit, snapshot=snapshot):
            log.info("Imported %s for repository %s.", commit, self.repository.name)
        else:
            # The import can drop the objects of a merge that joined the queue since, so its delivery imports again.
            log.info(
                "Imported %s for repository %s, and the import stays owed because a merge joined the queue.",
                commit,
                self.repository.name,
            )

    async def _broadcast(self, *, commit: str) -> None:
        try:
            await self.git.broadcast(commit=commit)
        except Exception:
            # A worker that missed the message fetches the commit when it needs it.
            log.warning(
                "Failed to ask the workers to fetch %s for repository %s.", commit, self.repository.name, exc_info=True
            )

    async def _delete_source_branches(self, *, snapshot: WritebackIntent) -> None:
        flagged = {entry.source_git_branch for entry in snapshot.queue.entries if entry.delete_source_git_branch}
        if not flagged:
            return
        snapshot_entry_ids = {entry.entry_id for entry in snapshot.queue.entries}
        current = await self.state.read(repository_id=self.repository.id)
        still_named = {
            entry.source_git_branch for entry in current.queue.entries if entry.entry_id not in snapshot_entry_ids
        }
        for git_branch in sorted(flagged):
            if git_branch in still_named:
                log.info(
                    "Kept the remote branch %s of repository %s, because a queued merge comes from it.",
                    git_branch,
                    self.repository.name,
                )
                continue
            try:
                await self.git.delete_remote_branch(git_branch=git_branch)
            except Exception:
                # The delivery succeeded, so a deletion that fails keeps the branch and nothing else.
                log.warning(
                    "Failed to delete the remote branch %s of repository %s.",
                    git_branch,
                    self.repository.name,
                    exc_info=True,
                )
                continue
            log.info("Deleted the remote branch %s of repository %s.", git_branch, self.repository.name)

    async def _release(
        self, *, lease: ReleaseLease, result: DeliveryAttemptResult, final_attempt: bool
    ) -> DeliveryAttemptResult:
        repository_id = self.repository.id

        async def renew() -> None:
            await self.state.renew_lease(repository_id=repository_id, lease_id=lease.lease_id)

        try:
            with _step(DeliveryStage.RELEASE):
                await self.releaser.release(repository_id=repository_id, held=lease.window, renew=renew)
        except _StepFailedError as failed:
            # Nothing cleared the items, so the next lease takes them and the next run releases every one.
            await self._expire(lease=lease)
            await self._fail(failed=failed, final_attempt=final_attempt, commit=result.commit)
        await self.state.clear_released(repository_id=repository_id, lease_id=lease.lease_id)
        log.info("Released the held regeneration of lease %s for repository %s.", lease.lease_id, self.repository.name)
        return result

    async def _expire(self, *, lease: ReleaseLease) -> None:
        try:
            await self.state.expire_lease(repository_id=self.repository.id, lease_id=lease.lease_id)
        except Exception:
            # The lease then ends at its own expiry, and a later attempt leases its items again.
            log.warning(
                "Failed to end the release lease %s of repository %s.",
                lease.lease_id,
                self.repository.name,
                exc_info=True,
            )

    async def _fail(self, *, failed: _StepFailedError, final_attempt: bool, commit: str | None = None) -> NoReturn:
        """Record the failure of the step, then stop the attempt, or raise to retry it when a retry can fix it.

        Raises:
            RetryableDeliveryError: A retry can fix the failure, and the attempt is not the final one.
            _AttemptStoppedError: Otherwise, with the failed result.

        """
        failure = classify_delivery_failure(error=failed.error, stage=failed.stage)
        final = final_attempt or not failure.retryable
        # The log comes first, so the failure stays visible when the record of it fails too.
        if final:
            log.error(
                "The %s step of the delivery to repository %s failed: %s",
                failed.stage,
                self.repository.name,
                failure.message,
                exc_info=failed.error,
            )
        else:
            log.warning(
                "The %s step of the delivery to repository %s failed, and a later attempt retries it: %s",
                failed.stage,
                self.repository.name,
                failure.message,
            )
        # The merges of a failed release are on the remote already, so no user has to act on it.
        await self.state.record_failure(
            repository_id=self.repository.id,
            failure=failure,
            final=final and failed.stage != DeliveryStage.RELEASE,
            retry_due_at=None,
        )
        if not final:
            raise RetryableDeliveryError(failure=failure) from failed.error
        raise _AttemptStoppedError(
            result=DeliveryAttemptResult(outcome=DeliveryOutcome.FAILED, commit=commit, failure=failure)
        ) from failed.error

    async def _refuse(self, *, cause: RepositoryDeliveryFailureCause, message: str) -> NoReturn:
        """Record that the queue cannot be replayed without a user's action, and stop the attempt with nothing pushed.

        Raises:
            _AttemptStoppedError: Always, with the unreplayable result.

        """
        failure = DeliveryFailure(cause=cause, retryable=False, message=message)
        log.error("The delivery to repository %s was refused: %s", self.repository.name, message)
        await self.state.record_failure(
            repository_id=self.repository.id, failure=failure, final=True, retry_due_at=None
        )
        raise _AttemptStoppedError(result=DeliveryAttemptResult(outcome=DeliveryOutcome.UNREPLAYABLE, failure=failure))
