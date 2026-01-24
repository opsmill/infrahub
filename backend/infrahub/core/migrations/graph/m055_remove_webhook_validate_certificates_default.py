from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from infrahub.core.constants import NULL_VALUE
from infrahub.core.migrations.shared import MigrationResult
from infrahub.core.query import Query, QueryType

from ..shared import GraphMigration

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class Migration055Query01(Query):
    """Remove the default_value from CoreWebhook's validate_certificates attribute.

    This migration finds the CoreWebhook SchemaGeneric, locates its validate_certificates
    SchemaAttribute, and sets the default_value to NULL. This removes the previous default
    of True.
    """

    name = "migration_055_01"
    type: QueryType = QueryType.WRITE

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        self.params["at"] = self.at.to_string()
        self.params["null_value"] = NULL_VALUE

        query = """
// get the generic schema
MATCH p1 = (sg:SchemaGeneric)-[:HAS_ATTRIBUTE]->(:Attribute {name: "name"})-[:HAS_VALUE]->(:AttributeValueIndexed {value: "Webhook"})
WHERE all(r IN relationships(p1) WHERE r.status = "active" AND r.to IS NULL)

// for safety, also check that the sg is in the namespace "Core"
MATCH p2 = (sg)-[:HAS_ATTRIBUTE]->(:Attribute {name: "namespace"})-[:HAS_VALUE]->(:AttributeValueIndexed {value: "Core"})
WHERE all(r IN relationships(p2) WHERE r.status = "active" AND r.to IS NULL)

// there should only be 1 CoreWebhook schema generic
WITH sg
LIMIT 1

// find the validate_certificates attribute
MATCH p3 = (sg)-[:IS_RELATED]-(:Relationship {name: "schema__node__attributes"})
    -[:IS_RELATED]-(sa:SchemaAttribute)
    -[:HAS_ATTRIBUTE]->(:Attribute {name: "name"})
    -[:HAS_VALUE]->(:AttributeValueIndexed {value: "validate_certificates"})
WHERE all(r IN relationships(p3) WHERE r.status = "active" AND r.to IS NULL)
// there should only be 1 validate_certificates attribute
WITH sa
LIMIT 1

// get the default_value Attribute
MATCH (sa)-[ha:HAS_ATTRIBUTE]->(default_value_attr:Attribute {name: "default_value"})-[hv:HAS_VALUE]->(default_value)
WHERE all(r IN [ha, hv] WHERE r.status = "active" AND r.to IS NULL)
LIMIT 1

// skip if it is already NULL
WITH sa, default_value_attr, hv, default_value
WHERE default_value.value <> $null_value

// close the HAS_VALUE edge for the current default value
SET hv.to = $at

// get the new value
MERGE (new_value:AttributeValue:AttributeValueIndexed {value: $null_value, is_default: true})
LIMIT 1

// link the new value
CREATE (default_value_attr)-[new_hv:HAS_VALUE]->(new_value)
SET new_hv = properties(hv)
SET new_hv.from = $at, new_hv.to = NULL
        """
        self.add_to_query(query)
        self.return_labels = ["new_value"]


class Migration055(GraphMigration):
    name: str = "055_remove_webhook_validate_certificates_default"
    queries: Sequence[type[Query]] = [Migration055Query01]
    minimum_version: int = 54

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        result = MigrationResult()

        return result
