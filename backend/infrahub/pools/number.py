from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub.core.query.resource_manager import NumberPoolGetAllocated
from infrahub.core.registry import registry

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase
    from infrahub.pools.number_ranges import EffectiveSpace


@dataclass
class UsedNumber:
    number: int
    branch: str


def _percentage(count: int, size: int) -> float:
    if size <= 0:
        return 0.0
    return (count / size) * 100


@dataclass(frozen=True)
class UtilizationFigures:
    """Counts of numbers in use within a space of `size` numbers, on the default branch and on other branches only."""

    size: int
    used_default_branch: int
    used_branches: int

    @property
    def utilization(self) -> float:
        return _percentage(self.used_default_branch + self.used_branches, self.size)

    @property
    def utilization_default_branch(self) -> float:
        return _percentage(self.used_default_branch, self.size)

    @property
    def utilization_branches(self) -> float:
        return _percentage(self.used_branches, self.size)


class NumberUtilizationGetter:
    """Utilization of a number pool measured against its effective space, for the pool and for each range."""

    def __init__(
        self,
        db: InfrahubDatabase,
        pool: CoreNumberPool,
        space: EffectiveSpace,
        branch: Branch,
        at: Timestamp | str | None = None,
    ) -> None:
        self.db = db
        self.at = at
        self.pool = pool
        self.space = space
        self.branch = branch
        self.used: list[UsedNumber] = []
        self.used_default_branch: set[int] = set()
        self.used_branches: set[int] = set()
        self._default_branch_by_range: Counter[str | None] = Counter()
        self._branches_by_range: Counter[str | None] = Counter()

    async def load_data(self) -> None:
        if not self.space.is_empty:
            query = await NumberPoolGetAllocated.init(
                db=self.db,
                pool=self.pool,
                ranges=self.space.as_query_ranges(),
                branch=self.branch,
                branch_agnostic=True,
            )
            await query.execute(db=self.db)
            self.used = [UsedNumber(number=item.value, branch=item.branch) for item in query.get_data()]

        self.used_default_branch = {entry.number for entry in self.used if entry.branch == registry.default_branch}
        used_branches = {entry.number for entry in self.used if entry.branch != registry.default_branch}
        self.used_branches = used_branches - self.used_default_branch

        self._default_branch_by_range = Counter(self.space.range_for(number) for number in self.used_default_branch)
        self._branches_by_range = Counter(self.space.range_for(number) for number in self.used_branches)

    @property
    def figures(self) -> UtilizationFigures:
        """Return the figures of the whole pool, measured against its effective space."""
        return UtilizationFigures(
            size=self.space.size,
            used_default_branch=len(self.used_default_branch),
            used_branches=len(self.used_branches),
        )

    def range_figures(self, range_id: str) -> UtilizationFigures:
        """Return the figures of one range, measured against the part of the effective space it contributes."""
        return UtilizationFigures(
            size=self.space.size_of(range_id),
            used_default_branch=self._default_branch_by_range[range_id],
            used_branches=self._branches_by_range[range_id],
        )
