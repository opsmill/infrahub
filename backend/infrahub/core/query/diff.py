from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generator

from infrahub import config
from infrahub.core.constants import GLOBAL_BRANCH_NAME, BranchSupportType, DiffAction, RelationshipStatus
from infrahub.core.query import Query, QueryType
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.diff.model.field_specifiers_map import NodeFieldSpecifierMap
    from infrahub.database import InfrahubDatabase


class DiffQuery(Query):
    branch_names: list[str]
    diff_from: Timestamp
    diff_to: Timestamp
    type: QueryType = QueryType.READ

    def __init__(
        self,
        branch: Branch,
        diff_from: Timestamp | str = None,
        diff_to: Timestamp | str = None,
        **kwargs,
    ):
        """A diff is always in the context of a branch"""

        if not diff_from and branch.is_default:
            raise ValueError("diff_from is mandatory when the diff is on the main branch.")

        # If diff from hasn't been provided, we'll use the creation of the branch as the starting point
        if diff_from:
            self.diff_from = Timestamp(diff_from)
        else:
            self.diff_from = Timestamp(branch.created_at)

        # If Diff_to is not defined it will automatically select the current time.
        self.diff_to = Timestamp(diff_to)

        if self.diff_to < self.diff_from:
            raise ValueError("diff_to must be later than diff_from")

        self.branch_names = branch.get_branches_in_scope()

        super().__init__(branch, **kwargs)


class DiffCountChanges(Query):
    name = "diff_count_changes"
    type = QueryType.READ

    def __init__(
        self,
        branch_names: list[str],
        diff_from: Timestamp,
        diff_to: Timestamp,
        **kwargs,
    ):
        self.branch_names = branch_names
        self.diff_from = diff_from
        self.diff_to = diff_to
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs) -> None:  # noqa: ARG002
        self.params = {
            "from_time": self.diff_from.to_string(),
            "to_time": self.diff_to.to_string(),
            "branch_names": self.branch_names,
        }
        query = """
        MATCH (p)-[diff_rel]-(q)
        WHERE any(l in labels(p) WHERE l in ["Node", "Attribute", "Relationship"])
        AND diff_rel.branch in $branch_names
        AND (
            (diff_rel.from >= $from_time AND diff_rel.from < $to_time)
            OR (diff_rel.to >= $to_time AND diff_rel.to < $to_time)
        )
        AND (p.branch_support = "aware" OR q.branch_support = "aware")
        WITH diff_rel.branch AS branch_name, count(*) AS num_changes
        """
        self.add_to_query(query=query)
        self.return_labels = ["branch_name", "num_changes"]

    def get_num_changes_by_branch(self) -> dict[str, int]:
        branch_count_map = {}
        for result in self.get_results():
            branch_name = str(result.get("branch_name"))
            try:
                count = int(result.get("num_changes"))
            except (TypeError, ValueError):
                count = 0
            branch_count_map[branch_name] = count
        for branch_name in self.branch_names:
            if branch_name not in branch_count_map:
                branch_count_map[branch_name] = 0
        return branch_count_map


class DiffCalculationQuery(DiffQuery):
    type = QueryType.READ
    insert_limit = False

    def __init__(
        self,
        base_branch: Branch,
        diff_branch_from_time: Timestamp,
        current_node_field_specifiers: NodeFieldSpecifierMap | None = None,
        new_node_field_specifiers: NodeFieldSpecifierMap | None = None,
        **kwargs: Any,
    ):
        self.base_branch = base_branch
        self.diff_branch_from_time = diff_branch_from_time
        self.current_node_field_specifiers = current_node_field_specifiers
        self.new_node_field_specifiers = new_node_field_specifiers

        super().__init__(**kwargs)

    previous_base_path_query = """
WITH DISTINCT diff_path AS diff_path, has_more_data
CALL (diff_path) {
    WITH nodes(diff_path) AS d_nodes, relationships(diff_path) AS d_rels
    WITH d_rels[0] AS r_root, d_nodes[1] AS n, d_rels[1] AS r_node, d_nodes[2] AS attr_rel, d_rels[2] AS r_prop
    // -------------------------------------
    // add base branch paths before branched_from, if they exist
    // -------------------------------------
    WITH n, attr_rel, r_node, r_prop
    // 'base_n' instead of 'n' here to get previous value for node with a migrated kind/inheritance
    OPTIONAL MATCH latest_base_path = (:Root)<-[base_r_root:IS_PART_OF {branch: $base_branch_name}]
        -(base_n {uuid: n.uuid})-[base_r_node {branch: $base_branch_name}]
        -(attr_rel)-[base_r_prop {branch: $base_branch_name}]->(base_prop)
    WHERE type(base_r_node) = type(r_node)
    AND type(base_r_prop) = type(r_prop)
    AND [%(id_func)s(base_n), type(base_r_node)] <> [%(id_func)s(base_prop), type(base_r_prop)]
    AND all(
        r in relationships(latest_base_path)
        WHERE r.from < $branch_from_time
    )
    // ------------------------
    // special handling for nodes that had their kind updated,
    // the migration leaves two nodes with the same UUID linked to the same Relationship
    // ------------------------
    AND (
        base_n.uuid IS NULL OR base_prop.uuid IS NULL OR base_n.uuid <> base_prop.uuid
        OR type(base_r_node) <> "IS_RELATED" OR type(base_r_prop) <> "IS_RELATED"
    )
    WITH latest_base_path, base_r_root, base_r_node, base_r_prop
    ORDER BY base_r_prop.from DESC, base_r_node.from DESC, base_r_root.from DESC
    LIMIT 1
    RETURN latest_base_path
}
    """
    relationship_peer_side_query = """
WITH diff_path, latest_base_path, has_more_data
UNWIND [diff_path, latest_base_path] AS penultimate_path
WITH DISTINCT penultimate_path, has_more_data
CALL (penultimate_path) {
    WITH nodes(penultimate_path) AS d_nodes, relationships(penultimate_path) AS d_rels
    WITH d_rels[0] AS r_root, d_nodes[1] AS n, d_rels[1] AS r_node, d_nodes[2] AS attr_rel, d_rels[2] AS r_prop
    // -------------------------------------
    // Add peer-side of any relationships to get the peer's ID
    // -------------------------------------
    WITH r_root, n, r_node, attr_rel, r_prop
    OPTIONAL MATCH peer_path = (
        (:Root)<-[peer_r_root:IS_PART_OF]-(n)-[peer_r_node:IS_RELATED]-(attr_rel:Relationship)-[r_peer:IS_RELATED]-(peer:Node)
    )
    WHERE type(r_prop) <> "IS_RELATED"
    AND %(id_func)s(peer_r_root) = %(id_func)s(r_root)
    AND %(id_func)s(peer_r_node) = %(id_func)s(r_node)
    AND [%(id_func)s(n), type(peer_r_node)] <> [%(id_func)s(peer), type(r_peer)]
    AND r_peer.from < $to_time
    // filter out paths where an earlier from time follows a later from time
    AND peer_r_node.from <= r_peer.from
    // filter out paths where a base branch edge follows a branch edge
    AND (peer_r_node.branch = $base_branch_name OR r_peer.branch = $branch_name)
    // filter out paths where an active edge follows a deleted edge
    AND (peer_r_node.status = "active" OR r_peer.status = "deleted")
    // require adjacent edge pairs to have overlapping times, but only if on the same branch
    AND (
        peer_r_node.branch <> r_peer.branch
        OR peer_r_node.to IS NULL
        OR peer_r_node.to >= r_peer.from
    )
    // ------------------------
    // special handling for nodes that had their kind updated,
    // the migration leaves two nodes with the same UUID linked to the same Relationship
    // ------------------------
    AND (n.uuid IS NULL OR peer.uuid IS NULL OR n.uuid <> peer.uuid)
    WITH peer_path, r_peer, r_prop
    ORDER BY r_peer.branch = r_prop.branch DESC, r_peer.status = r_prop.status DESC, r_peer.from DESC, r_peer.status ASC
    LIMIT 1
    RETURN peer_path
}
WITH penultimate_path, peer_path, has_more_data
WITH reduce(
    diff_rel_paths = [], item IN [penultimate_path, peer_path] |
    CASE WHEN item IS NULL THEN diff_rel_paths ELSE diff_rel_paths + [item] END
) AS diff_rel_paths, has_more_data
// ------------------------
// make sure we still include has_more_data if diff_rel_paths is empty
// ------------------------
WITH CASE
    WHEN diff_rel_paths = [] THEN [NULL]
    ELSE diff_rel_paths
END AS diff_rel_paths, has_more_data
    """

    def get_previous_base_path_query(self, db: InfrahubDatabase) -> str:
        return self.previous_base_path_query % {"id_func": db.get_id_function_name()}

    def get_relationship_peer_side_query(self, db: InfrahubDatabase) -> str:
        return self.relationship_peer_side_query % {"id_func": db.get_id_function_name()}

    def get_params(self) -> dict[str, Any]:
        from_str = self.diff_from.to_string()
        return {
            "base_branch_name": self.base_branch.name,
            "branch_name": self.branch.name,
            "global_branch_name": GLOBAL_BRANCH_NAME,
            "branch_from_time": self.diff_branch_from_time.to_string(),
            "from_time": from_str,
            "to_time": self.diff_to.to_string(),
            "branch_local": BranchSupportType.LOCAL.value,
            "branch_aware": BranchSupportType.AWARE.value,
            "branch_agnostic": BranchSupportType.AGNOSTIC.value,
            "limit": self.limit or config.SETTINGS.database.query_size_limit,
            "offset": self.offset or 0,
        }


class DiffNodePathsQuery(DiffCalculationQuery):
    name = "diff_node_paths"

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        params_dict = self.get_params()
        self.params.update(params_dict)
        self.params.update(
            {
                "new_node_ids_list": self.new_node_field_specifiers.get_uuids_list()
                if self.new_node_field_specifiers
                else None,
                "current_node_ids_list": self.current_node_field_specifiers.get_uuids_list()
                if self.current_node_field_specifiers
                else None,
            }
        )
        nodes_path_query = """
// -------------------------------------
// Identify nodes added/removed on branch
// -------------------------------------
MATCH (q:Root)<-[diff_rel:IS_PART_OF {branch: $branch_name}]-(p:Node)
WHERE (
    ($new_node_ids_list IS NOT NULL AND p.uuid IN $new_node_ids_list)
    OR ($current_node_ids_list IS NOT NULL AND p.uuid IN $current_node_ids_list)
    OR ($new_node_ids_list IS NULL AND $current_node_ids_list IS NULL)
)
AND p.branch_support = $branch_aware
AND (
    (
        ($new_node_ids_list IS NOT NULL AND p.uuid IN $new_node_ids_list)
        AND (
            ($branch_from_time <= diff_rel.from < $to_time AND (diff_rel.to IS NULL OR diff_rel.to > $to_time))
            OR ($branch_from_time <= diff_rel.to < $to_time)
        )
    )
    OR (
        (
            ($current_node_ids_list IS NOT NULL AND p.uuid IN $current_node_ids_list)
            OR ($current_node_ids_list IS NULL AND $new_node_ids_list IS NULL)
        )
        AND (
            ($from_time <= diff_rel.from < $to_time AND (diff_rel.to IS NULL OR diff_rel.to > $to_time))
            OR ($from_time <= diff_rel.to < $to_time)
        )
    )
)
// -------------------------------------
// Limit the number of nodes
// -------------------------------------
WITH p, q, diff_rel, CASE
    WHEN $new_node_ids_list IS NOT NULL AND p.uuid IN $new_node_ids_list THEN $branch_from_time
    ELSE $from_time
END AS row_from_time
ORDER BY %(id_func)s(p) DESC
SKIP $offset
LIMIT $limit
// -------------------------------------
// Add flag to indicate if there is more data after this
// -------------------------------------
WITH collect([p, q, diff_rel, row_from_time]) AS limited_results
WITH limited_results, size(limited_results) = $limit AS has_more_data
UNWIND limited_results AS one_result
WITH one_result[0] AS p, one_result[1] AS q, one_result[2] AS diff_rel, one_result[3] AS row_from_time, has_more_data
// -------------------------------------
// Exclude nodes added then removed on branch within timeframe
// -------------------------------------
CALL (p, q, row_from_time) {
    OPTIONAL MATCH (q)<-[is_part_of:IS_PART_OF {branch: $branch_name}]-(p)
    WHERE row_from_time <= is_part_of.from < $to_time
    WITH DISTINCT is_part_of.status AS rel_status
    WITH collect(rel_status) AS rel_statuses
    RETURN ("active" IN rel_statuses AND "deleted" IN rel_statuses) AS intra_branch_update
}
WITH p, q, diff_rel, row_from_time, has_more_data, intra_branch_update
WHERE intra_branch_update = FALSE
// -------------------------------------
// Get every path on this branch under each node
// -------------------------------------
CALL (p, q, diff_rel, row_from_time) {
    OPTIONAL MATCH path = (
        (q)<-[top_diff_rel:IS_PART_OF]-(p)-[r_node]-(node)-[r_prop]-(prop)
    )
    WHERE %(id_func)s(diff_rel) = %(id_func)s(top_diff_rel)
    AND type(r_node) IN ["HAS_ATTRIBUTE", "IS_RELATED"]
    AND any(l in labels(node) WHERE l in ["Attribute", "Relationship"])
    AND node.branch_support IN [$branch_aware, $branch_agnostic]
    AND type(r_prop) IN ["IS_VISIBLE", "IS_PROTECTED", "HAS_SOURCE", "HAS_OWNER", "HAS_VALUE", "IS_RELATED"]
    AND any(l in labels(prop) WHERE l in ["Boolean", "Node", "AttributeValue"])
    AND (top_diff_rel.to IS NULL OR top_diff_rel.to >= r_node.from)
    AND (r_node.to IS NULL OR r_node.to >= r_prop.from)
    AND [%(id_func)s(p), type(r_node)] <> [%(id_func)s(prop), type(r_prop)]
    AND r_node.from < $to_time
    AND r_node.branch = top_diff_rel.branch
    AND r_node.status = top_diff_rel.status
    AND r_prop.from < $to_time
    AND r_prop.branch = top_diff_rel.branch
    AND r_prop.status = top_diff_rel.status
    // ------------------------
    // special handling for nodes that had their kind updated,
    // the migration leaves two nodes with the same UUID linked to the same Relationship
    // ------------------------
    AND (
        p.uuid IS NULL OR prop.uuid IS NULL OR p.uuid <> prop.uuid
        OR type(r_node) <> "IS_RELATED" OR type(r_prop) <> "IS_RELATED"
    )
    WITH path, node, prop, r_prop, r_node, type(r_node) AS rel_type, row_from_time
    // -------------------------------------
    // Exclude attributes/relationships added then removed on branch within timeframe
    // -------------------------------------
    CALL (p, rel_type, node, row_from_time) {
        OPTIONAL MATCH (p)-[rel_to_check {branch: $branch_name}]-(node)
        WHERE row_from_time <= rel_to_check.from < $to_time
        AND type(rel_to_check) = rel_type
        WITH DISTINCT rel_to_check.status AS rel_status
        WITH collect(rel_status) AS rel_statuses
        RETURN ("active" IN rel_statuses AND "deleted" IN rel_statuses) AS intra_branch_update
    }
    WITH path, node, prop, r_prop, r_node, intra_branch_update
    WHERE intra_branch_update = FALSE
    WITH path, node, prop, r_prop, r_node
    ORDER BY
        %(id_func)s(node),
        %(id_func)s(prop),
        r_prop.from DESC,
        r_node.from DESC
    WITH node, prop, type(r_prop) AS r_prop_type, type(r_node) AS r_node_type, head(collect(path)) AS diff_path
    RETURN diff_path
}
""" % {"id_func": db.get_id_function_name()}
        self.add_to_query(nodes_path_query)
        self.add_to_query(self.get_previous_base_path_query(db=db))
        self.add_to_query(self.get_relationship_peer_side_query(db=db))
        self.add_to_query("UNWIND diff_rel_paths AS diff_path")
        self.return_labels = ["DISTINCT diff_path AS diff_path", "has_more_data"]


class DiffFieldPathsQuery(DiffCalculationQuery):
    name = "diff_field_paths"

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        params_dict = self.get_params()
        self.params.update(params_dict)

        self.params.update(
            {
                "current_node_ids_list": self.current_node_field_specifiers.get_uuids_list()
                if self.current_node_field_specifiers
                else None,
                "new_node_ids_list": self.new_node_field_specifiers.get_uuids_list()
                if self.new_node_field_specifiers
                else None,
                "current_node_field_specifiers_map": self.current_node_field_specifiers.get_uuid_field_names_map()
                if self.current_node_field_specifiers is not None
                else None,
                "new_node_field_specifiers_map": self.new_node_field_specifiers.get_uuid_field_names_map()
                if self.new_node_field_specifiers is not None
                else None,
            }
        )
        fields_path_query = """
// -------------------------------------
// Identify attributes/relationships added/removed on branch
// -------------------------------------
MATCH (root:Root)<-[r_root:IS_PART_OF]-(p:Node)-[diff_rel {branch: $branch_name}]-(q)
// simple filters to start
WHERE type(diff_rel) IN ["HAS_ATTRIBUTE", "IS_RELATED"]
AND ("Attribute" IN labels(q) OR "Relationship" IN labels(q))
AND r_root.branch IN [$branch_name, $base_branch_name, $global_branch_name]
AND q.branch_support = $branch_aware
AND r_root.status = "active"
AND r_root.from <= diff_rel.from
AND (r_root.to IS NULL OR diff_rel.branch <> r_root.branch OR r_root.to >= diff_rel.from)
// node ID and field name filtering first pass
AND (
    (
        $current_node_ids_list IS NOT NULL
        AND p.uuid IN $current_node_ids_list
        AND q.name IN $current_node_field_specifiers_map[p.uuid]
    ) OR (
        $new_node_ids_list IS NOT NULL
        AND p.uuid IN $new_node_ids_list
        AND q.name IN $new_node_field_specifiers_map[p.uuid]
    ) OR (
        $new_node_ids_list IS NULL
        AND $current_node_ids_list IS NULL
    )
)
// node ID and field name filtering second pass
AND (
    // time-based filters for nodes already included in the diff or fresh changes
    (
        (
            (
                $current_node_ids_list IS NOT NULL
                AND p.uuid IN $current_node_ids_list
                AND q.name IN $current_node_field_specifiers_map[p.uuid]
            )
            OR ($current_node_ids_list IS NULL AND $new_node_ids_list IS NULL)
        )
        AND (r_root.from < $from_time OR p.branch_support = $branch_agnostic)
        AND (
            ($from_time <= diff_rel.from < $to_time AND (diff_rel.to IS NULL OR diff_rel.to > $to_time))
            OR ($from_time <= diff_rel.to < $to_time)
        )
    )
    // time-based filters for new nodes
    OR (
        (
            $new_node_ids_list IS NOT NULL
            AND p.uuid IN $new_node_ids_list
            AND q.name IN $new_node_field_specifiers_map[p.uuid]
        )
        AND (r_root.from < $branch_from_time OR p.branch_support = $branch_agnostic)
        AND (
            ($branch_from_time <= diff_rel.from < $to_time AND (diff_rel.to IS NULL OR diff_rel.to > $to_time))
            OR ($branch_from_time <= diff_rel.to < $to_time)
        )
    )
)
// -------------------------------------
// Limit the number of paths
// -------------------------------------
WITH root, r_root, p, diff_rel, q
ORDER BY r_root.from, p.uuid, q.uuid, diff_rel.branch, diff_rel.from
SKIP $offset
LIMIT $limit
// -------------------------------------
// Add flag to indicate if there is more data after this
// -------------------------------------
WITH collect([root, r_root, p, diff_rel, q]) AS limited_results
WITH limited_results, size(limited_results) = $limit AS has_more_data
UNWIND limited_results AS one_result
WITH one_result[0] AS root, one_result[1] AS r_root, one_result[2] AS p, one_result[3] AS diff_rel, one_result[4] AS q, has_more_data
// -------------------------------------
// Add correct from_time for row
// -------------------------------------
WITH root, r_root, p, diff_rel, q, has_more_data, CASE
    WHEN
        $new_node_ids_list IS NOT NULL
        AND p.uuid IN $new_node_ids_list
        AND q.name IN $new_node_field_specifiers_map[p.uuid]
    THEN $branch_from_time
    ELSE $from_time
END AS row_from_time
// -------------------------------------
// Exclude attributes/relationship under nodes deleted on this branch in the timeframe
// because those were all handled above at the node level
// -------------------------------------
CALL (root, p, row_from_time) {
    OPTIONAL MATCH (root)<-[r_root_deleted:IS_PART_OF {branch: $branch_name}]-(p)
    WHERE row_from_time <= r_root_deleted.from < $to_time
    WITH r_root_deleted
    ORDER BY r_root_deleted.status DESC
    LIMIT 1
    RETURN COALESCE(r_root_deleted.status = "deleted", FALSE) AS node_deleted
}
WITH root, r_root, p, diff_rel, q, has_more_data, row_from_time, node_deleted
WHERE node_deleted = FALSE
// -------------------------------------
// Exclude relationships added and deleted within the timeframe
// -------------------------------------
WITH root, r_root, p, diff_rel, q, has_more_data, row_from_time, type(diff_rel) AS rel_type
CALL (p, rel_type, q, row_from_time) {
    OPTIONAL MATCH (p)-[rel_to_check {branch: $branch_name}]-(q)
    WHERE row_from_time <= rel_to_check.from < $to_time
    AND type(rel_to_check) = rel_type
    WITH DISTINCT rel_to_check.status AS rel_status
    WITH collect(rel_status) AS rel_statuses
    RETURN ("active" IN rel_statuses AND "deleted" IN rel_statuses) AS intra_branch_update
}
WITH root, r_root, p, diff_rel, q, has_more_data, row_from_time, intra_branch_update
WHERE intra_branch_update = FALSE
// -------------------------------------
// Get every path on this branch under each attribute/relationship
// -------------------------------------
CALL (root, r_root, p, diff_rel, q) {
    OPTIONAL MATCH path = (
        (root:Root)<-[mid_r_root:IS_PART_OF]-(p)-[mid_diff_rel]-(q)-[r_prop]-(prop)
    )
    WHERE %(id_func)s(mid_r_root) =  %(id_func)s(r_root)
    AND %(id_func)s(mid_diff_rel) =  %(id_func)s(diff_rel)
    AND type(r_prop) IN ["IS_VISIBLE", "IS_PROTECTED", "HAS_SOURCE", "HAS_OWNER", "HAS_VALUE", "IS_RELATED"]
    AND any(l in labels(prop) WHERE l in ["Boolean", "Node", "AttributeValue"])
    AND r_prop.from < $to_time AND r_prop.branch = mid_diff_rel.branch
    AND (mid_diff_rel.to IS NULL OR mid_diff_rel.to >= r_prop.from)
    AND [%(id_func)s(p), type(mid_diff_rel)] <> [%(id_func)s(prop), type(r_prop)]
    // exclude paths where an active edge is below a deleted edge
    AND (mid_diff_rel.status = "active" OR r_prop.status = "deleted")
    // ------------------------
    // special handling for nodes that had their kind updated,
    // the migration leaves two nodes with the same UUID linked to the same Relationship
    // ------------------------
    AND (
        p.uuid IS NULL OR prop.uuid IS NULL OR p.uuid <> prop.uuid
        OR type(mid_diff_rel) <> "IS_RELATED" OR type(r_prop) <> "IS_RELATED"
    )
    WITH path, prop, r_prop, mid_r_root
    ORDER BY
        type(r_prop),
        mid_r_root.branch = mid_diff_rel.branch DESC,
        (mid_diff_rel.status = r_prop.status AND mid_diff_rel.branch = r_prop.branch) DESC,
        r_prop.from DESC,
        mid_r_root.from DESC
    WITH prop, type(r_prop) AS type_r_prop, head(collect(path)) AS latest_prop_path
    RETURN latest_prop_path
}
// -------------------------------------
// Exclude properties added and deleted within the timeframe
// -------------------------------------
WITH q, nodes(latest_prop_path)[3] AS prop, type(relationships(latest_prop_path)[2]) AS rel_type, latest_prop_path, has_more_data, row_from_time
CALL (q, rel_type, prop, row_from_time) {
    OPTIONAL MATCH (q)-[rel_to_check {branch: $branch_name}]-(prop)
    WHERE row_from_time <= rel_to_check.from < $to_time
    AND type(rel_to_check) = rel_type
    WITH DISTINCT rel_to_check.status AS rel_status
    WITH collect(rel_status) AS rel_statuses
    RETURN ("active" IN rel_statuses AND "deleted" IN rel_statuses) AS intra_branch_update
}
WITH latest_prop_path AS diff_path, has_more_data, intra_branch_update
WHERE intra_branch_update = FALSE
        """ % {"id_func": db.get_id_function_name()}
        self.add_to_query(fields_path_query)
        self.add_to_query(self.get_previous_base_path_query(db=db))
        self.add_to_query(self.get_relationship_peer_side_query(db=db))
        self.add_to_query("UNWIND diff_rel_paths AS diff_path")
        self.return_labels = ["DISTINCT diff_path AS diff_path", "has_more_data"]


class DiffPropertyPathsQuery(DiffCalculationQuery):
    name = "diff_property_paths"

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        params_dict = self.get_params()
        self.params.update(params_dict)

        self.params.update(
            {
                "current_node_ids_list": self.current_node_field_specifiers.get_uuids_list()
                if self.current_node_field_specifiers
                else None,
                "new_node_ids_list": self.new_node_field_specifiers.get_uuids_list()
                if self.new_node_field_specifiers
                else None,
                "current_node_field_specifiers_map": self.current_node_field_specifiers.get_uuid_field_names_map()
                if self.current_node_field_specifiers is not None
                else None,
                "new_node_field_specifiers_map": self.new_node_field_specifiers.get_uuid_field_names_map()
                if self.new_node_field_specifiers is not None
                else None,
            }
        )
        properties_path_query = """
// -------------------------------------
// Identify properties added/removed on branch
// -------------------------------------
MATCH diff_rel_path = (root:Root)<-[r_root:IS_PART_OF]-(n:Node)-[r_node]-(p)-[diff_rel {branch: $branch_name}]->(q)
WHERE p.branch_support = $branch_aware
AND any(l in labels(p) WHERE l in ["Attribute", "Relationship"])
AND type(diff_rel) IN ["IS_VISIBLE", "IS_PROTECTED", "HAS_SOURCE", "HAS_OWNER", "HAS_VALUE"]
AND any(l in labels(q) WHERE l in ["Boolean", "Node", "AttributeValue"])
AND type(r_node) IN ["HAS_ATTRIBUTE", "IS_RELATED"]
// node ID and field name filtering first pass
AND (
    (
        $current_node_ids_list IS NOT NULL
        AND n.uuid IN $current_node_ids_list
        AND p.name IN $current_node_field_specifiers_map[n.uuid]
    ) OR (
        $new_node_ids_list IS NOT NULL
        AND n.uuid IN $new_node_ids_list
        AND p.name IN $new_node_field_specifiers_map[n.uuid]
    ) OR (
        $new_node_ids_list IS NULL
        AND $current_node_ids_list IS NULL
    )
)
// node ID and field name filtering second pass
AND (
    // time-based filters for nodes already included in the diff or fresh changes
    (
        (
            (
                $current_node_ids_list IS NOT NULL
                AND n.uuid IN $current_node_ids_list
                AND p.name IN $current_node_field_specifiers_map[n.uuid]
            )
            OR ($current_node_ids_list IS NULL AND $new_node_ids_list IS NULL)
        )
        AND (
            ($from_time <= diff_rel.from < $to_time AND (diff_rel.to IS NULL OR diff_rel.to > $to_time))
            OR ($from_time <= diff_rel.to < $to_time)
        )
        // skip paths where nodes/attrs/rels are updated after $from_time, those are handled in other queries
        AND (
            r_root.from <= $from_time AND (r_root.to IS NULL OR r_root.branch <> diff_rel.branch OR r_root.to <= $from_time)
            AND r_node.from <= $from_time AND (r_node.to IS NULL OR r_node.branch <> diff_rel.branch OR r_node.to <= $from_time)
        )
    )
    // time-based filters for new nodes
    OR (
        (
            $new_node_ids_list IS NOT NULL
            AND n.uuid IN $new_node_ids_list
            AND p.name IN $new_node_field_specifiers_map[n.uuid]
        )
        AND (
            ($branch_from_time <= diff_rel.from < $to_time AND (diff_rel.to IS NULL OR diff_rel.to > $to_time))
            OR ($branch_from_time <= diff_rel.to < $to_time)
        )
        // skip paths where nodes/attrs/rels are updated after $branch_from_time, those are handled in other queries
        AND (
            r_root.from <= $branch_from_time AND (r_root.to IS NULL OR r_root.branch <> diff_rel.branch OR r_root.to <= $branch_from_time)
            AND r_node.from <= $branch_from_time AND (r_node.to IS NULL OR r_node.branch <> diff_rel.branch OR r_node.to <= $branch_from_time)
        )
    )
)
// ------------------------
// special handling for nodes that had their kind updated,
// the migration leaves two nodes with the same UUID linked to the same Relationship
// ------------------------
AND (
    n.uuid IS NULL OR q.uuid IS NULL OR n.uuid <> q.uuid
    OR type(r_node) <> "IS_RELATED" OR type(diff_rel) <> "IS_RELATED"
)
AND ALL(
    r_pair IN [[r_root, r_node], [r_node, diff_rel]]
    // filter out paths where a base branch edge follows a branch edge
    WHERE ((r_pair[0]).branch = $base_branch_name OR (r_pair[1]).branch = $branch_name)
    // filter out paths where an active edge follows a deleted edge
    AND ((r_pair[0]).status = "active" OR (r_pair[1]).status = "deleted")
    // filter out paths where an earlier from time follows a later from time
    AND (r_pair[0]).from <= (r_pair[1]).from
    // require adjacent edge pairs to have overlapping times, but only if on the same branch
    AND (
        (r_pair[0]).branch <> (r_pair[1]).branch
        OR (r_pair[0]).to IS NULL
        OR (r_pair[0]).to >= (r_pair[1]).from
    )
)
AND [%(id_func)s(n), type(r_node)] <> [%(id_func)s(q), type(diff_rel)]
// -------------------------------------
// Limit the number of paths
// -------------------------------------
WITH diff_rel_path, r_root, n, r_node, p, diff_rel
ORDER BY r_root.from, n.uuid, p.uuid, type(diff_rel), diff_rel.branch, diff_rel.from
SKIP $offset
LIMIT $limit
// -------------------------------------
// Add flag to indicate if there is more data after this
// -------------------------------------
WITH collect([diff_rel_path, r_root, n, r_node, p, diff_rel]) AS limited_results
WITH limited_results, size(limited_results) = $limit AS has_more_data
UNWIND limited_results AS one_result
WITH one_result[0] AS diff_rel_path, one_result[1] AS r_root, one_result[2] AS n,
    one_result[3] AS r_node, one_result[4] AS p, one_result[5] AS diff_rel, has_more_data
// -------------------------------------
// Add correct from_time for row
// -------------------------------------
WITH diff_rel_path, r_root, n, r_node, p, diff_rel, has_more_data, CASE
    WHEN
        $new_node_ids_list IS NOT NULL
        AND n.uuid IN $new_node_ids_list
        AND p.name IN $new_node_field_specifiers_map[n.uuid]
    THEN $branch_from_time
    ELSE $from_time
END AS row_from_time
WITH diff_rel_path, r_root, n, r_node, p, diff_rel, has_more_data, row_from_time
ORDER BY
    %(id_func)s(n) DESC,
    %(id_func)s(p) DESC,
    type(diff_rel),
    r_node.branch = diff_rel.branch DESC,
    r_root.branch = diff_rel.branch DESC,
    diff_rel.from DESC,
    r_node.from DESC,
    r_root.from DESC
WITH n, p, row_from_time, diff_rel, diff_rel_path, has_more_data
CALL (n, p, row_from_time){
    // -------------------------------------
    // Exclude properties under nodes and attributes/relationships deleted
    // on this branch in the timeframe because those were all handled above
    // -------------------------------------
    CALL (n, row_from_time) {
        OPTIONAL MATCH (root:Root)<-[r_root_deleted:IS_PART_OF {branch: $branch_name}]-(n)
        WHERE r_root_deleted.from < $to_time
        WITH r_root_deleted
        ORDER BY r_root_deleted.status DESC
        LIMIT 1
        RETURN COALESCE(r_root_deleted.status = "deleted", FALSE) AS node_deleted
    }
    WITH node_deleted
    CALL (n, p, row_from_time) {
        OPTIONAL MATCH (n)-[r_node_deleted {branch: $branch_name}]-(p)
        WHERE row_from_time <= r_node_deleted.from < $to_time
        AND type(r_node_deleted) IN ["HAS_ATTRIBUTE", "IS_RELATED"]
        WITH r_node_deleted
        ORDER BY r_node_deleted.status DESC
        LIMIT 1
        RETURN COALESCE(r_node_deleted.status = "deleted", FALSE) AS field_deleted
    }
    RETURN node_deleted OR field_deleted AS node_or_field_deleted
}
WITH n, p, diff_rel, diff_rel_path, has_more_data, node_or_field_deleted
WHERE node_or_field_deleted = FALSE
WITH n, p, type(diff_rel) AS drt, head(collect(diff_rel_path)) AS diff_path, has_more_data
        """ % {"id_func": db.get_id_function_name()}
        self.add_to_query(properties_path_query)
        self.add_to_query(self.get_previous_base_path_query(db=db))
        self.add_to_query(self.get_relationship_peer_side_query(db=db))
        self.add_to_query("UNWIND diff_rel_paths AS diff_path")
        self.return_labels = ["DISTINCT diff_path AS diff_path", "has_more_data"]


@dataclass
class MigratedKindNode:
    uuid: str
    kind: str
    db_id: str
    from_time: Timestamp
    action: DiffAction
    has_more_data: bool


class DiffMigratedKindNodesQuery(DiffCalculationQuery):
    name = "diff_migrated_kind_nodes_query"

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        params_dict = self.get_params()
        self.params.update(params_dict)
        migrated_kind_nodes_query = """
// -------------------------------------
// Identify nodes added/removed on branch in the time frame
// -------------------------------------
MATCH (:Root)<-[diff_rel:IS_PART_OF {branch: $branch_name}]-(n:Node)
WHERE (
    ($from_time <= diff_rel.from < $to_time AND (diff_rel.to IS NULL OR diff_rel.to > $to_time))
    OR ($from_time <= diff_rel.to < $to_time)
)
AND n.branch_support = $branch_aware
WITH DISTINCT n.uuid AS node_uuid, %(id_func)s(n) AS db_id
WITH node_uuid, count(*) AS num_nodes_with_uuid
WHERE num_nodes_with_uuid > 1
// -------------------------------------
// Limit the number of nodes
// -------------------------------------
WITH node_uuid
ORDER BY node_uuid
SKIP $offset
LIMIT $limit
WITH collect(node_uuid) AS node_uuids
WITH node_uuids, size(node_uuids) = $limit AS has_more_data
MATCH (:Root)<-[diff_rel:IS_PART_OF {branch: $branch_name}]-(n:Node)
WHERE n.uuid IN node_uuids
AND (
    ($from_time <= diff_rel.from < $to_time AND (diff_rel.to IS NULL OR diff_rel.to > $to_time))
    OR ($from_time <= diff_rel.to < $to_time)
)
// -------------------------------------
// Ignore node created and deleted on this branch
// -------------------------------------
CALL (n) {
    OPTIONAL MATCH (:Root)<-[diff_rel:IS_PART_OF {branch: $branch_name}]-(n)
    WITH diff_rel
    ORDER BY diff_rel.from ASC
    WITH collect(diff_rel.status) AS statuses
    RETURN statuses = ["active", "deleted"] AS intra_branch_update
}
WITH n.uuid AS uuid, n.kind AS kind, %(id_func)s(n) AS db_id, diff_rel.from_time AS from_time, diff_rel.status AS status, has_more_data
WHERE intra_branch_update = FALSE
        """ % {"id_func": db.get_id_function_name()}
        self.add_to_query(query=migrated_kind_nodes_query)
        self.return_labels = [
            "uuid",
            "kind",
            "db_id",
            "from_time",
            "status",
            "has_more_data",
        ]

    def get_migrated_kind_nodes(self) -> Generator[MigratedKindNode, None, None]:
        for result in self.get_results():
            yield MigratedKindNode(
                uuid=result.get_as_type("uuid", return_type=str),
                kind=result.get_as_type("kind", return_type=str),
                db_id=result.get_as_type("db_id", return_type=str),
                from_time=result.get_as_type("from_time", return_type=Timestamp),
                action=DiffAction.REMOVED
                if result.get_as_type("status", return_type=str).lower() == RelationshipStatus.DELETED.value
                else DiffAction.ADDED,
                has_more_data=result.get_as_type("has_more_data", bool),
            )
