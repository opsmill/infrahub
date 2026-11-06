"""Doubles for the time a derived-value write spends waiting on a merge of its branch."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.branch.enums import BranchStatus
    from infrahub.database import InfrahubDatabase


class FakeClock:
    """A monotonic clock that moves only when a test advances it."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class MergeEndingSleep:
    """Advance the clock on every wait and, on the first one, save the status the merge ends with."""

    def __init__(
        self, *, clock: FakeClock, db: InfrahubDatabase, branch: Branch, end_status: BranchStatus | None
    ) -> None:
        self.clock = clock
        self.db = db
        self.branch = branch
        self.end_status = end_status
        self.waits: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.waits.append(seconds)
        self.clock.now += seconds
        if self.end_status is not None and len(self.waits) == 1:
            self.branch.status = self.end_status
            await self.branch.save(db=self.db)
