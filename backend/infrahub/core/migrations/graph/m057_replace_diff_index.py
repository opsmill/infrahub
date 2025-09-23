from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from infrahub.constants.database import IndexType
from infrahub.core.migrations.shared import MigrationInput, MigrationResult
from infrahub.core.query import Query  # noqa: TC001
from infrahub.database import DatabaseType
from infrahub.database.index import IndexItem
from infrahub.database.neo4j import IndexManagerNeo4j

from ..shared import GraphMigration

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


INDEX_TO_DELETE = [
    IndexItem(name="diff_uuid", label="DiffRoot", properties=["uuid"], type=IndexType.TEXT),
    IndexItem(name="diff_node_uuid", label="DiffNode", properties=["uuid"], type=IndexType.TEXT),
]


class Migration057(GraphMigration):
    name: str = "057_replace_diff_index"
    queries: Sequence[type[Query]] = []
    minimum_version: int = 56

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        db = migration_input.db
        result = MigrationResult()

        # Only execute this migration for Neo4j
        if db.db_type != DatabaseType.NEO4J:
            return result

        try:
            index_manager = IndexManagerNeo4j(db=db)
            index_manager.init(nodes=INDEX_TO_DELETE, rels=[])
            await index_manager.drop()
        except Exception as exc:
            result.errors.append(str(exc))
            return result

        return result

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        result = MigrationResult()
        return result
