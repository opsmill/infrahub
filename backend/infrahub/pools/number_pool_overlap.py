from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from infrahub.exceptions import ValidationError
from infrahub.pools.number_pool_space import attribute_domain
from infrahub.pools.range_refusal import other_pool_overlap_refusal

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.core.schema import AttributeSchema
    from infrahub.pools.number_pool_range_validation import NumberRangeBounds


@dataclass(frozen=True)
class PoolRangeSet:
    """The ranges of one number pool."""

    pool_id: str
    pool_name: str
    ranges: list[NumberRangeBounds]


@dataclass(frozen=True)
class RangeClash:
    """A range of one pool that overlaps a range of another pool."""

    range: NumberRangeBounds
    other_pool_name: str
    other_range: NumberRangeBounds


class AttributePoolRangeReader(Protocol):
    """Reads the ranges of every pool that allocates numbers for one attribute of one kind."""

    async def get_attribute_pool_ranges(self, kind: str, attribute_name: str) -> list[PoolRangeSet]: ...


def pool_overlap_refusal(
    pool_id: str,
    pool_name: str,
    ranges: Sequence[NumberRangeBounds],
    pools: Sequence[PoolRangeSet],
    attribute: AttributeSchema,
) -> str | None:
    """Return why the pool's `ranges` overlap another pool of `pools` on the attribute, or None when none overlaps."""
    clashes = _find_range_clashes(ranges=ranges, others=[other for other in pools if other.pool_id != pool_id])
    if not clashes:
        return None
    return other_pool_overlap_refusal(
        pool_name=pool_name, attribute_name=attribute.name, clashes=clashes, domain=attribute_domain(attribute)
    )


def _find_range_clashes(ranges: Sequence[NumberRangeBounds], others: Sequence[PoolRangeSet]) -> list[RangeClash]:
    """Return every pair of a range of `ranges` and a range of `others` that overlap, lowest range first."""
    return [
        RangeClash(range=candidate, other_pool_name=other.pool_name, other_range=other_range)
        for candidate in sorted(ranges, key=lambda pool_range: (pool_range.lower, pool_range.upper))
        for other in sorted(others, key=lambda other: other.pool_name)
        for other_range in sorted(other.ranges, key=lambda pool_range: (pool_range.lower, pool_range.upper))
        if candidate.overlaps(other_range)
    ]


class NumberPoolOverlapChecker:
    """Refuses ranges that overlap a range of another pool allocating numbers for the same unique attribute.

    A pool hands out the numbers its own records leave free, so two pools sharing numbers of a unique attribute would
    each offer what the other already gave, and the uniqueness constraint would refuse every such save.
    """

    def __init__(self, pool_reader: AttributePoolRangeReader) -> None:
        self.pool_reader = pool_reader

    async def check(
        self, pool_id: str, pool_name: str, kind: str, attribute: AttributeSchema, ranges: Sequence[NumberRangeBounds]
    ) -> None:
        """Refuse `ranges` for the pool when one overlaps a range of another pool feeding the kind's unique attribute.

        Raises:
            ValidationError: Naming every other pool's range that one of `ranges` overlaps.

        """
        if not attribute.unique:
            return
        refusal = pool_overlap_refusal(
            pool_id=pool_id,
            pool_name=pool_name,
            ranges=ranges,
            pools=await self.pool_reader.get_attribute_pool_ranges(kind=kind, attribute_name=attribute.name),
            attribute=attribute,
        )
        if refusal is not None:
            raise ValidationError(input_value=refusal)
