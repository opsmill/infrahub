from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from infrahub.core.migrations.shared import GraphMigration, MigrationResult
from infrahub.log import get_logger

from ...query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

log = get_logger()


class DeduplicateRelationshipVerticesQuery(Query):
    """
    For each group of duplicate Relationships with the same UUID, delete any Relationship that meets the following criteria:
    - is linked to a deleted node (only if the delete time is before the Relationship's from time)
    - is linked to a node on an incorrect branch (ie Relationship added on main, but Node is on a branch)
    """

    name = "deduplicate_relationship_vertices"
    type = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        query = """
MATCH (root:Root)
WITH root.default_branch AS default_branch_name
// ------------
// Find all Relationship vertices with duplicate UUIDs
// ------------
MATCH (r:Relationship)
WITH r.uuid AS r_uuid, default_branch_name, count(*) AS num_dups
WHERE num_dups > 1
WITH DISTINCT r_uuid, default_branch_name
// ------------
// get the branched_from time for each relationship edge and node
// ------------
MATCH (rel:Relationship {uuid: r_uuid})
CALL (rel) {
    MATCH (rel)-[is_rel_e:IS_RELATED {status: "active"}]-(n:Node)
    MATCH (rel_branch:Branch {name: is_rel_e.branch})
    RETURN is_rel_e, rel_branch.branched_from AS rel_branched_from, n
}
// ------------
// for each IS_RELATED edge of the relationship, check the IS_PART_OF edges of the Node vertex
// to determine if this side of the relationship is legal
// ------------
CALL (n, is_rel_e, rel_branched_from, default_branch_name) {
    OPTIONAL MATCH (n)-[is_part_of_e:IS_PART_OF {status: "active"}]->(:Root)
    WHERE (
        // the Node's create time must precede the Relationship's create time
        is_part_of_e.from <= is_rel_e.from AND (is_part_of_e.to >= is_rel_e.from OR is_part_of_e.to IS NULL)
        // the Node must have been created on a branch of equal or lesser depth than the Relationship
        AND is_part_of_e.branch_level <= is_rel_e.branch_level
        // if the Node and Relationships were created on branch_level = 2, then they must be on the same branch
        AND (
            is_part_of_e.branch_level = 1
            OR is_part_of_e.branch = is_rel_e.branch
        )
        // if the Node was created on the default branch, and the Relationship was created on a branch,
        // then the Node must have been created after the branched_from time of the Relationship's branch
        AND (
            is_part_of_e.branch <> default_branch_name
            OR is_rel_e.branch_level = 1
            OR is_part_of_e.from <= rel_branched_from
        )
    )
    WITH is_part_of_e IS NOT NULL AS is_legal
    ORDER BY is_legal DESC
    RETURN is_legal
    LIMIT 1
}
WITH rel, is_legal
ORDER BY rel, is_legal ASC
WITH rel, head(collect(is_legal)) AS is_legal
WHERE is_legal = false
DETACH DELETE rel
        """
        self.add_to_query(query)


class Migration033(GraphMigration):
    """
    Identifies duplicate Relationship vertices that have the same UUID property. Deletes any duplicates that
    are linked to deleted nodes or nodes on in incorrect branch.
    """

    name: str = "033_deduplicate_relationship_vertices"
    minimum_version: int = 32
    queries: Sequence[type[Query]] = [DeduplicateRelationshipVerticesQuery]

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        result = MigrationResult()
        return result
