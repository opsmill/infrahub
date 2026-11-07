"""Hold recompute writes back from the source branch of an in-progress merge."""

from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.branch.status_checker import BranchStatusChecker
from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.exceptions import BranchNotFoundError, MergeInProgressError, MergeRecoveryRequiredError
from infrahub.log import get_logger
from infrahub.utils import InfrahubStringEnum

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from infrahub.core.merge.write_blocker import MergeWriteBlocker
    from infrahub.database import InfrahubDatabase

log = get_logger()

MERGE_WAIT_POLL_INTERVAL_SECONDS = 1.0


class MergeGateVerdict(InfrahubStringEnum):
    """Whether a recompute write may go ahead on its branch.

    ``OPEN``: no merge is taking the branch, write now. ``REOPENED``: a merge held the write back and
    rolled back, so reload what may have changed, then write. ``CLOSED``: the branch merged or was
    deleted while the write was held back, so drop the write.
    """

    OPEN = "open"
    REOPENED = "reopened"
    CLOSED = "closed"


class MergeSourceWriteGate:
    """Keep recompute writes off the source branch of an in-progress merge.

    A merge carries every edge still active on its source branch, but takes its changelog, and with it
    the post-merge recompute, from a diff snapshot taken before that. A derived value written to the
    source branch in between reaches the destination with none of its readers recomputed there, so the
    write waits the merge out instead; once the branch has merged it is read-only, and the post-merge
    recompute derives the value on the destination.

    The destination is not held: a write delayed past the merge could land after the post-merge
    recompute and overwrite its value with one rendered from the pre-merge inputs.
    """

    def __init__(
        self,
        db: InfrahubDatabase,
        merge_write_blocker: MergeWriteBlocker,
        sleep: Callable[[float], Awaitable[None]],
        poll_interval_seconds: float,
    ) -> None:
        self.db = db
        self.merge_write_blocker = merge_write_blocker
        self.sleep = sleep
        self.poll_interval_seconds = poll_interval_seconds

    async def admit(self, branch: Branch) -> MergeGateVerdict:
        """Wait out a merge that is taking ``branch``, then say whether the write may go ahead.

        Raises:
            MergeRecoveryRequiredError: if a failed merge of ``branch`` is awaiting recovery.

        """
        if not await self._is_merge_source(branch=branch):
            return MergeGateVerdict.OPEN
        log.info("Holding a recompute write until the merge of its branch ends", branch=branch.name)
        while await self._is_merge_source(branch=branch):
            await self.sleep(self.poll_interval_seconds)

        verdict = await self._verdict_after_merge(branch=branch)
        log.info("Released a recompute write held by a merge", branch=branch.name, verdict=verdict.value)
        return verdict

    async def _verdict_after_merge(self, branch: Branch) -> MergeGateVerdict:
        try:
            # A worker runs concurrent flows through one database object, and a session runs one query at a time.
            async with self.db.start_session(read_only=True) as db:
                reloaded = await Branch.get_by_name(db=db, name=branch.name)
        except BranchNotFoundError:
            return MergeGateVerdict.CLOSED
        if reloaded.status == BranchStatus.MERGED:
            return MergeGateVerdict.CLOSED
        return MergeGateVerdict.REOPENED

    async def _is_merge_source(self, branch: Branch) -> bool:
        try:
            # The check falls back to the database when the cache cannot be read, so it needs its own session too.
            async with self.db.start_session(read_only=True) as db:
                status_checker = BranchStatusChecker(db=db, merge_write_blocker=self.merge_write_blocker)
                await status_checker.check_merging_status(branch)
        except MergeInProgressError as exc:
            return exc.merging_branch == branch.name
        except MergeRecoveryRequiredError as exc:
            if exc.merging_branch == branch.name:
                raise
            return False
        return False
