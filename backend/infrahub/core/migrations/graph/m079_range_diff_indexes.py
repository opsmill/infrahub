from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.constants.database import IndexType
from infrahub.core.migrations.shared import ArbitraryMigration, MigrationInput, MigrationResult
from infrahub.database import DatabaseType
from infrahub.database.index import IndexItem
from infrahub.database.neo4j import IndexManagerNeo4j

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

TEXT_INDEXES_TO_DROP: list[IndexItem] = [
    IndexItem(name="diff_uuid", label="DiffRoot", properties=["uuid"], type=IndexType.TEXT),
    IndexItem(name="diff_node_uuid", label="DiffNode", properties=["uuid"], type=IndexType.TEXT),
]

RANGE_INDEXES_TO_ADD: list[IndexItem] = [
    IndexItem(name="diff_uuid", label="DiffRoot", properties=["uuid"], type=IndexType.RANGE),
    IndexItem(name="diff_node_uuid", label="DiffNode", properties=["uuid"], type=IndexType.RANGE),
    IndexItem(name="diff_branch", label="DiffRoot", properties=["diff_branch"], type=IndexType.RANGE),
    IndexItem(name="diff_tracking_id", label="DiffRoot", properties=["tracking_id"], type=IndexType.RANGE),
]


def _index_keys(items: list[IndexItem]) -> set[tuple[str, tuple[str, ...], IndexType]]:
    return {(item.label, tuple(item.properties), item.type) for item in items}


class Migration079(ArbitraryMigration):
    """Index the diff graph with RANGE indexes.

    A TEXT index is only usable when the planner knows the looked-up value is a string, which it does not for a
    value read out of a map parameter, so diff root and diff node lookups by uuid fell back to label scans. RANGE
    indexes seek whatever the value's type. Diff roots also gain indexes on their branch and tracking id, the two
    other properties they are looked up by, since stored diffs accumulate and are never deleted.
    """

    name: str = "079_range_diff_indexes"
    description: str = "Replace the TEXT diff indexes with RANGE ones and index diff roots by branch and tracking id"
    minimum_version: int = 78

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        db = migration_input.db
        result = MigrationResult()

        if db.db_type != DatabaseType.NEO4J:
            return result

        index_manager = IndexManagerNeo4j(db=db)
        try:
            # the replacements exist before the old indexes go, so no diff lookup runs unindexed in between
            index_manager.init(nodes=RANGE_INDEXES_TO_ADD, rels=[])
            await index_manager.add()
            index_manager.init(nodes=TEXT_INDEXES_TO_DROP, rels=[])
            await index_manager.drop()
        # reported through the result so the runner prints it against this migration
        except Exception as exc:
            result.errors.append(f"Unable to replace the diff indexes: {exc}")

        return result

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:
        result = MigrationResult()

        if db.db_type != DatabaseType.NEO4J:
            return result

        index_manager = IndexManagerNeo4j(db=db)
        existing = {(info.label, tuple(info.properties), info.type) for info in await index_manager.list()}
        for label, properties, index_type in sorted(_index_keys(TEXT_INDEXES_TO_DROP) & existing):
            result.errors.append(f"{index_type.value} index on {label}({', '.join(properties)}) still exists")
        for label, properties, index_type in sorted(_index_keys(RANGE_INDEXES_TO_ADD) - existing):
            result.errors.append(f"{index_type.value} index on {label}({', '.join(properties)}) is missing")

        return result
