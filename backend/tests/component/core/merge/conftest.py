"""Shared fakes and builders for the merge-failure recovery tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.merge.failure_identifier import MergeFailureIdentifier
from infrahub.core.merge.failure_recoverer import MergeFailureRecoverer
from infrahub.core.merge.write_blocker import MergeWriteBlocker

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from infrahub.services.component import InfrahubComponent
    from tests.adapters.cache import MemoryCache

# Recovery finds the durably flagged branch directly, so the liveness grace period is irrelevant to
# most tests; those that exercise the MERGING liveness gate override it per-call.
GRACE_PERIOD_SECONDS = 180


class FailAtBranchResetRecoverer(MergeFailureRecoverer):
    """Real recoverer that raises while resetting the branch, after the graph rollback has run.

    Reproduces a recovery interrupted after the rollback lands but before the branch is reopened and
    the protection lifted, so the branch stays flagged and protected for a re-run.
    """

    async def _reset_branch(self, branch: Branch) -> None:
        raise RuntimeError("branch reset failed")


class FailAtLockReleaseRecoverer(MergeFailureRecoverer):
    """Real recoverer whose merge-lock release fails, before the branch is reopened.

    Reproduces a cache backend that cannot drop the stale lock key. The failure must not be swallowed:
    a held lock blocks every future merge, so recovery must report failure and leave the branch flagged,
    the protection held and the lock in place for a re-run.
    """

    async def _release_merge_lock(self) -> None:
        raise RuntimeError("lock release failed")


def build_identifier(
    db: InfrahubDatabase,
    cache: MemoryCache,
    component: InfrahubComponent,
    default_branch: Branch,
    grace_period_seconds: int = GRACE_PERIOD_SECONDS,
) -> MergeFailureIdentifier:
    return MergeFailureIdentifier(
        db=db,
        cache=cache,
        component=component,
        merge_write_blocker=MergeWriteBlocker(cache=cache),
        default_branch=default_branch,
        grace_period_seconds=grace_period_seconds,
    )


def build_recovery(
    db: InfrahubDatabase,
    cache: MemoryCache,
    component: InfrahubComponent,
    default_branch: Branch,
    grace_period_seconds: int = GRACE_PERIOD_SECONDS,
) -> MergeFailureRecoverer:
    return MergeFailureRecoverer(
        db=db,
        merge_write_blocker=MergeWriteBlocker(cache=cache),
        identifier=build_identifier(
            db=db,
            cache=cache,
            component=component,
            default_branch=default_branch,
            grace_period_seconds=grace_period_seconds,
        ),
        default_branch=default_branch,
        cache=cache,
    )
