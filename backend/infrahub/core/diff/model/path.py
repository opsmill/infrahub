from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

from infrahub.core.constants import DiffAction, RelationshipStatus
from infrahub.core.timestamp import Timestamp

from ..exceptions import InvalidCypherPathError

if TYPE_CHECKING:
    from neo4j.graph import Node as Neo4jNode
    from neo4j.graph import Path as Neo4jPath
    from neo4j.graph import Relationship as Neo4jRelationship


class ConflictBranchChoice(Enum):
    BASE = "base"
    DIFF = "diff"


@dataclass
class EnrichedDiffPropertyConflict:
    uuid: str
    base_branch_action: DiffAction
    base_branch_value: Any
    base_branch_changed_at: Timestamp
    diff_branch_action: DiffAction
    diff_branch_value: Any
    diff_branch_changed_at: Timestamp
    selected_branch: Optional[ConflictBranchChoice]

    def __hash__(self) -> int:
        return hash(self.uuid)


@dataclass
class EnrichedDiffProperty:
    property_type: str
    changed_at: Timestamp
    previous_value: Any
    new_value: Any
    action: DiffAction
    conflict: Optional[EnrichedDiffPropertyConflict]

    def __hash__(self) -> int:
        return hash(self.property_type)


@dataclass
class EnrichedDiffAttribute:
    name: str
    changed_at: Timestamp
    action: DiffAction
    properties: set[EnrichedDiffProperty] = field(default_factory=set)

    def __hash__(self) -> int:
        return hash(self.name)


@dataclass
class EnrichedDiffSingleRelationship:
    changed_at: Timestamp
    action: DiffAction
    peer_id: str
    conflict: Optional[EnrichedDiffPropertyConflict]
    properties: set[EnrichedDiffProperty] = field(default_factory=set)

    def __hash__(self) -> int:
        return hash(self.peer_id)


@dataclass
class EnrichedDiffRelationship:
    name: str
    changed_at: Timestamp
    action: DiffAction
    relationships: set[EnrichedDiffSingleRelationship] = field(default_factory=set)
    nodes: set[EnrichedDiffNode] = field(default_factory=set)

    def __hash__(self) -> int:
        return hash(self.name)


@dataclass
class EnrichedDiffNode:
    uuid: str
    kind: str
    label: str
    changed_at: Timestamp
    action: DiffAction
    attributes: set[EnrichedDiffAttribute] = field(default_factory=set)
    relationships: set[EnrichedDiffRelationship] = field(default_factory=set)

    def __hash__(self) -> int:
        return hash(self.uuid)

    def get_all_child_nodes(self) -> set[EnrichedDiffNode]:
        all_children = set()
        for r in self.relationships:
            for n in r.nodes:
                all_children.add(n)
                all_children |= n.get_all_child_nodes()
        return all_children

    def get_trimmed_node(self, max_depth: int) -> EnrichedDiffNode:
        trimmed = replace(self, relationships=set())
        for rel in self.relationships:
            trimmed_rel = replace(rel, nodes=set())
            trimmed.relationships.add(trimmed_rel)
            if max_depth == 0:
                continue
            for child_node in rel.nodes:
                trimmed_rel.nodes.add(child_node.get_trimmed_node(max_depth=max_depth - 1))
        return trimmed

    def get_relationship(self, name: str) -> EnrichedDiffRelationship:
        for rel in self.relationships:
            if rel.name == name:
                return rel
        raise ValueError(f"No relationship {name} found")


@dataclass
class EnrichedDiffRoot:
    base_branch_name: str
    diff_branch_name: str
    from_time: Timestamp
    to_time: Timestamp
    uuid: str
    nodes: set[EnrichedDiffNode] = field(default_factory=set)

    def __hash__(self) -> int:
        return hash(self.uuid)

    def get_nodes_without_parents(self) -> set[EnrichedDiffNode]:
        nodes_with_parent_uuids = set()
        for n in self.nodes:
            for r in n.relationships:
                nodes_with_parent_uuids |= {child_n.uuid for child_n in r.nodes}
        return {node for node in self.nodes if node.uuid not in nodes_with_parent_uuids}

    def get_node(self, node_uuid: str) -> EnrichedDiffNode:
        for n in self.nodes:
            if n.uuid == node_uuid:
                return n
        raise ValueError(f"No node {node_uuid} in diff root")


@dataclass
class CalculatedDiffs:
    base_branch_name: str
    diff_branch_name: str
    base_branch_diff: DiffRoot
    diff_branch_diff: DiffRoot


@dataclass
class DiffProperty:
    property_type: str
    changed_at: Timestamp
    previous_value: Any
    new_value: Any
    action: DiffAction


@dataclass
class DiffAttribute:
    uuid: str
    name: str
    changed_at: Timestamp
    action: DiffAction
    properties: list[DiffProperty] = field(default_factory=list)


@dataclass
class DiffSingleRelationship:
    changed_at: Timestamp
    action: DiffAction
    peer_id: str
    properties: list[DiffProperty] = field(default_factory=list)


@dataclass
class DiffRelationship:
    name: str
    changed_at: Timestamp
    action: DiffAction
    relationships: list[DiffSingleRelationship] = field(default_factory=list)


@dataclass
class DiffNode:
    uuid: str
    kind: str
    changed_at: Timestamp
    action: DiffAction
    attributes: list[DiffAttribute] = field(default_factory=list)
    relationships: list[DiffRelationship] = field(default_factory=list)


@dataclass
class DiffRoot:
    from_time: Timestamp
    to_time: Timestamp
    uuid: str
    branch: str
    nodes: list[DiffNode] = field(default_factory=list)


@dataclass
class DatabasePath:  # pylint: disable=too-many-public-methods
    root_node: Neo4jNode
    path_to_node: Neo4jRelationship
    node_node: Neo4jNode
    path_to_attribute: Neo4jRelationship
    attribute_node: Neo4jNode
    path_to_property: Neo4jRelationship
    property_node: Neo4jNode

    def __str__(self) -> str:
        node_branch = self.path_to_node.get("branch")
        node_status = self.path_to_node.get("status")
        attribute_branch = self.path_to_attribute.get("branch")
        attribute_status = self.path_to_attribute.get("status")
        property_branch = self.path_to_property.get("branch")
        property_status = self.path_to_property.get("status")
        property_value = self.property_value if self.property_value is not None else self.peer_id
        return (
            f"branch={self.deepest_branch} (:Root)-[{node_branch=},{node_status=}]-({self.node_kind}"
            f" '{self.node_id}')-[{attribute_branch=},{attribute_status=}]-({self.attribute_name})-"
            f"[{property_branch=},{property_status=}]-({self.property_type=},{property_value=})"
        )

    @classmethod
    def from_cypher_path(cls, cypher_path: Neo4jPath) -> DatabasePath:
        try:
            return cls(
                root_node=cypher_path.nodes[0],
                path_to_node=cypher_path.relationships[0],
                node_node=cypher_path.nodes[1],
                path_to_attribute=cypher_path.relationships[1],
                attribute_node=cypher_path.nodes[2],
                path_to_property=cypher_path.relationships[2],
                property_node=cypher_path.nodes[3],
            )
        except KeyError as exc:
            raise InvalidCypherPathError(cypher_path=cypher_path) from exc

    @property
    def branches(self) -> set[str]:
        return {
            str(database_edge.get("branch"))
            for database_edge in (self.path_to_node, self.path_to_attribute, self.path_to_property)
        }

    @property
    def deepest_branch(self) -> str:
        deepest_edge = max(
            (self.path_to_node, self.path_to_attribute, self.path_to_property),
            key=lambda edge: int(edge.get("branch_level")),
        )
        return str(deepest_edge.get("branch"))

    @property
    def root_id(self) -> str:
        return str(self.root_node.get("uuid"))

    @property
    def node_id(self) -> str:
        return str(self.node_node.get("uuid"))

    @property
    def node_kind(self) -> str:
        return str(self.node_node.get("kind"))

    @property
    def node_changed_at(self) -> Timestamp:
        return Timestamp(self.path_to_node.get("from"))

    @property
    def node_status(self) -> RelationshipStatus:
        return RelationshipStatus(self.path_to_node.get("status"))

    @property
    def attribute_name(self) -> str:
        return str(self.attribute_node.get("name"))

    @property
    def attribute_id(self) -> str:
        return str(self.attribute_node.get("uuid"))

    @property
    def attribute_changed_at(self) -> Timestamp:
        return Timestamp(self.path_to_attribute.get("from"))

    @property
    def attribute_status(self) -> RelationshipStatus:
        return RelationshipStatus(self.path_to_attribute.get("status"))

    @property
    def relationship_id(self) -> str:
        return self.attribute_name

    @property
    def property_type(self) -> str:
        return self.path_to_property.type

    @property
    def property_id(self) -> str:
        return self.property_node.element_id

    @property
    def property_changed_at(self) -> Timestamp:
        return Timestamp(self.path_to_property.get("from"))

    @property
    def property_status(self) -> RelationshipStatus:
        return RelationshipStatus(self.path_to_property.get("status"))

    @property
    def property_end_time(self) -> Optional[Timestamp]:
        end_time_str = self.path_to_property.get("to")
        if not end_time_str:
            return None
        return Timestamp(end_time_str)

    @property
    def property_value(self) -> Any:
        return self.property_node.get("value")

    @property
    def peer_id(self) -> Optional[str]:
        if "Node" not in self.property_node.labels:
            return None
        return str(self.property_node.get("uuid"))

    @property
    def peer_kind(self) -> Optional[str]:
        if "Node" not in self.property_node.labels:
            return None
        return str(self.property_node.get("kind"))
