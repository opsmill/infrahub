from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import SYSTEM_USER_ID, InfrahubKind, MetadataOptions
from infrahub.core.manager import NodeManager
from infrahub.core.metadata.model import MetadataQueryOptions
from infrahub.core.node import Node
from infrahub.git.writeback.models import PendingMerge
from infrahub.git.writeback.store import STATE_LOCK_NAMESPACE, WritebackIntentStore
from tests.adapters.lock import LockAction, LockTimeline, RecordingLockRegistry

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase
    from infrahub.git.writeback.models import WritebackIntent

NOW = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)
SOURCE_COMMIT = "0123456789abcdef0123456789abcdef01234567"
DELIVERED_COMMIT = "89abcdef0123456789abcdef0123456789abcdef"

STATUS = "delivery_status"
FAILURE_CAUSE = "delivery_failure_cause"
ERROR = "delivery_error"
QUEUE = "delivery_queue"
HELD_REGENERATION = "delivery_held_regeneration"
LAST_ABANDONMENT = "delivery_last_abandonment"
LAST_DELIVERED_COMMIT = "delivery_last_delivered_commit"
REVERTED = "delivery_reverted"
PROGRESS = "delivery_progress"
DELIVERY_ATTRIBUTES = (
    STATUS,
    FAILURE_CAUSE,
    ERROR,
    QUEUE,
    HELD_REGENERATION,
    LAST_ABANDONMENT,
    LAST_DELIVERED_COMMIT,
    REVERTED,
    PROGRESS,
)


class SteppingClock:
    """A clock that stays at its time until the test moves it."""

    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now

    def advance(self, *, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


@dataclass(frozen=True)
class AttributeWrite:
    updated_at: Timestamp | None
    updated_by: str | None


@dataclass
class StoreUnderTest:
    db: InfrahubDatabase
    branch: Branch
    store: WritebackIntentStore
    clock: SteppingClock
    lock_registry: RecordingLockRegistry
    timeline: LockTimeline
    repository_id: str

    @property
    def lock_name(self) -> str:
        return f"{STATE_LOCK_NAMESPACE}.{self.repository_id}"

    async def read(self) -> WritebackIntent:
        return await self.store.read(repository_id=self.repository_id)

    async def attribute_writes(self) -> dict[str, AttributeWrite]:
        return await read_attribute_writes(db=self.db, branch=self.branch, repository_id=self.repository_id)

    @asynccontextmanager
    async def expect_transition(self, *, saved: set[str], user_id: str = SYSTEM_USER_ID) -> AsyncIterator[None]:
        """Assert that the block takes the state lock once and writes exactly the `saved` attributes, in one save."""
        before = await self.attribute_writes()
        first_event = len(self.timeline.events)

        yield

        after = await self.attribute_writes()
        assert {name for name in DELIVERY_ATTRIBUTES if after[name] != before[name]} == saved
        if saved:
            assert len({after[name].updated_at for name in saved}) == 1
            assert {after[name].updated_by for name in saved} == {user_id}
        assert [(event.name, event.action) for event in self.timeline.events[first_event:]] == [
            (self.lock_name, LockAction.ACQUIRE),
            (self.lock_name, LockAction.RELEASE),
        ]


async def read_attribute_writes(db: InfrahubDatabase, branch: Branch, repository_id: str) -> dict[str, AttributeWrite]:
    """Return when and by whom each delivery attribute of the repository was last written."""
    node = await NodeManager.get_one(
        db=db,
        id=repository_id,
        kind=InfrahubKind.REPOSITORY,
        branch=branch,
        include_metadata=MetadataQueryOptions(attribute_level=MetadataOptions.UPDATED_AT | MetadataOptions.UPDATED_BY),
        raise_on_error=True,
    )
    return {
        name: AttributeWrite(
            updated_at=node.get_attribute(name=name)._get_updated_at(),
            updated_by=node.get_attribute(name=name)._get_updated_by(),
        )
        for name in DELIVERY_ATTRIBUTES
    }


async def create_repository(db: InfrahubDatabase, branch: Branch, name: str) -> Node:
    repository = await Node.init(db=db, schema=InfrahubKind.REPOSITORY, branch=branch)
    await repository.new(db=db, name=name, location=f"https://git.example.com/{name}.git")
    await repository.save(db=db)
    return repository


def pending_merge(entry_id: str, source_git_branch: str = "feature-1") -> PendingMerge:
    return PendingMerge(
        entry_id=entry_id,
        source_branch=source_git_branch,
        source_git_branch=source_git_branch,
        source_commit=SOURCE_COMMIT,
        merged_at=NOW,
    )


@pytest.fixture
async def subject(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> StoreUnderTest:
    repository = await create_repository(db=db, branch=default_branch, name="delivery-repository")
    timeline = LockTimeline()
    lock_registry = RecordingLockRegistry(timeline=timeline)
    clock = SteppingClock()
    return StoreUnderTest(
        db=db,
        branch=default_branch,
        store=WritebackIntentStore(db=db, lock_registry=lock_registry, default_branch=default_branch, clock=clock),
        clock=clock,
        lock_registry=lock_registry,
        timeline=timeline,
        repository_id=repository.id,
    )
