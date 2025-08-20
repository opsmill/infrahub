from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from infrahub.core.migrations.shared import MigrationResult
from infrahub.core.query import Query, QueryType

from ..shared import GraphMigration

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class Migration011Query01(Query):
    name = "migration_011_01"
    type: QueryType = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        query = """
        // get all the SchemaRelationship nodes for 'profiles' relationships
        MATCH (sr_to_delete:SchemaRelationship)-[HAS_ATTRIBUTE]->(:Attribute {name: "name"})-[HAS_VALUE]->(av:AttributeValue {value: "profiles"})
        // get the Relationship node for each 'profiles' SchemaRelationship
        MATCH (node_rel_to_delete:Relationship)-[IS_RELATED]-(sr_to_delete)
        WITH node_rel_to_delete, sr_to_delete
        // get all the Attributes and AttributeValues of the 'profiles' SchemaRelationships
        MATCH (sr_to_delete)-[HAS_ATTRIBUTE]->(attribute_to_delete:Attribute)-[HAS_VALUE]->(av_to_maybe_delete:AttributeValue)
        // detach delete the Relationship, SchemaRelationship, and Attribute nodes
        DETACH DELETE node_rel_to_delete, sr_to_delete, attribute_to_delete
        // delete the AttributeValue nodes from earlier that are not attached to anything
        WITH av_to_maybe_delete
        WHERE NOT EXISTS {
            MATCH (av_to_maybe_delete)-[]-()
        }
        DELETE av_to_maybe_delete
        """
        self.add_to_query(query)


class Migration011(GraphMigration):
    name: str = "011_remove_profiles_relationship_schemas"
    queries: Sequence[type[Query]] = [Migration011Query01]
    minimum_version: int = 10

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        result = MigrationResult()

        return result
