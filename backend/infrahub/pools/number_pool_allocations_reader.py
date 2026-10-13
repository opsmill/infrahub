from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub.core.query.resource_manager import NumberPoolGetAllocated
from infrahub.exceptions import ValidationError
from infrahub.pools.number_pool_usage import RangeReference, TrackedNumber, TrackedNumbersPage

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.core.branch import Branch
    from infrahub.core.constants import PoolRecordProvenance
    from infrahub.database import InfrahubDatabase
    from infrahub.pools.number_pool_usage_nodes import HoldingObjectReader
    from infrahub.pools.number_pool_usage_state import NumberPoolStateLoader
    from infrahub.pools.number_ranges import EffectiveSpace

DEFAULT_OFFSET = 0
DEFAULT_LIMIT = 1000


@dataclass(frozen=True)
class AllocationFilters:
    """The filters and the page of a tracked numbers query; a filter left as None does not filter."""

    division: Sequence[tuple[str, object]] | None = None
    """Pairs of a scope element name and the value the division holds for it."""
    range_id: str | None = None
    branch_name: str | None = None
    provenance: PoolRecordProvenance | None = None
    offset: int | None = None
    limit: int | None = None

    def __post_init__(self) -> None:
        """Refuse a negative page bound.

        Raises:
            ValidationError: When `offset` or `limit` is negative.

        """
        for name, page_value in (("offset", self.offset), ("limit", self.limit)):
            if page_value is not None and page_value < 0:
                raise ValidationError(f"{name} must be 0 or greater")


class NumberPoolAllocationsReader:
    """Reads one page of the numbers a number pool tracks, one row per number and branch holding it."""

    def __init__(
        self, db: InfrahubDatabase, branch: Branch, loader: NumberPoolStateLoader, holder_reader: HoldingObjectReader
    ) -> None:
        self.db = db
        self.branch = branch
        self.loader = loader
        self.holder_reader = holder_reader

    async def read(self, pool_id: str, filters: AllocationFilters) -> TrackedNumbersPage:
        """Return the page of tracked numbers the filters select, ordered by value, branch, then holding object id.

        Raises:
            NodeNotFoundError: When `pool_id` is not a number pool.
            ValidationError: When the range filter is not a range of the pool, the division filter is given on an
                unscoped pool, names no scope element or one twice or gives a value that does not have the type its
                element stores, or when the schema of the branch does not define a scope element.

        """
        state = await self.loader.load(pool_id=pool_id)
        space = state.space if filters.range_id is None else state.range_space(range_id=filters.range_id)
        division = state.scope.division_filter(entries=filters.division)
        if space.is_empty:
            return TrackedNumbersPage(count=0, allocations=())

        query = await NumberPoolGetAllocated.init(
            db=self.db,
            pool=state.pool,
            ranges=space.as_query_ranges(),
            branch_name=filters.branch_name,
            provenance=filters.provenance,
            division=division,
            offset=DEFAULT_OFFSET if filters.offset is None else filters.offset,
            limit=DEFAULT_LIMIT if filters.limit is None else filters.limit,
            branch=self.branch,
            branch_agnostic=True,
        )
        count = await query.count(db=self.db)
        # A query with no limit reads every row, so a page of zero rows is not read at all.
        if filters.limit == 0:
            return TrackedNumbersPage(count=count, allocations=())
        await query.execute(db=self.db)
        rows = query.get_data()
        holders = await self.holder_reader.read(rows=rows, kind=str(state.pool.get_attribute("node").value))
        return TrackedNumbersPage(
            count=count,
            allocations=tuple(
                TrackedNumber(
                    value=row.value,
                    branch=row.branch,
                    holder=holders[row.branch, row.id],
                    identifier=row.identifier,
                    provenance=row.provenance,
                    range=_range_reference(space=state.space, labels=state.range_labels, value=row.value),
                )
                for row in rows
            ),
        )


def _range_reference(space: EffectiveSpace, labels: dict[str, str], value: int) -> RangeReference:
    range_id = space.range_for(value) or ""
    return RangeReference(id=range_id, display_label=labels.get(range_id, ""))
