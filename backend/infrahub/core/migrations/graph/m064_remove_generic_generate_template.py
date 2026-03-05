from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from infrahub.core.migrations.shared import MigrationResult
from infrahub.core.query import Query, QueryType

from ..shared import GraphMigration

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class RemoveGenericGenerateTemplateQuery(Query):
    """Remove generate_template Attribute nodes from all SchemaGeneric-labeled instances."""

    name = "migration_062_remove_generic_generate_template"
    type: QueryType = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        query = """
MATCH (sg:SchemaGeneric)-[:HAS_ATTRIBUTE]->(attr:Attribute {name: "generate_template"})
WITH DISTINCT attr
DETACH DELETE attr
        """
        self.add_to_query(query)


class RemoveGenericGenerateTemplateSchemaAttributeQuery(Query):
    """Remove the generate_template SchemaAttribute from the SchemaGeneric type definition."""

    name = "migration_062_remove_generic_generate_template_schema_attribute"
    type: QueryType = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        query = """
// Find the SchemaGeneric type definition (stored as SchemaNode)
MATCH p1 = (sn:SchemaNode)-[:HAS_ATTRIBUTE]->(:Attribute {name: "name"})-[:HAS_VALUE]->(:AttributeValueIndexed {value: "Generic"})
WHERE all(r IN relationships(p1) WHERE r.status = "active" AND r.to IS NULL)
MATCH p2 = (sn)-[:HAS_ATTRIBUTE]->(:Attribute {name: "namespace"})-[:HAS_VALUE]->(:AttributeValueIndexed {value: "Schema"})
WHERE all(r IN relationships(p2) WHERE r.status = "active" AND r.to IS NULL)
WITH sn
LIMIT 1
// Find the generate_template SchemaAttribute child
MATCH p3 = (sn)-[:IS_RELATED]-(rel:Relationship {name: "schema__node__attributes"})
               -[:IS_RELATED]-(sa:SchemaAttribute)
               -[:HAS_ATTRIBUTE]->(:Attribute {name: "name"})
               -[:HAS_VALUE]->(:AttributeValueIndexed {value: "generate_template"})
WHERE all(r IN relationships(p3) WHERE r.status = "active" AND r.to IS NULL)
WITH sa, rel
LIMIT 1
// Find child Attribute nodes and their value nodes
MATCH (sa)-[:HAS_ATTRIBUTE]->(attr:Attribute)-[:HAS_VALUE]->(val)
// Delete the SchemaAttribute, Relationship node, and child Attributes
DETACH DELETE sa, rel, attr
// Clean up orphaned value nodes (Boolean nodes are shared and will still have edges)
WITH val
WHERE NOT EXISTS { MATCH (val)-[]-() }
DELETE val
        """
        self.add_to_query(query)


class Migration064(GraphMigration):
    name: str = "064_remove_generic_generate_template"
    minimum_version: int = 63
    queries: Sequence[type[Query]] = [
        RemoveGenericGenerateTemplateQuery,
        RemoveGenericGenerateTemplateSchemaAttributeQuery,
    ]

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()
