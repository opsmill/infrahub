from __future__ import annotations

import bisect
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from infrahub.core.constants import DiffAction, RelationshipStatus
from infrahub.core.timestamp import Timestamp

from ..exceptions import InvalidCypherPathError

if TYPE_CHECKING:
    from neo4j.graph import Node as Neo4jNode
    from neo4j.graph import Path as Neo4jPath
    from neo4j.graph import Relationship as Neo4jRelationship


@dataclass
class DiffValue:
    changed_at: Timestamp
    value: Any

    def __hash__(self) -> int:
        return hash(f"{self.changed_at.to_string()}|{self.value}")


@dataclass
class DiffProperty:
    db_id: str
    property_type: str
    diff_values_by_asc_time: list[DiffValue] = field(default_factory=list)
    diff_values_set: set[DiffValue] = field(default_factory=set)

    def add_value(self, diff_value: DiffValue) -> None:
        if diff_value in self.diff_values_set:
            return
        bisect.insort(self.diff_values_by_asc_time, diff_value, key=lambda df: df.changed_at)
        self.diff_values_set.add(diff_value)

    @property
    def previous_diff_value(self) -> Optional[DiffValue]:
        if not self.diff_values_by_asc_time:
            return None
        return self.diff_values_by_asc_time[0]

    @property
    def new_diff_value(self) -> Optional[DiffValue]:
        if not self.diff_values_by_asc_time:
            return None
        return self.diff_values_by_asc_time[-1]

    @property
    def previous_value(self) -> Any:
        diff_value = self.previous_diff_value
        return diff_value.value if diff_value is not None else None

    @property
    def new_value(self) -> Any:
        diff_value = self.new_diff_value
        return diff_value.value if diff_value is not None else None

    @property
    def previous_value_changed_at(self) -> Optional[Timestamp]:
        diff_value = self.previous_diff_value
        return diff_value.changed_at if diff_value is not None else None

    @property
    def new_value_changed_at(self) -> Optional[Timestamp]:
        diff_value = self.new_diff_value
        return diff_value.changed_at if diff_value is not None else None

    def get_diff_action(self, from_time: Timestamp) -> DiffAction:
        if len(self.diff_values_by_asc_time) == 0:
            return DiffAction.UNCHANGED
        if len(self.diff_values_by_asc_time) == 1:
            lone_value = self.diff_values_by_asc_time[0]
            if lone_value.changed_at < from_time:
                return DiffAction.REMOVED
            return DiffAction.ADDED
        previous_diff_value = self.diff_values_by_asc_time[0]
        new_diff_value = self.diff_values_by_asc_time[-1]
        action = DiffAction.UPDATED
        if previous_diff_value.value is None and new_diff_value.value:
            action = DiffAction.ADDED
        if previous_diff_value.value and new_diff_value.value is None:
            action = DiffAction.REMOVED
        if previous_diff_value.value == new_diff_value.value:
            action = DiffAction.UNCHANGED
        return action


@dataclass
class DiffAttribute:
    uuid: str
    name: str
    changed_at: Timestamp
    action: DiffAction
    properties_by_type: dict[str, DiffProperty] = field(default_factory=dict)


@dataclass
class DiffSingleRelationship:
    uuid: str
    changed_at: Timestamp
    action: DiffAction
    properties_by_type: dict[str, DiffProperty] = field(default_factory=dict)

    def __hash__(self) -> int:
        return hash(self.uuid)


@dataclass
class DiffRelationshipOne:
    name: str
    changed_at: Timestamp
    action: DiffAction
    properties_by_type: dict[str, DiffProperty] = field(default_factory=dict)


@dataclass
class DiffRelationshipMany:
    name: str
    changed_at: Timestamp
    action: DiffAction
    relationships: set[DiffSingleRelationship] = field(default_factory=set)


@dataclass
class DiffNode:
    uuid: str
    kind: str
    changed_at: Timestamp
    action: DiffAction
    attributes_by_name: dict[str, DiffAttribute] = field(default_factory=dict)
    one_relationships_by_name: dict[str, DiffRelationshipOne] = field(default_factory=dict)
    many_relationships_by_name: dict[str, DiffRelationshipMany] = field(default_factory=dict)


@dataclass
class DiffRoot:
    uuid: str
    branch: str
    nodes_by_id: dict[str, DiffNode] = field(default_factory=dict)


@dataclass
class DatabasePath:
    root_node: Neo4jNode
    path_to_node: Neo4jRelationship
    node_node: Neo4jNode
    path_to_attribute: Neo4jRelationship
    attribute_node: Neo4jNode
    path_to_property: Neo4jRelationship
    property_node: Neo4jNode

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
        deepest_edge = self.path_to_node
        deepest_branch_level = 0
        for database_edge in (self.path_to_node, self.path_to_attribute, self.path_to_property):
            branch_level = int(database_edge.get("branch_level"))
            if branch_level > deepest_branch_level:
                deepest_edge = database_edge
                deepest_branch_level = branch_level
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
