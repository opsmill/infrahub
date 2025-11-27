from __future__ import annotations

from collections import defaultdict
from itertools import chain
from typing import TYPE_CHECKING, Any

import ujson
from rich.progress import Progress, TaskID

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import GLOBAL_BRANCH_NAME, BranchSupportType, RelationshipDirection
from infrahub.core.initialization import get_root_node
from infrahub.core.migrations.shared import MigrationResult, get_migration_console
from infrahub.core.query import Query, QueryType
from infrahub.core.schema import NodeSchema
from infrahub.exceptions import SchemaNotFoundError
from infrahub.types import is_large_attribute_type

from ..shared import MigrationRequiringRebase
from .load_schema_branch import get_or_load_schema_branch

if TYPE_CHECKING:
    from infrahub.core.schema import AttributeSchema, NodeSchema, ProfileSchema, TemplateSchema
    from infrahub.core.schema.basenode_schema import SchemaAttributePath
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


console = get_migration_console()


class DefaultBranchNodeCount(Query):
    """
    Get the number of Node vertices on the given branches that are not in the kinds_to_skip list
    Only works for default and global branches. Non-default branches would only return a count of nodes
    created on the given branches
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
        """
        Get the values for the given schema paths for all the Nodes captured by this query
        """
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
    """
    Get the values of the given schema paths for the given kind of node on the default and global branches
    Supports limit and offset for pagination
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


class UpdateAttributeValuesQuery(Query):
    """
    Update the values of the given attribute schema for the input Node-id-to-value map
    Includes special handling for updating large-type attributes b/c they are not indexed and will be slow to update
    on large data sets
    """

    name = "update_attribute_values"
    type = QueryType.WRITE
    insert_return = False

    def __init__(self, attribute_schema: AttributeSchema, values_by_id_map: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.attribute_name = attribute_schema.name
        self.is_large_type_attribute = is_large_attribute_type(attribute_schema.kind)
        self.is_branch_agnostic = attribute_schema.get_branch() is BranchSupportType.AGNOSTIC
        self.values_by_id_map = values_by_id_map

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        self.params = {
            "node_uuids": list(self.values_by_id_map.keys()),
            "attribute_name": self.attribute_name,
            "values_by_id": self.values_by_id_map,
            "default_branch": registry.default_branch,
            "global_branch": GLOBAL_BRANCH_NAME,
            "branch": GLOBAL_BRANCH_NAME if self.is_branch_agnostic else self.branch.name,
            "branch_level": 1 if self.is_branch_agnostic else self.branch.hierarchy_level,
            "at": self.at.to_string(),
        }
        branch_filter, branch_filter_params = self.branch.get_query_filter_path(at=self.at)
        self.params.update(branch_filter_params)

        if self.is_large_type_attribute:
            # we make our own index of value to database ID, creating any vertices that are missing
            # the mapping is a list of tuples instead of an actual mapping b/c creating an actual map is not possible
            # without apoc functions
            all_distinct_values = list(set(self.values_by_id_map.values()))
            diy_index_query = """
MATCH (av:AttributeValue&!AttributeValueIndexed {is_default: false})
WHERE av.value IN $all_distinct_values
WITH collect([av.value, elementId(av)]) AS value_id_pairs, collect(av.value) AS found_values
WITH value_id_pairs, found_values,
    reduce(
        missing_distinct_values = [], value IN $all_distinct_values |
            CASE
                WHEN value IN found_values THEN missing_distinct_values
                ELSE missing_distinct_values + [value]
            END
    ) AS missing_distinct_values
CALL (missing_distinct_values) {
    UNWIND missing_distinct_values AS missing_value
    CREATE (av:AttributeValue {is_default: false, value: missing_value})
    RETURN collect([av.value, elementId(av)]) AS created_value_id_pairs
}
WITH value_id_pairs + created_value_id_pairs AS value_id_pairs
            """
            self.params["all_distinct_values"] = all_distinct_values
        else:
            # if this is not a large-type attribute, then just set the map to be empty
            diy_index_query = """WITH [] AS value_id_pairs"""

        self.add_to_query(diy_index_query)

        if self.branch.name in [registry.default_branch, GLOBAL_BRANCH_NAME]:
            update_value_query = """
// ------------
// Find the Nodes and Attributes we need to update
// ------------
MATCH (n:Node)-[e:IS_PART_OF]->(:Root)
WHERE n.uuid IN $node_uuids
AND e.branch IN [$default_branch, $global_branch]
AND e.to IS NULL
AND e.status = "active"
WITH DISTINCT n, value_id_pairs
MATCH (n)-[e:HAS_ATTRIBUTE]->(attr:Attribute {name: $attribute_name})
WHERE e.branch IN [$default_branch, $global_branch]
AND e.to IS NULL
AND e.status = "active"
// ------------
// If the attribute has an existing value on the branch, then set the to time on it
// but only if the value is different from the new value
// ------------
WITH DISTINCT n, attr, value_id_pairs
CALL (attr) {
    OPTIONAL MATCH (attr)-[e:HAS_VALUE]->(existing_av)
    WHERE e.branch IN [$default_branch, $global_branch]
    AND e.to IS NULL
    AND e.status = "active"
    RETURN existing_av, e AS existing_has_value
}
CALL (existing_has_value) {
    WITH existing_has_value
    WHERE existing_has_value IS NOT NULL
    SET existing_has_value.to = $at
}
            """
        else:
            update_value_query = """
// ------------
// Find the Nodes and Attributes we need to update
// ------------
MATCH (n:Node)
WHERE n.uuid IN $node_uuids
CALL (n) {
    MATCH (n)-[r:IS_PART_OF]->(:Root)
    WHERE %(branch_filter)s
    RETURN r.status = "active" AS is_active
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
}
WITH n, value_id_pairs, is_active
WHERE is_active = TRUE
WITH DISTINCT n, value_id_pairs
CALL (n) {
    MATCH (n)-[r:HAS_ATTRIBUTE]->(attr:Attribute {name: $attribute_name})
    WHERE %(branch_filter)s
    RETURN attr, r.status = "active"  AS is_active
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
}
WITH DISTINCT n, attr, value_id_pairs, is_active
WHERE is_active = TRUE
// ------------
// If the attribute has an existing value on the branch, then set the to time on it
// but only if the value is different from the new value
// ------------
CALL (n, attr) {
    OPTIONAL MATCH (attr)-[r:HAS_VALUE]->(existing_av)
    WHERE %(branch_filter)s
    WITH r, existing_av
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
    WITH CASE
        WHEN existing_av.value <> $values_by_id[n.uuid]
        AND r.status = "active"
        AND r.branch = $branch
        THEN [r, existing_av]
        ELSE [NULL, NULL]
    END AS existing_details
    RETURN existing_details[0] AS existing_has_value, existing_details[1] AS existing_av
}
CALL (existing_has_value) {
    WITH existing_has_value
    WHERE existing_has_value IS NOT NULL
    SET existing_has_value.to = $at
}
            """ % {"branch_filter": branch_filter}
        self.add_to_query(update_value_query)

        if self.is_large_type_attribute:
            # use the index we created at the start to get the database ID of the AttributeValue vertex
            # and then link the Attribute to the AttributeValue
            set_value_query = """
// ------------
// only make updates if the existing value is not the same as the new value
// ------------
WITH attr, existing_av, value_id_pairs, $values_by_id[n.uuid] AS required_value
WHERE existing_av.value <> required_value
OR existing_av IS NULL
WITH attr, value_id_pairs, required_value,
    reduce(av_vertex_id = NULL, pair IN value_id_pairs |
        CASE
            WHEN av_vertex_id IS NOT NULL THEN av_vertex_id
            WHEN pair[0] = required_value THEN pair[1]
            ELSE av_vertex_id
        END
    ) AS av_vertex_id
MATCH (av:AttributeValue)
WHERE elementId(av) = av_vertex_id
CREATE (attr)-[r:HAS_VALUE { branch: $branch, branch_level: $branch_level, status: "active", from: $at }]->(av)
            """
        else:
            # if not a large-type attribute, then we can just use the regular MERGE clause
            # that makes use of the index on AttributeValueIndexed
            set_value_query = """
// ------------
// only make updates if the existing value is not the same as the new value
// ------------
WITH n, attr, existing_av, value_id_pairs, $values_by_id[n.uuid] AS required_value
WHERE existing_av.value <> required_value
OR existing_av IS NULL
CALL (n, attr) {
    MERGE (av:AttributeValue&AttributeValueIndexed {is_default: false, value: $values_by_id[n.uuid]} )
    WITH av, attr
    LIMIT 1
    CREATE (attr)-[r:HAS_VALUE { branch: $branch, branch_level: $branch_level, status: "active", from: $at }]->(av)
}
            """
        self.add_to_query(set_value_query)


class Migration044(MigrationRequiringRebase):
    """
    Backfill `human_friendly_id` and `display_label` attributes for nodes with schemas that define them.
    """

    name: str = "044_backfill_hfid_display_label_in_db"
    minimum_version: int = 43
    update_batch_size: int = 1000
    # skip these b/c the attributes on these schema-related nodes are used to define the values included in
    # the human_friendly_id and display_label attributes on instances of these schema, so should not be updated
    kinds_to_skip: list[str] = ["SchemaNode", "SchemaAttribute", "SchemaRelationship", "SchemaGeneric"]

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    async def _do_one_schema_all(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        schema: NodeSchema | ProfileSchema | TemplateSchema,
        schema_branch: SchemaBranch,
        attribute_schema_map: dict[AttributeSchema, AttributeSchema],
        progress: Progress | None = None,
        update_task: TaskID | None = None,
    ) -> None:
        print(f"Processing {schema.kind}...", end="")

        schema_paths_by_name: dict[str, list[SchemaAttributePath]] = {}
        for source_attribute_schema in attribute_schema_map.keys():
            node_schema_property = getattr(schema, source_attribute_schema.name)
            if not node_schema_property:
                continue
            if isinstance(node_schema_property, list):
                schema_paths_by_name[source_attribute_schema.name] = [
                    schema.parse_schema_path(path=str(path), schema=schema_branch) for path in node_schema_property
                ]
            else:
                schema_paths_by_name[source_attribute_schema.name] = [
                    schema.parse_schema_path(path=str(node_schema_property), schema=schema_branch)
                ]
        all_schema_paths = list(chain(*schema_paths_by_name.values()))
        offset = 0

        # loop until we get no results from the get_details_query
        while True:
            if branch.is_default:
                get_details_query: GetResultMapQuery = await GetPathDetailsDefaultBranch.init(
                    db=db,
                    schema_kind=schema.kind,
                    schema_paths=all_schema_paths,
                    offset=offset,
                    limit=self.update_batch_size,
                )
            else:
                get_details_query = await GetPathDetailsBranchQuery.init(
                    db=db,
                    branch=branch,
                    schema_kind=schema.kind,
                    schema_paths=all_schema_paths,
                    updates_only=False,
                    offset=offset,
                    limit=self.update_batch_size,
                )
            await get_details_query.execute(db=db)

            num_updates = 0
            for source_attribute_schema, destination_attribute_schema in attribute_schema_map.items():
                schema_paths = schema_paths_by_name[source_attribute_schema.name]
                schema_path_values_map = get_details_query.get_result_map(schema_paths)
                num_updates = max(num_updates, len(schema_path_values_map))
                formatted_schema_path_values_map = {}
                for k, v in schema_path_values_map.items():
                    if not v:
                        continue
                    if destination_attribute_schema.kind == "List":
                        formatted_schema_path_values_map[k] = ujson.dumps(v)
                    else:
                        formatted_schema_path_values_map[k] = " ".join(item for item in v if item is not None)

                if not formatted_schema_path_values_map:
                    continue

                update_display_label_query = await UpdateAttributeValuesQuery.init(
                    db=db,
                    branch=branch,
                    attribute_schema=destination_attribute_schema,
                    values_by_id_map=formatted_schema_path_values_map,
                )
                await update_display_label_query.execute(db=db)

            if progress is not None and update_task is not None:
                progress.update(update_task, advance=num_updates)

            if num_updates == 0:
                break

            offset += self.update_batch_size

        print("done")

    async def execute(self, db: InfrahubDatabase) -> MigrationResult:
        root_node = await get_root_node(db=db, initialize=False)
        default_branch_name = root_node.default_branch
        default_branch = await Branch.get_by_name(db=db, name=default_branch_name)

        main_schema_branch = await get_or_load_schema_branch(db=db, branch=default_branch)

        total_nodes_query = await DefaultBranchNodeCount.init(db=db, kinds_to_skip=self.kinds_to_skip)
        await total_nodes_query.execute(db=db)
        total_nodes_count = total_nodes_query.get_num_nodes()

        base_node_schema = main_schema_branch.get("SchemaNode", duplicate=False)
        display_label_attribute_schema = base_node_schema.get_attribute("display_label")
        display_labels_attribute_schema = base_node_schema.get_attribute("display_labels")
        hfid_attribute_schema = base_node_schema.get_attribute("human_friendly_id")

        try:
            with Progress(console=console) as progress:
                update_task = progress.add_task(
                    f"Set display_label and human_friendly_id for {total_nodes_count} nodes on default branch",
                    total=total_nodes_count,
                )
                for node_schema_name in main_schema_branch.node_names:
                    if node_schema_name in self.kinds_to_skip:
                        continue

                    node_schema = main_schema_branch.get_node(name=node_schema_name, duplicate=False)

                    if node_schema.branch is not BranchSupportType.AWARE:
                        continue

                    attribute_schema_map = {}
                    if node_schema.display_labels:
                        attribute_schema_map[display_labels_attribute_schema] = display_label_attribute_schema
                    if node_schema.human_friendly_id:
                        attribute_schema_map[hfid_attribute_schema] = hfid_attribute_schema
                    if not attribute_schema_map:
                        continue

                    await self._do_one_schema_all(
                        db=db,
                        branch=default_branch,
                        schema=node_schema,
                        schema_branch=main_schema_branch,
                        attribute_schema_map=attribute_schema_map,
                        progress=progress,
                        update_task=update_task,
                    )

        except Exception as exc:
            return MigrationResult(errors=[str(exc)])
        return MigrationResult()

    async def _do_one_schema_branch(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        schema: NodeSchema | ProfileSchema | TemplateSchema,
        schema_branch: SchemaBranch,
        source_attribute_schema: AttributeSchema,
        destination_attribute_schema: AttributeSchema,
    ) -> None:
        print(f"Processing {schema.kind}.{destination_attribute_schema.name} for {branch.name}...", end="")

        schema_property = getattr(schema, source_attribute_schema.name)
        if isinstance(schema_property, list):
            schema_paths = [
                schema.parse_schema_path(path=str(path_part), schema=schema_branch) for path_part in schema_property
            ]
        else:
            schema_paths = [schema.parse_schema_path(path=str(schema_property), schema=schema_branch)]

        offset = 0

        while True:
            # loop until we get no results from the get_details_query
            get_details_query = await GetPathDetailsBranchQuery.init(
                db=db,
                branch=branch,
                schema_kind=schema.kind,
                schema_paths=schema_paths,
                offset=offset,
                limit=self.update_batch_size,
            )
            await get_details_query.execute(db=db)

            schema_path_values_map = get_details_query.get_result_map(schema_paths)
            if not schema_path_values_map:
                print("done")
                break
            formatted_schema_path_values_map = {}
            for k, v in schema_path_values_map.items():
                if not v:
                    continue
                if destination_attribute_schema.kind == "List":
                    formatted_v = ujson.dumps(v)
                else:
                    formatted_v = " ".join(item for item in v if item is not None)
                formatted_schema_path_values_map[k] = formatted_v

            update_attr_values_query = await UpdateAttributeValuesQuery.init(
                db=db,
                branch=branch,
                attribute_schema=destination_attribute_schema,
                values_by_id_map=formatted_schema_path_values_map,
            )
            await update_attr_values_query.execute(db=db)

            offset += self.update_batch_size

    async def execute_against_branch(self, db: InfrahubDatabase, branch: Branch) -> MigrationResult:
        default_branch = await Branch.get_by_name(db=db, name=registry.default_branch)
        main_schema_branch = await get_or_load_schema_branch(db=db, branch=default_branch)
        schema_branch = await get_or_load_schema_branch(db=db, branch=branch)

        base_node_schema = schema_branch.get("SchemaNode", duplicate=False)
        display_label_attribute_schema = base_node_schema.get_attribute("display_label")
        display_labels_attribute_schema = base_node_schema.get_attribute("display_labels")
        hfid_attribute_schema = base_node_schema.get_attribute("human_friendly_id")

        try:
            for node_schema_name in schema_branch.node_names:
                if node_schema_name in self.kinds_to_skip:
                    continue

                node_schema = schema_branch.get_node(name=node_schema_name, duplicate=False)
                if node_schema.branch not in (BranchSupportType.AWARE, BranchSupportType.LOCAL):
                    continue
                try:
                    default_node_schema = main_schema_branch.get_node(name=node_schema_name, duplicate=False)
                except SchemaNotFoundError:
                    default_node_schema = None
                schemas_for_universal_update_map = {}
                schemas_for_targeted_update_map = {}
                if node_schema.display_label:
                    if default_node_schema is None or default_node_schema.display_label != node_schema.display_label:
                        schemas_for_universal_update_map[display_labels_attribute_schema] = (
                            display_label_attribute_schema
                        )
                    else:
                        schemas_for_targeted_update_map[display_labels_attribute_schema] = (
                            display_label_attribute_schema
                        )

                if node_schema.human_friendly_id:
                    if (
                        default_node_schema is None
                        or default_node_schema.human_friendly_id != node_schema.human_friendly_id
                    ):
                        schemas_for_universal_update_map[hfid_attribute_schema] = hfid_attribute_schema
                    else:
                        schemas_for_targeted_update_map[hfid_attribute_schema] = hfid_attribute_schema

                if schemas_for_universal_update_map:
                    await self._do_one_schema_all(
                        db=db,
                        branch=branch,
                        schema=node_schema,
                        schema_branch=schema_branch,
                        attribute_schema_map=schemas_for_universal_update_map,
                    )

                if not schemas_for_targeted_update_map:
                    continue

                for source_attribute_schema, destination_attribute_schema in schemas_for_targeted_update_map.items():
                    await self._do_one_schema_branch(
                        db=db,
                        branch=branch,
                        schema=node_schema,
                        schema_branch=schema_branch,
                        source_attribute_schema=source_attribute_schema,
                        destination_attribute_schema=destination_attribute_schema,
                    )

        except Exception as exc:
            return MigrationResult(errors=[str(exc)])
        return MigrationResult()
