from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.query.resource_manager import NumberPoolAttributeBranchValuesQuery
from infrahub.pools.range_refusal import BranchValue

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class NumberPoolAttributeBranchValues:
    """Reads the number each live branch holds for an attribute a number pool may track."""

    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def read(self, attribute_ids: list[str]) -> list[BranchValue]:
        """Return the number each live branch holds for each of the attributes, leaving out a branch that holds none."""
        query = await NumberPoolAttributeBranchValuesQuery.init(db=self.db, attribute_ids=attribute_ids)
        await query.execute(db=self.db)
        return [
            BranchValue(attribute_id=row.attribute_id, branch=row.branch, value=row.value) for row in query.get_data()
        ]
