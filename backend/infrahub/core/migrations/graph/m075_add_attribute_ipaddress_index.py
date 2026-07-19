from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from infrahub.constants.database import IndexType
from infrahub.core.migrations.shared import MigrationResult
from infrahub.core.query import Query  # noqa: TC001
from infrahub.database import DatabaseType
from infrahub.database.index import IndexItem
from infrahub.database.neo4j import IndexManagerNeo4j

from ..shared import GraphMigration

if TYPE_CHECKING:
    from infrahub.core.migrations.shared import MigrationInput
    from infrahub.database import InfrahubDatabase


INDEX_TO_ADD = IndexItem(
    name="attr_ipaddress_bin", label="AttributeIPAddress", properties=["binary_address"], type=IndexType.RANGE
)


class Migration075(GraphMigration):
    name: str = "075_add_attribute_ipaddress_index"
    description: str = "Add the binary_address RANGE index for the new AttributeIPAddress value nodes"
    queries: Sequence[type[Query]] = []
    minimum_version: int = 74

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        db = migration_input.db
        result = MigrationResult()

        # The dedicated AttributeIPAddress index only exists on Neo4j
        if db.db_type != DatabaseType.NEO4J:
            return result

        try:
            index_manager = IndexManagerNeo4j(db=db)
            index_manager.init(nodes=[INDEX_TO_ADD], rels=[])
            await index_manager.add()
        except Exception as exc:
            result.errors.append(str(exc))
            return result

        return result

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()
