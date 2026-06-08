from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.constants.enums import OrderByField, OrderDirection
from infrahub.core.node.standard import StandardNodeOrdering

from .queries import TelemetrySnapshotGetListQuery
from .snapshot import TelemetrySnapshot

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class TelemetrySnapshotRepository:
    """CRUD operations for `TelemetrySnapshot` against the database."""

    def __init__(self, db: InfrahubDatabase) -> None:
        self._db = db

    async def save(self, snapshot: TelemetrySnapshot) -> TelemetrySnapshot:
        async with self._db.start_session() as db:
            await snapshot.save(db=db)
        return snapshot

    async def get_list(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[TelemetrySnapshot]:
        async with self._db.start_session(read_only=True) as db:
            ordering = StandardNodeOrdering(
                order_by=OrderByField.CREATED_AT,
                direction=OrderDirection.DESC,
            )
            query = await TelemetrySnapshotGetListQuery.init(
                db=db,
                node_class=TelemetrySnapshot,
                node_ordering=ordering,
                limit=limit,
                offset=offset,
                start_date=start_date,
                end_date=end_date,
            )
            await query.execute(db=db)
            return [TelemetrySnapshot.from_db(result.get_node("n")) for result in query.get_results()]

    async def count(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> int:
        async with self._db.start_session(read_only=True) as db:
            ordering = StandardNodeOrdering(
                order_by=OrderByField.CREATED_AT,
                direction=OrderDirection.DESC,
            )
            query = await TelemetrySnapshotGetListQuery.init(
                db=db,
                node_class=TelemetrySnapshot,
                node_ordering=ordering,
                start_date=start_date,
                end_date=end_date,
            )
            return await query.count(db=db)
