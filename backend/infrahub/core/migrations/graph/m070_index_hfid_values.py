from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from infrahub.core.attribute import MAX_STRING_LENGTH
from infrahub.core.migrations.shared import MigrationResult
from infrahub.core.query import Query, QueryType

from ..shared import GraphMigration

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class IndexHFIDValuesQuery(Query):
    name = "index_hfid_values"
    type: QueryType = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        self.params["max_length"] = MAX_STRING_LENGTH
        query = """
        MATCH (attr:Attribute {name: "human_friendly_id"})-[:HAS_VALUE]->(av:AttributeValue)
        WHERE NOT av:AttributeValueIndexed AND size(av.value) < $max_length
        SET av:AttributeValueIndexed
        """
        self.add_to_query(query)


class Migration070(GraphMigration):
    name: str = "070_index_hfid_values"
    minimum_version: int = 69
    queries: Sequence[type[Query]] = [IndexHFIDValuesQuery]

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()
