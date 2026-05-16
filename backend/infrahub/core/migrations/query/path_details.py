from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from infrahub.core import registry
from infrahub.core.constants import GLOBAL_BRANCH_NAME, RelationshipDirection
from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.core.schema.basenode_schema import SchemaAttributePath
    from infrahub.database import InfrahubDatabase


SCHEMA_KINDS_TO_SKIP: list[str] = ["SchemaNode", "SchemaAttribute", "SchemaRelationship", "SchemaGeneric"]


class DefaultBranchNodeCount(Query):
    """Get the number of Node vertices on the given branches that are not in the kinds_to_skip list.

    Only works for default and global branches. Non-default branches would only return a count of nodes
    created on the given branches.

    """

    name = "get_branch_node_count"
    type = QueryType.READ

    def __init__(
        self, kinds_to_skip: list[str] | None = None, kinds_to_include: list[str] | None = None, **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)
        self.kinds_to_skip = kinds_to_skip or []
        self.kinds_to_include = kinds_to_include

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        self.params = {
            "branch_names": [registry.default_branch, GLOBAL_BRANCH_NAME],
            "kinds_to_skip": self.kinds_to_skip,
            "kinds_to_include": self.kinds_to_include,
        }
        query = """
MATCH (n:Node)-[e:IS_PART_OF]->(:Root)
WHERE NOT n.kind IN $kinds_to_skip
AND ($kinds_to_include IS NULL OR n.kind IN $kinds_to_include)
AND e.branch IN $branch_names
AND e.status = "active"
AND e.to IS NULL
AND NOT exists((n)-[:IS_PART_OF {branch: e.branch, status: "deleted"}]->(:Root))
WITH count(*) AS num_nodes
        """
        self.add_to_query(query)
        self.return_labels = ["num_nodes"]

    def get_num_nodes(self) -> int:
        result = self.get_result()
        if not result:
            return 0
        return result.get_as_type(label="num_nodes", return_type=int)


class GetResultMapQuery(Query):
    def get_result_map(self, schema_paths: list[SchemaAttributePath]) -> dict[str, list[str | None]]:
        """Get the values for the given schema paths for all the Nodes captured by this query."""
        # the query results for attribute and schema paths are unordered
        # so we make this list of keys for ordering the results from the query
        schema_path_keys: list[tuple[str, RelationshipDirection, str] | str] = []
        for schema_path in schema_paths:
            if schema_path.is_type_attribute and schema_path.attribute_schema:
                path_key: str | tuple[str, RelationshipDirection, str] = schema_path.attribute_schema.name
            elif schema_path.is_type_relationship and schema_path.relationship_schema and schema_path.attribute_schema:
                path_key = (
                    schema_path.relationship_schema.get_identifier(),
                    schema_path.relationship_schema.direction,
                    schema_path.attribute_schema.name,
                )
            schema_path_keys.append(path_key)

        result_map: dict[str, list[str | None]] = {}
        for result in self.get_results():
            node_uuid = result.get_as_type(label="n_uuid", return_type=str)

            # for each node, build a map of the schema path key to value so that they
            # can be ordered correctly for the input `schema_paths`
            schema_path_value_map: dict[str | tuple[str, RelationshipDirection, str], Any] = {}
            attr_values_tuples: list[tuple[str, Any]] = result.get_as_type(label="attr_vals_list", return_type=list)
            for attr_value_tuple in attr_values_tuples:
                attr_name = attr_value_tuple[0]
                attr_value = attr_value_tuple[1]
                schema_path_value_map[attr_name] = attr_value

            relationship_values_tuples: list[tuple[str, str, str, Any]] = result.get_as_type(
                label="peer_attr_vals_list", return_type=list
            )
            for rel_value_tuple in relationship_values_tuples:
                rel_name = rel_value_tuple[0]
                direction_raw = rel_value_tuple[1]
                direction = RelationshipDirection.BIDIR
                match direction_raw:
                    case "outbound":
                        direction = RelationshipDirection.OUTBOUND
                    case "inbound":
                        direction = RelationshipDirection.INBOUND
                peer_attr_name = rel_value_tuple[2]
                peer_val = rel_value_tuple[3]
                schema_path_value_map[rel_name, direction, peer_attr_name] = peer_val

            schema_path_values: list[str | None] = []
            for schema_path_key in schema_path_keys:
                value = schema_path_value_map.get(schema_path_key)
                schema_path_values.append(str(value) if value is not None else None)
            result_map[node_uuid] = schema_path_values
        return result_map


class GetPathDetailsBranchQuery(GetResultMapQuery):
    name = "get_path_details_branch"
    type = QueryType.READ
    insert_limit = False

    def __init__(
        self, schema_kind: str, schema_paths: list[SchemaAttributePath], updates_only: bool = True, **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)

        if self.branch.name in [registry.default_branch, GLOBAL_BRANCH_NAME]:
            raise ValueError("This query can only be used on non-default branches")
        self.schema_kind = schema_kind
        self.updates_only = updates_only
        self.attribute_names = []
        self.bidir_rel_attr_map: dict[str, list[str]] = defaultdict(list)
        self.outbound_rel_attr_map: dict[str, list[str]] = defaultdict(list)
        self.inbound_rel_attr_map: dict[str, list[str]] = defaultdict(list)
        for schema_path in schema_paths:
            if schema_path.is_type_attribute and schema_path.attribute_schema:
                self.attribute_names.append(schema_path.attribute_schema.name)
            elif schema_path.is_type_relationship and schema_path.relationship_schema and schema_path.attribute_schema:
                key = schema_path.relationship_schema.get_identifier()
                value = schema_path.attribute_schema.name
                if schema_path.relationship_schema.direction is RelationshipDirection.BIDIR:
                    self.bidir_rel_attr_map[key].append(value)
                elif schema_path.relationship_schema.direction is RelationshipDirection.OUTBOUND:
                    self.outbound_rel_attr_map[key].append(value)
                elif schema_path.relationship_schema.direction is RelationshipDirection.INBOUND:
                    self.inbound_rel_attr_map[key].append(value)

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        branch_filter, branch_filter_params = self.branch.get_query_filter_path(at=self.at)
        self.params.update(branch_filter_params)
        self.params.update(
            {
                "branch_name": self.branch.name,
                "attribute_names": self.attribute_names,
                "outbound_rel_ids": list(self.outbound_rel_attr_map.keys()),
                "inbound_rel_ids": list(self.inbound_rel_attr_map.keys()),
                "bidirectional_rel_ids": list(self.bidir_rel_attr_map.keys()),
                "outbound_rel_attr_map": self.outbound_rel_attr_map,
                "inbound_rel_attr_map": self.inbound_rel_attr_map,
                "bidirectional_rel_attr_map": self.bidir_rel_attr_map,
                "offset": self.offset,
                "limit": self.limit,
            }
        )
        get_active_nodes_query = """
// ------------
// Get the active nodes of the given kind on the branches
// ------------
MATCH (n:%(schema_kind)s)-[r:IS_PART_OF]->(:Root)
WHERE %(branch_filter)s
WITH DISTINCT n
CALL (n) {
    MATCH (n)-[r:IS_PART_OF]->(:Root)
    WHERE %(branch_filter)s
    RETURN r.status = "active" AS is_active
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
}
WITH n, is_active
WHERE is_active = TRUE
        """ % {"schema_kind": self.schema_kind, "branch_filter": branch_filter}
        self.add_to_query(get_active_nodes_query)

        if self.updates_only:
            updated_nodes_filter_query = """
// ------------
// filter to any nodes that might have changes on the branch we care about
// ------------
OPTIONAL MATCH (n)-[r1:HAS_ATTRIBUTE]->(attr:Attribute)-[r2:HAS_VALUE]->(attr_val:AttributeValue)
WHERE attr.name in $attribute_names
AND r2.branch = $branch_name
AND r2.status = "active"
AND r2.to IS NULL
WITH n, attr_val IS NOT NULL AS has_attr_update
OPTIONAL MATCH (n)-[r1:IS_RELATED]-(rel:Relationship)-[r2:IS_RELATED]-(peer:Node)-[r3:HAS_ATTRIBUTE]-(attr:Attribute)-[r4:HAS_VALUE]->(attr_val)
WHERE rel.name IN $bidirectional_rel_ids + $outbound_rel_ids + $inbound_rel_ids
AND n.uuid <> peer.uuid
AND (
    attr.name IN $outbound_rel_attr_map[rel.name]
    OR attr.name IN $inbound_rel_attr_map[rel.name]
    OR attr.name IN $bidirectional_rel_attr_map[rel.name]
)
AND $branch_name IN [r1.branch, r2.branch, r3.branch, r4.branch]
WITH n, has_attr_update, attr_val IS NOT NULL AS has_rel_update
WITH n, any(x IN collect(has_attr_update OR has_rel_update) WHERE x = TRUE) AS has_update
WITH n, has_update
WHERE has_update = TRUE
            """
            self.add_to_query(updated_nodes_filter_query)

        get_node_details_query = """
// ------------
// Order and limit the Nodes
// ------------
ORDER BY elementId(n)
SKIP toInteger($offset)
LIMIT toInteger($limit)
// ------------
// for every possibly updated node
// get all the attribute values on this branch
// ------------
OPTIONAL MATCH (n)-[r:HAS_ATTRIBUTE]->(attr:Attribute)
WHERE attr.name IN $attribute_names
WITH DISTINCT n, attr
CALL (n, attr) {
    OPTIONAL MATCH (n)-[r1:HAS_ATTRIBUTE]->(attr)-[r2:HAS_VALUE]->(attr_val)
    WHERE all(r in [r1, r2] WHERE %(branch_filter)s)
    RETURN attr_val.value AS attr_value, r1.status = "active" AND r2.status = "active" AS is_active
    ORDER BY r2.branch_level DESC, r2.from DESC, r2.status ASC, r1.branch_level DESC, r1.from DESC, r1.status ASC
    LIMIT 1
}
WITH n, attr, attr_value
WHERE is_active = TRUE
WITH n, collect([attr.name, attr_value]) AS attr_vals_list
// ------------
// for every possibly updated node
// get all the relationships on this branch
// ------------
OPTIONAL MATCH (n)-[:IS_RELATED]-(rel:Relationship)
WHERE rel.name IN $bidirectional_rel_ids + $outbound_rel_ids + $inbound_rel_ids
WITH DISTINCT n, attr_vals_list, rel
CALL (n, rel) {
    OPTIONAL MATCH (n)-[r1:IS_RELATED]-(rel)-[r2:IS_RELATED]-(peer:Node)
    WHERE all(r in [r1, r2] WHERE %(branch_filter)s)
    AND n.uuid <> peer.uuid
    AND (
        (startNode(r1) = n AND startNode(r2) = rel AND rel.name IN $outbound_rel_ids)
        OR (startNode(r1) = rel AND startNode(r2) = peer AND rel.name IN $inbound_rel_ids)
        OR (startNode(r1) = n AND startNode(r2) = peer AND rel.name IN $bidirectional_rel_ids)
    )
    RETURN
        peer,
        r1.status = "active" AND r2.status = "active" AS is_active,
        CASE
            WHEN startNode(r1) = n AND startNode(r2) = rel AND rel.name IN $outbound_rel_ids THEN "outbound"
            WHEN startNode(r1) = rel AND startNode(r2) = peer AND rel.name IN $inbound_rel_ids THEN "inbound"
            ELSE "bidir"
        END AS direction
    ORDER BY r2.branch_level DESC, r2.from DESC, r2.status ASC, r1.branch_level DESC, r1.from DESC, r1.status ASC
    LIMIT 1
}
// ------------
// get the attribute values that we care about for each relationship
// ------------
WITH n, attr_vals_list, rel.name AS rel_name, direction, peer
WHERE is_active = TRUE OR rel_name IS NULL
WITH *, CASE
    WHEN direction = "outbound" THEN $outbound_rel_attr_map[rel_name]
    WHEN direction = "inbound" THEN $inbound_rel_attr_map[rel_name]
    ELSE $bidirectional_rel_attr_map[rel_name]
END AS peer_attr_names
UNWIND COALESCE(peer_attr_names, [NULL]) AS peer_attr_name
CALL (rel_name, direction, peer, peer_attr_name){
    OPTIONAL MATCH (peer)-[r1:HAS_ATTRIBUTE]->(attr:Attribute)-[r2:HAS_VALUE]->(attr_val)
    WHERE attr.name = peer_attr_name
    AND all(r in [r1, r2] WHERE %(branch_filter)s)
    RETURN attr_val.value AS peer_attr_value, r1.status = "active" AND r2.status = "active" AS is_active
    ORDER BY r2.branch_level DESC, r2.from DESC, r2.status ASC, r1.branch_level DESC, r1.from DESC, r1.status ASC
    LIMIT 1
}
// ------------
// collect everything to return a pair of lists with each node UUID
// ------------
WITH DISTINCT n, attr_vals_list, rel_name, peer, direction, peer_attr_name, peer_attr_value
WITH n, attr_vals_list, collect([rel_name, direction, peer_attr_name, peer_attr_value]) AS peer_attr_vals_list
        """ % {"branch_filter": branch_filter}
        self.add_to_query(get_node_details_query)
        self.return_labels = ["n.uuid AS n_uuid", "attr_vals_list", "peer_attr_vals_list"]


class GetPathDetailsDefaultBranch(GetResultMapQuery):
    """Get the values of the given schema paths for the given kind of node on the default and global branches.

    Supports limit and offset for pagination.

    """

    name = "get_path_details_default_branch"
    type = QueryType.READ
    insert_limit = False

    def __init__(self, schema_kind: str, schema_paths: list[SchemaAttributePath], **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.branch_names = [registry.default_branch, GLOBAL_BRANCH_NAME]
        self.schema_kind = schema_kind
        self.attribute_names = []
        self.bidir_rel_attr_map: dict[str, list[str]] = defaultdict(list)
        self.outbound_rel_attr_map: dict[str, list[str]] = defaultdict(list)
        self.inbound_rel_attr_map: dict[str, list[str]] = defaultdict(list)
        for schema_path in schema_paths:
            if schema_path.is_type_attribute and schema_path.attribute_schema:
                self.attribute_names.append(schema_path.attribute_schema.name)
            elif schema_path.is_type_relationship and schema_path.relationship_schema and schema_path.attribute_schema:
                key = schema_path.relationship_schema.get_identifier()
                value = schema_path.attribute_schema.name
                if schema_path.relationship_schema.direction is RelationshipDirection.BIDIR:
                    self.bidir_rel_attr_map[key].append(value)
                elif schema_path.relationship_schema.direction is RelationshipDirection.OUTBOUND:
                    self.outbound_rel_attr_map[key].append(value)
                elif schema_path.relationship_schema.direction is RelationshipDirection.INBOUND:
                    self.inbound_rel_attr_map[key].append(value)

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        self.params = {
            "branch_names": self.branch_names,
            "attribute_names": self.attribute_names,
            "outbound_rel_ids": list(self.outbound_rel_attr_map.keys()),
            "inbound_rel_ids": list(self.inbound_rel_attr_map.keys()),
            "bidirectional_rel_ids": list(self.bidir_rel_attr_map.keys()),
            "outbound_rel_attr_map": self.outbound_rel_attr_map,
            "inbound_rel_attr_map": self.inbound_rel_attr_map,
            "bidirectional_rel_attr_map": self.bidir_rel_attr_map,
            "offset": self.offset,
            "limit": self.limit,
        }
        get_details_query = """
// ------------
// Get the active nodes of the given kind on the branches
// ------------
MATCH (n:%(schema_kind)s)-[e:IS_PART_OF]->(:Root)
WHERE e.branch IN $branch_names
AND e.to IS NULL
AND e.status = "active"
// ------------
// Order and limit the Nodes
// ------------
WITH DISTINCT n
ORDER BY elementId(n)
SKIP toInteger($offset)
LIMIT toInteger($limit)
// ------------
// Get the values for the attribute schema paths of the Nodes, if any
// ------------
OPTIONAL MATCH (n)-[e:HAS_ATTRIBUTE]->(attr:Attribute)
WHERE attr.name IN $attribute_names
AND e.branch IN $branch_names
AND e.to IS NULL
AND e.status = "active"
WITH n, attr
OPTIONAL MATCH (attr)-[e:HAS_VALUE]->(attr_val:AttributeValue)
WHERE e.branch IN $branch_names
AND e.to IS NULL
AND e.status = "active"
WITH n, collect([attr.name, attr_val.value]) AS attr_vals_list
// ------------
// Get the values for the relationship schema paths of the Nodes, if any
// ------------
OPTIONAL MATCH (n)-[e1:IS_RELATED]-(rel:Relationship)-[e2:IS_RELATED]-(peer:Node)
WHERE rel.name IN $bidirectional_rel_ids + $outbound_rel_ids + $inbound_rel_ids
AND n.uuid <> peer.uuid
AND e1.branch IN $branch_names
AND e1.to IS NULL
AND e1.status = "active"
AND e2.branch IN $branch_names
AND e2.to IS NULL
AND e2.status = "active"
AND (
    (startNode(e1) = n AND startNode(e2) = rel AND rel.name IN $outbound_rel_ids)
    OR (startNode(e1) = rel AND startNode(e2) = peer AND rel.name IN $inbound_rel_ids)
    OR (startNode(e1) = n AND startNode(e2) = peer AND rel.name IN $bidirectional_rel_ids)
)
WITH DISTINCT n, attr_vals_list, rel.name AS rel_name, peer,  CASE
    WHEN startNode(e1) = n AND startNode(e2) = rel AND rel.name IN $outbound_rel_ids THEN "outbound"
    WHEN startNode(e1) = rel AND startNode(e2) = peer AND rel.name IN $inbound_rel_ids THEN "inbound"
    ELSE "bidir"
END AS direction
OPTIONAL MATCH (peer)-[e1:HAS_ATTRIBUTE]->(attr:Attribute)-[e2:HAS_VALUE]->(peer_attr_val:AttributeValue)
WHERE (
    (direction = "outbound" AND attr.name IN $outbound_rel_attr_map[rel_name])
    OR (direction = "inbound" AND attr.name IN $inbound_rel_attr_map[rel_name])
    OR (direction = "bidir" AND attr.name IN $bidirectional_rel_attr_map[rel_name])
)
AND e1.branch IN $branch_names
AND e1.to IS NULL
AND e1.status = "active"
AND e2.branch IN $branch_names
AND e2.to IS NULL
AND e2.status = "active"
// ------------
// collect everything to return a pair of lists with each node UUID
// ------------
WITH DISTINCT n, attr_vals_list, rel_name, peer, direction, attr.name AS peer_attr_name, peer_attr_val.value AS peer_val
WITH n, attr_vals_list, collect([rel_name, direction, peer_attr_name, peer_val]) AS peer_attr_vals_list
        """ % {"schema_kind": self.schema_kind}
        self.add_to_query(get_details_query)
        self.return_labels = ["n.uuid AS n_uuid", "attr_vals_list", "peer_attr_vals_list"]
