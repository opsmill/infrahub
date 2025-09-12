from typing import Any

from infrahub.core.query import Query, QueryType
from infrahub.database import InfrahubDatabase

from ..model.path import TrackingId


class DiffFieldsSummaryCountsEnricherQuery(Query):
    """Update summary counters for the attributes and relationshipsin in a diff"""

    name = "diff_fields_summary_count_enricher"
    type = QueryType.WRITE
    insert_return = False

    def __init__(
        self,
        diff_branch_name: str,
        tracking_id: TrackingId | None = None,
        diff_id: str | None = None,
        node_uuids: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        if (diff_id is None and tracking_id is None) or (diff_id and tracking_id):
            raise ValueError(
                "DiffFieldsSummaryCountsEnricherQuery requires one and only one of `tracking_id` or `diff_id`"
            )
        self.diff_branch_name = diff_branch_name
        self.tracking_id = tracking_id
        self.diff_id = diff_id
        if self.tracking_id is None and self.diff_id is None:
            raise RuntimeError("tracking_id or diff_id is required")
        self.node_uuids = node_uuids

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params = {
            "diff_branch_name": self.diff_branch_name,
            "diff_id": self.diff_id,
            "tracking_id": self.tracking_id.serialize() if self.tracking_id else None,
            "node_uuids": self.node_uuids,
        }
        query = """
MATCH (root:DiffRoot)
WHERE ($diff_id IS NOT NULL AND root.uuid = $diff_id)
OR ($tracking_id IS NOT NULL AND root.tracking_id = $tracking_id AND root.diff_branch = $diff_branch_name)
MATCH (root)-[:DIFF_HAS_NODE]->(dn:DiffNode)
WHERE $node_uuids IS NULL OR dn.uuid IN $node_uuids
CALL (dn) {
    // ----------------------
    // handle attribute count updates
    // ----------------------
    MATCH (dn)-[:DIFF_HAS_ATTRIBUTE]->(da:DiffAttribute)
    CALL (da) {
        OPTIONAL MATCH (da)-[:DIFF_HAS_PROPERTY]->(dp:DiffProperty)-[:DIFF_HAS_CONFLICT]->(dc:DiffConflict)
        WITH count(dc) AS num_conflicts
        SET da.num_conflicts = num_conflicts
        SET da.contains_conflict = (num_conflicts > 0)
    }
    CALL (da) {
        OPTIONAL MATCH (da)-[:DIFF_HAS_PROPERTY]->(dp:DiffProperty {action: "added"})
        WITH count(dp.action) AS num_added
        SET da.num_added = num_added
    }
    CALL (da) {
        OPTIONAL MATCH (da)-[:DIFF_HAS_PROPERTY]->(dp:DiffProperty {action: "updated"})
        WITH count(dp.action) AS num_updated
        SET da.num_updated = num_updated
    }
    CALL (da) {
        OPTIONAL MATCH (da)-[:DIFF_HAS_PROPERTY]->(dp:DiffProperty {action: "removed"})
        WITH count(dp.action) AS num_removed
        SET da.num_removed = num_removed
    }
}
CALL (dn) {
    MATCH (dn)-[:DIFF_HAS_RELATIONSHIP]->(dr:DiffRelationship)
    CALL (dr) {
        // ----------------------
        // handle relationship element count updates
        // ----------------------
        MATCH (dr)-[:DIFF_HAS_ELEMENT]->(dre:DiffRelationshipElement)
        CALL (dre) {
            OPTIONAL MATCH (dre)-[*..4]->(dc:DiffConflict)
            WITH count(dc) AS num_conflicts
            SET dre.num_conflicts = num_conflicts
            SET dre.contains_conflict = (num_conflicts > 0)
        }
        CALL (dre) {
            OPTIONAL MATCH (dre)-[:DIFF_HAS_PROPERTY]->(dp:DiffProperty {action: "added"})
            WITH count(dp.action) AS num_added
            SET dre.num_added = num_added
        }
        CALL (dre) {
            OPTIONAL MATCH (dre)-[:DIFF_HAS_PROPERTY]->(dp:DiffProperty {action: "updated"})
            WITH count(dp.action) AS num_updated
            SET dre.num_updated = num_updated
        }
        CALL (dre) {
            OPTIONAL MATCH (dre)-[:DIFF_HAS_PROPERTY]->(dp:DiffProperty {action: "removed"})
            WITH count(dp.action) AS num_removed
            SET dre.num_removed = num_removed
        }
    }
    // ----------------------
    // handle relationship count updates
    // ----------------------
    OPTIONAL MATCH (dr)-[:DIFF_HAS_ELEMENT]->(conflict_dre:DiffRelationshipElement {contains_conflict: TRUE})
    WITH dr, sum(conflict_dre.num_conflicts) AS num_conflicts
    SET dr.num_conflicts = num_conflicts
    SET dr.contains_conflict = (num_conflicts > 0)
    WITH dr
    CALL (dr) {
        OPTIONAL MATCH (dr)-[:DIFF_HAS_ELEMENT]->(dre:DiffRelationshipElement {action: "added"})
        WITH count(dre.action) AS num_added
        SET dr.num_added = num_added
    }
    CALL (dr) {
        OPTIONAL MATCH (dr)-[:DIFF_HAS_ELEMENT]->(dre:DiffRelationshipElement {action: "updated"})
        WITH count(dre.action) AS num_updated
        SET dr.num_updated = num_updated
    }
    CALL (dr) {
        OPTIONAL MATCH (dr)-[:DIFF_HAS_ELEMENT]->(dre:DiffRelationshipElement {action: "removed"})
        WITH count(dre.action) AS num_removed
        SET dr.num_removed = num_removed
    }
}
        """
        self.add_to_query(query)


class DiffNodesSummaryCountsEnricherQuery(Query):
    """Update summary counters for the nodes and root in a diff"""

    name = "diff_nodes_summary_count_enricher"
    type = QueryType.WRITE
    insert_return = False

    def __init__(
        self,
        diff_branch_name: str,
        tracking_id: TrackingId | None = None,
        diff_id: str | None = None,
        node_uuids: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        if (diff_id is None and tracking_id is None) or (diff_id and tracking_id):
            raise ValueError(
                "DiffNodesSummaryCountsEnricherQuery requires one and only one of `tracking_id` or `diff_id`"
            )
        self.diff_branch_name = diff_branch_name
        self.tracking_id = tracking_id
        self.diff_id = diff_id
        if self.tracking_id is None and self.diff_id is None:
            raise RuntimeError("tracking_id or diff_id is required")
        self.node_uuids = node_uuids

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params = {
            "diff_branch_name": self.diff_branch_name,
            "diff_id": self.diff_id,
            "tracking_id": self.tracking_id.serialize() if self.tracking_id else None,
            "node_uuids": self.node_uuids,
        }

        query = """
MATCH (root:DiffRoot)
WHERE ($diff_id IS NOT NULL AND root.uuid = $diff_id)
OR ($tracking_id IS NOT NULL AND root.tracking_id = $tracking_id AND root.diff_branch = $diff_branch_name)
MATCH (root)-[:DIFF_HAS_NODE]->(dn:DiffNode)
WHERE $node_uuids IS NULL OR dn.uuid IN $node_uuids
// ----------------------
// handle node count updates
// ----------------------
WITH root, dn, coalesce(dn.num_conflicts, 0) AS previous_num_conflicts
CALL (dn) {
    // ----------------------
    // handle node num_conflicts update
    // ----------------------
    OPTIONAL MATCH (dn)-[:DIFF_HAS_ATTRIBUTE]->(da:DiffAttribute {contains_conflict: TRUE})
    RETURN sum(da.num_conflicts) AS num_conflicts
    UNION ALL
    OPTIONAL MATCH (dn)-[:DIFF_HAS_RELATIONSHIP]->(dr:DiffRelationship {contains_conflict: TRUE})
    RETURN sum(dr.num_conflicts) AS num_conflicts
    UNION ALL
    OPTIONAL MATCH (dn)-[:DIFF_HAS_CONFLICT]->(dc:DiffConflict)
    RETURN count(dc) AS num_conflicts
}
WITH root, dn, previous_num_conflicts, sum(num_conflicts) AS updated_num_conflicts
SET dn.num_conflicts = updated_num_conflicts
SET dn.contains_conflict = (updated_num_conflicts > 0)
WITH root, dn, updated_num_conflicts - previous_num_conflicts AS num_conflicts_delta
CALL (dn) {
    // ----------------------
    // handle node added/updated/removed updates
    // ----------------------
    OPTIONAL MATCH (dn)-[:DIFF_HAS_ATTRIBUTE]->(da:DiffAttribute)
    WITH collect(da.action) AS attr_actions
    OPTIONAL MATCH (dn)-[:DIFF_HAS_RELATIONSHIP]->(dr:DiffRelationship)
    WITH attr_actions, collect(dr.action) AS rel_actions
    WITH attr_actions + rel_actions AS actions
    WITH reduce(counts = [0,0,0], a IN actions |
        CASE
            WHEN a = "added" THEN [counts[0] + 1, counts[1], counts[2]]
            WHEN a = "updated" THEN [counts[0], counts[1] + 1, counts[2]]
            WHEN a = "removed" THEN [counts[0], counts[1], counts[2] + 1]
            ELSE counts
        END
    ) AS action_counts
    WITH action_counts[0] AS num_added, action_counts[1] AS num_updated, action_counts[2] AS num_removed
    SET dn.num_added = num_added
    SET dn.num_updated = num_updated
    SET dn.num_removed = num_removed
}
// ----------------------
// handle conflict updates for parent nodes
// ----------------------
WITH root, dn, num_conflicts_delta
CALL (dn, num_conflicts_delta) {
    OPTIONAL MATCH (dn)-[:DIFF_HAS_RELATIONSHIP|DIFF_HAS_NODE*1..]->(parent_node:DiffNode)
    SET parent_node.num_conflicts = parent_node.num_conflicts + num_conflicts_delta
    SET parent_node.contains_conflict = (parent_node.num_conflicts > 0)
}
// ----------------------
// handle root count updates
// ----------------------
WITH root, sum(num_conflicts_delta) AS total_conflicts_delta
CALL (root, total_conflicts_delta) {
    SET root.num_conflicts = coalesce(root.num_conflicts, 0) + total_conflicts_delta
    SET root.contains_conflict = root.num_conflicts > 0
    WITH root
    OPTIONAL MATCH (root)-[:DIFF_HAS_NODE]->(dn:DiffNode {action: "added"})
    WITH root, count(dn.action) AS num_added
    SET root.num_added = num_added
    WITH root
    OPTIONAL MATCH (root)-[:DIFF_HAS_NODE]->(dn:DiffNode {action: "updated"})
    WITH root, count(dn.action) AS num_updated
    SET root.num_updated = num_updated
    WITH root
    OPTIONAL MATCH (root)-[:DIFF_HAS_NODE]->(dn:DiffNode {action: "removed"})
    WITH root, count(dn.action) AS num_removed
    SET root.num_removed = num_removed
}
        """
        self.add_to_query(query)
