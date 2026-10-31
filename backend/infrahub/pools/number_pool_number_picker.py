from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from infrahub.exceptions import PoolExhaustedError
from infrahub.pools.number_pool_space import attribute_domain
from infrahub.pools.number_ranges import EffectiveSpace

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
    from infrahub.core.schema import AttributeSchema
    from infrahub.core.timestamp import Timestamp
    from infrahub.pools.number_ranges import PoolRange
    from infrahub.pools.scope import Division


class NumberPoolNumberReader(Protocol):
    """Reads a pool's ranges and the next number its records leave free in a span."""

    async def get_pool_ranges(self, pool_id: str, at: Timestamp | None = None) -> list[PoolRange]: ...

    async def get_free(
        self,
        pool: CoreNumberPool,
        branch: Branch,
        min_value: int,
        max_value: int,
        division: Division | None = None,
    ) -> int | None: ...


class NumberPoolNumberPicker:
    """Picks the next number a pool hands out for the attribute it feeds."""

    def __init__(self, number_reader: NumberPoolNumberReader) -> None:
        self.number_reader = number_reader

    async def next_number(
        self, pool: CoreNumberPool, branch: Branch, attribute: AttributeSchema, division: Division | None = None
    ) -> int:
        """Return the next number `pool` hands out for `attribute`, within `division` when one is given.

        The pool's ranges are clipped to the numbers the attribute accepts, then drained heaviest first and
        lowest start first, each from its lowest free number.

        Raises:
            PoolExhaustedError: If the attribute accepts no number of the ranges, or none of them is free.

        """
        space = EffectiveSpace(
            ranges=await self.number_reader.get_pool_ranges(pool_id=pool.get_id()),
            domain=attribute_domain(attribute=attribute),
        )
        if space.is_empty:
            raise PoolExhaustedError(f"Pool {_label(pool)} has no number the attribute accepts in its ranges.")

        for segment in space.segments:
            candidate = await self.number_reader.get_free(
                pool=pool, branch=branch, min_value=segment.start, max_value=segment.end, division=division
            )
            if candidate is not None:
                return candidate

        raise PoolExhaustedError(f"Pool {_label(pool)} has no free number left in its ranges.")


def _label(pool: CoreNumberPool) -> str:
    return f"{pool.get_attribute('name').value} ({pool.get_id()})"
