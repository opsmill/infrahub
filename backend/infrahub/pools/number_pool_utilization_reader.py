from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.pools.number import NumberUtilizationGetter
from infrahub.pools.number_pool_usage import PoolUsage, RangeUsage

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from infrahub.pools.number_pool_usage_state import NumberPoolStateLoader


class NumberPoolUtilizationReader:
    """Reads the utilization of one number pool and of each of its ranges, only of one division on a scoped pool."""

    def __init__(self, db: InfrahubDatabase, branch: Branch, loader: NumberPoolStateLoader) -> None:
        self.db = db
        self.branch = branch
        self.loader = loader

    async def read(self, pool_id: str, division: Sequence[tuple[str, object]] | None) -> PoolUsage:
        """Return the figures of the pool and of each range, ranges ordered by start.

        Raises:
            NodeNotFoundError: When `pool_id` is not a number pool.
            ValidationError: When `division` is given on an unscoped pool, names no scope element or one twice, gives
                a value that does not have the type its element stores, or is missing on a scoped pool, or when the
                schema of the branch does not define a scope element.

        """
        state = await self.loader.load(pool_id=pool_id)
        selected = state.scope.complete_division(entries=division)
        getter = NumberUtilizationGetter(
            db=self.db, pool=state.pool, space=state.space, branch=self.branch, division=selected
        )
        await getter.load_data()
        ranges = sorted(state.ranges, key=lambda item: int(item.start.value))
        return PoolUsage(
            id=pool_id,
            display_label=await state.pool.get_display_label(db=self.db),
            allocation_scope=state.scope.elements,
            figures=getter.figures,
            ranges=tuple(
                RangeUsage(
                    id=item.get_id(),
                    display_label=state.range_labels[item.get_id()],
                    start=int(item.start.value),
                    end=int(item.end.value),
                    weight=item.allocation_weight.value or 0,
                    figures=getter.range_figures(range_id=item.get_id()),
                )
                for item in ranges
            ),
        )
