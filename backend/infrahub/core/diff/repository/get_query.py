from typing import Any, Iterable

from neo4j.graph import Node as Neo4jNode

from infrahub.core.constants import DiffAction
from infrahub.core.query import Query, QueryResult, QueryType
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase

from ..model.path import (
    ConflictBranchChoice,
    EnrichedDiffAttribute,
    EnrichedDiffNode,
    EnrichedDiffProperty,
    EnrichedDiffPropertyConflict,
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
        query = """
        // get the roots of all diffs in the query
        MATCH (diff_root:DiffRoot)
        WHERE diff_root.base_branch = $base_branch
        AND diff_root.diff_branch IN $diff_branches
        AND diff_root.from_time >= $from_time
        AND diff_root.to_time <= $to_time
        // get all the nodes attached to the diffs
        OPTIONAL MATCH (diff_root)-[DIFF_HAS_NODE]->(diff_node:DiffNode)
        // if root_node_uuids, filter on uuids
        WHERE ($root_node_uuids IS NULL OR diff_node.uuid in $root_node_uuids)
        // do the pagination
        WITH diff_root, diff_node
        ORDER BY diff_root.diff_branch ASC, diff_root.from_time ASC, diff_node.kind ASC, diff_node.uuid ASC
        SKIP COALESCE($offset, 0)
        LIMIT $limit
        WITH diff_root, diff_node
        // if depth limit, make sure not to exceed it when traversing linked nodes
        WITH diff_root, diff_node, NULL as parent_node
        CALL {
            WITH diff_node
            OPTIONAL MATCH descendant_path = (diff_node) ((parent:DiffNode)-[:DIFF_HAS_RELATIONSHIP]->(:DiffRelationship)-[:DIFF_HAS_NODE]->(child:DiffNode)){0, %(max_depth)s}
            // turn them into a nested list of the form [[parent node, child node], ...]
            RETURN reduce(pairs = [], i IN range(0, size(parent)- 1) | pairs + [[parent[i], child[i]]]) AS parent_child_pairs
        }
        WITH diff_root, diff_node, parent_node, parent_child_pairs
        WITH diff_root, [[parent_node, diff_node]] + parent_child_pairs AS parent_child_pairs
        UNWIND parent_child_pairs AS parent_child_pair
        WITH diff_root, parent_child_pair[0] AS parent_node, parent_child_pair[1] AS diff_node

        // attributes
        CALL {
            WITH diff_node
            OPTIONAL MATCH (diff_node)-[DIFF_HAS_ATTRIBUTE]->(diff_attribute:DiffAttribute)
            WITH diff_attribute
            OPTIONAL MATCH (diff_attribute)-[DIFF_HAS_PROPERTY]->(diff_attr_property:DiffProperty)
            WITH diff_attribute, diff_attr_property
            OPTIONAL MATCH (diff_attr_property)-[DIFF_HAS_CONFLICT]->(diff_attr_conflict:DiffConflict)
            RETURN diff_attribute, diff_attr_property, diff_attr_conflict
            ORDER BY diff_attribute.name, diff_attr_property.property_type
        }
        WITH diff_root, parent_node, diff_node, collect([diff_attribute, diff_attr_property, diff_attr_conflict]) as diff_attributes

        // relationships
        CALL {
            WITH diff_node
            OPTIONAL MATCH (diff_node)-[DIFF_HAS_RELATIONSHIP]->(diff_relationship:DiffRelationship)
            WITH diff_relationship
            OPTIONAL MATCH (diff_relationship)-[DIFF_HAS_ELEMENT]->(diff_rel_element:DiffRelationshipElement)
            WITH diff_relationship, diff_rel_element
            OPTIONAL MATCH (diff_rel_element)-[DIFF_HAS_CONFLICT]->(diff_rel_element_conflict:DiffConflict)
            WITH diff_relationship, diff_rel_element, diff_rel_element_conflict
            OPTIONAL MATCH (diff_rel_element)-[DIFF_HAS_PROPERTY]->(diff_rel_property:DiffProperty)
            WITH diff_relationship, diff_rel_element, diff_rel_element_conflict, diff_rel_property
            OPTIONAL MATCH (diff_rel_property)-[DIFF_HAS_CONFLICT]->(diff_rel_conflict:DiffConflict)
            RETURN diff_relationship, diff_rel_element, diff_rel_element_conflict, diff_rel_property, diff_rel_conflict
            ORDER BY diff_relationship.name, diff_rel_element.peer_id, diff_rel_property.property_type
        }
        WITH
            diff_root,
            parent_node,
            diff_node,
            diff_attributes,
            collect([diff_relationship, diff_rel_element, diff_rel_element_conflict, diff_rel_property, diff_rel_conflict]) AS diff_relationships

        // child nodes
        CALL {
            WITH diff_node
            OPTIONAL MATCH (diff_node:DiffNode)-[DIFF_HAS_RELATIONSHIP]->(diff_relationship:DiffRelationship)-[DIFF_HAS_NODE]->(child_node:DiffNode)
            RETURN collect([diff_relationship, child_node]) AS diff_child_nodes
        }
        WITH
            diff_root,
            parent_node,
            diff_node,
            diff_attributes,
            diff_relationships,
            diff_child_nodes
        """ % {"max_depth": self.max_depth}
        self.return_labels = [
            "diff_root",
            "diff_node",
            "parent_node",
            "diff_attributes",
            "diff_relationships",
            "diff_child_nodes",
        ]
        self.order_by = ["diff_root.diff_branch_name ASC", "diff_root.from_time ASC", "diff_node.label ASC"]
        self.add_to_query(query=query)

    async def get_enriched_diff_roots(self) -> list[EnrichedDiffRoot]:
        deserializer = EnrichedDiffDeserializer()
        enriched_diffs = await deserializer.deserialize(database_results=self.get_results())
        return enriched_diffs


class EnrichedDiffDeserializer:
    def __init__(self) -> None:
        self._diff_root_map: dict[str, EnrichedDiffRoot] = {}
        self._diff_node_map: dict[str, EnrichedDiffNode] = {}
        self._diff_node_attr_map: dict[tuple[str, str], EnrichedDiffAttribute] = {}
        self._diff_node_rel_group_map: dict[tuple[str, str], EnrichedDiffRelationship] = {}
        self._diff_node_rel_element_map: dict[tuple[str, str, str], EnrichedDiffSingleRelationship] = {}
        self._diff_prop_map: dict[tuple[str, str, str] | tuple[str, str, str, str], EnrichedDiffProperty] = {}
        self._node_child_map: dict[EnrichedDiffNode, list[tuple[str, str]]] = {}

    async def deserialize(self, database_results: Iterable[QueryResult]) -> list[EnrichedDiffRoot]:
        for result in database_results:
            enriched_root = self._deserialize_diff_root(root_node=result.get_node("diff_root"))
            node_node = result.get("diff_node")
            if not isinstance(node_node, Neo4jNode):
                continue
            enriched_node = self._deserialize_diff_node(node_node=node_node, enriched_root=enriched_root)
            self._deserialize_attributes(result=result, enriched_node=enriched_node)
            self._deserialize_relationships(result=result, enriched_node=enriched_node)
            self._track_child_nodes(result=result, enriched_node=enriched_node)

        self._apply_child_nodes()

        return list(self._diff_root_map.values())

    def _deserialize_attributes(self, result: QueryResult, enriched_node: EnrichedDiffNode) -> None:
        for attribute_result in result.get_nested_node_collection("diff_attributes"):
            diff_attr_node, diff_attr_property_node, diff_attr_conflict_node = attribute_result
            if diff_attr_node is None or diff_attr_property_node is None:
                continue
            enriched_attribute = self._deserialize_diff_attr(diff_attr_node=diff_attr_node, enriched_node=enriched_node)
            enriched_property = self._deserialize_diff_attr_property(
                diff_attr_property_node=diff_attr_property_node,
                enriched_attr=enriched_attribute,
                enriched_node=enriched_node,
            )
            if diff_attr_conflict_node:
                enriched_conflict = self._conflict_node_to_enriched_conflict(conflict_node=diff_attr_conflict_node)
                enriched_property.conflict = enriched_conflict

    def _deserialize_relationships(self, result: QueryResult, enriched_node: EnrichedDiffNode) -> None:
        for relationship_result in result.get_nested_node_collection("diff_relationships"):
            group_node, element_node, element_conflict, property_node, conflict_node = relationship_result
            if group_node is None or element_node is None or property_node is None:
                continue
            enriched_relationship_group = self._deserialize_diff_relationship_group(
                relationship_group_node=group_node, enriched_node=enriched_node
            )
            enriched_relationship_element = self._deserialize_diff_relationship_element(
                relationship_element_node=element_node,
                relationship_element_conflict_node=element_conflict,
                enriched_relationship_group=enriched_relationship_group,
                enriched_node=enriched_node,
            )
            enriched_property = self._deserialize_diff_relationship_element_property(
                relationship_element_property_node=property_node,
                enriched_relationship_element=enriched_relationship_element,
                enriched_relationship_group=enriched_relationship_group,
                enriched_node=enriched_node,
            )
            if conflict_node:
                enriched_conflict = self._conflict_node_to_enriched_conflict(conflict_node=conflict_node)
                enriched_property.conflict = enriched_conflict

    def _track_child_nodes(self, result: QueryResult, enriched_node: EnrichedDiffNode) -> None:
        self._node_child_map[enriched_node] = []
        diff_child_nodes: list[list[Neo4jNode]] = result.get_nested_node_collection("diff_child_nodes")
        for relationship_group_node, child_node_node in diff_child_nodes:
            if relationship_group_node is None or child_node_node is None:
                continue
            relationship_name = str(relationship_group_node.get("name"))
            child_node_uuid = str(child_node_node.get("uuid"))
            self._node_child_map[enriched_node].append((relationship_name, child_node_uuid))

    def _apply_child_nodes(self) -> None:
        for enriched_node, child_node_list in self._node_child_map.items():
            for relationship_name, child_node_uuid in child_node_list:
                enriched_relationship = enriched_node.get_relationship(name=relationship_name)
                node = self._diff_node_map[child_node_uuid]
                enriched_relationship.nodes.add(node)

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
        )
        self._diff_root_map[root_uuid] = enriched_root
        return enriched_root

    def _deserialize_diff_node(self, node_node: Neo4jNode, enriched_root: EnrichedDiffRoot) -> EnrichedDiffNode:
        node_uuid = str(node_node.get("uuid"))
        if node_uuid in self._diff_node_map:
            return self._diff_node_map[node_uuid]

        enriched_node = EnrichedDiffNode(
            uuid=node_uuid,
            kind=str(node_node.get("kind")),
            label=str(node_node.get("label")),
            changed_at=Timestamp(node_node.get("changed_at")),
            action=DiffAction(str(node_node.get("action"))),
        )
        self._diff_node_map[node_uuid] = enriched_node
        enriched_root.nodes.add(enriched_node)
        return enriched_node

    def _deserialize_diff_attr(
        self, diff_attr_node: Neo4jNode, enriched_node: EnrichedDiffNode
    ) -> EnrichedDiffAttribute:
        attr_name = str(diff_attr_node.get("name"))
        attr_key = (enriched_node.uuid, attr_name)
        if attr_key in self._diff_node_attr_map:
            return self._diff_node_attr_map[attr_key]

        enriched_attr = EnrichedDiffAttribute(
            name=str(diff_attr_node.get("name")),
            changed_at=Timestamp(str(diff_attr_node.get("changed_at"))),
            action=DiffAction(str(diff_attr_node.get("action"))),
        )
        self._diff_node_attr_map[attr_key] = enriched_attr
        enriched_node.attributes.add(enriched_attr)
        return enriched_attr

    def _deserialize_diff_relationship_group(
        self, relationship_group_node: Neo4jNode, enriched_node: EnrichedDiffNode
    ) -> EnrichedDiffRelationship:
        diff_rel_name = str(relationship_group_node.get("name"))
        rel_key = (enriched_node.uuid, diff_rel_name)
        if rel_key in self._diff_node_rel_group_map:
            return self._diff_node_rel_group_map[rel_key]

        enriched_relationship = EnrichedDiffRelationship(
            name=diff_rel_name,
            changed_at=Timestamp(str(relationship_group_node.get("changed_at"))),
            action=DiffAction(str(relationship_group_node.get("action"))),
        )
        self._diff_node_rel_group_map[rel_key] = enriched_relationship
        enriched_node.relationships.add(enriched_relationship)
        return enriched_relationship

    def _deserialize_diff_relationship_element(
        self,
        relationship_element_node: Neo4jNode,
        relationship_element_conflict_node: Neo4jNode | None,
        enriched_relationship_group: EnrichedDiffRelationship,
        enriched_node: EnrichedDiffNode,
    ) -> EnrichedDiffSingleRelationship:
        diff_element_peer_id = str(relationship_element_node.get("peer_id"))
        rel_element_key = (enriched_node.uuid, enriched_relationship_group.name, diff_element_peer_id)
        if rel_element_key in self._diff_node_rel_element_map:
            return self._diff_node_rel_element_map[rel_element_key]

        enriched_rel_element = EnrichedDiffSingleRelationship(
            changed_at=Timestamp(str(relationship_element_node.get("changed_at"))),
            action=DiffAction(str(relationship_element_node.get("action"))),
            peer_id=diff_element_peer_id,
            conflict=None,
        )
        if relationship_element_conflict_node is not None:
            enriched_rel_element.conflict = self._conflict_node_to_enriched_conflict(
                conflict_node=relationship_element_conflict_node
            )
        enriched_relationship_group.relationships.add(enriched_rel_element)
        self._diff_node_rel_element_map[rel_element_key] = enriched_rel_element
        return enriched_rel_element

    def _property_node_to_enriched_property(self, property_node: Neo4jNode) -> EnrichedDiffProperty:
        previous_value = self._get_str_or_none_property_value(node=property_node, property_name="previous_value")
        new_value = self._get_str_or_none_property_value(node=property_node, property_name="new_value")
        return EnrichedDiffProperty(
            property_type=str(property_node.get("property_type")),
            changed_at=Timestamp(str(property_node.get("changed_at"))),
            previous_value=previous_value,
            new_value=new_value,
            action=DiffAction(str(property_node.get("action"))),
            conflict=None,
        )

    def _deserialize_diff_attr_property(
        self, diff_attr_property_node: Neo4jNode, enriched_attr: EnrichedDiffAttribute, enriched_node: EnrichedDiffNode
    ) -> EnrichedDiffProperty:
        diff_prop_type = str(diff_attr_property_node.get("property_type"))
        attr_property_key = (enriched_node.uuid, enriched_attr.name, diff_prop_type)
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
    ) -> EnrichedDiffProperty:
        diff_prop_type = str(relationship_element_property_node.get("property_type"))
        rel_property_key = (
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

    def _conflict_node_to_enriched_conflict(self, conflict_node: Neo4jNode) -> EnrichedDiffPropertyConflict:
        base_value = self._get_str_or_none_property_value(node=conflict_node, property_name="base_branch_value")
        branch_value = self._get_str_or_none_property_value(node=conflict_node, property_name="diff_branch_value")
        selected_branch_value = self._get_str_or_none_property_value(
            node=conflict_node, property_name="selected_branch"
        )
        return EnrichedDiffPropertyConflict(
            uuid=str(conflict_node.get("uuid")),
            base_branch_action=DiffAction(str(conflict_node.get("base_branch_action"))),
            base_branch_value=base_value,
            base_branch_changed_at=Timestamp(str(conflict_node.get("base_branch_changed_at"))),
            diff_branch_action=DiffAction(str(conflict_node.get("diff_branch_action"))),
            diff_branch_value=branch_value,
            diff_branch_changed_at=Timestamp(str(conflict_node.get("diff_branch_changed_at"))),
            selected_branch=ConflictBranchChoice(selected_branch_value) if selected_branch_value else None,
        )
