from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from infrahub.core.migrations.shared import MigrationResult
from infrahub.core.query import Query, QueryType

from ..shared import GraphMigration

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class SchemaRelationshipCleanupQuery(Query):
    name = "schema_relationship_cleanup"
    type: QueryType = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        query = """
        // ---------------------------------------------------------------
        // Find all "profiles" and "object_template" SchemaRelationship nodes,
        // plus any SchemaRelationship with no parent SchemaNode/SchemaGeneric
        // ---------------------------------------------------------------
        CALL {
            MATCH (sr:SchemaRelationship)-[:HAS_ATTRIBUTE]->(:Attribute {name: "name"})
                  -[:HAS_VALUE]->(av:AttributeValue)
            WHERE av.value IN ["profiles", "object_template"]
            RETURN sr
            UNION
            MATCH (sr:SchemaRelationship)
            WHERE NOT EXISTS {
                MATCH (sr)-[:IS_RELATED]-(:Relationship {name: "schema__node__relationships"})
            }
            RETURN sr
        }
        WITH DISTINCT sr AS sr_to_delete

        // ---------------------------------------------------------------
        // Collect any connected Relationship vertices for cleanup
        // ---------------------------------------------------------------
        OPTIONAL MATCH (rel_to_delete:Relationship)-[:IS_RELATED]-(sr_to_delete)

        // ---------------------------------------------------------------
        // Collect all Attributes and AttributeValues for cleanup
        // ---------------------------------------------------------------
        MATCH (sr_to_delete)-[:HAS_ATTRIBUTE]->(attribute_to_delete:Attribute)-[:HAS_VALUE]->(av_to_maybe_delete:AttributeValue)
        DETACH DELETE rel_to_delete, sr_to_delete, attribute_to_delete

        // ---------------------------------------------------------------
        // Delete orphaned AttributeValue nodes
        // ---------------------------------------------------------------
        WITH DISTINCT av_to_maybe_delete
        WHERE NOT EXISTS {
            MATCH (av_to_maybe_delete)-[]-()
        }
        DELETE av_to_maybe_delete
        """
        self.add_to_query(query)


class Migration058(GraphMigration):
    name: str = "058_remove_virtual_schema_relationships"
    queries: Sequence[type[Query]] = [SchemaRelationshipCleanupQuery]
    minimum_version: int = 57

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()
