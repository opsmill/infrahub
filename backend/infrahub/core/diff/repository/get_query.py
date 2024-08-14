from typing import Any, Iterable

from neo4j.graph import Node as Neo4jNode

from infrahub.core.constants import DiffAction
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.query import Query, QueryResult, QueryType
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.database.constants import DatabaseType

from ..model.path import (
    ConflictSelection,
    EnrichedDiffAttribute,
    EnrichedDiffConflict,
    EnrichedDiffNode,
    EnrichedDiffProperty,
    EnrichedDiffRelationship,
    EnrichedDiffRoot,
    EnrichedDiffSingleRelationship,
)


class EnrichedDiffGetQuery(Query):
    """Get all EnrichedDiffRoots for the given branches that are within the given timeframe in chronological order"""

    name = "enriched_diff_get"
    type = QueryType.READ
    insert_limit = False

    def __init__(
        self,
        base_branch_name: str,
        diff_branch_names: list[str],
        from_time: Timestamp,
        to_time: Timestamp,
        root_node_uuids: list[str] | None,
        max_depth: int,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.base_branch_name = base_branch_name
        self.diff_branch_names = diff_branch_names
        self.from_time = from_time
        self.to_time = to_time
        self.root_node_uuids = root_node_uuids
        self.max_depth = max_depth

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:
        self.params = {
            "base_branch": self.base_branch_name,
            "diff_branches": self.diff_branch_names,
            "from_time": self.from_time.to_string(),
            "to_time": self.to_time.to_string(),
            "root_node_uuids": self.root_node_uuids,
            "limit": self.limit,
            "offset": self.offset,
        }
        # ruff: noqa: E501
        query_1 = """
        // get the roots of all diffs in the query
        MATCH (diff_root:DiffRoot)
        WHERE diff_root.base_branch = $base_branch
        AND diff_root.diff_branch IN $diff_branches
        AND diff_root.from_time >= $from_time
        AND diff_root.to_time <= $to_time
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
        // if root_node_uuids, filter on uuids
        WHERE (
            // only parent-less nodes if no root node uuids
            ($root_node_uuids IS NULL AND NOT exists((:DiffRelationship)-[:DIFF_HAS_NODE]->(diff_node)))
            // filter on uuids if included
            OR diff_node.uuid in $root_node_uuids
        )
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
        """
        self.add_to_query(query=query_1)

        if db.db_type is DatabaseType.NEO4J:
            children_query = """
            WITH diff_root, diff_node
            CALL {
                WITH diff_node
                OPTIONAL MATCH descendant_path = (diff_node) ((parents:DiffNode)-[:DIFF_HAS_RELATIONSHIP]->(rel_nodes:DiffRelationship)-[:DIFF_HAS_NODE]->(children:DiffNode)){0, %(max_depth)s}
                // turn them into a nested list of the form [[parent node, relationship node, child node], ...]
                RETURN reduce(acc = [], i IN range(0, size(parents)- 1) | acc + [[parents[i], rel_nodes[i], children[i]]]) AS parent_child_tuples
            }
            """ % {"max_depth": self.max_depth}
        elif db.db_type is DatabaseType.MEMGRAPH:
            children_query = """
            CALL {
                WITH diff_node
                OPTIONAL MATCH descendant_path = (diff_node)-[:DIFF_HAS_RELATIONSHIP | :DIFF_HAS_NODE * ..%(max_depth)s]->(children:DiffNode)
                WITH nodes(descendant_path)[-3] AS parent_node, nodes(descendant_path)[-2] AS rel_node, nodes(descendant_path)[-1] AS child_node
                RETURN collect([parent_node, rel_node, child_node]) AS parent_child_tuples
            }
            """ % {"max_depth": self.max_depth * 2}

        self.add_to_query(query=children_query)

        query_2 = """
        WITH diff_root, diff_node, parent_child_tuples
        WITH diff_root, ([[NULL, NULL, diff_node]] + parent_child_tuples) AS parent_child_tuples
        UNWIND parent_child_tuples AS parent_child_tuple
        WITH diff_root, (parent_child_tuple[0]).uuid AS parent_node_uuid, (parent_child_tuple[1]).name AS parent_rel_name, parent_child_tuple[2] AS diff_node
        OPTIONAL MATCH (diff_node)-[:DIFF_HAS_CONFLICT]->(diff_node_conflict:DiffConflict)
        WITH diff_root, parent_node_uuid, parent_rel_name, diff_node, diff_node_conflict
        // attributes
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
        WITH diff_root, parent_node_uuid, parent_rel_name, diff_node, diff_node_conflict, collect([diff_attribute, diff_attr_property, diff_attr_property_conflict]) as diff_attributes

        // relationships
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
            parent_node_uuid,
            parent_rel_name,
            diff_node,
            diff_node_conflict,
            diff_attributes,
            collect([diff_relationship, diff_rel_element, diff_rel_conflict, diff_rel_property, diff_rel_property_conflict]) AS diff_relationships
        """
        self.add_to_query(query=query_2)

        self.return_labels = [
            "diff_root",
            "diff_node",
            "diff_node_conflict",
            "parent_node_uuid",
            "parent_rel_name",
            "diff_attributes",
            "diff_relationships",
        ]
        self.order_by = ["diff_root.diff_branch_name ASC", "diff_root.from_time ASC", "diff_node.label ASC"]

    async def get_enriched_diff_roots(self) -> list[EnrichedDiffRoot]:
        deserializer = EnrichedDiffDeserializer()
        enriched_diffs = await deserializer.deserialize(database_results=self.get_results())
        return enriched_diffs


class EnrichedDiffDeserializer:
    def __init__(self) -> None:
        self._diff_root_map: dict[str, EnrichedDiffRoot] = {}
        self._diff_node_map: dict[tuple[str, str], EnrichedDiffNode] = {}
        self._diff_node_attr_map: dict[tuple[str, str, str], EnrichedDiffAttribute] = {}
        self._diff_node_rel_group_map: dict[tuple[str, str, str], EnrichedDiffRelationship] = {}
        self._diff_node_rel_element_map: dict[tuple[str, str, str, str], EnrichedDiffSingleRelationship] = {}
        self._diff_prop_map: dict[tuple[str, str, str, str] | tuple[str, str, str, str, str], EnrichedDiffProperty] = {}
        # {(root uuid, node uuid): (parent node uuid, parent relationship name)}
        self._node_parent_map: dict[tuple[str, str], tuple[str, str]] = {}

    async def deserialize(self, database_results: Iterable[QueryResult]) -> list[EnrichedDiffRoot]:
        for result in database_results:
            enriched_root = self._deserialize_diff_root(root_node=result.get_node("diff_root"))
            node_node = result.get_node(label="diff_node")
            if not isinstance(node_node, Neo4jNode):
                continue
            enriched_node = self._deserialize_diff_node(node_node=node_node, enriched_root=enriched_root)
            node_conflict_node = result.get(label="diff_node_conflict")
            if isinstance(node_conflict_node, Neo4jNode) and not enriched_node.conflict:
                self._deserialize_conflict(diff_conflict_node=node_conflict_node, linked_node=enriched_node)
            self._deserialize_attributes(result=result, enriched_root=enriched_root, enriched_node=enriched_node)
            self._deserialize_relationships(result=result, enriched_root=enriched_root, enriched_node=enriched_node)
            self._track_child_nodes(result=result, enriched_root=enriched_root, enriched_node=enriched_node)

        self._apply_child_nodes()

        return list(self._diff_root_map.values())

    def _deserialize_attributes(
        self, result: QueryResult, enriched_root: EnrichedDiffRoot, enriched_node: EnrichedDiffNode
    ) -> None:
        for attribute_result in result.get_nested_node_collection("diff_attributes"):
            diff_attr_node, diff_attr_property_node, diff_attr_property_conflict = attribute_result
            if diff_attr_node is None or diff_attr_property_node is None:
                continue
            enriched_attribute = self._deserialize_diff_attr(
                diff_attr_node=diff_attr_node, enriched_root=enriched_root, enriched_node=enriched_node
            )
            enriched_property = self._deserialize_diff_attr_property(
                diff_attr_property_node=diff_attr_property_node,
                enriched_attr=enriched_attribute,
                enriched_node=enriched_node,
                enriched_root=enriched_root,
            )
            if diff_attr_property_conflict:
                self._deserialize_conflict(
                    diff_conflict_node=diff_attr_property_conflict, linked_node=enriched_property
                )

    def _deserialize_relationships(
        self, result: QueryResult, enriched_root: EnrichedDiffRoot, enriched_node: EnrichedDiffNode
    ) -> None:
        for relationship_result in result.get_nested_node_collection("diff_relationships"):
            group_node, element_node, element_conflict, property_node, property_conflict = relationship_result
            if group_node is not None and element_node is None and property_node is None:
                enriched_node.add_relationship_from_DiffRelationship(diff_rel=group_node)
                continue
            if group_node is None or element_node is None or property_node is None:
                continue

            enriched_relationship_group = self._deserialize_diff_relationship_group(
                relationship_group_node=group_node, enriched_root=enriched_root, enriched_node=enriched_node
            )
            enriched_relationship_element = self._deserialize_diff_relationship_element(
                relationship_element_node=element_node,
                enriched_relationship_group=enriched_relationship_group,
                enriched_node=enriched_node,
                enriched_root=enriched_root,
            )
            if element_conflict and not enriched_relationship_element.conflict:
                self._deserialize_conflict(
                    diff_conflict_node=element_conflict, linked_node=enriched_relationship_element
                )
            element_property = self._deserialize_diff_relationship_element_property(
                relationship_element_property_node=property_node,
                enriched_relationship_element=enriched_relationship_element,
                enriched_relationship_group=enriched_relationship_group,
                enriched_node=enriched_node,
                enriched_root=enriched_root,
            )
            if property_conflict:
                self._deserialize_conflict(diff_conflict_node=property_conflict, linked_node=element_property)

    def _track_child_nodes(
        self, result: QueryResult, enriched_root: EnrichedDiffRoot, enriched_node: EnrichedDiffNode
    ) -> None:
        parent_node_uuid = result.get_as_str("parent_node_uuid")
        parent_rel_name = result.get_as_str("parent_rel_name")
        if parent_node_uuid is None or parent_rel_name is None:
            return
        self._node_parent_map[(enriched_root.uuid, enriched_node.uuid)] = (parent_node_uuid, parent_rel_name)

    def _apply_child_nodes(self) -> None:
        for (enriched_root_uuid, child_node_uuid), (parent_node_uuid, parent_rel_name) in self._node_parent_map.items():
            enriched_root = self._diff_root_map[enriched_root_uuid]
            child_node = enriched_root.get_node(node_uuid=child_node_uuid)
            parent_node = enriched_root.get_node(node_uuid=parent_node_uuid)
            parent_relationship = parent_node.get_relationship(name=parent_rel_name)
            parent_relationship.nodes.add(child_node)

    def _get_str_or_none_property_value(self, node: Neo4jNode, property_name: str) -> str | None:
        value_raw = node.get(property_name)
        return str(value_raw) if value_raw is not None else None

    def _deserialize_diff_root(self, root_node: Neo4jNode) -> EnrichedDiffRoot:
        root_uuid = str(root_node.get("uuid"))
        if root_uuid in self._diff_root_map:
            return self._diff_root_map[root_uuid]

        from_time = Timestamp(str(root_node.get("from_time")))
        to_time = Timestamp(str(root_node.get("to_time")))
        enriched_root = EnrichedDiffRoot(
            base_branch_name=str(root_node.get("base_branch")),
            diff_branch_name=str(root_node.get("diff_branch")),
            from_time=from_time,
            to_time=to_time,
            uuid=str(root_uuid),
            num_added=int(root_node.get("num_added")),
            num_updated=int(root_node.get("num_updated")),
            num_removed=int(root_node.get("num_removed")),
            num_conflicts=int(root_node.get("num_conflicts")),
            contains_conflict=str(root_node.get("contains_conflict")).lower() == "true",
        )
        self._diff_root_map[root_uuid] = enriched_root
        return enriched_root

    def _deserialize_diff_node(self, node_node: Neo4jNode, enriched_root: EnrichedDiffRoot) -> EnrichedDiffNode:
        node_uuid = str(node_node.get("uuid"))
        node_key = (enriched_root.uuid, node_uuid)
        if node_key in self._diff_node_map:
            return self._diff_node_map[node_key]

        enriched_node = EnrichedDiffNode(
            uuid=node_uuid,
            kind=str(node_node.get("kind")),
            label=str(node_node.get("label")),
            changed_at=Timestamp(node_node.get("changed_at")),
            action=DiffAction(str(node_node.get("action"))),
            num_added=int(node_node.get("num_added")),
            num_updated=int(node_node.get("num_updated")),
            num_removed=int(node_node.get("num_removed")),
            num_conflicts=int(node_node.get("num_conflicts")),
            contains_conflict=str(node_node.get("contains_conflict")).lower() == "true",
        )
        self._diff_node_map[node_key] = enriched_node
        enriched_root.nodes.add(enriched_node)
        return enriched_node

    def _deserialize_diff_attr(
        self, diff_attr_node: Neo4jNode, enriched_root: EnrichedDiffRoot, enriched_node: EnrichedDiffNode
    ) -> EnrichedDiffAttribute:
        attr_name = str(diff_attr_node.get("name"))
        attr_key = (enriched_root.uuid, enriched_node.uuid, attr_name)
        if attr_key in self._diff_node_attr_map:
            return self._diff_node_attr_map[attr_key]

        enriched_attr = EnrichedDiffAttribute(
            name=str(diff_attr_node.get("name")),
            changed_at=Timestamp(str(diff_attr_node.get("changed_at"))),
            action=DiffAction(str(diff_attr_node.get("action"))),
            num_added=int(diff_attr_node.get("num_added")),
            num_updated=int(diff_attr_node.get("num_updated")),
            num_removed=int(diff_attr_node.get("num_removed")),
            num_conflicts=int(diff_attr_node.get("num_conflicts")),
            contains_conflict=str(diff_attr_node.get("contains_conflict")).lower() == "true",
        )
        self._diff_node_attr_map[attr_key] = enriched_attr
        enriched_node.attributes.add(enriched_attr)
        return enriched_attr

    def _deserialize_diff_relationship_group(
        self, relationship_group_node: Neo4jNode, enriched_root: EnrichedDiffRoot, enriched_node: EnrichedDiffNode
    ) -> EnrichedDiffRelationship:
        diff_rel_name = str(relationship_group_node.get("name"))
        rel_key = (enriched_root.uuid, enriched_node.uuid, diff_rel_name)
        if rel_key in self._diff_node_rel_group_map:
            return self._diff_node_rel_group_map[rel_key]

        enriched_relationship = EnrichedDiffRelationship.from_graph(node=relationship_group_node)
        self._diff_node_rel_group_map[rel_key] = enriched_relationship
        enriched_node.relationships.add(enriched_relationship)
        return enriched_relationship

    def _deserialize_diff_relationship_element(
        self,
        relationship_element_node: Neo4jNode,
        enriched_relationship_group: EnrichedDiffRelationship,
        enriched_node: EnrichedDiffNode,
        enriched_root: EnrichedDiffRoot,
    ) -> EnrichedDiffSingleRelationship:
        diff_element_peer_id = str(relationship_element_node.get("peer_id"))
        rel_element_key = (
            enriched_root.uuid,
            enriched_node.uuid,
            enriched_relationship_group.name,
            diff_element_peer_id,
        )
        if rel_element_key in self._diff_node_rel_element_map:
            return self._diff_node_rel_element_map[rel_element_key]

        enriched_rel_element = EnrichedDiffSingleRelationship(
            changed_at=Timestamp(str(relationship_element_node.get("changed_at"))),
            action=DiffAction(str(relationship_element_node.get("action"))),
            peer_id=diff_element_peer_id,
            num_added=int(relationship_element_node.get("num_added")),
            num_updated=int(relationship_element_node.get("num_updated")),
            num_removed=int(relationship_element_node.get("num_removed")),
            num_conflicts=int(relationship_element_node.get("num_conflicts")),
            contains_conflict=str(relationship_element_node.get("contains_conflict")).lower() == "true",
        )
        enriched_relationship_group.relationships.add(enriched_rel_element)
        self._diff_node_rel_element_map[rel_element_key] = enriched_rel_element
        return enriched_rel_element

    def _property_node_to_enriched_property(self, property_node: Neo4jNode) -> EnrichedDiffProperty:
        previous_value = self._get_str_or_none_property_value(node=property_node, property_name="previous_value")
        new_value = self._get_str_or_none_property_value(node=property_node, property_name="new_value")
        return EnrichedDiffProperty(
            property_type=DatabaseEdgeType(str(property_node.get("property_type"))),
            changed_at=Timestamp(str(property_node.get("changed_at"))),
            previous_value=previous_value,
            new_value=new_value,
            action=DiffAction(str(property_node.get("action"))),
        )

    def _deserialize_diff_attr_property(
        self,
        diff_attr_property_node: Neo4jNode,
        enriched_attr: EnrichedDiffAttribute,
        enriched_node: EnrichedDiffNode,
        enriched_root: EnrichedDiffRoot,
    ) -> EnrichedDiffProperty:
        diff_prop_type = str(diff_attr_property_node.get("property_type"))
        attr_property_key = (enriched_root.uuid, enriched_node.uuid, enriched_attr.name, diff_prop_type)
        if attr_property_key in self._diff_prop_map:
            return self._diff_prop_map[attr_property_key]

        enriched_property = self._property_node_to_enriched_property(property_node=diff_attr_property_node)
        enriched_attr.properties.add(enriched_property)
        self._diff_prop_map[attr_property_key] = enriched_property
        return enriched_property

    def _deserialize_diff_relationship_element_property(
        self,
        relationship_element_property_node: Neo4jNode,
        enriched_relationship_element: EnrichedDiffSingleRelationship,
        enriched_relationship_group: EnrichedDiffRelationship,
        enriched_node: EnrichedDiffNode,
        enriched_root: EnrichedDiffRoot,
    ) -> EnrichedDiffProperty:
        diff_prop_type = str(relationship_element_property_node.get("property_type"))
        rel_property_key = (
            enriched_root.uuid,
            enriched_node.uuid,
            enriched_relationship_group.name,
            enriched_relationship_element.peer_id,
            diff_prop_type,
        )
        if rel_property_key in self._diff_prop_map:
            return self._diff_prop_map[rel_property_key]

        enriched_property = self._property_node_to_enriched_property(property_node=relationship_element_property_node)
        self._diff_prop_map[rel_property_key] = enriched_property
        enriched_relationship_element.properties.add(enriched_property)
        return enriched_property

    def _deserialize_conflict(
        self,
        diff_conflict_node: Neo4jNode,
        linked_node: EnrichedDiffNode | EnrichedDiffSingleRelationship | EnrichedDiffProperty,
    ) -> EnrichedDiffConflict:
        base_branch_value = self._get_str_or_none_property_value(
            node=diff_conflict_node, property_name="base_branch_value"
        )
        diff_branch_value = self._get_str_or_none_property_value(
            node=diff_conflict_node, property_name="diff_branch_value"
        )
        selected_branch = self._get_str_or_none_property_value(node=diff_conflict_node, property_name="selected_branch")
        conflict = EnrichedDiffConflict(
            uuid=str(diff_conflict_node.get("uuid")),
            base_branch_action=DiffAction(str(diff_conflict_node.get("base_branch_action"))),
            base_branch_value=base_branch_value,
            base_branch_changed_at=Timestamp(str(diff_conflict_node.get("base_branch_changed_at"))),
            diff_branch_action=DiffAction(str(diff_conflict_node.get("diff_branch_action"))),
            diff_branch_value=diff_branch_value,
            diff_branch_changed_at=Timestamp(str(diff_conflict_node.get("diff_branch_changed_at"))),
            selected_branch=ConflictSelection(selected_branch) if selected_branch else None,
        )

        linked_node.conflict = conflict
        return conflict
