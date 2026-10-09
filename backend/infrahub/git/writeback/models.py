from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_serializer, field_validator

from infrahub.core.constants import (
    FullRegenerationReason,
    RepositoryDeliveryFailureCause,
    RepositoryDeliveryStatus,
)
from infrahub.exceptions import DeliveryQueueChangedError, NothingPendingError
from infrahub.git.writeback.constants import RELEASE_LEASE_SECONDS, REMOVED_ENTRY_IDS_KEPT, STALE_AFTER_SECONDS
from infrahub.git.writeback.credentials import scrub_credentials

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping
    from datetime import datetime


class DeliveryStage(StrEnum):
    """The step of a delivery attempt that failed."""

    ENQUEUE = "enqueue"
    FETCH = "fetch"
    PUSH = "push"
    RECORD = "record"
    IMPORT = "import"
    REPLAY = "replay"
    RELEASE = "release"


class DeliveryOutcome(StrEnum):
    """What one delivery attempt did."""

    NOTHING_PENDING = "nothing-pending"
    DELIVERED = "delivered"
    OBSERVED = "observed"
    """The remote already held every entry, so nothing was pushed."""
    RELEASED = "released"
    """The queue was empty, so the attempt only released the held regeneration."""
    FAILED = "failed"
    UNREPLAYABLE = "unreplayable"
    DEFERRED = "deferred"
    """Another automatic retry of the repository was already due, and it delivers the queue."""


class PendingMerge(BaseModel):
    """A merge whose repository content waits for its push to the remote."""

    model_config = ConfigDict(frozen=True)

    entry_id: str
    source_branch: str
    """The Infrahub branch that merged, which can be deleted after the merge."""
    source_git_branch: str
    """The remote branch that holds the source commit."""
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    merged_at: AwareDatetime
    delete_source_git_branch: bool = False
    """Delete the remote source branch once the merge is delivered."""


class AbandonmentRecord(BaseModel):
    """The last abandonment of the pending pushes of a repository."""

    model_config = ConfigDict(frozen=True)

    format: Literal[1] = 1
    abandoned_at: AwareDatetime
    account_id: str
    account_name: str
    queue_version: int
    recorded_commit: str
    """The commit that the default branch kept."""
    import_owed_commit: str | None = None
    """An import that was still owed and was dropped with the queue."""
    entries: tuple[PendingMerge, ...] = ()

    @property
    def entry_ids(self) -> frozenset[str]:
        return frozenset(entry.entry_id for entry in self.entries)


class DeliveryQueue(BaseModel):
    """The merges of a repository that wait for their push to the remote, in merge order."""

    model_config = ConfigDict(frozen=True)

    format: Literal[1] = 1
    version: int = 0
    """Moves only when an entry joins or leaves the queue, so an abandonment can name the queue it saw."""
    entries: tuple[PendingMerge, ...] = ()
    removed_entry_ids: tuple[str, ...] = ()
    """The most recent ids that left the queue, which never join it again."""
    import_owed_commit: str | None = None
    """A recorded commit whose import has not succeeded yet."""

    def with_entry(self, *, entry: PendingMerge, last_abandonment: AbandonmentRecord | None) -> DeliveryQueue | None:
        """Return the queue with the entry appended, or None when its id is queued, removed or abandoned."""
        refused = {queued.entry_id for queued in self.entries} | set(self.removed_entry_ids)
        if last_abandonment is not None:
            refused |= last_abandonment.entry_ids
        if entry.entry_id in refused:
            return None
        return self.model_copy(update={"version": self.version + 1, "entries": (*self.entries, entry)})

    def without_entries(self, *, entry_ids: Collection[str]) -> DeliveryQueue:
        """Return the queue without these entries, keeping their ids as removed."""
        leaving = frozenset(entry_ids)
        removed = tuple(entry.entry_id for entry in self.entries if entry.entry_id in leaving)
        if not removed:
            return self
        return self.model_copy(
            update={
                "version": self.version + 1,
                "entries": tuple(entry for entry in self.entries if entry.entry_id not in leaving),
                "removed_entry_ids": (*self.removed_entry_ids, *removed)[-REMOVED_ENTRY_IDS_KEPT:],
            }
        )

    def with_branch_deletion_requested(self, *, git_branch: str) -> DeliveryQueue | None:
        """Flag every entry from this remote branch for deletion, or return None when no entry is from it."""
        if all(entry.source_git_branch != git_branch for entry in self.entries):
            return None
        return self.model_copy(
            update={
                "entries": tuple(
                    entry.model_copy(update={"delete_source_git_branch": True})
                    if entry.source_git_branch == git_branch
                    else entry
                    for entry in self.entries
                )
            }
        )


class DeliveryProgress(BaseModel):
    """When a delivery of the repository last moved."""

    model_config = ConfigDict(frozen=True)

    format: Literal[1] = 1
    last_progress_at: AwareDatetime | None = None
    attempt_started_at: AwareDatetime | None = None
    retry_due_at: AwareDatetime | None = None
    """When a waiting automatic retry is due."""


class HeldItem(BaseModel):
    """A held artifact or generator definition, at the sequence of its latest hold."""

    model_config = ConfigDict(frozen=True)

    id: str
    hold_seq: int

    @property
    def identifier(self) -> str:
        return self.id


class HeldPythonAttribute(BaseModel):
    """A held Python computed attribute, at the sequence of its latest hold."""

    model_config = ConfigDict(frozen=True)

    kind: str
    attribute: str
    hold_seq: int

    @property
    def identifier(self) -> str:
        return f"{self.kind}.{self.attribute}"


class HeldWiden(BaseModel):
    """A regeneration of the repository owed by its next release, of scope `all` or `terminals`."""

    model_config = ConfigDict(frozen=True)

    scope: Literal["all", "terminals"]
    """`all` covers every definition and Python attribute; `terminals` covers the artifact definitions only."""
    reason: FullRegenerationReason
    """Stored by its member name, so a new wording of the log sentence never breaks a stored value."""
    hold_seq: int

    @field_validator("reason", mode="before")
    @classmethod
    def _reason_from_name(cls, value: object) -> object:
        if isinstance(value, str) and value in FullRegenerationReason.__members__:
            return FullRegenerationReason[value]
        return value

    @field_serializer("reason")
    def _reason_name(self, reason: FullRegenerationReason) -> str:
        return reason.name


class ReleaseLease(BaseModel):
    """A release in progress, naming each item it releases at the sequence the item had when the lease was taken."""

    model_config = ConfigDict(frozen=True)

    lease_id: str
    expires_at: AwareDatetime
    artifact_definitions: tuple[HeldItem, ...] = ()
    generator_definitions: tuple[HeldItem, ...] = ()
    python_attributes: tuple[HeldPythonAttribute, ...] = ()
    widen: HeldWiden | None = None

    @classmethod
    def over(cls, *, lease_id: str, window: HeldRegeneration, expires_at: datetime) -> ReleaseLease:
        """Build the lease that names every item of the window."""
        return cls(
            lease_id=lease_id,
            expires_at=expires_at,
            artifact_definitions=window.artifact_definitions,
            generator_definitions=window.generator_definitions,
            python_attributes=window.python_attributes,
            widen=window.widen,
        )

    @property
    def window(self) -> HeldRegeneration:
        """The named items, in the shape that a release dispatches."""
        return HeldRegeneration(
            artifact_definitions=self.artifact_definitions,
            generator_definitions=self.generator_definitions,
            python_attributes=self.python_attributes,
            widen=self.widen,
        )

    @property
    def names_nothing(self) -> bool:
        return self.window.is_empty

    def is_live(self, *, now: datetime) -> bool:
        return now < self.expires_at


class HeldRegeneration(BaseModel):
    """Regeneration held back until the pending merges of the repository reach the remote."""

    model_config = ConfigDict(frozen=True)

    format: Literal[1] = 1
    next_hold_seq: int = 1
    artifact_definitions: tuple[HeldItem, ...] = ()
    generator_definitions: tuple[HeldItem, ...] = ()
    python_attributes: tuple[HeldPythonAttribute, ...] = ()
    widen: HeldWiden | None = None
    release_leases: tuple[ReleaseLease, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not (self.artifact_definitions or self.generator_definitions or self.python_attributes or self.widen)

    def with_hold(self, *, held: HeldRegeneration) -> tuple[HeldRegeneration, HoldReceipt]:
        """Hold the items of `held` under the next sequence, which also refreshes an item held already.

        The sequences that `held` carries are ignored.
        """
        hold_seq = self.next_hold_seq
        artifacts, previous_artifacts = _refreshed(
            current=self.artifact_definitions, requested=held.artifact_definitions, hold_seq=hold_seq
        )
        generators, previous_generators = _refreshed(
            current=self.generator_definitions, requested=held.generator_definitions, hold_seq=hold_seq
        )
        python_attributes, previous_python_attributes = _refreshed(
            current=self.python_attributes, requested=held.python_attributes, hold_seq=hold_seq
        )
        updated = self.model_copy(
            update={
                "next_hold_seq": hold_seq + 1,
                "artifact_definitions": artifacts,
                "generator_definitions": generators,
                "python_attributes": python_attributes,
                "widen": _merged_widen(current=self.widen, requested=held.widen, hold_seq=hold_seq),
            }
        )
        receipt = HoldReceipt(
            hold_seq=hold_seq,
            previous_seqs=previous_artifacts | previous_generators | previous_python_attributes,
        )
        return updated, receipt

    def lease_window(self, *, now: datetime, max_hold_seq: int | None) -> HeldRegeneration:
        """Return the held items that no live lease covers, each at its current sequence.

        Args:
            max_hold_seq: Leave out the items held after this sequence; None leaves out none.

        """
        live = [lease for lease in self.release_leases if lease.is_live(now=now)]
        widen = self.widen
        if widen is not None and (
            (max_hold_seq is not None and widen.hold_seq > max_hold_seq) or any(lease.widen == widen for lease in live)
        ):
            widen = None
        return HeldRegeneration(
            artifact_definitions=_uncovered(
                items=self.artifact_definitions,
                covered={item for lease in live for item in lease.artifact_definitions},
                max_hold_seq=max_hold_seq,
            ),
            generator_definitions=_uncovered(
                items=self.generator_definitions,
                covered={item for lease in live for item in lease.generator_definitions},
                max_hold_seq=max_hold_seq,
            ),
            python_attributes=_uncovered(
                items=self.python_attributes,
                covered={item for lease in live for item in lease.python_attributes},
                max_hold_seq=max_hold_seq,
            ),
            widen=widen,
        )

    def with_lease(self, *, lease: ReleaseLease, now: datetime) -> HeldRegeneration:
        """Add the lease, moving to it the items that it takes from expired leases, and drop the emptied ones."""
        return self.model_copy(
            update={"release_leases": (*_cleaned_expired_leases(held=self, now=now, taken=lease), lease)}
        )

    def without_window(self, *, lease_id: str, now: datetime) -> HeldRegeneration:
        """Remove each item that the lease names and that still has the named sequence, then the lease itself.

        An item held again after the lease was taken stays. Does nothing when the lease is gone, because a
        newer lease then owns its items.
        """
        lease = next((lease for lease in self.release_leases if lease.lease_id == lease_id), None)
        if lease is None:
            return self
        cleared = self.model_copy(
            update={
                "artifact_definitions": tuple(
                    item for item in self.artifact_definitions if item not in lease.artifact_definitions
                ),
                "generator_definitions": tuple(
                    item for item in self.generator_definitions if item not in lease.generator_definitions
                ),
                "python_attributes": tuple(
                    item for item in self.python_attributes if item not in lease.python_attributes
                ),
                "widen": None if self.widen == lease.widen else self.widen,
                "release_leases": tuple(other for other in self.release_leases if other.lease_id != lease_id),
            }
        )
        return cleared.model_copy(update={"release_leases": _cleaned_expired_leases(held=cleared, now=now, taken=None)})

    def with_lease_expiry(self, *, lease_id: str, expires_at: datetime) -> HeldRegeneration:
        """Move the expiry of the lease. Does nothing when the lease is gone."""
        return self.model_copy(
            update={
                "release_leases": tuple(
                    lease.model_copy(update={"expires_at": expires_at}) if lease.lease_id == lease_id else lease
                    for lease in self.release_leases
                )
            }
        )


class RevertedDelivery(BaseModel):
    """A delivered commit that a rewrite of the remote default branch discarded."""

    model_config = ConfigDict(frozen=True)

    format: Literal[1] = 1
    delivered_commit: str
    new_head: str
    detected_at: AwareDatetime


@dataclass(frozen=True)
class HoldReceipt:
    """The sequence of one hold, and the sequence that each refreshed item had before it."""

    hold_seq: int
    previous_seqs: Mapping[str, int]
    """By the identifier of each refreshed definition or Python attribute."""


@dataclass(frozen=True)
class WritebackIntent:
    """The whole delivery state of one repository, read in one snapshot.

    Each transition is pure, and a save writes only the attributes that it changes.
    """

    repository_id: str
    status: RepositoryDeliveryStatus
    cause: RepositoryDeliveryFailureCause | None
    error: str | None
    queue: DeliveryQueue
    held: HeldRegeneration
    progress: DeliveryProgress
    last_delivered_commit: str | None
    last_abandonment: AbandonmentRecord | None = None
    reverted: RevertedDelivery | None = None

    def with_entry(self, *, entry: PendingMerge, widen: bool, now: datetime) -> WritebackIntent | None:
        """Append the merge and set the status to pending, or return None when the queue refuses its id.

        Args:
            widen: Hold a regeneration of every definition of the repository under the next sequence too.

        """
        queue = self.queue.with_entry(entry=entry, last_abandonment=self.last_abandonment)
        if queue is None:
            return None
        held = self.held
        if widen:
            held, _ = held.with_hold(
                held=HeldRegeneration(
                    widen=HeldWiden(scope="all", reason=FullRegenerationReason.UNHELD_FOLLOW_UP, hold_seq=0)
                )
            )
        return replace(
            self,
            status=RepositoryDeliveryStatus.PENDING,
            queue=queue,
            held=held,
            progress=self.progress.model_copy(update={"last_progress_at": now}),
        )

    def with_attempt_started(self, *, now: datetime) -> WritebackIntent:
        """Stamp the start of an attempt, which sets the status to pending only while merges are queued."""
        return replace(
            self,
            status=RepositoryDeliveryStatus.PENDING if self.queue.entries else self.status,
            progress=self.progress.model_copy(
                update={"attempt_started_at": now, "last_progress_at": now, "retry_due_at": None}
            ),
        )

    def with_failure(
        self, *, failure: DeliveryFailure, final: bool, retry_due_at: datetime | None, now: datetime
    ) -> WritebackIntent:
        """Record the failure; a final one sets `action-required` and drops the retry, only while merges are queued.

        While merges are queued, a failure with no cause keeps the stored cause and error; otherwise both come from the
        failure, so the cause and the error always describe the same failure. The stored message never holds a
        credential, whoever built the failure.
        """
        action_required = final and bool(self.queue.entries)
        keeps_stored = failure.cause is None and bool(self.queue.entries)
        return replace(
            self,
            status=RepositoryDeliveryStatus.ACTION_REQUIRED if action_required else self.status,
            cause=self.cause if keeps_stored else failure.cause,
            error=self.error if keeps_stored else scrub_credentials(text=failure.message),
            progress=self.progress.model_copy(
                update={"last_progress_at": now, "retry_due_at": None if action_required else retry_due_at}
            ),
        )

    def with_import_owed(self, *, commit: str) -> WritebackIntent:
        """Owe the import of the commit, or change nothing when no merge is queued, as an owed import needs one."""
        if not self.queue.entries:
            return self
        return replace(self, queue=self.queue.model_copy(update={"import_owed_commit": commit}))

    def without_owed_import(self, *, commit: str, snapshot: WritebackIntent) -> WritebackIntent | None:
        """Clear the owed import, or return None when another commit is owed or a merge joined after the snapshot."""
        snapshot_entry_ids = {entry.entry_id for entry in snapshot.queue.entries}
        if self.queue.import_owed_commit != commit or any(
            entry.entry_id not in snapshot_entry_ids for entry in self.queue.entries
        ):
            return None
        return replace(self, queue=self.queue.model_copy(update={"import_owed_commit": None}))

    def with_branch_deletion_requested(self, *, git_branch: str) -> WritebackIntent | None:
        """Flag every pending merge from the remote branch, or return None when no pending merge comes from it."""
        queue = self.queue.with_branch_deletion_requested(git_branch=git_branch)
        if queue is None:
            return None
        return replace(self, queue=queue)

    def with_progress(self, *, now: datetime) -> WritebackIntent:
        return replace(self, progress=self.progress.model_copy(update={"last_progress_at": now}))

    def with_hold(self, *, held: HeldRegeneration) -> tuple[WritebackIntent, HoldReceipt] | None:
        """Hold the items under the next sequence, or return None when no merge is queued."""
        if not self.queue.entries:
            return None
        updated, receipt = self.held.with_hold(held=held)
        return replace(self, held=updated), receipt

    def with_delivery_settled(
        self, *, snapshot: WritebackIntent, delivered_commit: str | None, lease_id: str, now: datetime
    ) -> tuple[WritebackIntent, ReleaseLease | None]:
        """Remove the merges of the snapshot, and lease the uncovered held items up to the snapshot's sequence.

        The lease is None when no held item is left to lease.

        Raises:
            ValueError: The settle would leave an import owed with no merge queued, which no attempt would then run.

        """
        held, lease = _leased(held=self.held, lease_id=lease_id, now=now, max_hold_seq=snapshot.held.next_hold_seq - 1)
        settled = replace(
            self,
            queue=self.queue.without_entries(entry_ids=[entry.entry_id for entry in snapshot.queue.entries]),
            held=held,
            last_delivered_commit=self.last_delivered_commit if delivered_commit is None else delivered_commit,
        )
        if not settled.queue.entries and settled.queue.import_owed_commit is not None:
            raise ValueError(
                f"The settle of repository {self.repository_id} leaves the import of commit "
                f"{settled.queue.import_owed_commit} owed with no merge queued"
            )
        return settled._with_status_of_queue(), lease

    def abandoned(
        self, *, repository_name: str, queue_version: int, record: AbandonmentRecord, lease_id: str, now: datetime
    ) -> tuple[WritebackIntent, ReleaseLease | None]:
        """Drop every pending merge and the owed import with their record, and lease every uncovered held item.

        The record names the merges and the owed import that this transition drops. The lease is None when no
        held item is left to lease.

        Raises:
            DeliveryQueueChangedError: The queue is no longer at `queue_version`.
            NothingPendingError: The queue is empty.

        """
        if queue_version != self.queue.version:
            raise DeliveryQueueChangedError(repository_name=repository_name, queue_version=queue_version)
        if not self.queue.entries:
            raise NothingPendingError(repository_name=repository_name)
        held, lease = _leased(held=self.held, lease_id=lease_id, now=now, max_hold_seq=None)
        abandoned = replace(
            self,
            queue=self.queue.without_entries(entry_ids=[entry.entry_id for entry in self.queue.entries]).model_copy(
                update={"import_owed_commit": None}
            ),
            held=held,
            last_abandonment=record.model_copy(
                update={"entries": self.queue.entries, "import_owed_commit": self.queue.import_owed_commit}
            ),
        )
        return abandoned._with_status_of_queue(), lease

    def with_owed_release_leased(self, *, lease_id: str, now: datetime) -> tuple[WritebackIntent, ReleaseLease] | None:
        """Lease every held item that no live lease covers, or return None while merges are queued or none is left."""
        if self.queue.entries:
            return None
        held, lease = _leased(held=self.held, lease_id=lease_id, now=now, max_hold_seq=None)
        if lease is None:
            return None
        return replace(self, held=held), lease

    def with_lease_renewed(self, *, lease_id: str, now: datetime) -> WritebackIntent:
        return replace(
            self,
            held=self.held.with_lease_expiry(
                lease_id=lease_id, expires_at=now + timedelta(seconds=RELEASE_LEASE_SECONDS)
            ),
        )

    def with_lease_expired(self, *, lease_id: str, now: datetime) -> WritebackIntent:
        """End the lease now and keep its items held, so the next lease takes them."""
        return replace(self, held=self.held.with_lease_expiry(lease_id=lease_id, expires_at=now))

    def without_window(self, *, lease_id: str, now: datetime) -> WritebackIntent:
        """Clear the released items of the lease, and with no merge queued, the failure of an earlier release too."""
        if not any(lease.lease_id == lease_id for lease in self.held.release_leases):
            return self
        cleared = replace(self, held=self.held.without_window(lease_id=lease_id, now=now))
        if self.queue.entries:
            return cleared
        return replace(cleared, cause=None, error=None)

    def with_reverted(self, *, reverted: RevertedDelivery) -> WritebackIntent:
        return replace(self, reverted=reverted)

    def _with_status_of_queue(self) -> WritebackIntent:
        if self.queue.entries:
            return replace(self, status=RepositoryDeliveryStatus.PENDING)
        # Nothing is pending any more, so the last failure no longer asks the user for an action.
        return replace(self, status=RepositoryDeliveryStatus.NONE, cause=None, error=None)

    def has_work(self, *, now: datetime) -> bool:
        """Whether entries wait in the queue, or held items that no live lease covers."""
        return bool(self.queue.entries) or not self.held.lease_window(now=now, max_hold_seq=None).is_empty

    def is_stale(self, *, now: datetime, lock_free: bool, run_queued: bool) -> bool:
        """Whether the pending delivery lost its attempt, and nothing will start another one.

        Args:
            lock_free: No holder has the repository lock, so no attempt runs its Git work or its import.
            run_queued: The orchestrator holds a delivery run of the repository that waits to start.

        """
        if self.status != RepositoryDeliveryStatus.PENDING or not lock_free or run_queued:
            return False
        retry_due_at = self.progress.retry_due_at
        if retry_due_at is not None and retry_due_at > now:
            return False
        last_progress_at = self.progress.last_progress_at
        return last_progress_at is None or now - last_progress_at > timedelta(seconds=STALE_AFTER_SECONDS)


@dataclass(frozen=True)
class DeliveryFailure:
    """Why a delivery attempt failed."""

    cause: RepositoryDeliveryFailureCause | None
    """None when the failed step leaves the cause that the repository shows as it is."""
    retryable: bool
    message: str
    """With credentials removed."""


@dataclass(frozen=True)
class DeliveryAttemptResult:
    """What one delivery attempt did, and why it failed when it did."""

    outcome: DeliveryOutcome
    commit: str | None = None
    """The commit that the remote holds after the attempt, when the attempt delivered."""
    failure: DeliveryFailure | None = None


@dataclass(frozen=True)
class Actor:
    """The account that requested an abandonment."""

    account_id: str
    account_name: str


def _refreshed[ItemT: (HeldItem, HeldPythonAttribute)](
    *, current: tuple[ItemT, ...], requested: tuple[ItemT, ...], hold_seq: int
) -> tuple[tuple[ItemT, ...], dict[str, int]]:
    by_identifier = {item.identifier: item for item in current}
    previous = {
        item.identifier: by_identifier[item.identifier].hold_seq
        for item in requested
        if item.identifier in by_identifier
    }
    by_identifier.update({item.identifier: item.model_copy(update={"hold_seq": hold_seq}) for item in requested})
    return tuple(sorted(by_identifier.values(), key=lambda item: item.identifier)), previous


def _merged_widen(*, current: HeldWiden | None, requested: HeldWiden | None, hold_seq: int) -> HeldWiden | None:
    if requested is None:
        return current
    # The wider scope already covers the narrower one, so the marker keeps its scope and its reason.
    if current is not None and current.scope == "all" and requested.scope == "terminals":
        return current.model_copy(update={"hold_seq": hold_seq})
    return requested.model_copy(update={"hold_seq": hold_seq})


def _leased(
    *, held: HeldRegeneration, lease_id: str, now: datetime, max_hold_seq: int | None
) -> tuple[HeldRegeneration, ReleaseLease | None]:
    window = held.lease_window(now=now, max_hold_seq=max_hold_seq)
    if window.is_empty:
        return held, None
    lease = ReleaseLease.over(
        lease_id=lease_id, window=window, expires_at=now + timedelta(seconds=RELEASE_LEASE_SECONDS)
    )
    return held.with_lease(lease=lease, now=now), lease


def _uncovered[ItemT: (HeldItem, HeldPythonAttribute)](
    *, items: tuple[ItemT, ...], covered: Collection[ItemT], max_hold_seq: int | None
) -> tuple[ItemT, ...]:
    return tuple(
        item for item in items if item not in covered and (max_hold_seq is None or item.hold_seq <= max_hold_seq)
    )


def _still_named[ItemT: (HeldItem, HeldPythonAttribute)](
    *, named: tuple[ItemT, ...], held: tuple[ItemT, ...], taken: tuple[ItemT, ...]
) -> tuple[ItemT, ...]:
    taken_identifiers = {item.identifier for item in taken}
    return tuple(item for item in named if item in held and item.identifier not in taken_identifiers)


def _cleaned_expired_leases(
    *, held: HeldRegeneration, now: datetime, taken: ReleaseLease | None
) -> tuple[ReleaseLease, ...]:
    """Trim each expired lease to the items still held at the named sequence and not taken, and drop the empty ones."""
    leases: list[ReleaseLease] = []
    for lease in held.release_leases:
        if lease.is_live(now=now):
            leases.append(lease)
            continue
        trimmed = lease.model_copy(
            update={
                "artifact_definitions": _still_named(
                    named=lease.artifact_definitions,
                    held=held.artifact_definitions,
                    taken=taken.artifact_definitions if taken else (),
                ),
                "generator_definitions": _still_named(
                    named=lease.generator_definitions,
                    held=held.generator_definitions,
                    taken=taken.generator_definitions if taken else (),
                ),
                "python_attributes": _still_named(
                    named=lease.python_attributes,
                    held=held.python_attributes,
                    taken=taken.python_attributes if taken else (),
                ),
                "widen": lease.widen if lease.widen == held.widen and (taken is None or taken.widen is None) else None,
            }
        )
        if not trimmed.names_nothing:
            leases.append(trimmed)
    return tuple(leases)
