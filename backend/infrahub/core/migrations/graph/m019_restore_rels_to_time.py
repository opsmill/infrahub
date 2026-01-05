from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from infrahub.core.migrations.shared import GraphMigration, MigrationResult
from infrahub.log import get_logger

from ...constants import GLOBAL_BRANCH_NAME, BranchSupportType
from ...query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

log = get_logger()


class FixBranchAwareEdgesQuery(Query):
    name = "replace_global_edges"
    type = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        """
        Between a Node and a Relationship, if Relationship.branch_support=aware, replace any global edge
        to the branch of a non-global edge leaving out of the Relationship node. Note that there can't
        be multiple non-global branches on these edges, as a dedicated Relationship node would exist for that.
        """

        query = """
        MATCH (node:Node)-[global_edge:IS_RELATED {branch: $global_branch}]-(rel:Relationship)
        WHERE rel.branch_support=$branch_aware
        MATCH (rel)-[non_global_edge:IS_RELATED]-(node_2: Node)
        WHERE non_global_edge.branch <> $global_branch
        SET global_edge.branch = non_global_edge.branch
        """

        params = {
            "global_branch": GLOBAL_BRANCH_NAME,
            "branch_aware": BranchSupportType.AWARE.value,
            "branch_agnostic": BranchSupportType.AGNOSTIC.value,
        }

        self.params.update(params)
        self.add_to_query(query)


class SetMissingToTimeQuery(Query):
    name = "set_missing_to_time"
    type = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        """
        If both a deleted edge and an active edge with no time exist between 2 nodes on the same branch,
        set `to` time of active edge using `from` time of the deleted one. This would typically happen after having
        replaced a deleted edge on global branch by correct branch with above query.
        """

        query = """
        MATCH (node:Node)-[deleted_edge:IS_RELATED {status: "deleted"}]-(rel:Relationship)
        MATCH (rel)-[active_edge:IS_RELATED {status: "active"}]-(node)
        WHERE active_edge.to IS NULL AND deleted_edge.branch = active_edge.branch
        SET active_edge.to = deleted_edge.from
        """

        self.add_to_query(query)


class DeleteNodesRelsQuery(Query):
    name = "delete_relationships_of_deleted_nodes"
    type = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        """
        Some nodes may have been incorrectly deleted, typically, while these nodes edges connected to Root
        are correctly deleted, edges connected to other `Node` through a `Relationship` node may still be active.
        Following query correctly deletes these edges by both setting correct to time and creating corresponding deleted edge.
        """

        query = """
        MATCH (deleted_node: Node)-[deleted_edge:IS_PART_OF {status: "deleted"}]->(:Root)
        MATCH (deleted_node)-[:IS_RELATED]-(rel:Relationship)

        // exclude nodes having been deleted through migration. find those with same uuid and exclude the one with earlier
        // timestamp on active branch
        WHERE NOT EXISTS {
          MATCH (deleted_node)-[e1:IS_RELATED]-(rel)-[e2:IS_RELATED]-(other_node)
          WITH deleted_node, other_node, MIN(e1.from) AS min_e1_from, MIN(e2.from) AS min_e2_from
          WHERE deleted_node <> other_node AND deleted_node.uuid = other_node.uuid AND min_e1_from < min_e2_from
        }

        // Note that if an AWARE node has been deleted on a branch and relationship is AGNOSTIC, we do not "delete" this relationship
        // right now as this aware node might exist on another branch.

        // Set to time if there is an active edge:
        // - on deleted edge branch
        // - or on any branch and deleted node is agnostic
        // - or deleted node is aware and rel is agnostic
        CALL (rel, deleted_edge) {
            OPTIONAL MATCH (rel)-[peer_active_edge {status: "active"}]-(peer_1)
            WHERE (peer_active_edge.branch = deleted_edge.branch OR (rel.branch_support <> $branch_agnostic AND deleted_edge.branch = $global_branch))
            AND peer_active_edge.to IS NULL
            SET peer_active_edge.to = deleted_edge.from
        }

        // Get distinct rel nodes linked to a deleted node, with the time at which we should delete rel edges.
        // Take the MAX time so if it does not take the deleted time of a node deleted through a duplication migration.
        WITH DISTINCT rel,
            deleted_edge.branch AS deleted_edge_branch,
            deleted_edge.branch_level AS branch_level,
            MAX(deleted_edge.from) as deleted_time,
            deleted_node.branch_support as deleted_node_branch_support


        // No need to check deleted edge branch because
        // If deleted_node has different branch support type (agnostic/aware) than rel type,
        // there might already be a deleted edge that we would not match if we filter on deleted_edge_branch.
        // If both are aware, it still works, as we would have one Relationship node for each branch on which this relationship exists.
        MATCH (rel)-[]-(peer_2)
        WHERE NOT exists((rel)-[{status: "deleted"}]-(peer_2))


        // If res is agnostic and delete node is agnostic, we should delete on global branch
        // If rel is aware and deleted node is aware, we should use deleted edge branch
        // If rel is aware and delete node is agnostic, we need to create deleted edges for every distinct branch on which this relationship exists.
        WITH DISTINCT
            CASE
                // Branch on which `deleted` edge should be created depends on rel.branch_support.
                WHEN rel.branch_support = $branch_agnostic
                THEN CASE
                    WHEN deleted_node_branch_support = $branch_agnostic THEN [$global_branch]
                    ELSE []
                END
                ELSE
                CASE
                    WHEN deleted_node_branch_support = $branch_agnostic
                    THEN COLLECT {
                        WITH rel
                        MATCH (rel)-[active_edge {status: "active"}]-(peer_2)
                        RETURN DISTINCT active_edge.branch
                    }
                    ELSE
                    CASE
                        // if no active edge on this branch exists it means this relationship node is dedicated for another branch
                        WHEN exists((rel)-[{status: "active", branch: deleted_edge_branch}]-(peer_2)) THEN [deleted_edge_branch]
                        ELSE []
                    END
                END
            END AS branches,
          branch_level,
          deleted_time,
          peer_2,
          rel

        UNWIND branches as branch

        // Then creates `deleted` edge.
        // Below CALL subqueries are called once for each rel-peer_2 pair for which we want to create a deleted edge.
        // Note that with current infrahub relationships edges design, only one of this CALL should be matched per pair.

        CALL (rel, peer_2, branch, branch_level, deleted_time) {
            MATCH (rel)-[:IS_RELATED]->(peer_2)
            MERGE (rel)-[:IS_RELATED {status: "deleted", branch: branch, branch_level: branch_level, from: deleted_time}]->(peer_2)
        }

        CALL (rel, peer_2, branch, branch_level, deleted_time) {
            MATCH (rel)-[:IS_PROTECTED]->(peer_2)
            MERGE (rel)-[:IS_PROTECTED {status: "deleted", branch: branch, branch_level: branch_level, from: deleted_time}]->(peer_2)
        }

        CALL (rel, peer_2, branch, branch_level, deleted_time) {
            MATCH (rel)-[:IS_VISIBLE]->(peer_2)
            MERGE (rel)-[:IS_VISIBLE {status: "deleted", branch: branch, branch_level: branch_level, from: deleted_time}]->(peer_2)
        }

        CALL (rel, peer_2, branch, branch_level, deleted_time) {
            MATCH (rel)-[:HAS_OWNER]->(peer_2)
            MERGE (rel)-[:HAS_OWNER {status: "deleted", branch: branch, branch_level: branch_level, from: deleted_time}]->(peer_2)
        }

        CALL (rel, peer_2, branch, branch_level, deleted_time) {
            MATCH (rel)-[:HAS_SOURCE]->(peer_2)
            MERGE (rel)-[:HAS_SOURCE {status: "deleted", branch: branch, branch_level: branch_level, from: deleted_time}]->(peer_2)
        }

        CALL (rel, peer_2, branch, branch_level, deleted_time) {
            MATCH (rel)<-[:IS_RELATED]-(peer_2)
            MERGE (rel)<-[:IS_RELATED {status: "deleted", branch: branch, branch_level: branch_level, from: deleted_time}]-(peer_2)
        }

        CALL (rel, peer_2, branch, branch_level, deleted_time) {
            MATCH (rel)<-[:IS_PROTECTED]-(peer_2)
            MERGE (rel)<-[:IS_PROTECTED {status: "deleted", branch: branch, branch_level: branch_level, from: deleted_time}]-(peer_2)
        }

        CALL (rel, peer_2, branch, branch_level, deleted_time) {
            MATCH (rel)<-[:IS_VISIBLE]-(peer_2)
            MERGE (rel)<-[:IS_VISIBLE {status: "deleted", branch: branch, branch_level: branch_level, from: deleted_time}]-(peer_2)
        }

        CALL (rel, peer_2, branch, branch_level, deleted_time) {
            MATCH (rel)<-[:HAS_OWNER]-(peer_2)
            MERGE (rel)<-[:HAS_OWNER {status: "deleted", branch: branch, branch_level: branch_level, from: deleted_time}]-(peer_2)
        }

        CALL (rel, peer_2, branch, branch_level, deleted_time) {
            MATCH (rel)<-[:HAS_SOURCE]-(peer_2)
            MERGE (rel)<-[:HAS_SOURCE {status: "deleted", branch: branch, branch_level: branch_level, from: deleted_time}]-(peer_2)
        }
        """

        params = {
            "global_branch": GLOBAL_BRANCH_NAME,
            "branch_aware": BranchSupportType.AWARE.value,
            "branch_agnostic": BranchSupportType.AGNOSTIC.value,
        }

        self.params.update(params)
        self.add_to_query(query)


class Migration019(GraphMigration):
    """
    Fix corrupted state introduced by Migration012 when duplicating a CoreAccount (branch Aware)
    being part of a CoreStandardGroup (branch Agnostic). Database is corrupted at multiple points:
    - Old CoreAccount node <> group_member node `active` edge has no `to` time (possibly because of #5590).
    - Old CoreAccount node <> group_member node `deleted` edge is on `$global_branch` branch instead of `main`.
    - New CoreAccount node <> group_member node `active` edge is on `$global_branch` branch instead of `main`.

    Also, users having deleted corresponding CoreStandardGroup will also have the following data corruption,
    as deletion did not happen correctly due to above issues:
    - Both CoreAccount <> group_member and CoreStandardGroup <> group_member edges
      have not been deleted (ie status is `active` without `to` time and no additional `deleted` edge).

    This migration fixes all above issues to have consistent edges, and fixes IFC-1204.
    """

    name: str = "019_fix_edges_state"
    minimum_version: int = 18
    queries: Sequence[type[Query]] = [FixBranchAwareEdgesQuery, SetMissingToTimeQuery, DeleteNodesRelsQuery]

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        result = MigrationResult()
        return result
