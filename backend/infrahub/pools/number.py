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
    from infrahub.pools.scope import Division


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
    def used(self) -> int:
        return self.used_default_branch + self.used_branches

    @property
    def utilization(self) -> float:
        return _percentage(self.used_default_branch + self.used_branches, self.size)

    @property
    def utilization_default_branch(self) -> float:
        return _percentage(self.used_default_branch, self.size)

    @property
    def utilization_branches(self) -> float:
        return _percentage(self.used_branches, self.size)


@dataclass(frozen=True)
class NumberPoolUtilization:
    """The numbers in use within an effective space, and the figures they give for the space and for each range."""

    space: EffectiveSpace
    used: tuple[UsedNumber, ...]
    used_default_branch: frozenset[int]
    used_branches: frozenset[int]
    """Numbers in use on other branches only, so a number used on the default branch is counted once."""
    used_default_branch_by_range: Counter[str | None]
    used_branches_by_range: Counter[str | None]

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
            used_default_branch=self.used_default_branch_by_range[range_id],
            used_branches=self.used_branches_by_range[range_id],
        )


class NumberUtilizationGetter:
    """Measures the utilization of a number pool against an effective space, for the pool and for each range.

    With a division, only the numbers whose holding object is in the division on some live branch are counted.
    """

    def __init__(self, db: InfrahubDatabase, branch: Branch, at: Timestamp | str | None = None) -> None:
        self.db = db
        self.branch = branch
        self.at = at

    async def measure(
        self, pool: CoreNumberPool, space: EffectiveSpace, division: Division | None = None
    ) -> NumberPoolUtilization:
        """Return the numbers of `pool` in use within `space`, only those of `division` when one is given."""
        used: list[UsedNumber] = []
        if not space.is_empty:
            query = await NumberPoolGetAllocated.init(
                db=self.db,
                pool=pool,
                ranges=space.as_query_ranges(),
                branch=self.branch,
                division=division,
            )
            await query.execute(db=self.db)
            used = [UsedNumber(number=item.value, branch=item.branch) for item in query.get_data()]

        used_default_branch = frozenset(entry.number for entry in used if entry.branch == registry.default_branch)
        used_branches = frozenset(entry.number for entry in used if entry.branch != registry.default_branch)
        used_branches -= used_default_branch
        return NumberPoolUtilization(
            space=space,
            used=tuple(used),
            used_default_branch=used_default_branch,
            used_branches=used_branches,
            used_default_branch_by_range=Counter(space.range_for(number) for number in used_default_branch),
            used_branches_by_range=Counter(space.range_for(number) for number in used_branches),
        )
