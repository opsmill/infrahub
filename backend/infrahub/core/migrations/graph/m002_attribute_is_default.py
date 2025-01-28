from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from infrahub.core.migrations.shared import MigrationResult
from infrahub.core.query import Query, QueryType

from ..shared import GraphMigration

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class Migration002Query01(Query):
    name = "migration_002_01"
    type: QueryType = QueryType.WRITE

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        query = """
        MATCH (a:AttributeValue)
        WHERE a.is_default IS NULL
        SET a.is_default = false
        """
        self.add_to_query(query)
        self.return_labels = ["a"]


class Migration002(GraphMigration):
    name: str = "002_attribute_is_default"
    queries: Sequence[type[Query]] = [Migration002Query01]
    minimum_version: int = 1

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        result = MigrationResult()

        return result
