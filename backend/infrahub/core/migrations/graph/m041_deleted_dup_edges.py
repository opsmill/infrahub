from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rich import print as rprint

from infrahub.core.branch import Branch
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import get_root_node
from infrahub.core.migrations.shared import MigrationResult
from infrahub.core.query import Query, QueryType
from infrahub.dependencies.registry import build_component_registry, get_component_registry
from infrahub.log import get_logger

from ..shared import ArbitraryMigration

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

log = get_logger()


class DeletePosthumousEdges(Query):
    name = "delete_posthumous_edges_query"
    type = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
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
CALL (added_e) {
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
        """
        self.add_to_query(query)


class DeleteDuplicateEdgesForMigratedKindNodes(Query):
    name = "delete_duplicate_edges_for_migrated_kind_nodes_query"
    type = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        query = """
// ------------
// get UUIDs for migrated kind/inheritance nodes
// ------------
MATCH (n:Node)
WITH n.uuid AS node_uuid, count(*) AS num_nodes_with_uuid
WHERE num_nodes_with_uuid > 1
CALL (node_uuid) {
    // ------------
    // find any Relationships for these nodes
    // ------------
    MATCH (n:Node {uuid: node_uuid})-[:IS_RELATED]-(rel:Relationship)
    WITH DISTINCT rel
    MATCH (rel)-[e]->(peer)
    WITH
        type(e) AS e_type,
        e.branch AS e_branch,
        e.from AS e_from,
        e.to AS e_to,
        e.status AS e_status,
        e.peer AS e_peer,
        CASE
            WHEN startNode(e) = rel THEN "out" ELSE "in"
        END AS direction,
        collect(e) AS duplicate_edges
    WHERE size(duplicate_edges) > 1
    WITH tail(duplicate_edges) AS duplicate_edges_to_delete
    UNWIND duplicate_edges_to_delete AS edge_to_delete
    DELETE edge_to_delete
} IN TRANSACTIONS OF 500 ROWS
        """
        self.add_to_query(query)


class Migration041(ArbitraryMigration):
    """Clean up improper merges that duplicated edges to nodes with migrated kinds

    - delete all existing diffs b/c they could contain incorrect nodes linking to deleted nodes with migrated kind/inheritance
    - delete all edges added to any nodes AFTER they were deleted on main
    - delete any duplicate edges touching migrated kind/inheritance nodes on main
    """

    name: str = "041_deleted_dup_edges"
    minimum_version: int = 40

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        result = MigrationResult()

        return result

    async def execute(self, db: InfrahubDatabase) -> MigrationResult:
        root_node = await get_root_node(db=db)
        default_branch_name = root_node.default_branch
        default_branch = await Branch.get_by_name(db=db, name=default_branch_name)

        rprint("Deleting all diffs", end="...")
        build_component_registry()
        component_registry = get_component_registry()
        diff_repo = await component_registry.get_component(DiffRepository, db=db, branch=default_branch)
        await diff_repo.delete_all_diff_roots()
        rprint("done")

        rprint("Deleting edges merged after node deleted", end="...")
        delete_posthumous_edges_query = await DeletePosthumousEdges.init(db=db)
        await delete_posthumous_edges_query.execute(db=db)
        rprint("done")

        rprint("Deleting duplicate edges for migrated kind/inheritance nodes", end="...")
        delete_duplicate_edges_query = await DeleteDuplicateEdgesForMigratedKindNodes.init(db=db)
        await delete_duplicate_edges_query.execute(db=db)
        rprint("done")

        return MigrationResult()
