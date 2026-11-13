from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.constants.database import IndexType
from infrahub.core.migrations.shared import ArbitraryMigration, MigrationInput, MigrationResult
from infrahub.database import DatabaseType
from infrahub.database.index import IndexItem
from infrahub.database.neo4j import IndexManagerNeo4j

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

EDGE_TIME_INDEXES_TO_ADD: list[IndexItem] = [
    IndexItem(name="attr_to", label="HAS_ATTRIBUTE", properties=["to"], type=IndexType.RANGE),
    IndexItem(name="value_to", label="HAS_VALUE", properties=["to"], type=IndexType.RANGE),
    IndexItem(name="related_from", label="IS_RELATED", properties=["from"], type=IndexType.RANGE),
    IndexItem(name="related_to", label="IS_RELATED", properties=["to"], type=IndexType.RANGE),
    IndexItem(name="protected_from", label="IS_PROTECTED", properties=["from"], type=IndexType.RANGE),
    IndexItem(name="protected_to", label="IS_PROTECTED", properties=["to"], type=IndexType.RANGE),
    IndexItem(name="source_from", label="HAS_SOURCE", properties=["from"], type=IndexType.RANGE),
    IndexItem(name="source_to", label="HAS_SOURCE", properties=["to"], type=IndexType.RANGE),
    IndexItem(name="owner_from", label="HAS_OWNER", properties=["from"], type=IndexType.RANGE),
    IndexItem(name="owner_to", label="HAS_OWNER", properties=["to"], type=IndexType.RANGE),
    IndexItem(name="is_part_of_from", label="IS_PART_OF", properties=["from"], type=IndexType.RANGE),
    IndexItem(name="is_part_of_to", label="IS_PART_OF", properties=["to"], type=IndexType.RANGE),
    IndexItem(name="reserved_from", label="IS_RESERVED", properties=["from"], type=IndexType.RANGE),
    IndexItem(name="reserved_to", label="IS_RESERVED", properties=["to"], type=IndexType.RANGE),
]

INDEX_POPULATION_TIMEOUT_SECONDS = 3600


class Migration084(ArbitraryMigration):
    """Index every edge type on the time it was opened and the time it was closed.

    The diff reads that select edges by `from` and by `to` in a time window seek these indexes. Without them
    those reads scan every edge of a type, or every node, to find the edges in the window.
    """

    name: str = "084_index_edge_times"
    description: str = "Add RANGE indexes on the from and to properties of every edge type"
    minimum_version: int = 83

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        db = migration_input.db
        result = MigrationResult()

        if db.db_type != DatabaseType.NEO4J:
            return result

        index_manager = IndexManagerNeo4j(db=db)
        try:
            index_manager.init(nodes=[], rels=EDGE_TIME_INDEXES_TO_ADD)
            await index_manager.add()
            # an index is built in the background and cannot be read before it is online
            await db.execute_query(
                query="CALL db.awaitIndexes($timeout)",
                params={"timeout": INDEX_POPULATION_TIMEOUT_SECONDS},
                name="index_await",
            )
        # reported through the result so the runner prints it against this migration
        except Exception as exc:  # noqa: BLE001
            result.errors.append(f"Unable to add the edge time indexes: {exc}")

        return result

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:
        result = MigrationResult()

        if db.db_type != DatabaseType.NEO4J:
            return result

        index_manager = IndexManagerNeo4j(db=db)
        existing = {(info.label, tuple(info.properties), info.type) for info in await index_manager.list()}
        expected = {(item.label, tuple(item.properties), item.type) for item in EDGE_TIME_INDEXES_TO_ADD}
        for label, properties, index_type in sorted(expected - existing):
            result.errors.append(f"{index_type.value} index on {label}({', '.join(properties)}) is missing")

        return result
