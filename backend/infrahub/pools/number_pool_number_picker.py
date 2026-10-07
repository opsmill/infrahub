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


class NumberPoolNumberReader(Protocol):
    """Reads a pool's ranges, the values its target attribute already holds and the next free number in a span."""

    async def get_pool_ranges(self, pool_id: str, at: Timestamp | None = None) -> list[PoolRange]: ...

    async def get_taken(self, pool: CoreNumberPool, branch: Branch, space: EffectiveSpace) -> set[int]: ...

    async def get_free(self, pool: CoreNumberPool, branch: Branch, min_value: int, max_value: int) -> int | None: ...


class NumberPoolNumberPicker:
    """Picks the next number a pool hands out for the attribute it feeds."""

    def __init__(self, number_reader: NumberPoolNumberReader) -> None:
        self.number_reader = number_reader

    async def next_number(self, pool: CoreNumberPool, branch: Branch, attribute: AttributeSchema) -> int:
        """Return the next number `pool` hands out for `attribute`.

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
        # Only a globally unique attribute rejects a duplicate, so skip existing values only then.
        taken = await self.number_reader.get_taken(pool=pool, branch=branch, space=space) if attribute.unique else set()

        for segment in space.segments:
            cursor = segment.start
            while cursor <= segment.end:
                # A run of taken values is stepped over in memory so it costs no round trip per value.
                if cursor in taken:
                    cursor += 1
                    continue
                candidate = await self.number_reader.get_free(
                    pool=pool, branch=branch, min_value=cursor, max_value=segment.end
                )
                if candidate is None:
                    break
                if candidate not in taken:
                    return candidate
                cursor = candidate + 1

        raise PoolExhaustedError(f"Pool {_label(pool)} has no free number left in its ranges.")


def _label(pool: CoreNumberPool) -> str:
    return f"{pool.get_attribute('name').value} ({pool.get_id()})"
