from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, cast

from infrahub.core.constants import RelationshipDirection
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


@dataclass
class DbNode:
    db_id: str
    labels: set[str]
    properties: dict[str, Any]

    def __hash__(self) -> int:
        cumulative_hash = hash(frozenset(self.labels))
        for k, v in self.properties.items():
            cumulative_hash += hash(k)
            cumulative_hash += hash(v)
        return hash(cumulative_hash)


@dataclass
class DbEdge:
    db_id: str
    from_db_id: str
    to_db_id: str
    edge_type: str
    properties: dict[str, Any]

    def __hash__(self) -> int:
        labels_hash = hash(self.edge_type)
        cumulative_hash = 0
        for k, v in self.properties.items():
            cumulative_hash += hash(k)
            cumulative_hash += hash(v)
        return hash(f"{labels_hash}:{cumulative_hash}")


@dataclass
class DbSnapshot:
    node_map: dict[int, DbNode]
    edge_map: dict[int, DbEdge]

    def __hash__(self) -> int:
        summed_node_hash = sum(self.node_map.keys())
        summed_edge_hash = sum(self.edge_map.keys())
        return hash(f"{summed_node_hash}:{summed_edge_hash}")


class DbSnapshotter:
    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def snapshot(self) -> DbSnapshot:
        node_query = """MATCH (n) RETURN n"""
        results = await self.db.execute_query(query=node_query)
        node_map = {}
        node_hashes_by_db_id: dict[str, int] = {}
        for result in results:
            n = result.get("n")
            db_node = DbNode(db_id=n.element_id, labels=n.labels, properties=dict(n.items()))
            node_hash = hash(db_node)
            node_map[node_hash] = db_node
            node_hashes_by_db_id[db_node.db_id] = node_hash
        edge_query = """MATCH (a)-[e]->(b) RETURN a, e, b"""
        results = await self.db.execute_query(query=edge_query)
        edge_map = {}
        for result in results:
            from_n = result.get("a")
            from_n_db_id = from_n.element_id
            from_n_hash = node_hashes_by_db_id[from_n_db_id]
            to_n = result.get("b")
            to_n_db_id = to_n.element_id
            to_n_hash = node_hashes_by_db_id[to_n_db_id]
            edge = result.get("e")
            db_edge = DbEdge(
                db_id=edge.element_id,
                from_db_id=from_n_db_id,
                to_db_id=to_n_db_id,
                edge_type=edge.type,
                properties=(dict(edge.items())),
            )
            edge_only_hash = hash(db_edge)
            full_edge_hash = hash(f"{from_n_hash}:{edge_only_hash}:{to_n_hash}")
            edge_map[full_edge_hash] = db_edge
        return DbSnapshot(node_map=node_map, edge_map=edge_map)


PropertyTypes = Literal[
    DatabaseEdgeType.HAS_OWNER,
    DatabaseEdgeType.HAS_SOURCE,
    DatabaseEdgeType.IS_VISIBLE,
    DatabaseEdgeType.IS_PROTECTED,
    DatabaseEdgeType.IS_RELATED,
]


@dataclass
class NodeIdentifier:
    uuid: str
    labels: frozenset[str]

    def __hash__(self) -> int:
        return hash((self.uuid, self.labels))

    def __str__(self) -> str:
        return f"{self.uuid} ({':'.join(self.labels)})"


@dataclass
class BranchStatus:
    active_from: str
    deleted_at: str | None

    def __str__(self) -> str:
        return f"{self.active_from=},{self.deleted_at=}"


@dataclass
class BranchProperty(BranchStatus):
    property_type: PropertyTypes
    value: Any

    def __hash__(self) -> int:
        return hash((self.active_from, self.deleted_at, self.property_type, self.value))

    def assert_equal(self, other: BranchProperty) -> None:
        assert self.property_type is other.property_type
        assert self.value == other.value
        assert self.active_from == other.active_from
        assert self.deleted_at == other.deleted_at


@dataclass
class RelationshipDeduplicated:
    name: str
    direction: RelationshipDirection
    peer_uuid: str
    # {branch name: {property type: {BranchProperty, ...}}}
    branch_properties_map: dict[str, dict[PropertyTypes, set[BranchProperty]]]

    def assert_equal(self, other: RelationshipDeduplicated) -> None:
        assert self.name == other.name
        assert self.direction == other.direction
        assert self.peer_uuid == other.peer_uuid
        these_branches = set(self.branch_properties_map.keys())
        other_branches = set(other.branch_properties_map.keys())
        assert these_branches == other_branches
        for branch_name, property_type_map in self.branch_properties_map.items():
            other_property_type_map = other.branch_properties_map[branch_name]
            these_property_types = set(property_type_map.keys())
            other_property_types = set(other_property_type_map.keys())
            assert these_property_types == other_property_types
            for property_type, these_branch_properties in property_type_map.items():
                other_branch_properties = other_property_type_map[property_type]
                assert these_branch_properties == other_branch_properties


@dataclass
class AttributeDeduplicated:
    name: str
    # {branch name: {property type: {BranchProperty, ...}}}
    branch_properties_map: dict[str, dict[PropertyTypes, set[BranchProperty]]]

    def assert_equal(self, other: AttributeDeduplicated) -> None:
        assert self.name == other.name
        these_branches = set(self.branch_properties_map.keys())
        other_branches = set(other.branch_properties_map.keys())
        assert these_branches == other_branches
        for branch_name, property_type_map in self.branch_properties_map.items():
            other_property_type_map = other.branch_properties_map[branch_name]
            these_property_types = set(property_type_map.keys())
            other_property_types = set(other_property_type_map.keys())
            assert these_property_types == other_property_types
            for property_type, these_branch_properties in property_type_map.items():
                other_branch_properties = other_property_type_map[property_type]
                assert these_branch_properties == other_branch_properties


@dataclass
class DeduplicatedNode:
    identifier: NodeIdentifier
    # {branch name: BranchStatus}
    status_map: dict[str, BranchStatus]
    # {attribute name: AttributeDeduplicated}
    attributes_map: dict[str, AttributeDeduplicated]
    # {(relationship name, peer uuid, direction): RelationshipDeduplicated}
    relationships_map: dict[tuple[str, str, RelationshipDirection], RelationshipDeduplicated]

    def assert_equal(self, other: DeduplicatedNode) -> None:
        assert self.identifier == other.identifier
        these_branches = set(self.status_map.keys())
        other_branches = set(other.status_map.keys())
        assert these_branches == other_branches
        for branch_name, this_branch_status in self.status_map.items():
            other_branch_status = other.status_map[branch_name]
            assert this_branch_status == other_branch_status

        these_attr_names = set(self.attributes_map.keys())
        other_attr_names = set(other.attributes_map.keys())
        assert these_attr_names == other_attr_names
        for attr_name, this_attr in self.attributes_map.items():
            other_attr = other.attributes_map[attr_name]
            this_attr.assert_equal(other_attr)

        these_rel_keys = set(self.relationships_map.keys())
        other_rel_keys = set(other.relationships_map.keys())
        assert these_rel_keys == other_rel_keys
        for rel_key, this_rel in self.relationships_map.items():
            other_rel = other.relationships_map[rel_key]
            this_rel.assert_equal(other_rel)


@dataclass
class DbSnapshotDeduplicated:
    nodes_map: dict[NodeIdentifier, DeduplicatedNode]

    def assert_equal(self, other: DbSnapshotDeduplicated) -> None:
        these_node_ids = set(self.nodes_map.keys())
        other_node_ids = set(other.nodes_map.keys())
        assert these_node_ids == other_node_ids
        for node_id, this_node in self.nodes_map.items():
            other_node = other.nodes_map[node_id]
            this_node.assert_equal(other_node)


class DeduplicatedNodesQuery(Query):
    type = QueryType.READ
    insert_return = True

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:
        query = """
// ---------
// group all the Nodes by their UUID and sorted labels to deduplicate them
// ---------
MATCH (n:Node)
CALL (n) {
    WITH labels(n) AS n_labels
    UNWIND n_labels AS n_label
    WITH n_label
    ORDER BY n_label ASC
    RETURN collect(n_label) AS sorted_labels
}
WITH n.uuid AS n_uuid, sorted_labels, collect(%(id_func)s(n)) AS vertex_element_ids
// ---------
// for each Node group get the active and deleted times for IS_PART_OF edges on each branch
// only include a deleted time if every Node active on the branch is also deleted
// ---------
CALL (n_uuid, vertex_element_ids) {
    MATCH (n:Node {uuid: n_uuid})-[e:IS_PART_OF]->(:Root)
    WHERE %(id_func)s(n) IN vertex_element_ids
    WITH DISTINCT n_uuid, vertex_element_ids, e.branch AS branch
    // MATCH (n:Node {uuid: n_uuid})-[e:IS_PART_OF {branch: branch, status: "active"}]->(:Root)
    MATCH (n:Node {uuid: n_uuid})-[e:IS_PART_OF {branch: branch}]->(:Root)
    WHERE %(id_func)s(n) IN vertex_element_ids
    WITH n_uuid, vertex_element_ids, branch, collect(e) AS is_part_ofs
    WITH n_uuid, vertex_element_ids, branch,
    reduce(
        active_from = NULL, edge IN is_part_ofs |
        CASE
            WHEN edge.status = "active" AND (active_from IS NULL OR edge.from < active_from) THEN edge.from
            ELSE active_from
        END
    ) AS earliest_active,
    reduce(
        deleted_at = NULL, edge IN is_part_ofs |
        CASE
            WHEN edge.status = "active" AND edge.to IS NOT NULL AND (deleted_at IS NULL OR edge.to > deleted_at) THEN edge.to
            WHEN edge.status = "deleted" AND (deleted_at IS NULL OR edge.from > deleted_at) THEN edge.from
            ELSE deleted_at
        END
    ) AS latest_deleted
    CALL (n_uuid, branch, vertex_element_ids) {
        MATCH (n:Node {uuid: n_uuid})-[is_part_of_e:IS_PART_OF {branch: branch}]->(:Root)
        WHERE %(id_func)s(n) IN vertex_element_ids
        WITH n, is_part_of_e
        ORDER BY %(id_func)s(n), is_part_of_e.from DESC
        WITH n, head(collect(is_part_of_e)) AS latest_edge
        RETURN latest_edge.status = "deleted" OR (latest_edge.status = "active" AND latest_edge.to IS NOT NULL) AS is_deleted
        ORDER BY is_deleted ASC
        LIMIT 1
    }
    RETURN branch, earliest_active, CASE
        WHEN is_deleted THEN latest_deleted
        ELSE NULL
    END AS latest_deleted
}
WITH n_uuid, sorted_labels, vertex_element_ids,
    collect({branch: branch, earliest_active: earliest_active, latest_deleted: latest_deleted}) AS branch_statuses
// ---------
// for each Attribute name linked to this Node group
//   get the active and deleted times for each property on each branch
//   only include a deleted time if every active property of the same type on the branch is also deleted
// ---------
CALL (n_uuid, vertex_element_ids) {
    MATCH (n:Node {uuid: n_uuid})
    WHERE %(id_func)s(n) IN vertex_element_ids
    MATCH (n)-[:HAS_ATTRIBUTE]->(attr:Attribute)-[property_e]->(value_peer)
    WITH DISTINCT n_uuid, vertex_element_ids, property_e.branch AS branch,
        attr.name AS attr_name, type(property_e) AS property_type, COALESCE(value_peer.value, value_peer.uuid) AS property_value
    // ---------
    // is this property for this value of this attribute name deleted on this branch
    // ---------
    CALL (n_uuid, vertex_element_ids, branch, attr_name, property_type, property_value) {
        MATCH (n:Node {uuid: n_uuid})-[:HAS_ATTRIBUTE]->(attr:Attribute {name: attr_name})
        WHERE %(id_func)s(n) IN vertex_element_ids
        WITH DISTINCT branch, property_type, property_value, attr
        MATCH (attr)-[property_e {branch: branch}]->(value_peer)
        WHERE type(property_e) = property_type
        AND COALESCE(value_peer.value, value_peer.uuid) = property_value
        WITH attr, property_e
        ORDER BY %(id_func)s(attr), property_e.from DESC
        WITH attr, head(collect(property_e)) AS latest_edge
        RETURN latest_edge.status = "deleted" OR (latest_edge.status = "active" AND latest_edge.to IS NOT NULL) AS is_deleted
        ORDER BY is_deleted ASC
        LIMIT 1
    }
    // ---------
    // earliest active time for this value of this property for this attribute name on this branch
    // ---------
    CALL (n_uuid, vertex_element_ids, branch, attr_name, property_type, property_value) {
        MATCH (n:Node {uuid: n_uuid})-[:HAS_ATTRIBUTE]->(attr:Attribute {name: attr_name})
        WHERE %(id_func)s(n) IN vertex_element_ids
        WITH DISTINCT branch, property_type, property_value, attr
        MATCH (attr)-[property_e {branch: branch, status: "active"}]->(value_peer)
        WHERE type(property_e) = property_type
        AND COALESCE(value_peer.value, value_peer.uuid) = property_value
        RETURN property_e.from AS earliest_active
        ORDER BY property_e.from ASC
        LIMIT 1
    }
    // ---------
    // latest deleted time for this value of this property for this attribute name on this branch
    // ---------
    CALL (n_uuid, vertex_element_ids, branch, attr_name, property_type, property_value) {
        MATCH (n:Node {uuid: n_uuid})-[:HAS_ATTRIBUTE]->(attr:Attribute {name: attr_name})
        WHERE %(id_func)s(n) IN vertex_element_ids
        WITH DISTINCT branch, property_type, property_value, attr
        OPTIONAL MATCH (attr)-[property_e {branch: branch}]->(value_peer)
        WHERE type(property_e) = property_type
        AND COALESCE(value_peer.value, value_peer.uuid) = property_value
        AND (property_e.status = "deleted" OR property_e.to IS NOT NULL)
        WITH CASE
            WHEN property_e.status = "deleted" THEN property_e.from
            ELSE property_e.to
        END AS delete_time
        RETURN delete_time AS latest_deleted
        ORDER BY delete_time DESC
        LIMIT 1
    }
    WITH branch, attr_name, property_type, property_value, earliest_active, CASE
        WHEN is_deleted THEN latest_deleted
        ELSE NULL
    END AS latest_deleted
    WITH branch, attr_name, property_type,
        collect({property_value: property_value, earliest_active: earliest_active, latest_deleted: latest_deleted}) AS property_value_statuses
    WITH branch, attr_name, collect({property_type: property_type, property_value_maps: property_value_statuses}) AS property_type_maps
    RETURN collect({branch: branch, attr_name: attr_name, property_type_maps: property_type_maps}) AS attr_branch_details
}
// ---------
// for each Relationship name linked to this Node group
//   get the active and deleted times for each property on each branch
//   only include a deleted time if every active property of the same type on the branch is also deleted
//   account for direction in uniqueness determination
// ---------
CALL (n_uuid, vertex_element_ids) {
    // ------------
    // Get the default and global branch names
    // ------------
    OPTIONAL MATCH (default_b:Branch)
    WHERE default_b.is_default = TRUE
    WITH *, COALESCE(default_b.name, "main") AS default_branch
    LIMIT 1
    OPTIONAL MATCH (global_b:Branch)
    WHERE global_b.is_global = TRUE
    WITH *, COALESCE(global_b.name, "-global-") AS global_branch
    LIMIT 1
    WITH default_branch, global_branch, n_uuid, vertex_element_ids
    MATCH (n:Node {uuid: n_uuid})
    WHERE %(id_func)s(n) IN vertex_element_ids
    // get the unique combinations of rel_name, peer_uuid, and direction
    MATCH (n)-[e1:IS_RELATED]-(rel:Relationship)-[e2:IS_RELATED]-(peer:Node)
    WHERE peer.uuid <> n.uuid
    AND e1.branch = e2.branch
    AND e1.status = e2.status
    // make sure both n and peer are active on this branch
    CALL (default_branch, global_branch, n, peer, e1) {
        WITH default_branch, global_branch, n, peer, e1.branch AS branch, e1.status AS status
        MATCH (b:Branch {name: branch})
        OPTIONAL MATCH (n)-[n_is_part_of:IS_PART_OF]-(:Root)
        WHERE n_is_part_of.branch IN [branch, default_branch, global_branch]
        AND (
            n_is_part_of.branch = branch
            OR (n_is_part_of.from < b.branched_from)
        )
        WITH *
        ORDER BY n_is_part_of.from DESC
        LIMIT 1

        OPTIONAL MATCH (peer)-[peer_is_part_of:IS_PART_OF]-(:Root)
        WHERE peer_is_part_of.branch IN [branch, default_branch, global_branch]
        AND (
            peer_is_part_of.branch = branch
            OR (peer_is_part_of.from < b.branched_from)
        )
        WITH n_is_part_of, peer_is_part_of, status
        ORDER BY peer_is_part_of.from DESC
        LIMIT 1
        // active relationship with at least one node that is deleted is illegal
        RETURN status = "active"
        AND (
            (n_is_part_of.status = "deleted" OR n_is_part_of.to IS NOT NULL)
            OR (peer_is_part_of.status = "deleted" OR peer_is_part_of.to IS NOT NULL)
        ) AS illegal_rel
    }
    WITH *, illegal_rel
    WHERE illegal_rel = FALSE
    // get the branches, property types, and values of every Relationship
    MATCH (rel)-[property_edge]-(value_peer)
    WHERE value_peer.uuid IS NULL OR value_peer.uuid <> n.uuid
    WITH DISTINCT default_branch, global_branch, n_uuid, vertex_element_ids,
        property_edge.branch AS branch,
        rel.name AS rel_name,
        peer.uuid AS peer_uuid,
        CASE
            WHEN startNode(e1) = n AND startNode(e2) = rel THEN "outbound"
            WHEN startNode(e1) = rel AND startNode(e2) = peer THEN "inbound"
            ELSE "bidirectional"
        END AS direction,
        type(property_edge) AS property_type,
        COALESCE(value_peer.value, value_peer.uuid) AS property_value,
        collect(property_edge) AS property_edges
    WITH default_branch, global_branch, n_uuid, vertex_element_ids, branch, rel_name, peer_uuid, direction, property_type, property_value,
    reduce(
        active_from = NULL, edge IN property_edges |
        CASE
            WHEN edge.status = "active" AND (active_from IS NULL OR edge.from < active_from) THEN edge.from
            ELSE active_from
        END
    ) AS earliest_active,
    reduce(
        deleted_at = NULL, edge IN property_edges |
        CASE
            WHEN edge.status = "active" AND edge.to IS NOT NULL AND (deleted_at IS NULL OR edge.to > deleted_at) THEN edge.to
            WHEN edge.status = "deleted" AND (deleted_at IS NULL OR edge.from > deleted_at) THEN edge.from
            ELSE deleted_at
        END
    ) AS latest_deleted
    CALL (default_branch, global_branch, n_uuid, vertex_element_ids, branch, rel_name, peer_uuid, direction, property_type, property_value) {
        // ---------
        // determine if the combination is active by looking for any active path
        // ---------
        OPTIONAL MATCH (n:Node {uuid: n_uuid})-[e1:IS_RELATED]-(rel:Relationship {name: rel_name})-[e2:IS_RELATED]-(peer:Node {uuid: peer_uuid})
        WHERE %(id_func)s(n) IN vertex_element_ids
        AND e1.status = "active" AND e2. status = "active"
        AND e1.to IS NULL AND e2.to IS NULL
        AND e1.branch IN [branch, default_branch, global_branch]
        AND e2.branch IN [branch, default_branch, global_branch]
        AND (
            (direction = "outbound" AND startNode(e1) = n AND startNode(e2) = rel)
            OR (direction = "inbound" AND startNode(e1) = rel AND startNode(e2) = peer)
            OR (direction = "bidirectional" AND startNode(e1) = n AND startNode(e2) = peer)
        )
        OPTIONAL MATCH (rel)-[property_edge {branch: branch, status: "active"}]-(property_vertex)
        WHERE type(property_edge) = property_type
        AND COALESCE(property_vertex.uuid, property_vertex.value) = property_value
        AND property_edge.to IS NULL
        WITH collect(property_vertex) AS active_properties
        RETURN size(active_properties) > 0 AS is_active
    }
    WITH *, CASE
        WHEN is_active THEN NULL
        ELSE latest_deleted
    END AS latest_deleted
    WITH branch, rel_name, direction, peer_uuid, property_type,
        collect({property_value: property_value, earliest_active: earliest_active, latest_deleted: latest_deleted}) AS property_value_statuses
    WITH branch, rel_name, direction, peer_uuid,
        collect({property_type: property_type, property_value_maps: property_value_statuses}) AS property_type_maps
    RETURN collect(
        {branch: branch, rel_name: rel_name, direction: direction, peer_uuid: peer_uuid, property_type_maps: property_type_maps}
    ) AS rel_branch_details
}

        """ % {"id_func": db.get_id_function_name()}
        self.return_labels = ["n_uuid", "sorted_labels", "branch_statuses", "attr_branch_details", "rel_branch_details"]
        self.add_to_query(query)

    def get_deduplicated_nodes(self) -> list[DeduplicatedNode]:
        deduplicated_nodes = []
        for result in self.get_results():
            # get the node-level data
            node_uuid = result.get_as_type("n_uuid", return_type=str)
            labels: frozenset[str] = result.get_as_type("sorted_labels", return_type=frozenset)
            deduplicated_node = DeduplicatedNode(
                identifier=NodeIdentifier(uuid=node_uuid, labels=labels),
                status_map={},
                attributes_map={},
                relationships_map={},
            )
            branch_status_dicts: list[dict[str, str]] = result.get_as_type("branch_statuses", return_type=list)
            for branch_status in branch_status_dicts:
                branch = branch_status["branch"]
                earliest_active = branch_status["earliest_active"]
                latest_deleted = branch_status["latest_deleted"]
                deduplicated_node.status_map[branch] = BranchStatus(
                    active_from=earliest_active, deleted_at=latest_deleted
                )

            # get the attribute-level data
            attr_branch_details_dicts: list[dict] = result.get_as_type("attr_branch_details", return_type=list)
            deduplicated_attrs_by_name: dict[str, AttributeDeduplicated] = {}
            for attr_branch_dict in attr_branch_details_dicts:
                attr_name = attr_branch_dict["attr_name"]
                if attr_name not in deduplicated_attrs_by_name:
                    deduplicated_attrs_by_name[attr_name] = AttributeDeduplicated(
                        name=attr_name, branch_properties_map={}
                    )
                deduplicated_attr = deduplicated_attrs_by_name[attr_name]
                branch = attr_branch_dict["branch"]
                if branch not in deduplicated_attr.branch_properties_map:
                    deduplicated_attr.branch_properties_map[branch] = {}
                for property_type_map in attr_branch_dict["property_type_maps"]:
                    property_type = DatabaseEdgeType(property_type_map["property_type"])
                    property_type = cast("PropertyTypes", property_type)
                    if property_type not in deduplicated_attr.branch_properties_map[branch]:
                        deduplicated_attr.branch_properties_map[branch][property_type] = set()
                    for property_value_statuses in property_type_map["property_value_maps"]:
                        property_value = property_value_statuses["property_value"]
                        earliest_active = property_value_statuses["earliest_active"]
                        latest_deleted = property_value_statuses["latest_deleted"]
                        branch_property = BranchProperty(
                            active_from=earliest_active,
                            deleted_at=latest_deleted,
                            property_type=property_type,
                            value=property_value,
                        )
                        deduplicated_attr.branch_properties_map[branch][property_type].add(branch_property)
            deduplicated_node.attributes_map = deduplicated_attrs_by_name

            # get the relationship-level data
            rel_branch_details_dicts: list[dict] = result.get_as_type("rel_branch_details", return_type=list)
            deduplicated_rels_map: dict[tuple[str, str, RelationshipDirection], RelationshipDeduplicated] = {}
            for rel_branch_details in rel_branch_details_dicts:
                branch = rel_branch_details["branch"]
                rel_name = rel_branch_details["rel_name"]
                direction = RelationshipDirection(rel_branch_details["direction"])
                peer_uuid = rel_branch_details["peer_uuid"]
                deduplicated_rel_key = (rel_name, peer_uuid, direction)
                if deduplicated_rel_key not in deduplicated_rels_map:
                    deduplicated_rels_map[deduplicated_rel_key] = RelationshipDeduplicated(
                        name=rel_name, direction=direction, peer_uuid=peer_uuid, branch_properties_map={}
                    )
                dedup_rel = deduplicated_rels_map[deduplicated_rel_key]
                if branch not in dedup_rel.branch_properties_map:
                    dedup_rel.branch_properties_map[branch] = {}
                for property_type_map in rel_branch_details["property_type_maps"]:
                    property_type = DatabaseEdgeType(property_type_map["property_type"])
                    property_type = cast("PropertyTypes", property_type)
                    if property_type not in dedup_rel.branch_properties_map[branch]:
                        dedup_rel.branch_properties_map[branch][property_type] = set()
                    for property_value_statuses in property_type_map["property_value_maps"]:
                        property_value = property_value_statuses["property_value"]
                        earliest_active = property_value_statuses["earliest_active"]
                        latest_deleted = property_value_statuses["latest_deleted"]
                        branch_property = BranchProperty(
                            active_from=earliest_active,
                            deleted_at=latest_deleted,
                            property_type=property_type,
                            value=property_value,
                        )
                        dedup_rel.branch_properties_map[branch][property_type].add(branch_property)
            deduplicated_node.relationships_map = deduplicated_rels_map

            deduplicated_nodes.append(deduplicated_node)
        return deduplicated_nodes


class DbSnapshotterDeduplicated:
    """
    DOES NOT WORK QUITE RIGHT FOR SOME RELATIONSHIPS TOUCHING MULTIPLE NODES WITH THE SAME UUID
    NEEDS INVESTIGATION BEFORE BEING USED ANYWHERE

    Captures the state of all nodes, attributes, and relationships on the database, removing duplicated edges/vertices

    NOTES:
    - Does not account for the IS_RESERVED edge type
    - Does not fully account for the same attribute/relationship being removed and re-added on the same branch.
      - for example, if I do the following updates
        - (t0) n.car.name = "a"
        - (t1) n.car.name = "b"
        - (t2) n.car.name = "a"
        - (t3) n.car.name = "b"
      - then the "a" value on n.car will be recorded as active from t0 to t2 and the "b" value will be recorded as active from t1
    """

    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def snapshot(self) -> DbSnapshotDeduplicated:
        nodes_query = await DeduplicatedNodesQuery.init(db=self.db)
        await nodes_query.execute(db=self.db)
        deduplicated_nodes = nodes_query.get_deduplicated_nodes()
        return DbSnapshotDeduplicated(nodes_map={n.identifier: n for n in deduplicated_nodes})
