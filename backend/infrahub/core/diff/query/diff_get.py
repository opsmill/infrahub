from typing import Any, Iterable

from neo4j.graph import Node as Neo4jNode
from neo4j.graph import Path as Neo4jPath

from infrahub.core.constants import DiffAction
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.query import Query, QueryResult, QueryType
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase

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
from .filters import EnrichedDiffQueryFilters

QUERY_MATCH_NODES = """
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
        from_time: Timestamp,
        to_time: Timestamp,
        filters: EnrichedDiffQueryFilters,
        max_depth: int,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.base_branch_name = base_branch_name
        self.diff_branch_names = diff_branch_names
        self.from_time = from_time
        self.to_time = to_time
        self.max_depth = max_depth
        self.filters = filters or EnrichedDiffQueryFilters()

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:
        self.params = {
            "base_branch": self.base_branch_name,
            "diff_branches": self.diff_branch_names,
            "from_time": self.from_time.to_string(),
            "to_time": self.to_time.to_string(),
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

    async def deserialize(self, database_results: Iterable[QueryResult]) -> list[EnrichedDiffRoot]:
        results = list(database_results)
        for result in results:
            enriched_root = self._deserialize_diff_root(root_node=result.get_node("diff_root"))
            node_node = result.get(label="diff_node")
            if not isinstance(node_node, Neo4jNode):
                continue
            enriched_node = self._deserialize_diff_node(node_node=node_node, enriched_root=enriched_root)
            node_conflict_node = result.get(label="diff_node_conflict")
            if isinstance(node_conflict_node, Neo4jNode) and not enriched_node.conflict:
                self._deserialize_conflict(diff_conflict_node=node_conflict_node, linked_node=enriched_node)
            self._deserialize_attributes(result=result, enriched_root=enriched_root, enriched_node=enriched_node)
            self._deserialize_relationships(result=result, enriched_root=enriched_root, enriched_node=enriched_node)

        for result in results:
            enriched_root = self._deserialize_diff_root(root_node=result.get_node("diff_root"))
            self._deserialize_parents(result=result, enriched_root=enriched_root)

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

    def _deserialize_parents(self, result: QueryResult, enriched_root: EnrichedDiffRoot) -> None:
        parents_path = result.get("parents_path")
        if not parents_path or not isinstance(parents_path, Neo4jPath):
            return

        node_uuid = result.get(label="diff_node").get("uuid")

        # Remove the node itself from the path
        parents_path = parents_path.nodes[1:]  # type: ignore[union-attr]

        # TODO Ensure the list is even
        current_node_uuid = node_uuid
        for rel, parent in zip(parents_path[::2], parents_path[1::2]):
            enriched_root.add_parent(
                node_id=current_node_uuid,
                parent_id=parent.get("uuid"),
                parent_kind=parent.get("kind"),
                parent_label=parent.get("label"),
                parent_rel_name=rel.get("name"),
                parent_rel_label=rel.get("label"),
            )
            current_node_uuid = parent.get("uuid")

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
            path_identifier=str(node_node.get("path_identifier")),
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
            path_identifier=str(diff_attr_node.get("path_identifier")),
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

        peer_label = self._get_str_or_none_property_value(node=relationship_element_node, property_name="peer_label")
        enriched_rel_element = EnrichedDiffSingleRelationship(
            changed_at=Timestamp(str(relationship_element_node.get("changed_at"))),
            action=DiffAction(str(relationship_element_node.get("action"))),
            peer_id=diff_element_peer_id,
            peer_label=peer_label,
            path_identifier=str(relationship_element_node.get("path_identifier")),
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
            path_identifier=str(property_node.get("path_identifier")),
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
