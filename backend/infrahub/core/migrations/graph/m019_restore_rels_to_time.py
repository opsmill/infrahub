from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from infrahub.core.migrations.shared import GraphMigration, MigrationResult
from infrahub.log import get_logger

from ...constants import GLOBAL_BRANCH_NAME
from ...query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

log = get_logger()


class FixBranchAwareEdgesQuery(Query):
    name = "replace_global_edges"
    type = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:
        """
        Between a Node and a Relationship, if Relationship.branch_support=aware, replace any global edge
        to the branch of a non-global edge leaving out of the Relationship node. Note that there can't
        be multiple non-global branches on these edges, as a dedicated Relationship node would exist for that.
        """

        query = """
        MATCH (node:Node)-[global_edge:IS_RELATED {branch: $global_branch}]-(rel:Relationship)
        MATCH (rel)-[non_global_edge:IS_RELATED]-(node_2: Node)
        WHERE non_global_edge.branch <> $global_branch
        SET global_edge.branch = non_global_edge.branch
        """

        params = {"global_branch": GLOBAL_BRANCH_NAME}
        self.params.update(params)
        self.add_to_query(query)


class SetMissingToTimeQuery(Query):
    name = "set_missing_to_time"
    type = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:
        """
        If both a deleted edge and an active edge with no time exist between 2 nodes on the same branch,
        set `to` time of active edge using `from` time of the deleted one. This would typically happen after having
        replaced a deleted edge on global branch by correct branch with above query.
        """

        query = """
        MATCH (node:Node)-[deleted_edge:IS_RELATED {status: "deleted"}]-(rel:Relationship)
        MATCH (rel)-[active_edge:IS_RELATED {status: "active"}]-()
        WHERE active_edge.to IS NULL AND deleted_edge.branch = active_edge.branch
        SET active_edge.to = deleted_edge.from
        """

        params = {"global_branch": GLOBAL_BRANCH_NAME}
        self.params.update(params)
        self.add_to_query(query)


class DeleteNodesRelsQuery(Query):
    name = "delete_relationships_of_deleted_nodes"
    type = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:
        """
        Some nodes may have been deleted while having corrupted state that are fixes by above migrations.
        While these nodes edges connected to Root are correctly deleted,
        edges connected to other `Node` through a `Relationship` node may still be active.
        Following query correctly deletes these edges by both setting correct to time and creating corresponding deleted edge.
        """

        query = """
        MATCH (deleted_node: CoreStandardGroup)-[deleted_edge:IS_PART_OF {status: "deleted"}]->(:Root)
        MATCH (deleted_node)-[:IS_RELATED]-(rel:Relationship)

        // Set to time if there is an active edge on deleted edge branch
        OPTIONAL MATCH (rel)-[peer_active_edge:IS_RELATED {status: "active"}]-(peer_1: Node)
        WHERE peer_active_edge.branch = deleted_edge.branch AND peer_active_edge.to IS NULL
        SET peer_active_edge.to = deleted_edge.from

        // Check if deleted edge exists on this branch between Relationship and any peer_2 Node connected. Create it if it doesn't.
        WITH deleted_edge.branch AS branch, deleted_edge.branch_level AS branch_level, deleted_edge.from as deleted_time, rel
        MATCH (rel)-[:IS_RELATED]-(peer_2:Node)
        CALL {
            WITH rel, peer_2, branch
            OPTIONAL MATCH (rel)-[r:IS_RELATED {branch: branch}]-(peer_2)
            WHERE r.status = "deleted"
            RETURN r IS NOT NULL AS has_deleted_edge
        }

        // The branch on which `deleted` edge might be created depends on Relationship.branch_support
        WITH branch, branch_level, deleted_time, rel, has_deleted_edge, peer_2
        WHERE has_deleted_edge = FALSE  // only look at rel-peer_2 couples not having a deleted edge
        OPTIONAL MATCH (rel)-[active_edge:IS_RELATED {status: "active"}]-(peer_3: Node)
        WHERE active_edge.branch IS NOT NULL
        WITH rel, active_edge, peer_3,
             CASE
               WHEN rel.branch_support = "agnostic" THEN $global_branch
               WHEN rel.branch_support = "aware" THEN COALESCE(active_edge.branch, NULL)
               ELSE NULL  // Ending up here means there is no active branch between rel its peer Node,
                          // so there must be a deleted edge already, and thus we will not create one.
             END AS branch,
             branch_level,
             deleted_time,
             peer_2

        // Need 2 calls to create the edge in the correct direction. Also note that MERGE ensures we do not create multiple times.
        CALL {
            WITH rel, peer_2, branch, branch_level, deleted_time
            MATCH (rel)-[:IS_RELATED]->(peer_2)
            MERGE (rel)-[:IS_RELATED {status: "deleted", branch: branch, branch_level: branch_level, from: deleted_time}]->(peer_2)
        }
        CALL {
            WITH rel, peer_2, branch, branch_level, deleted_time
            MATCH (rel)<-[:IS_RELATED]-(peer_2)
            MERGE (rel)<-[:IS_RELATED {status: "deleted", branch: branch, branch_level: branch_level, from: deleted_time}]-(peer_2)
        }
        """

        params = {"global_branch": GLOBAL_BRANCH_NAME}
        self.params.update(params)
        self.add_to_query(query)


class Migration019(GraphMigration):
    """
    Fix corrupted state introduced by Migration012 when duplicating a CoreAccount (branch Aware)
    being part of a CoreStandardGroup (branch Agnostic). Database is corrupted at multiple points:
    - Old CoreAccount node <> group_member node `active` edge has no `to` time (possibly because of #5590).
    - Old CoreAccount node <> group_member node `deleted` edge is on `-global-` branch instead of `main`.
    - New CoreAccount node <> group_member node `active` edge is on `-global-` branch instead of `main`.

    Also, users having deleted corresponding CoreStandardGroup will also have the following data corruption,
    as deletion did not happen correctly due to above issues:
    - Both CoreAccount <> group_member and CoreStandardGroup <> group_member edges
      have not been deleted (ie status is `active` without `to` time and no additional `deleted` edge).

    This migration fixes all above issues to have consistent edges, and fixes IFC-1204.
    """

    name: str = "019_fix_edges_state"
    minimum_version: int = 18
    queries: Sequence[type[Query]] = [FixBranchAwareEdgesQuery, SetMissingToTimeQuery, DeleteNodesRelsQuery]

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:
        result = MigrationResult()
        return result
