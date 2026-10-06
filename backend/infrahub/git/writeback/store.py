from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from infrahub.core.constants import (
    SYSTEM_USER_ID,
    InfrahubKind,
    RepositoryDeliveryFailureCause,
    RepositoryDeliveryStatus,
)
from infrahub.core.manager import NodeManager
from infrahub.core.query.node import NodeGetListQuery
from infrahub.exceptions import DeliveryStateUnavailableError
from infrahub.git.writeback.constants import STATE_LOCK_ACQUIRE_SECONDS, STATE_LOCK_TTL_SECONDS
from infrahub.git.writeback.models import (
    AbandonmentRecord,
    DeliveryProgress,
    DeliveryQueue,
    HeldRegeneration,
    RevertedDelivery,
    WritebackIntent,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable
    from datetime import datetime

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase
    from infrahub.git.writeback.models import (
        Actor,
        DeliveryFailure,
        HoldReceipt,
        PendingMerge,
        ReleaseLease,
    )
    from infrahub.git.writeback.ports import Clock
    from infrahub.lock import InfrahubLockRegistry

STATE_LOCK_NAMESPACE = "repository-delivery"

STATUS = "delivery_status"
FAILURE_CAUSE = "delivery_failure_cause"
ERROR = "delivery_error"
QUEUE = "delivery_queue"
HELD_REGENERATION = "delivery_held_regeneration"
LAST_ABANDONMENT = "delivery_last_abandonment"
LAST_DELIVERED_COMMIT = "delivery_last_delivered_commit"
REVERTED = "delivery_reverted"
PROGRESS = "delivery_progress"

PENDING_STATUSES: list[str] = [RepositoryDeliveryStatus.PENDING.value, RepositoryDeliveryStatus.ACTION_REQUIRED.value]


@dataclass(frozen=True)
class _LockedState:
    """The state that a transition starts from, read under the delivery-state lock."""

    intent: WritebackIntent
    repository_name: str
    now: datetime


class WritebackIntentStore:
    """The only read and write path of the delivery state of the repositories, always on the default branch.

    Each transition is one read and at most one save under the delivery-state lock of the repository, and
    a transition that changes nothing saves nothing. A node save emits no node mutation event.
    """

    def __init__(
        self, db: InfrahubDatabase, lock_registry: InfrahubLockRegistry, default_branch: Branch, clock: Clock
    ) -> None:
        self.db = db
        self.lock_registry = lock_registry
        self.default_branch = default_branch
        self.clock = clock

    async def read(self, *, repository_id: str) -> WritebackIntent:
        node = await self._get_repository(db=self.db, repository_id=repository_id)
        return self._intent_of(node=node)

    async def pending_repository_ids(self) -> frozenset[str]:
        schema = self.db.schema.get_node_schema(
            name=InfrahubKind.REPOSITORY, branch=self.default_branch, duplicate=False
        )
        query = await NodeGetListQuery.init(
            db=self.db, schema=schema, branch=self.default_branch, filters={f"{STATUS}__values": PENDING_STATUSES}
        )
        await query.execute(db=self.db)
        return frozenset(query.get_node_ids())

    async def references_source_branch(self, *, repository_id: str, git_branch: str) -> bool:
        intent = await self.read(repository_id=repository_id)
        return any(entry.source_git_branch == git_branch for entry in intent.queue.entries)

    async def enqueue(self, *, repository_id: str, entry: PendingMerge, widen: bool) -> WritebackIntent:
        def transition(state: _LockedState) -> tuple[WritebackIntent, WritebackIntent]:
            appended = state.intent.with_entry(entry=entry, widen=widen, now=state.now)
            if appended is None:
                return state.intent, state.intent
            return appended, appended

        return await self._transition(repository_id=repository_id, transition=transition)

    async def start_attempt(self, *, repository_id: str) -> WritebackIntent:
        def transition(state: _LockedState) -> tuple[WritebackIntent, WritebackIntent]:
            started = state.intent.with_attempt_started(now=state.now)
            return started, started

        return await self._transition(repository_id=repository_id, transition=transition)

    async def record_failure(
        self, *, repository_id: str, failure: DeliveryFailure, final: bool, retry_due_at: datetime | None
    ) -> None:
        def transition(state: _LockedState) -> tuple[WritebackIntent, None]:
            failed = state.intent.with_failure(failure=failure, final=final, retry_due_at=retry_due_at, now=state.now)
            return failed, None

        await self._transition(repository_id=repository_id, transition=transition)

    async def owe_import(self, *, repository_id: str, commit: str) -> None:
        def transition(state: _LockedState) -> tuple[WritebackIntent, None]:
            return state.intent.with_import_owed(commit=commit), None

        await self._transition(repository_id=repository_id, transition=transition)

    async def settle_import(self, *, repository_id: str, commit: str, snapshot: WritebackIntent) -> bool:
        def transition(state: _LockedState) -> tuple[WritebackIntent, bool]:
            settled = state.intent.without_owed_import(commit=commit, snapshot=snapshot)
            if settled is None:
                return state.intent, False
            return settled, True

        return await self._transition(repository_id=repository_id, transition=transition)

    async def request_branch_deletion(self, *, repository_id: str, git_branch: str) -> bool:
        def transition(state: _LockedState) -> tuple[WritebackIntent, bool]:
            flagged = state.intent.with_branch_deletion_requested(git_branch=git_branch)
            if flagged is None:
                return state.intent, False
            return flagged, True

        return await self._transition(repository_id=repository_id, transition=transition)

    async def progress(self, *, repository_id: str) -> None:
        await self._move_progress(repository_id=repository_id)

    async def hold(self, *, repository_id: str, held: HeldRegeneration) -> HoldReceipt | None:
        def transition(state: _LockedState) -> tuple[WritebackIntent, HoldReceipt | None]:
            holding = state.intent.with_hold(held=held)
            if holding is None:
                return state.intent, None
            return holding

        return await self._transition(repository_id=repository_id, transition=transition)

    async def settle_delivery(
        self, *, repository_id: str, snapshot: WritebackIntent, delivered_commit: str | None
    ) -> ReleaseLease | None:
        def transition(state: _LockedState) -> tuple[WritebackIntent, ReleaseLease | None]:
            return state.intent.with_delivery_settled(
                snapshot=snapshot, delivered_commit=delivered_commit, lease_id=str(uuid4()), now=state.now
            )

        return await self._transition(repository_id=repository_id, transition=transition)

    async def abandon(
        self, *, repository_id: str, queue_version: int, record: AbandonmentRecord, actor: Actor
    ) -> tuple[WritebackIntent, ReleaseLease | None]:
        def transition(state: _LockedState) -> tuple[WritebackIntent, tuple[WritebackIntent, ReleaseLease | None]]:
            abandoned, lease = state.intent.abandoned(
                repository_name=state.repository_name,
                queue_version=queue_version,
                record=record,
                lease_id=str(uuid4()),
                now=state.now,
            )
            return abandoned, (abandoned, lease)

        return await self._transition(repository_id=repository_id, transition=transition, user_id=actor.account_id)

    async def lease_owed_release(self, *, repository_id: str) -> ReleaseLease | None:
        def transition(state: _LockedState) -> tuple[WritebackIntent, ReleaseLease | None]:
            leasing = state.intent.with_owed_release_leased(lease_id=str(uuid4()), now=state.now)
            if leasing is None:
                return state.intent, None
            return leasing

        return await self._transition(repository_id=repository_id, transition=transition)

    async def renew_lease(self, *, repository_id: str, lease_id: str) -> None:
        def transition(state: _LockedState) -> tuple[WritebackIntent, None]:
            return state.intent.with_lease_renewed(lease_id=lease_id, now=state.now), None

        await self._transition(repository_id=repository_id, transition=transition)

    async def expire_lease(self, *, repository_id: str, lease_id: str) -> None:
        def transition(state: _LockedState) -> tuple[WritebackIntent, None]:
            return state.intent.with_lease_expired(lease_id=lease_id, now=state.now), None

        await self._transition(repository_id=repository_id, transition=transition)

    async def clear_released(self, *, repository_id: str, lease_id: str) -> None:
        def transition(state: _LockedState) -> tuple[WritebackIntent, None]:
            return state.intent.without_window(lease_id=lease_id, now=state.now), None

        await self._transition(repository_id=repository_id, transition=transition)

    async def touch(self, *, repository_id: str) -> None:
        await self._move_progress(repository_id=repository_id)

    async def record_reverted(self, *, repository_id: str, reverted: RevertedDelivery) -> None:
        def transition(state: _LockedState) -> tuple[WritebackIntent, None]:
            return state.intent.with_reverted(reverted=reverted), None

        await self._transition(repository_id=repository_id, transition=transition)

    async def _move_progress(self, *, repository_id: str) -> None:
        def transition(state: _LockedState) -> tuple[WritebackIntent, None]:
            return state.intent.with_progress(now=state.now), None

        await self._transition(repository_id=repository_id, transition=transition)

    async def _transition[ResultT](
        self,
        *,
        repository_id: str,
        transition: Callable[[_LockedState], tuple[WritebackIntent, ResultT]],
        user_id: str = SYSTEM_USER_ID,
    ) -> ResultT:
        """Apply the transition to the stored state, and save the attributes that it changed in one save."""
        async with self._state_lock(repository_id=repository_id), self.db.start_transaction() as dbt:
            node = await self._get_repository(db=dbt, repository_id=repository_id)
            current = self._intent_of(node=node)
            updated, result = transition(
                _LockedState(
                    intent=current, repository_name=str(node.get_attribute(name="name").value), now=self.clock()
                )
            )
            current_values = self._attribute_values(intent=current)
            changed = {
                name: value
                for name, value in self._attribute_values(intent=updated).items()
                if value != current_values[name]
            }
            if changed:
                for name, value in changed.items():
                    node.get_attribute(name=name).value = value
                await node.save(db=dbt, user_id=user_id, fields=list(changed))
        return result

    @asynccontextmanager
    async def _state_lock(self, *, repository_id: str) -> AsyncIterator[None]:
        lock = self.lock_registry.get(name=repository_id, namespace=STATE_LOCK_NAMESPACE, ttl=STATE_LOCK_TTL_SECONDS)
        bound = asyncio.timeout(STATE_LOCK_ACQUIRE_SECONDS)
        try:
            async with bound:
                await lock.acquire()
        except TimeoutError as exc:
            if not bound.expired():
                raise
            raise DeliveryStateUnavailableError(
                repository_id=repository_id, acquire_seconds=STATE_LOCK_ACQUIRE_SECONDS
            ) from exc
        try:
            yield
        finally:
            await lock.release()

    async def _get_repository(self, *, db: InfrahubDatabase, repository_id: str) -> Node:
        return await NodeManager.get_one(
            db=db, id=repository_id, kind=InfrahubKind.REPOSITORY, branch=self.default_branch, raise_on_error=True
        )

    def _intent_of(self, *, node: Node) -> WritebackIntent:
        status = node.get_attribute(name=STATUS).value
        cause = node.get_attribute(name=FAILURE_CAUSE).value
        error = node.get_attribute(name=ERROR).value
        queue = node.get_attribute(name=QUEUE).value
        held = node.get_attribute(name=HELD_REGENERATION).value
        progress = node.get_attribute(name=PROGRESS).value
        last_delivered_commit = node.get_attribute(name=LAST_DELIVERED_COMMIT).value
        last_abandonment = node.get_attribute(name=LAST_ABANDONMENT).value
        reverted = node.get_attribute(name=REVERTED).value
        return WritebackIntent(
            repository_id=node.get_id(),
            status=RepositoryDeliveryStatus(status) if status else RepositoryDeliveryStatus.NONE,
            cause=RepositoryDeliveryFailureCause(cause) if cause else None,
            error=error if isinstance(error, str) else None,
            queue=DeliveryQueue.model_validate(queue) if queue else DeliveryQueue(),
            held=HeldRegeneration.model_validate(held) if held else HeldRegeneration(),
            progress=DeliveryProgress.model_validate(progress) if progress else DeliveryProgress(),
            last_delivered_commit=last_delivered_commit if isinstance(last_delivered_commit, str) else None,
            last_abandonment=AbandonmentRecord.model_validate(last_abandonment) if last_abandonment else None,
            reverted=RevertedDelivery.model_validate(reverted) if reverted else None,
        )

    def _attribute_values(self, *, intent: WritebackIntent) -> dict[str, Any]:
        return {
            STATUS: intent.status.value,
            FAILURE_CAUSE: intent.cause.value if intent.cause else None,
            ERROR: intent.error,
            QUEUE: intent.queue.model_dump(mode="json"),
            HELD_REGENERATION: intent.held.model_dump(mode="json"),
            PROGRESS: intent.progress.model_dump(mode="json"),
            LAST_ABANDONMENT: intent.last_abandonment.model_dump(mode="json") if intent.last_abandonment else None,
            LAST_DELIVERED_COMMIT: intent.last_delivered_commit,
            REVERTED: intent.reverted.model_dump(mode="json") if intent.reverted else None,
        }
