from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from infrahub.core.migrations.shared import MigrationResult
from infrahub.core.query import Query  # noqa: TC001
from infrahub.database import DatabaseType
from infrahub.database.constants import IndexType
from infrahub.database.index import IndexItem

from ..shared import GraphMigration

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


INDEX_TO_DELETE = IndexItem(name="attr_value", label="AttributeValue", properties=["value"], type=IndexType.RANGE)


class Migration014(GraphMigration):
    name: str = "014_remove_index_attr_value"
    queries: Sequence[type[Query]] = []
    minimum_version: int = 13

    async def execute(self, db: InfrahubDatabase) -> MigrationResult:
        result = MigrationResult()

        # Only execute this migration for Neo4j
        if db.db_type != DatabaseType.NEO4J:
            return result

        async with db.start_transaction() as ts:
            try:
                ts.manager.index.init(nodes=[INDEX_TO_DELETE], rels=[])
                await ts.manager.index.drop()
            except Exception as exc:
                result.errors.append(str(exc))
                return result

        return result

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        result = MigrationResult()
        return result
