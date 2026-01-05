from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from infrahub.core.migrations.shared import GraphMigration, MigrationResult

from ...query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class CleanupOrphanedRelationshipsQuery(Query):
    name = "cleanup_orphaned_relationships"
    type = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        query = """
MATCH (rel:Relationship)-[:IS_RELATED]-(peer:Node)
WITH DISTINCT rel, peer.uuid AS p_uuid
WITH rel, count(*) AS num_peers
WHERE num_peers < 2
DETACH DELETE rel
        """
        self.add_to_query(query)


class Migration035(GraphMigration):
    """
    Remove Relationship vertices that only have a single peer
    """

    name: str = "035_clean_up_orphaned_relationships"
    minimum_version: int = 34
    queries: Sequence[type[Query]] = [CleanupOrphanedRelationshipsQuery]

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    async def execute(self, db: InfrahubDatabase) -> MigrationResult:
        # overrides parent class to skip transaction in case there are a lot of relationships to delete
        return await self.do_execute(db=db)
