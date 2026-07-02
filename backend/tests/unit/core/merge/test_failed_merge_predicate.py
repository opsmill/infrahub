from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

import pytest

from infrahub.core.branch.enums import BranchStatus
from infrahub.core.merge.failure_recovery import MergeFailureRecovery
from infrahub.core.merge.write_blocker import MergeWriteBlocker
from infrahub.core.timestamp import Timestamp
from tests.adapters.cache import MemoryCache

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase
    from infrahub.services.component import InfrahubComponent

GRACE_SECONDS = 180


def _recovery() -> MergeFailureRecovery:
    # is_failed_merge is pure (it ignores every collaborator and decides from its arguments alone),
    # so the unused db/component are not needed to exercise it.
    return MergeFailureRecovery(
        db=cast("InfrahubDatabase", None),
        cache=MemoryCache(),
        component=cast("InfrahubComponent", None),
        merge_write_blocker=MergeWriteBlocker(cache=MemoryCache()),
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
    merge_started_at = now.add(seconds=-case.started_seconds_ago) if case.started_seconds_ago is not None else None

    result = _recovery().is_failed_merge(
        status=case.status,
        lock_holder_worker_id=case.lock_holder_worker_id,
        active_worker_ids=case.active_worker_ids,
        merge_started_at=merge_started_at,
        now=now,
        grace_period_seconds=case.grace_seconds,
    )

    assert result is case.expected
