from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

import pytest

from infrahub.components import ComponentType
from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.merge.failure_identifier import MergeFailureIdentifier
from infrahub.core.merge.merge_locker import MERGE_LOCK_KEY
from infrahub.core.merge.write_blocker import MergeWriteBlocker
from infrahub.core.timestamp import Timestamp
from infrahub.services.component import InfrahubComponent
from infrahub.worker import WORKER_IDENTITY
from tests.adapters.cache import MemoryCache
from tests.adapters.message_bus import BusRecorder

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

DEAD_WORKER = "dead-worker"
GRACE_PERIOD_SECONDS = 180


def _lock_token(worker_id: str) -> str:
    return f"{Timestamp().to_string()}::{worker_id}"


@dataclass
class IsFailedMergeCase:
    name: str
    status: BranchStatus
    lock_worker_id: str | None  # None means no merge-lock key is set at all
    started_seconds_ago: int | None
    expected: bool


CASES = [
    IsFailedMergeCase(
        name="dead-holder-past-grace-is-failed",
        status=BranchStatus.MERGING,
        lock_worker_id=DEAD_WORKER,
        started_seconds_ago=600,
        expected=True,
    ),
    IsFailedMergeCase(
        name="live-holder-not-flagged",
        status=BranchStatus.MERGING,
        lock_worker_id=WORKER_IDENTITY,
        started_seconds_ago=600,
        expected=False,
    ),
    IsFailedMergeCase(
        name="absent-lock-not-flagged",
        status=BranchStatus.MERGING,
        lock_worker_id=None,
        started_seconds_ago=600,
        expected=False,
    ),
    IsFailedMergeCase(
        name="within-grace-not-flagged",
        status=BranchStatus.MERGING,
        lock_worker_id=DEAD_WORKER,
        started_seconds_ago=0,
        expected=False,
    ),
    IsFailedMergeCase(
        name="merge-failed-status-not-flagged",
        status=BranchStatus.MERGE_FAILED,
        lock_worker_id=DEAD_WORKER,
        started_seconds_ago=600,
        expected=False,
    ),
    IsFailedMergeCase(
        name="open-status-not-flagged",
        status=BranchStatus.OPEN,
        lock_worker_id=DEAD_WORKER,
        started_seconds_ago=600,
        expected=False,
    ),
    IsFailedMergeCase(
        name="missing-merge-started-not-flagged",
        status=BranchStatus.MERGING,
        lock_worker_id=DEAD_WORKER,
        started_seconds_ago=None,
        expected=False,
    ),
]


@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
async def test_should_mark_as_failed_merge(case: IsFailedMergeCase) -> None:
    # should_mark_as_failed_merge reads only the cache (the merge lock plus worker heartbeats) and the branch
    # object it is handed, so a cache-backed component needs no database — this stays a unit test.
    cache = MemoryCache()
    db = cast("InfrahubDatabase", None)  # unused by list_workers / should_mark_as_failed_merge
    component = InfrahubComponent(
        cache=cache, db=db, message_bus=BusRecorder(), component_type=ComponentType.API_SERVER
    )
    await component.refresh_heartbeat()  # marks WORKER_IDENTITY active in the cache

    if case.lock_worker_id is not None:
        await cache.set(MERGE_LOCK_KEY, _lock_token(case.lock_worker_id))

    identifier = MergeFailureIdentifier(
        db=db,
        cache=cache,
        component=component,
        merge_write_blocker=MergeWriteBlocker(cache=cache),
        default_branch=Branch(name="main", status=BranchStatus.OPEN, branched_from=Timestamp().to_string()),
        grace_period_seconds=GRACE_PERIOD_SECONDS,
    )

    merge_started_at = (
        Timestamp().add(seconds=-case.started_seconds_ago).to_string() if case.started_seconds_ago is not None else None
    )
    branch = Branch(
        name=f"is-failed-merge-{case.name}",
        status=case.status,
        branched_from=Timestamp().to_string(),
        merge_started_at=merge_started_at,
    )

    assert await identifier.should_mark_as_failed_merge(branch=branch, now=Timestamp()) is case.expected
