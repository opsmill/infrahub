from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from infrahub.core.migrations.shared import MigrationResult
from infrahub.core.query import Query, QueryType

from ..shared import GraphMigration

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class SetCoreProposedChangeCreatedByOnNodeQuery(Query):
    name = "set_coreproposedchange_created_by_on_node"
    type: QueryType = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        query = """
        MATCH (pc:CoreProposedChange)
        CALL (pc) {
            MATCH (pc)-[r1:IS_RELATED]-(:Relationship {name: "coreaccount__proposedchange_created_by"})-[r2:IS_RELATED]-(account:CoreGenericAccount)
            RETURN account
            ORDER BY r1.from DESC, r2.from DESC
            LIMIT 1
        }
        SET pc.created_by = account.uuid
        """
        self.add_to_query(query)


class Migration054(GraphMigration):
    name: str = "054_set_coreproposedchange_created_by_on_node"
    minimum_version: int = 53
    queries: Sequence[type[Query]] = [SetCoreProposedChangeCreatedByOnNodeQuery]

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()
