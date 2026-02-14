from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from infrahub.core.migrations.shared import MigrationResult
from infrahub.core.query import Query, QueryType

from ..shared import GraphMigration

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class LinkOpenProposedChangesToDiffRootsQuery(Query):
    """
    Link open proposed changes to their DiffRoots.

    For open PCs, find DiffRoots where:
    - diff_branch matches the PC's source_branch
    - is_merged IS NULL (not yet merged)
    """

    name = "link_open_proposed_changes_to_diff_roots"
    type: QueryType = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        query = """
        // Find all proposed changes
        MATCH (pc:CoreProposedChange)

        // Get the latest active state value using a subquery
        CALL (pc) {
            MATCH (pc)-[:HAS_ATTRIBUTE]->(state_attr:Attribute {name: "state"})
                -[state_hv:HAS_VALUE]->(state_val:AttributeValue)
            WHERE state_hv.status = "active"
            AND state_hv.to IS NULL
            RETURN state_val.value AS state_value
            ORDER BY state_hv.from DESC
            LIMIT 1
        }
        // Filter to only open proposed changes
        WITH pc, state_value
        WHERE state_value = "open"

        // Get the latest active source_branch value using a subquery
        CALL (pc) {
            MATCH (pc)-[:HAS_ATTRIBUTE]->(sb_attr:Attribute {name: "source_branch"})
                -[sb_hv:HAS_VALUE]->(sb_val:AttributeValue)
            WHERE sb_hv.status = "active"
            AND sb_hv.to IS NULL
            RETURN sb_val.value AS source_branch
            ORDER BY sb_hv.from DESC
            LIMIT 1
        }

        // Find DiffRoots that match this source_branch and are not merged
        MATCH (diff_root:DiffRoot)
        WHERE diff_root.diff_branch = source_branch
        AND diff_root.tracking_id = "branch." + source_branch
        AND (diff_root.is_merged IS NULL OR diff_root.is_merged <> TRUE)

        // Create the edge if it doesn't exist
        MERGE (diff_root)-[:DIFF_FOR_PROPOSED_CHANGE]->(pc)

        // Also link the partner DiffRoot if it exists
        WITH diff_root, pc
        MATCH (diff_root)-[:DIFF_HAS_PARTNER]-(partner:DiffRoot)
        MERGE (partner)-[:DIFF_FOR_PROPOSED_CHANGE]->(pc)
        """
        self.add_to_query(query)


class LinkMergedProposedChangesToDiffRootsQuery(Query):
    """
    Link merged proposed changes to their DiffRoots.

    For merged PCs, find DiffRoots where:
    - diff_branch matches the PC's source_branch
    - is_merged = TRUE
    - to_time falls within the time window of the PC's state transitions
      (from "merging" to "merged")
    """

    name = "link_merged_proposed_changes_to_diff_roots"
    type: QueryType = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        query = """
        // Find all proposed changes
        MATCH (pc:CoreProposedChange)

        // Get the latest active state value and its from timestamp using a subquery
        CALL (pc) {
            MATCH (pc)-[:HAS_ATTRIBUTE]->(state_attr:Attribute {name: "state"})
                -[state_hv:HAS_VALUE]->(state_val:AttributeValue)
            WHERE state_hv.status = "active"
            AND state_hv.to IS NULL
            RETURN state_val.value AS state_value, state_hv.from AS merged_time
            ORDER BY state_hv.from DESC
            LIMIT 1
        }
        // Filter to only merged proposed changes
        WITH pc, state_value, merged_time
        WHERE state_value = "merged"

        // Get the latest active source_branch value using a subquery
        CALL (pc) {
            MATCH (pc)-[:HAS_ATTRIBUTE]->(sb_attr:Attribute {name: "source_branch"})
                -[sb_hv:HAS_VALUE]->(sb_val:AttributeValue)
            WHERE sb_hv.status = "active"
            AND sb_hv.to IS NULL
            RETURN sb_val.value AS source_branch
            ORDER BY sb_hv.from DESC
            LIMIT 1
        }

        // Find the time when the state became "merging" (start of merge window)
        CALL (pc) {
            MATCH (pc)-[:HAS_ATTRIBUTE]->(state_attr:Attribute {name: "state"})
                -[merging_hv:HAS_VALUE]->(merging_val:AttributeValue)
            WHERE merging_val.value = "merging"
            RETURN merging_hv.from AS merging_time
            ORDER BY merging_hv.from DESC
            LIMIT 1
        }

        // Use the merging time as start of window, merged time as end
        // If no merging state found, use merged time as both start and end
        WITH pc, source_branch,
             COALESCE(merging_time, merged_time) AS merge_window_start,
             merged_time AS merge_window_end

        // Find DiffRoots that match this source_branch and are merged
        // with to_time within the merge window
        MATCH (diff_root:DiffRoot)
        WHERE diff_root.diff_branch = source_branch
        AND diff_root.is_merged = TRUE
        AND diff_root.tracking_id = "branch." + source_branch
        AND diff_root.to_time >= merge_window_start
        AND diff_root.to_time <= merge_window_end

        // Create the edge if it doesn't exist
        MERGE (diff_root)-[:DIFF_FOR_PROPOSED_CHANGE]->(pc)

        // Also link the partner DiffRoot if it exists
        WITH diff_root, pc
        MATCH (diff_root)-[:DIFF_HAS_PARTNER]-(partner:DiffRoot)
        MERGE (partner)-[:DIFF_FOR_PROPOSED_CHANGE]->(pc)
        """
        self.add_to_query(query)


class Migration058(GraphMigration):
    name: str = "058_link_proposed_changes_to_diff_roots"
    minimum_version: int = 57
    queries: Sequence[type[Query]] = [
        LinkOpenProposedChangesToDiffRootsQuery,
        LinkMergedProposedChangesToDiffRootsQuery,
    ]

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()
