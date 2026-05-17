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
// Match all affected nodes, accounting for nodes with migrated kind
// for each UUID, get the latest Node that was active on this branch
// --------------------
UNWIND $node_uuids AS node_uuid
CALL (node_uuid) {
    MATCH (n:Node {uuid: node_uuid})-[e:IS_PART_OF]->(:Root)
    WHERE e.branch IN [$target_branch, $global_branch]
    AND (
        (e.branch = $target_branch AND (e.from <= $branched_from OR e.from = $at))
        OR (e.branch = $global_branch AND e.from <= $at)
    )
    RETURN n, e AS is_part_of_e
    ORDER BY e.from DESC, e.status ASC
    LIMIT 1
}
// --------------------
// Special handling for the new version of a migrated kind/inheritance Node
// set updated_at/by to the time/user that created the new version of the Node
// --------------------
CALL (n, is_part_of_e) {
    WITH n, is_part_of_e
    WHERE n.updated_at IS NULL
    SET n.updated_at = is_part_of_e.from, n.updated_by = is_part_of_e.from_user_id
}
// --------------------
// Get all the Attributes and Relationships for this Node that were active on this branch at some point
// --------------------
MATCH (n)-[e:HAS_ATTRIBUTE|IS_RELATED]-(field:Attribute|Relationship)
WHERE e.branch IN [$source_branch, $target_branch, $global_branch]
AND (
    (e.branch = $target_branch AND e.from <= $branched_from)
    OR (e.branch IN [$source_branch, $global_branch] AND e.from <= $at)
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
// Update Node metadata with latest change across all its fields
// ------------------------------------
WITH n, node_updated_by
WHERE node_updated_by IS NOT NULL
SET n.previous_updated_at = n.updated_at, n.previous_updated_by = n.updated_by
SET n.updated_at = $at, n.updated_by = node_updated_by
        """
        self.add_to_query(query=query)
