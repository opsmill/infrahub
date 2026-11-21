from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.constants.database import IndexType
from infrahub.core.migrations.shared import ArbitraryMigration, MigrationInput, MigrationResult
from infrahub.database import DatabaseType
from infrahub.database.index import IndexItem
from infrahub.database.neo4j import IndexManagerNeo4j

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

SCHEMA_CHANGE_INDEXES_TO_ADD: list[IndexItem] = [
    IndexItem(name="schema_change_uuid", label="SchemaChange", properties=["uuid"], type=IndexType.RANGE),
    IndexItem(name="schema_change_branch", label="SchemaChange", properties=["branch"], type=IndexType.RANGE),
    IndexItem(
        name="schema_change_application_uuid",
        label="SchemaChangeApplication",
        properties=["uuid"],
        type=IndexType.RANGE,
    ),
]


class Migration084(ArbitraryMigration):
    """Index schema changes by uuid and branch and applications by uuid, the records that every query starts from."""

    name: str = "084_schema_change_indexes"
    description: str = "Index the schema changes by uuid and branch, and their applications by uuid"
    minimum_version: int = 83

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        db = migration_input.db
        result = MigrationResult()

        if db.db_type != DatabaseType.NEO4J:
            return result

        index_manager = IndexManagerNeo4j(db=db)
        index_manager.init(nodes=SCHEMA_CHANGE_INDEXES_TO_ADD, rels=[])
        try:
            await index_manager.add()
        # reported through the result so the runner prints it against this migration
        except Exception as exc:  # noqa: BLE001
            result.errors.append(f"Unable to add the schema change indexes: {exc}")

        return result

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:
        result = MigrationResult()

        if db.db_type != DatabaseType.NEO4J:
            return result

        index_manager = IndexManagerNeo4j(db=db)
        existing = {(info.label, tuple(info.properties), info.type) for info in await index_manager.list()}
        for item in SCHEMA_CHANGE_INDEXES_TO_ADD:
            if (item.label, tuple(item.properties), item.type) not in existing:
                result.errors.append(
                    f"{item.type.value} index on {item.label}({', '.join(item.properties)}) is missing"
                )

        return result
