from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.schema.queries import SchemaElementIdsQuery

if TYPE_CHECKING:
    from collections.abc import Collection

    from infrahub.database import InfrahubDatabase


class SchemaElementRepository:
    """Looks up schema element IDs in the database."""

    def __init__(self, db: InfrahubDatabase) -> None:
        self._db = db

    async def get_existing_ids(self, ids: Collection[str]) -> set[str]:
        """Return the subset of ``ids`` held by a schema element on any branch, at any time."""
        if not ids:
            return set()
        query = await SchemaElementIdsQuery.init(db=self._db, ids=list(ids))
        await query.execute(db=self._db)
        return set(query.get_data().ids)
