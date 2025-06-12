from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from infrahub.core.migrations.shared import MigrationResult
from infrahub.core.query import Query, QueryType
from infrahub.core.timestamp import Timestamp

from ..shared import GraphMigration

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class Migration003Query01(Query):
    name = "migration_003_01"
    type: QueryType = QueryType.WRITE

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        at = Timestamp()
        filters, params = at.get_query_filter_path()

        self.params.update(params)

        # ruff: noqa: E501
        query = """
        MATCH path = (av2:AttributeValue)-[:HAS_VALUE]-(:Attribute {name: "optional"})-[:HAS_ATTRIBUTE]-(n:SchemaRelationship)-[:HAS_ATTRIBUTE]-(:Attribute {name: "kind"})-[:HAS_VALUE]-(av1:AttributeValue)
        WHERE av1.value = "Parent" AND av2.value = true AND all(r IN relationships(path) WHERE ( %(filters)s ))
        CALL (n) {
            MATCH path22 = (av22:AttributeValue)-[r22:HAS_VALUE]-(a2:Attribute {name: "optional"})-[:HAS_ATTRIBUTE]-(n:SchemaRelationship)-[:HAS_ATTRIBUTE]-(:Attribute {name:"kind"})-[:HAS_VALUE]-(av11:AttributeValue)
            WHERE av11.value = "Parent" AND av22.value = true AND all(r IN relationships(path22) WHERE ( %(filters)s ))
            RETURN av22 as av2_sub, r22, a2, path22 as path2
            ORDER BY r22.branch_level DESC, r22.from DESC
            LIMIT 1
        }
        WITH av2_sub as av2, r22, a2, path2
        WHERE all(r IN relationships(path2) WHERE r.status = "active")
        MERGE (new_value: AttributeValue { value: false, is_default: false })
        CREATE (a2)-[:HAS_VALUE { branch: r22.branch, branch_level: r22.branch_level, status: "active", from: $at } ]->(new_value)
        SET r22.to = $at
        """ % {"filters": filters}
        self.add_to_query(query)
        self.return_labels = ["av2"]


class Migration003(GraphMigration):
    name: str = "003_relationship_parent_mandatory"
    queries: Sequence[type[Query]] = [Migration003Query01]
    minimum_version: int = 2

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        result = MigrationResult()

        return result
