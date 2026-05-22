from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


class DiffMergeMetadataQuery(Query):
    """Set metadata properties on Nodes, Attributes, and Relationships included in this merge.

    Each Node, Attribute, and Relationship should have its current updated_at/by (if it exists) saved in the
    previous_updated_at/by properties to support a rollback.
    For Attributes and Relationships (let's call them fields), set updated_by to the user_id of the latest change on
        the field on the branch being merged
    For Nodes, set the updated_by to the user_id of the latest change on any associated fields on this branch
    For Nodes, Attributes, and Relationships, set updated_at to the merge time.

    The logic in pseudocode
        For each Node we care about:
        a. For each Attribute/Relationship (let's call them "fields") linked to the Node
            i. filter to only fields updated on the source branch
            ii. previous_updated_at/by = updated_at/by
            iii. identify the latest update and set updated_by = the associated user_id
            iv. set updated_at = $at
        b. set Node.updated_by to the user_id associated with the latest change of ALL the Node's fields
        c. set Node.updated_at = $at
    """

    name = "merge_metadata"
    type = QueryType.WRITE
    insert_return = False

    def __init__(
        self,
        node_uuids: list[str],
        at: Timestamp,
        target_branch: Branch,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.node_uuids = node_uuids
        self.at = at
        self.target_branch = target_branch

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params = {
            "node_uuids": self.node_uuids,
            "at": self.at.to_string(),
            "target_branch": self.target_branch.name,
            "source_branch": self.branch.name,
            "global_branch": GLOBAL_BRANCH_NAME,
            "branched_from": self.branch.get_branched_from(),
        }
        query = """
// --------------------
// Match all affected Node vertices for each UUID, including post-migration
// siblings created by a target-branch migration after the source branch was
// forked. A UUID can map to more than one Node vertex when migrated, and the
// merge can have touched edges on more than one of those vertices; we want
// to refresh metadata on each. For each Node, pick its "best" IS_PART_OF
// (latest ``from``, prefer active before deleted) to anchor the
// updated_at/by fallback for newly-created vertices.
// --------------------
UNWIND $node_uuids AS node_uuid
MATCH (n:Node {uuid: node_uuid})
// --------------------
// Exclude Node vertices on the target branch that have previously been deleted
// as part of a node kind/inheritance migration
// --------------------
WHERE NOT EXISTS {
    MATCH (n)-[migrated_out:IS_PART_OF {branch: $target_branch, status: "deleted"}]->(:Root)
    WHERE migrated_out.from < $at AND migrated_out.to IS NULL
}
CALL (n) {
    // get add or delete IS_PART_OF edge if it exists
    OPTIONAL MATCH (n)-[e:IS_PART_OF]->(:Root)
    WHERE e.branch IN [$target_branch, $global_branch]
    AND (
        // pre-fork edge, edge created by the merge, or edge closed by the merge
        (e.branch = $target_branch AND (e.from <= $branched_from OR e.from = $at OR e.to = $at))
        OR (e.branch = $global_branch AND e.from <= $at)
    )
    WITH e
    ORDER BY e.from DESC, e.status ASC
    LIMIT 1
    RETURN e AS is_part_of_e
}
// --------------------
// Node-level metadata refresh for added and deleted Node vertices
//   - ADDED - ``updated_at``/``by`` on freshly-created Node vertices that the
//     merge just inserted (their IS_PART_OF has ``from = $at``).
//   - DELETED - ``updated_at``/``by`` on Node vertices whose IS_PART_OF was
//     closed by the merge (``to = $at``). This is required to cover Nodes with
//     their kind/inheritance migrated on the target branch then deleted in the merge
// --------------------
CALL (n, is_part_of_e) {
    WITH n, is_part_of_e
    WHERE n.updated_at IS NULL OR n.updated_at <> $at
    WITH n, is_part_of_e, CASE
        WHEN is_part_of_e.from = $at THEN is_part_of_e.from_user_id
        WHEN is_part_of_e.to = $at THEN is_part_of_e.to_user_id
        ELSE NULL
    END AS ipo_user_id
    WHERE ipo_user_id IS NOT NULL
    SET n.previous_updated_at = n.updated_at, n.previous_updated_by = n.updated_by
    SET n.updated_at = $at, n.updated_by = ipo_user_id
}
// --------------------
// Get all the Attributes and Relationships for this Node that were active on
// this branch at some point
// --------------------
MATCH (n)-[e:HAS_ATTRIBUTE|IS_RELATED]-(field:Attribute|Relationship)
WHERE e.branch IN [$source_branch, $target_branch, $global_branch]
AND (
    (e.branch = $target_branch AND (e.from <= $branched_from OR e.from = $at OR e.to = $at))
    OR (e.branch IN [$source_branch, $global_branch] AND e.from <= $at)
    // include any fields updated as part of this merge to cover the case where
    // a Node had its kind migrated on the default branch after the user branch forked
    OR exists((field)-[{branch: $target_branch, from: $at}]-())
    OR exists((field)-[{branch: $target_branch, to: $at}]-())
)

// --------------------
// For each field, only include it if it has an update at $at on the target branch
// to prevent updating metadata for conflicts in which the base branch version was accepted
// --------------------
WITH DISTINCT n, field
WHERE exists((field)-[{branch: $target_branch, from: $at}]-())
OR exists((field)-[{branch: $target_branch, to: $at}]-())

// --------------------
// For each changed field, find the latest time and user_id that updated it on the source branch
// Check both from (creation) and to (deletion) timestamps
// Prefer non-system users (those not starting with "__")
// --------------------
CALL (field) {
    // ignore HAS_ATTRIBUTE and IS_RELATED b/c these show when an Attribute/Relationship was created/deleted
    // not when it was updated
    MATCH ()-[edge:!HAS_ATTRIBUTE&!IS_RELATED {branch: $source_branch}]-(field)
    WHERE edge.from <= $at
    // Collect both from and to timestamps as potential "change times"
    WITH edge,
         edge.from AS from_time,
         edge.from_user_id AS from_user,
         edge.to AS to_time,
         edge.to_user_id AS to_user
    // Create rows for each type of change
    UNWIND [
        CASE WHEN from_time <= $at THEN {time: from_time, user_id: from_user} ELSE NULL END,
        CASE WHEN to_time IS NOT NULL AND to_time <= $at THEN {time: to_time, user_id: to_user} ELSE NULL END
    ] AS change
    WITH change WHERE change IS NOT NULL AND change.user_id IS NOT NULL
    // Sort by time DESC, then prefer non-system users (is_system ASC puts false before true)
    WITH change.user_id AS change_user_id, change.time AS change_time, change.user_id STARTS WITH "__" AS is_system
    RETURN change_user_id, change_time
    ORDER BY change_time DESC, is_system ASC
    LIMIT 1
}

// Save current field values for rollback, then update field metadata
WITH n, field, change_user_id, change_time
WHERE change_user_id IS NOT NULL
// --------------------
// make sure not to set the previous_updated_at multiple times
// --------------------
CALL (field, change_user_id) {
    WITH field
    WHERE field.updated_at <> $at OR field.updated_at IS NULL
    SET field.previous_updated_at = field.updated_at, field.previous_updated_by = field.updated_by
    SET field.updated_at = $at, field.updated_by = change_user_id
}

// Aggregate to find the latest change across all fields for Node-level metadata
WITH n, change_user_id, change_time, change_user_id STARTS WITH "__" AS is_system
ORDER BY change_time DESC, is_system ASC
WITH n, collect(change_user_id)[0] AS node_updated_by

// ------------------------------------
// Update Node metadata with latest change across all its fields.
// Skip setting ``previous_updated_at`` if the IS_PART_OF-driven refresh
// above already moved ``updated_at`` to ``$at`` — otherwise we'd clobber
// the real ``previous_updated_at`` it captured.
// ------------------------------------
WITH n, node_updated_by
WHERE node_updated_by IS NOT NULL
CALL (n) {
    WITH n
    WHERE n.updated_at IS NULL OR n.updated_at <> $at
    SET n.previous_updated_at = n.updated_at, n.previous_updated_by = n.updated_by
}
SET n.updated_at = $at, n.updated_by = node_updated_by
        """
        self.add_to_query(query=query)
