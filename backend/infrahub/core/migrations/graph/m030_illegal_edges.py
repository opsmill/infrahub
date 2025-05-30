from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from infrahub.core.migrations.shared import GraphMigration, MigrationResult
from infrahub.log import get_logger

from ...query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

log = get_logger()


class DeletePosthumousEdges(Query):
    name = "delete_posthumous_edges_query"
    type = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        query = """
// ------------
// find deleted nodes
// ------------
MATCH (n:Node)-[e:IS_PART_OF]->(:Root)
WHERE e.status = "deleted" OR e.to IS NOT NULL
WITH DISTINCT n, e.branch AS delete_branch, e.branch_level AS delete_branch_level, CASE
    WHEN e.status = "deleted" THEN e.from
    ELSE e.to
END AS delete_time
// ------------
// find the edges added to the deleted node after the delete time
// ------------
MATCH (n)-[added_e]-(peer)
WHERE added_e.from > delete_time
AND type(added_e) <> "IS_PART_OF"
// if the node was deleted on a branch (delete_branch_level > 1), and then updated on main/global (added_e.branch_level = 1), we can ignore it
AND added_e.branch_level >= delete_branch_level
AND (added_e.branch = delete_branch OR delete_branch_level = 1)
WITH DISTINCT n, delete_branch, delete_time, added_e, peer
// ------------
// get the branched_from for the branch on which the node was deleted
// ------------
CALL {
    WITH added_e
    MATCH (b:Branch {name: added_e.branch})
    RETURN b.branched_from AS added_e_branched_from
}
// ------------
// account for the following situations, given that the edge update time is after the node delete time
//  - deleted on main/global, updated on branch
//    - illegal if the delete is before branch.branched_from
//  - deleted on branch, updated on branch
//    - illegal
// ------------
WITH n, delete_branch, delete_time, added_e, peer
WHERE delete_branch = added_e.branch
OR delete_time < added_e_branched_from
DELETE added_e
// --------------
// the peer _should_ only be an Attribute, but I want to make sure we don't
// inadvertently delete Root or an AttributeValue or a Boolean
// --------------
WITH peer
WHERE "Attribute" IN labels(peer)
DETACH DELETE peer
        """
        self.add_to_query(query)


class Migration030(GraphMigration):
    """
    Edges could have been added to Nodes after the Node was deleted, so we need to hard-delete those illegal edges
    """

    name: str = "030_delete_illegal_edges"
    minimum_version: int = 29
    queries: Sequence[type[Query]] = [DeletePosthumousEdges]

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        result = MigrationResult()
        return result
