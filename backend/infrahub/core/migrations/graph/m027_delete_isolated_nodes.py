from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from infrahub.core.migrations.shared import GraphMigration, MigrationResult
from infrahub.log import get_logger

from ...query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

log = get_logger()


class DeleteIsolatedNodesQuery(Query):
    name = "delete_isolated_nodes_query"
    type = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        query = """
        MATCH p = (s: Node)-[r]-(d)
        WHERE NOT exists((s)-[:IS_PART_OF]-(:Root))
        DELETE r

        WITH p
        UNWIND nodes(p) AS n
        MATCH (n)
        WHERE NOT exists((n)--())
        DELETE n
        """
        self.add_to_query(query)


class Migration027(GraphMigration):
    """
    While deleting a branch containing some allocated nodes from a resource pool, relationship
    between pool node and resource node might be agnostic (eg: for IPPrefixPool) and incorrectly deleted,
    resulting in a node still linked to the resource pool but not linked to Root anymore.
    This query deletes nodes not linked to Root and their relationships (supposed to be agnostic).
    """

    name: str = "027_deleted_isolated_nodes"
    minimum_version: int = 26
    queries: Sequence[type[Query]] = [DeleteIsolatedNodesQuery]

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        result = MigrationResult()
        return result
