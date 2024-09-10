from typing import Any

from infrahub.core.query import Query, QueryType
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase

from ..model.path import TrackingId
from .filters import EnrichedDiffQueryFilters

QUERY_MATCH_NODES = """
    // get the roots of all diffs in the query
    MATCH (diff_root:DiffRoot)
    WHERE diff_root.base_branch = $base_branch
    AND diff_root.diff_branch IN $diff_branches
    AND diff_root.from_time >= $from_time
    AND diff_root.to_time <= $to_time
    AND ($tracking_id IS NULL OR diff_root.tracking_id = $tracking_id)
    AND ($diff_id IS NULL OR diff_root.uuid = $diff_id)
    WITH diff_root
    ORDER BY diff_root.base_branch, diff_root.diff_branch, diff_root.from_time, diff_root.to_time
    WITH diff_root.base_branch AS bb, diff_root.diff_branch AS db, collect(diff_root) AS same_branch_diff_roots
    WITH reduce(
        non_overlapping = [], dr in same_branch_diff_roots |
        CASE
            WHEN size(non_overlapping) = 0 THEN [dr]
            WHEN dr.from_time >= (non_overlapping[-1]).from_time AND dr.to_time <= (non_overlapping[-1]).to_time THEN non_overlapping
            WHEN (non_overlapping[-1]).from_time >= dr.from_time AND (non_overlapping[-1]).to_time <= dr.to_time THEN non_overlapping[..-1] + [dr]
            ELSE non_overlapping + [dr]
        END
    ) AS non_overlapping_diff_roots
    UNWIND non_overlapping_diff_roots AS diff_root
    // get all the nodes attached to the diffs
    OPTIONAL MATCH (diff_root)-[:DIFF_HAS_NODE]->(diff_node:DiffNode)
    """


class EnrichedDiffGetQuery(Query):
    """Get all EnrichedDiffRoots for the given branches that are within the given timeframe in chronological order"""

    name = "enriched_diff_get"
    type = QueryType.READ
    insert_limit = False

    def __init__(
        self,
        base_branch_name: str,
        diff_branch_names: list[str],
        filters: EnrichedDiffQueryFilters,
        max_depth: int,
        from_time: Timestamp | None = None,
        to_time: Timestamp | None = None,
        tracking_id: TrackingId | None = None,
        diff_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.base_branch_name = base_branch_name
        self.diff_branch_names = diff_branch_names
        self.from_time: Timestamp = from_time or Timestamp("2000-01-01T00:00:01Z")
        self.to_time: Timestamp = to_time or Timestamp()
        self.max_depth = max_depth
        self.tracking_id = tracking_id
        self.diff_id = diff_id
        self.filters = filters or EnrichedDiffQueryFilters()

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:
        self.params = {
            "base_branch": self.base_branch_name,
            "diff_branches": self.diff_branch_names,
            "from_time": self.from_time.to_string(),
            "to_time": self.to_time.to_string(),
            "tracking_id": self.tracking_id.serialize() if self.tracking_id else None,
            "diff_id": self.diff_id,
            "limit": self.limit,
            "offset": self.offset,
        }
        # ruff: noqa: E501
        self.add_to_query(query=QUERY_MATCH_NODES)

        if not self.filters.is_empty:
            filters, filter_params = self.filters.generate()
            self.params.update(filter_params)

            query_filters = """
            WHERE (
                %(filters)s
            )
            """ % {"filters": filters}
            self.add_to_query(query=query_filters)

        query_2 = """
        // group by diff node uuid for pagination
        WITH diff_node.uuid AS diff_node_uuid, diff_node.kind AS diff_node_kind, collect([diff_root, diff_node]) AS node_root_tuples
        // order by kind and latest label for each diff_node uuid
        CALL {
            WITH node_root_tuples
            UNWIND node_root_tuples AS nrt
            WITH nrt[0] AS diff_root, nrt[1] AS diff_node
            ORDER BY diff_root.from_time DESC
            RETURN diff_node.label AS latest_node_label
            LIMIT 1
        }
        WITH diff_node_kind, node_root_tuples, latest_node_label
        ORDER BY diff_node_kind, latest_node_label
        SKIP COALESCE($offset, 0)
        LIMIT $limit
        UNWIND node_root_tuples AS nrt
        WITH nrt[0] AS diff_root, nrt[1] AS diff_node
        WITH diff_root, diff_node
        // if depth limit, make sure not to exceed it when traversing linked nodes
        WITH diff_root, diff_node
        // -------------------------------------
        // Retrieve Parents
        // -------------------------------------
        CALL {
            WITH diff_node
            OPTIONAL MATCH parents_path = (diff_node)-[:DIFF_HAS_RELATIONSHIP|DIFF_HAS_NODE*1..%(max_depth)s]->(:DiffNode)
            RETURN parents_path
            ORDER BY size(nodes(parents_path)) DESC
            LIMIT 1
        }
        WITH diff_root, diff_node, parents_path
        // -------------------------------------
        // Retrieve conflicts
        // -------------------------------------
        OPTIONAL MATCH (diff_node)-[:DIFF_HAS_CONFLICT]->(diff_node_conflict:DiffConflict)
        WITH diff_root, diff_node, parents_path, diff_node_conflict
        // -------------------------------------
        // Retrieve Attributes
        // -------------------------------------
        CALL {
            WITH diff_node
            OPTIONAL MATCH (diff_node)-[:DIFF_HAS_ATTRIBUTE]->(diff_attribute:DiffAttribute)
            WITH diff_attribute
            OPTIONAL MATCH (diff_attribute)-[:DIFF_HAS_PROPERTY]->(diff_attr_property:DiffProperty)
            WITH diff_attribute, diff_attr_property
            OPTIONAL MATCH (diff_attr_property)-[:DIFF_HAS_CONFLICT]->(diff_attr_property_conflict:DiffConflict)
            RETURN diff_attribute, diff_attr_property, diff_attr_property_conflict
            ORDER BY diff_attribute.name, diff_attr_property.property_type
        }
        WITH diff_root, diff_node, parents_path, diff_node_conflict, collect([diff_attribute, diff_attr_property, diff_attr_property_conflict]) as diff_attributes
        // -------------------------------------
        // Retrieve Relationships
        // -------------------------------------
        CALL {
            WITH diff_node
            OPTIONAL MATCH (diff_node)-[:DIFF_HAS_RELATIONSHIP]->(diff_relationship:DiffRelationship)
            WITH diff_relationship
            OPTIONAL MATCH (diff_relationship)-[:DIFF_HAS_ELEMENT]->(diff_rel_element:DiffRelationshipElement)
            WITH diff_relationship, diff_rel_element
            OPTIONAL MATCH (diff_rel_element)-[:DIFF_HAS_CONFLICT]->(diff_rel_conflict:DiffConflict)
            WITH diff_relationship, diff_rel_element, diff_rel_conflict
            OPTIONAL MATCH (diff_rel_element)-[:DIFF_HAS_PROPERTY]->(diff_rel_property:DiffProperty)
            WITH diff_relationship, diff_rel_element, diff_rel_conflict, diff_rel_property
            OPTIONAL MATCH (diff_rel_property)-[:DIFF_HAS_CONFLICT]->(diff_rel_property_conflict:DiffConflict)

            RETURN diff_relationship, diff_rel_element, diff_rel_conflict, diff_rel_property, diff_rel_property_conflict
            ORDER BY diff_relationship.name, diff_rel_element.peer_id, diff_rel_property.property_type
        }
        WITH
            diff_root,
            diff_node,
            parents_path,
            diff_node_conflict,
            diff_attributes,
            collect([diff_relationship, diff_rel_element, diff_rel_conflict, diff_rel_property, diff_rel_property_conflict]) AS diff_relationships
        """ % {"max_depth": self.max_depth * 2}

        self.add_to_query(query=query_2)

        self.return_labels = [
            "diff_root",
            "diff_node",
            "parents_path",
            "diff_node_conflict",
            "diff_attributes",
            "diff_relationships",
        ]
        self.order_by = ["diff_root.diff_branch_name ASC", "diff_root.from_time ASC", "diff_node.label ASC"]
