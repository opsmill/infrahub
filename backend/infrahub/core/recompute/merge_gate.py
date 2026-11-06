"""Keep derived-value writes off a branch that is being merged or has been merged."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from infrahub.branch.status_checker import MERGE_RECOVERY_REQUIRED_MESSAGE
from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.exceptions import BranchNotFoundError, MergeInProgressError, MergeRecoveryRequiredError
from infrahub.log import get_logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from infrahub.database import InfrahubDatabase

log = get_logger()

# A large merge can run for minutes; past this bound the write fails instead of holding its worker.
MERGE_WAIT_TIMEOUT_SECONDS = 600.0
MERGE_WAIT_POLL_INTERVAL_SECONDS = 1.0


class MergingBranchWriteGate:
    """Decide whether derived values may be written to a branch, from its status in the database."""

    def __init__(
        self,
        *,
        db: InfrahubDatabase,
        timeout_seconds: float,
        poll_interval_seconds: float,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._db = db
        self._timeout_seconds = timeout_seconds
        self._poll_interval_seconds = poll_interval_seconds
        self._clock = clock
        self._sleep = sleep

    async def allows_write(self, branch_name: str) -> bool:
        """Return whether derived values may be written to the branch, waiting while it is being merged.

        Returns:
            False for a merged or deleted branch, True for any other branch that is not being merged.

        Raises:
            MergeRecoveryRequiredError: When the merge of the branch failed and waits for recovery.
            MergeInProgressError: When the branch is still being merged after the timeout.

        """
        deadline = self._clock() + self._timeout_seconds
        while True:
            try:
                # A worker runs concurrent flows through one database object, and a session runs one query at a time.
                async with self._db.start_session(read_only=True) as db:
                    branch = await Branch.get_by_name(db=db, name=branch_name)
            except BranchNotFoundError:
                return False

            if branch.status == BranchStatus.MERGED:
                log.info("Derived values not written to a merged branch", branch=branch_name)
                return False
            if branch.status == BranchStatus.MERGE_FAILED:
                raise MergeRecoveryRequiredError(
                    identifier=branch_name, message=MERGE_RECOVERY_REQUIRED_MESSAGE, merging_branch=branch_name
                )
            # The merge copies every edge active on the branch but announces only its diff, so a value
            # written now would reach the default branch without the recompute its change triggers there.
            if branch.status != BranchStatus.MERGING:
                return True
            if self._clock() >= deadline:
                raise MergeInProgressError(
                    identifier=branch_name,
                    message=(
                        f"Branch '{branch_name}' was still being merged after {self._timeout_seconds:.0f} seconds; "
                        "its derived values were not written."
                    ),
                    merging_branch=branch_name,
                )
            await self._sleep(self._poll_interval_seconds)
