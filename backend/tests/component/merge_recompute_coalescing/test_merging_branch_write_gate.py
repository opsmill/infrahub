"""Derived values are written to a branch only once no merge holds it, and never to a merged branch."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from infrahub.core.branch.enums import BranchStatus
from infrahub.core.initialization import create_branch
from infrahub.core.recompute.merge_gate import MergingBranchWriteGate
from infrahub.exceptions import MergeInProgressError, MergeRecoveryRequiredError
from tests.helpers.merge_recompute.merge_wait import FakeClock, MergeEndingSleep

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

POLL_INTERVAL_SECONDS = 1.0
TIMEOUT_SECONDS = 3.0
CONCURRENT_WRITES = 10


async def _branch_with_status(db: InfrahubDatabase, status: BranchStatus) -> Branch:
    branch = await create_branch(branch_name="gated-branch", db=db)
    branch.status = status
    await branch.save(db=db)
    return branch


def _gate(db: InfrahubDatabase, sleep: MergeEndingSleep) -> MergingBranchWriteGate:
    return MergingBranchWriteGate(
        db=db,
        timeout_seconds=TIMEOUT_SECONDS,
        poll_interval_seconds=POLL_INTERVAL_SECONDS,
        clock=sleep.clock,
        sleep=sleep,
    )


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        pytest.param(BranchStatus.OPEN, True, id="open"),
        pytest.param(BranchStatus.NEED_REBASE, True, id="need-rebase"),
        pytest.param(BranchStatus.MERGED, False, id="merged"),
    ],
)
async def test_decides_without_waiting_when_the_branch_is_not_being_merged(
    db: InfrahubDatabase, default_branch: Branch, status: BranchStatus, expected: bool
) -> None:
    branch = await _branch_with_status(db=db, status=status)
    sleep = MergeEndingSleep(clock=FakeClock(), db=db, branch=branch, end_status=None)

    assert await _gate(db=db, sleep=sleep).allows_write(branch_name=branch.name) is expected
    assert sleep.waits == []


async def test_decides_for_concurrent_writes_through_one_database_object(
    db: InfrahubDatabase, default_branch: Branch
) -> None:
    """A worker runs several recompute flows at once, all through the same database object."""
    branch = await _branch_with_status(db=db, status=BranchStatus.OPEN)
    sleep = MergeEndingSleep(clock=FakeClock(), db=db, branch=branch, end_status=None)
    gate = _gate(db=db, sleep=sleep)

    decisions = await asyncio.gather(*(gate.allows_write(branch_name=branch.name) for _ in range(CONCURRENT_WRITES)))

    assert decisions == [True] * CONCURRENT_WRITES


async def test_skips_a_branch_that_is_merged_while_the_write_waits(
    db: InfrahubDatabase, default_branch: Branch
) -> None:
    branch = await _branch_with_status(db=db, status=BranchStatus.MERGING)
    sleep = MergeEndingSleep(clock=FakeClock(), db=db, branch=branch, end_status=BranchStatus.MERGED)

    assert await _gate(db=db, sleep=sleep).allows_write(branch_name=branch.name) is False
    assert sleep.waits == [POLL_INTERVAL_SECONDS]


async def test_writes_a_branch_whose_merge_is_rolled_back_while_the_write_waits(
    db: InfrahubDatabase, default_branch: Branch
) -> None:
    branch = await _branch_with_status(db=db, status=BranchStatus.MERGING)
    sleep = MergeEndingSleep(clock=FakeClock(), db=db, branch=branch, end_status=BranchStatus.OPEN)

    assert await _gate(db=db, sleep=sleep).allows_write(branch_name=branch.name) is True
    assert sleep.waits == [POLL_INTERVAL_SECONDS]


async def test_skips_a_branch_that_no_longer_exists(db: InfrahubDatabase, default_branch: Branch) -> None:
    branch = await _branch_with_status(db=db, status=BranchStatus.OPEN)
    sleep = MergeEndingSleep(clock=FakeClock(), db=db, branch=branch, end_status=None)

    assert await _gate(db=db, sleep=sleep).allows_write(branch_name="branch-that-was-deleted") is False
    assert sleep.waits == []


async def test_raises_when_the_merge_of_the_branch_failed(db: InfrahubDatabase, default_branch: Branch) -> None:
    branch = await _branch_with_status(db=db, status=BranchStatus.MERGE_FAILED)
    sleep = MergeEndingSleep(clock=FakeClock(), db=db, branch=branch, end_status=None)

    with pytest.raises(MergeRecoveryRequiredError, match=r"^A previous merge failed and left the default branch"):
        await _gate(db=db, sleep=sleep).allows_write(branch_name=branch.name)
    assert sleep.waits == []


async def test_raises_when_the_branch_is_still_being_merged_after_the_timeout(
    db: InfrahubDatabase, default_branch: Branch
) -> None:
    branch = await _branch_with_status(db=db, status=BranchStatus.MERGING)
    sleep = MergeEndingSleep(clock=FakeClock(), db=db, branch=branch, end_status=None)

    with pytest.raises(
        MergeInProgressError,
        match=r"^Branch 'gated-branch' was still being merged after 3 seconds; its derived values were not written\.$",
    ):
        await _gate(db=db, sleep=sleep).allows_write(branch_name=branch.name)
    assert sleep.waits == [POLL_INTERVAL_SECONDS, POLL_INTERVAL_SECONDS, POLL_INTERVAL_SECONDS]
