from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

import pytest

from infrahub.core.branch.enums import BranchStatus
from infrahub.core.merge.failure_identifier import MergeFailureIdentifier
from infrahub.core.merge.write_blocker import MergeWriteBlocker
from infrahub.core.timestamp import Timestamp
from tests.adapters.cache import MemoryCache

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase
    from infrahub.services.component import InfrahubComponent

GRACE_SECONDS = 180


def _identifier(grace_period_seconds: int) -> MergeFailureIdentifier:
    # is_failed_merge decides from its arguments and the configured grace period alone, so the
    # unused db/component are not needed to exercise it.
    return MergeFailureIdentifier(
        db=cast("InfrahubDatabase", None),
        cache=MemoryCache(),
        component=cast("InfrahubComponent", None),
        merge_write_blocker=MergeWriteBlocker(cache=MemoryCache()),
        grace_period_seconds=grace_period_seconds,
    )


@dataclass
class PredicateCase:
    name: str
    status: BranchStatus
    lock_holder_worker_id: str | None
    active_worker_ids: set[str]
    started_seconds_ago: int | None
    expected: bool
    grace_seconds: int = GRACE_SECONDS


CASES = [
    PredicateCase(
        name="dead-holder-past-grace-is-failed",
        status=BranchStatus.MERGING,
        lock_holder_worker_id="dead-worker",
        active_worker_ids={"live-worker"},
        started_seconds_ago=600,
        expected=True,
    ),
    PredicateCase(
        name="live-holder-not-failed",
        status=BranchStatus.MERGING,
        lock_holder_worker_id="live-worker",
        active_worker_ids={"live-worker"},
        started_seconds_ago=600,
        expected=False,
    ),
    PredicateCase(
        name="absent-lock-not-flagged",
        status=BranchStatus.MERGING,
        lock_holder_worker_id=None,
        active_worker_ids=set(),
        started_seconds_ago=600,
        expected=False,
    ),
    PredicateCase(
        name="within-grace-not-flagged",
        status=BranchStatus.MERGING,
        lock_holder_worker_id="dead-worker",
        active_worker_ids=set(),
        started_seconds_ago=10,
        expected=False,
    ),
    PredicateCase(
        name="not-merging-not-flagged",
        status=BranchStatus.MERGE_FAILED,
        lock_holder_worker_id="dead-worker",
        active_worker_ids=set(),
        started_seconds_ago=600,
        expected=False,
    ),
    PredicateCase(
        name="open-status-not-flagged",
        status=BranchStatus.OPEN,
        lock_holder_worker_id="dead-worker",
        active_worker_ids=set(),
        started_seconds_ago=600,
        expected=False,
    ),
    PredicateCase(
        name="missing-merge-started-not-flagged",
        status=BranchStatus.MERGING,
        lock_holder_worker_id="dead-worker",
        active_worker_ids=set(),
        started_seconds_ago=None,
        expected=False,
    ),
]


@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
def test_is_failed_merge(case: PredicateCase) -> None:
    now = Timestamp()
    # Timestamp.add() is typed as the SDK base class; re-wrap so the value is the core Timestamp the
    # predicate expects (mirrors how production builds it from the stored string).
    merge_started_at = (
        Timestamp(now.add(seconds=-case.started_seconds_ago).to_string())
        if case.started_seconds_ago is not None
        else None
    )

    result = _identifier(grace_period_seconds=case.grace_seconds).is_failed_merge(
        status=case.status,
        lock_holder_worker_id=case.lock_holder_worker_id,
        active_worker_ids=case.active_worker_ids,
        merge_started_at=merge_started_at,
        now=now,
    )

    assert result is case.expected
