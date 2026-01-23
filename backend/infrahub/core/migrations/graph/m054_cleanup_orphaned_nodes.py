from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from infrahub.core.migrations.shared import GraphMigration, MigrationInput, MigrationResult

from ...query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class CleanupOrphanedNodesQuery(Query):
    """
    Clean up orphaned Node vertices (no IS_PART_OF edge to Root) and their linked
    Attributes and Relationships.
    """

    name = "cleanup_orphaned_nodes"
    type = QueryType.WRITE
    insert_return = False
    raise_error_if_empty = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        query = """
// Delete attributes of orphaned nodes
MATCH (n:Node)
WHERE NOT exists((n)-[:IS_PART_OF]->(:Root))
OPTIONAL MATCH (n)-[:HAS_ATTRIBUTE]->(attr:Attribute)
WITH DISTINCT attr
CALL (attr) {
    DETACH DELETE attr
} IN TRANSACTIONS

// reduce the results to a single row
WITH 1 AS one
LIMIT 1

// Delete relationships that will have < 2 Node peers after orphaned node removal
OPTIONAL MATCH (orphan:Node)-[:IS_RELATED]-(rel:Relationship)
WHERE NOT exists((orphan)-[:IS_PART_OF]->(:Root))
WITH DISTINCT rel
CALL (rel) {
    OPTIONAL MATCH (rel)-[:IS_RELATED]-(peer:Node)
    WHERE exists((peer)-[:IS_PART_OF]->(:Root))
    WITH rel, count(peer) AS remaining_peers
    WHERE remaining_peers < 2
    DETACH DELETE rel
} IN TRANSACTIONS

// reduce the results to a single row
WITH 1 AS one
LIMIT 1

// Delete the orphaned nodes
MATCH (n:Node)
WHERE NOT exists((n)-[:IS_PART_OF]->(:Root))
CALL (n) {
    DETACH DELETE n
} IN TRANSACTIONS
        """
        self.add_to_query(query)


class Migration054(GraphMigration):
    """
    Clean up orphaned Node vertices that have no IS_PART_OF edge to Root.

    This can happen when a branch-aware node is deleted during branch deletion,
    but its branch-agnostic attributes or relationships are not properly cleaned up.

    The migration:
    1. DETACH DELETEs Attributes linked to orphaned nodes
    2. DETACH DELETEs Relationships that would have < 2 Node peers after orphaned node removal
    3. DETACH DELETEs the orphaned nodes themselves
    """

    name: str = "054_cleanup_orphaned_nodes"
    minimum_version: int = 53
    queries: Sequence[type[Query]] = [CleanupOrphanedNodesQuery]

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        # Override parent class to skip transaction in case there are many nodes to delete
        return await self.do_execute(migration_input=migration_input)
