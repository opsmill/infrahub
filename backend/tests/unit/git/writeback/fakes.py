from __future__ import annotations

import itertools
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from infrahub.core.constants import InfrahubKind, RepositoryDeliveryStatus
from infrahub.exceptions import NodeNotFoundError
from infrahub.git.writeback.models import DeliveryProgress, DeliveryQueue, HeldRegeneration, WritebackIntent
from infrahub.git.writeback.ports import ReplayResult

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping, Sequence

    from infrahub.git.writeback.models import (
        AbandonmentRecord,
        Actor,
        DeliveryFailure,
        HoldReceipt,
        PendingMerge,
        ReleaseLease,
        RevertedDelivery,
    )
    from infrahub.git.writeback.ports import Clock


class FixedClock:
    """A clock that stays at its time until the test moves it."""

    def __init__(self, *, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, *, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


class InMemoryDeliveryState:
    """The delivery state of each repository in memory, changed by the same transitions as the persisted state.

    Every call is recorded in `calls` by its method name, in order. An error that a test appends to
    `failures[<method name>]` is raised by the next call of that method, before it reads or writes anything.
    """

    def __init__(self, *, clock: Clock, repository_names: Mapping[str, str], default_git_branch: str = "main") -> None:
        """Start every repository, given by its id and its name, with a delivery state that was never used.

        Args:
            default_git_branch: The remote branch that every repository delivers to.

        """
        self.clock = clock
        self.names = dict(repository_names)
        self.default_git_branch = default_git_branch
        self.intents: dict[str, WritebackIntent] = {
            repository_id: WritebackIntent(
                repository_id=repository_id,
                status=RepositoryDeliveryStatus.NONE,
                cause=None,
                error=None,
                queue=DeliveryQueue(),
                held=HeldRegeneration(),
                progress=DeliveryProgress(),
                last_delivered_commit=None,
            )
            for repository_id in repository_names
        }
        self.calls: list[str] = []
        self.failures: dict[str, list[BaseException]] = {}
        self._lease_numbers = itertools.count(start=1)

    async def read(self, *, repository_id: str) -> WritebackIntent:
        return self._enter(method="read", repository_id=repository_id)

    async def pending_repository_ids(self) -> frozenset[str]:
        self._record_call(method="pending_repository_ids")
        return frozenset(
            repository_id
            for repository_id, intent in self.intents.items()
            if intent.status != RepositoryDeliveryStatus.NONE
        )

    async def enqueue(self, *, repository_id: str, entry: PendingMerge, widen: bool) -> WritebackIntent:
        intent = self._enter(method="enqueue", repository_id=repository_id)
        appended = intent.with_entry(
            entry=entry, widen=widen, destination_git_branch=self.default_git_branch, now=self.clock()
        )
        if appended is None:
            return intent
        return self._save(intent=appended)

    async def start_attempt(self, *, repository_id: str) -> WritebackIntent:
        intent = self._enter(method="start_attempt", repository_id=repository_id)
        return self._save(intent=intent.with_attempt_started(now=self.clock()))

    async def record_failure(
        self, *, repository_id: str, failure: DeliveryFailure, final: bool, retry_due_at: datetime | None
    ) -> None:
        intent = self._enter(method="record_failure", repository_id=repository_id)
        self._save(
            intent=intent.with_failure(failure=failure, final=final, retry_due_at=retry_due_at, now=self.clock())
        )

    async def owe_import(self, *, repository_id: str, commit: str) -> None:
        intent = self._enter(method="owe_import", repository_id=repository_id)
        self._save(intent=intent.with_import_owed(commit=commit))

    async def settle_import(self, *, repository_id: str, commit: str, snapshot: WritebackIntent) -> bool:
        intent = self._enter(method="settle_import", repository_id=repository_id)
        settled = intent.without_owed_import(commit=commit, snapshot=snapshot)
        if settled is None:
            return False
        self._save(intent=settled)
        return True

    async def request_branch_deletion(self, *, repository_id: str, git_branch: str) -> bool:
        intent = self._enter(method="request_branch_deletion", repository_id=repository_id)
        flagged = intent.with_branch_deletion_requested(git_branch=git_branch)
        if flagged is None:
            return False
        self._save(intent=flagged)
        return True

    async def progress(self, *, repository_id: str) -> None:
        intent = self._enter(method="progress", repository_id=repository_id)
        self._save(intent=intent.with_progress(now=self.clock()))

    async def hold(self, *, repository_id: str, held: HeldRegeneration) -> HoldReceipt | None:
        intent = self._enter(method="hold", repository_id=repository_id)
        holding = intent.with_hold(held=held)
        if holding is None:
            return None
        updated, receipt = holding
        self._save(intent=updated)
        return receipt

    async def settle_delivery(
        self, *, repository_id: str, snapshot: WritebackIntent, delivered_commit: str | None
    ) -> ReleaseLease | None:
        intent = self._enter(method="settle_delivery", repository_id=repository_id)
        settled, lease = intent.with_delivery_settled(
            snapshot=snapshot, delivered_commit=delivered_commit, lease_id=self._next_lease_id(), now=self.clock()
        )
        self._save(intent=settled)
        return lease

    async def abandon(
        self, *, repository_id: str, queue_version: int, record: AbandonmentRecord, actor: Actor
    ) -> tuple[WritebackIntent, ReleaseLease | None]:
        intent = self._enter(method="abandon", repository_id=repository_id)
        abandoned, lease = intent.abandoned(
            repository_name=self.names[repository_id],
            queue_version=queue_version,
            actor=actor,
            record=record,
            lease_id=self._next_lease_id(),
            now=self.clock(),
        )
        return self._save(intent=abandoned), lease

    async def lease_owed_release(self, *, repository_id: str) -> ReleaseLease | None:
        intent = self._enter(method="lease_owed_release", repository_id=repository_id)
        leasing = intent.with_owed_release_leased(lease_id=self._next_lease_id(), now=self.clock())
        if leasing is None:
            return None
        updated, lease = leasing
        self._save(intent=updated)
        return lease

    async def renew_lease(self, *, repository_id: str, lease_id: str) -> None:
        intent = self._enter(method="renew_lease", repository_id=repository_id)
        self._save(intent=intent.with_lease_renewed(lease_id=lease_id, now=self.clock()))

    async def expire_lease(self, *, repository_id: str, lease_id: str) -> None:
        intent = self._enter(method="expire_lease", repository_id=repository_id)
        self._save(intent=intent.with_lease_expired(lease_id=lease_id, now=self.clock()))

    async def clear_released(self, *, repository_id: str, lease_id: str) -> None:
        intent = self._enter(method="clear_released", repository_id=repository_id)
        self._save(intent=intent.without_window(lease_id=lease_id, now=self.clock()))

    async def touch(self, *, repository_id: str) -> None:
        intent = self._enter(method="touch", repository_id=repository_id)
        self._save(intent=intent.with_progress(now=self.clock()))

    async def record_reverted(self, *, repository_id: str, reverted: RevertedDelivery) -> None:
        intent = self._enter(method="record_reverted", repository_id=repository_id)
        self._save(intent=intent.with_reverted(reverted=reverted))

    def _enter(self, *, method: str, repository_id: str) -> WritebackIntent:
        self._record_call(method=method)
        intent = self.intents.get(repository_id)
        if intent is None:
            raise NodeNotFoundError(node_type=InfrahubKind.REPOSITORY, identifier=repository_id)
        return intent

    def _record_call(self, *, method: str) -> None:
        self.calls.append(method)
        queued = self.failures.get(method)
        if queued:
            raise queued.pop(0)

    def _save(self, *, intent: WritebackIntent) -> WritebackIntent:
        self.intents[intent.repository_id] = intent
        return intent

    def _next_lease_id(self) -> str:
        return f"lease-{next(self._lease_numbers)}"


class InMemoryDeliveryGit:
    """A clone, its destination worktree and the remote branches as last fetched, in memory.

    A commit is present in the clone when it is a key of `parents`. A merge makes the commit
    `<head>+<merged commit>`, so a test can name the head that a replay gives. Every call is recorded in
    `calls` by its method name, in order. An error that a test appends to `failures[<method name>]` is
    raised by the next call of that method, before it changes anything. `reset` never raises, as the port
    says, so it ignores `failures`.
    """

    def __init__(self, *, destination_git_branch: str, head: str) -> None:
        """Start with the worktree at `head`, which is also the only commit in the clone."""
        self.destination_git_branch = destination_git_branch
        self.head = head
        self.parents: dict[str, tuple[str, ...]] = {head: ()}
        self.remote_heads: dict[str, str] = {}
        self.conflicting_commits: set[str] = set()
        self.pushed: list[str] = []
        self.recorded: list[str] = []
        self.imported: list[str] = []
        self.broadcasts: list[str] = []
        self.deleted_branches: list[str] = []
        self.notified_branches: list[str] = []
        self.calls: list[str] = []
        self.failures: dict[str, list[BaseException]] = {}

    def add_commit(self, *, commit: str, parents: Sequence[str]) -> None:
        self.parents[commit] = tuple(parents)

    async def fetch(self) -> None:
        self._record_call(method="fetch")

    def remote_head(self, *, git_branch: str) -> str | None:
        self._record_call(method="remote_head")
        return self.remote_heads.get(git_branch)

    def is_ancestor(self, *, ancestor: str, descendant: str) -> bool:
        self._record_call(method="is_ancestor")
        if ancestor not in self.parents or descendant not in self.parents:
            return False
        pending = [descendant]
        while pending:
            commit = pending.pop()
            if commit == ancestor:
                return True
            pending.extend(self.parents[commit])
        return False

    def replay(self, *, base: str, commits: Sequence[str]) -> ReplayResult:
        self._record_call(method="replay")
        self.head = base
        for commit in commits:
            if commit in self.conflicting_commits:
                self.head = base
                return ReplayResult(head=base, conflicting_commit=commit)
            merged = f"{self.head}+{commit}"
            self.add_commit(commit=merged, parents=(self.head, commit))
            self.head = merged
        return ReplayResult(head=self.head)

    async def push(self) -> None:
        self._record_call(method="push")
        self.pushed.append(self.head)
        self.remote_heads[self.destination_git_branch] = self.head

    def reset(self, *, commit: str) -> None:
        self.calls.append("reset")
        self.head = commit

    async def record(self, *, commit: str) -> None:
        self._record_call(method="record")
        self.recorded.append(commit)

    async def import_at(self, *, commit: str) -> None:
        self._record_call(method="import_at")
        self.imported.append(commit)

    async def broadcast(self, *, commit: str) -> None:
        self._record_call(method="broadcast")
        self.broadcasts.append(commit)

    async def delete_remote_branch(self, *, git_branch: str) -> None:
        self._record_call(method="delete_remote_branch")
        self.remote_heads.pop(git_branch, None)
        self.deleted_branches.append(git_branch)
        self.notified_branches.append(git_branch)

    async def notify_branch_deleted(self, *, git_branch: str) -> None:
        self._record_call(method="notify_branch_deleted")
        self.notified_branches.append(git_branch)

    def _record_call(self, *, method: str) -> None:
        self.calls.append(method)
        queued = self.failures.get(method)
        if queued:
            raise queued.pop(0)


@dataclass(frozen=True)
class Release:
    repository_id: str
    held: HeldRegeneration


class RecordingRegenerationReleaser:
    """Records each release of held regeneration, in order.

    An error that a test appends to `failures` is raised by the next release, before it renews the lease or
    records anything. A release that succeeds renews the lease once.
    """

    def __init__(self) -> None:
        self.releases: list[Release] = []
        self.failures: list[BaseException] = []

    async def release(
        self, *, repository_id: str, held: HeldRegeneration, renew: Callable[[], Awaitable[None]]
    ) -> None:
        if self.failures:
            raise self.failures.pop(0)
        await renew()
        self.releases.append(Release(repository_id=repository_id, held=held))
