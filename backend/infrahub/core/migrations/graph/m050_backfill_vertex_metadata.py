from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from infrahub.core.migrations.shared import MigrationResult
from infrahub.core.query import Query, QueryType

from ..shared import GraphMigration, MigrationInput

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class BackfillAttributeMetadataQuery(Query):
    """Backfill created_at and updated_at for Attribute vertices on default/global branches.

    - created_at = from time of HAS_ATTRIBUTE edge
    - updated_at = latest from or to time of any non-HAS_ATTRIBUTE edge
    """

    name = "backfill_attribute_metadata"
    type: QueryType = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        query = """
        // Find all Attribute vertices on default/global branch without created_at
        MATCH (:Node)-[ha:HAS_ATTRIBUTE {status: "active"}]->(attr:Attribute)
        WHERE ha.branch_level = 1
        AND attr.created_at IS NULL

        // created_at = from time of HAS_ATTRIBUTE edge
        WITH DISTINCT attr, ha.from AS created_at

        // Find latest change time from all non-HAS_ATTRIBUTE edges (both from and to)
        CALL (attr) {
            MATCH (attr)-[e]->()
            WHERE e.branch_level = 1
            WITH e.from AS change_time
            WHERE change_time IS NOT NULL
            RETURN change_time
            UNION ALL
            MATCH (attr)-[e]->()
            WHERE e.branch_level = 1
            AND e.to IS NOT NULL
            RETURN e.to AS change_time
        }
        WITH attr, created_at, max(change_time) AS updated_at

        // Set metadata (use coalesce to fall back to created_at if no changes found)
        CALL (attr, created_at, updated_at) {
            SET attr.created_at = created_at
            SET attr.updated_at = coalesce(updated_at, created_at)
        } IN TRANSACTIONS
        """
        self.add_to_query(query)


class BackfillRelationshipMetadataQuery(Query):
    """Backfill created_at and updated_at for Relationship vertices on default/global branches.

    - created_at = earliest from time of any IS_RELATED edge
    - updated_at = latest from or to time of any non-IS_RELATED edge
    """

    name = "backfill_relationship_metadata"
    type: QueryType = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        query = """
        // Find all Relationship vertices on default/global branch without created_at
        MATCH (:Node)-[ir:IS_RELATED]-(rel:Relationship)
        WHERE ir.branch_level = 1
        AND rel.created_at IS NULL
        WITH DISTINCT rel

        // created_at = earliest IS_RELATED edge from time
        CALL (rel) {
            MATCH ()-[ir:IS_RELATED]-(rel)
            WHERE ir.branch_level = 1
            RETURN min(ir.from) AS created_at
        }

        // Find latest change time from all non-IS_RELATED edges (both from and to)
        CALL (rel) {
            MATCH (rel)-[e:!IS_RELATED]-()
            WHERE e.branch_level = 1
            WITH e.from AS change_time
            WHERE change_time IS NOT NULL
            RETURN change_time
            UNION ALL
            MATCH (rel)-[e:!IS_RELATED]-()
            WHERE e.branch_level = 1
            AND e.to IS NOT NULL
            RETURN e.to AS change_time
        }
        WITH rel, created_at, max(change_time) AS updated_at

        // Set metadata (use coalesce to fall back to created_at if no changes found)
        CALL (rel, created_at, updated_at) {
            SET rel.created_at = created_at
            SET rel.updated_at = coalesce(updated_at, created_at)
        } IN TRANSACTIONS
        """
        self.add_to_query(query)


class BackfillNodeMetadataQuery(Query):
    """Backfill created_at and updated_at for Node vertices on default/global branches.

    - created_at = earliest from time of any IS_PART_OF edge for Nodes with this UUID
    - updated_at = latest updated_at from any linked Attribute or Relationship

    Must run after BackfillAttributeMetadataQuery and BackfillRelationshipMetadataQuery
    since Node.updated_at depends on field updated_at values.
    """

    name = "backfill_node_metadata"
    type: QueryType = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        query = """
        // Find all Node vertices on default/global branch without created_at
        MATCH (n:Node)-[e:IS_PART_OF]->(:Root)
        WHERE e.branch_level = 1
        AND n.created_at IS NULL
        WITH DISTINCT n

        // created_at = earliest IS_PART_OF edge from time for this UUID
        // (handles migrated kind/namespace where multiple Node vertices share same UUID)
        CALL (n) {
            MATCH (:Node {uuid: n.uuid})-[ip:IS_PART_OF]->(:Root)
            WHERE ip.branch_level = 1
            RETURN min(ip.from) AS created_at
        }

        // updated_at = latest updated_at from any linked Attribute or Relationship
        CALL (n) {
            MATCH (n)-[:HAS_ATTRIBUTE|IS_RELATED]-(field:Attribute|Relationship)
            WHERE field.updated_at IS NOT NULL
            RETURN max(field.updated_at) AS latest_field_update
        }

        // Set metadata (use coalesce to fall back to created_at if no field updates found)
        CALL (n, created_at, latest_field_update) {
            SET n.created_at = created_at
            SET n.updated_at = coalesce(latest_field_update, created_at)
        } IN TRANSACTIONS
        """
        self.add_to_query(query)


class Migration050(GraphMigration):
    name: str = "050_backfill_vertex_metadata"
    minimum_version: int = 49
    queries: Sequence[type[Query]] = [
        BackfillAttributeMetadataQuery,  # Run first
        BackfillRelationshipMetadataQuery,  # Run second
        BackfillNodeMetadataQuery,  # Run last (depends on Attr/Rel updated_at)
    ]

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        return await self.do_execute(migration_input=migration_input)
