from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import SYSTEM_USER_ID

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.core.node import Node
    from infrahub.core.protocols import CoreNumberPoolRange
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase
    from infrahub.pools.number_pool_repository import NumberPoolRangeStore


class NumberPoolShorthandMirror:
    """Keeps a number pool's deprecated start and end bounds in step with its range set.

    The shorthand carries the bounds of the single range a pool holds, and is null for a pool holding
    no range or more than one. It is only as fresh as the last sync, so a code path that changes the
    range set is expected to sync afterwards.
    """

    def __init__(self, db: InfrahubDatabase, repository: NumberPoolRangeStore) -> None:
        self.db = db
        self.repository = repository

    async def sync(
        self,
        pool: Node,
        ranges: Sequence[CoreNumberPoolRange] | None = None,
        at: Timestamp | None = None,
        user_id: str = SYSTEM_USER_ID,
    ) -> None:
        """Mirror the pool's range set onto its shorthand, writing nothing when the mirror is already right.

        Args:
            pool: The pool to mirror.
            ranges: The pool's ranges when the caller already holds them; read from the database when omitted.
            at: Time of the write, so it can share the timestamp of the range change it follows.
            user_id: Account the write is recorded under.

        """
        if ranges is None:
            ranges = await self.repository.get_ranges(pool_id=pool.get_id(), at=at)

        start: int | None = None
        end: int | None = None
        if len(ranges) == 1:
            start = int(ranges[0].start.value)
            end = int(ranges[0].end.value)

        if pool.get_attribute("start_range").value == start and pool.get_attribute("end_range").value == end:
            return

        pool.get_attribute("start_range").value = start
        pool.get_attribute("end_range").value = end
        # Only the two bounds are saved, so other pending changes on the caller's node stay unsaved.
        await pool.save(db=self.db, at=at, user_id=user_id, fields=["start_range", "end_range"])
