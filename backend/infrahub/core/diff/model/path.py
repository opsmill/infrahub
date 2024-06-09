from __future__ import annotations

import bisect
from textwrap import indent
from typing import TYPE_CHECKING, Any, Generic, Optional, TypeVar

from infrahub.core.constants import RelationshipStatus
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from neo4j.graph import Node as Neo4jNode
    from neo4j.graph import Relationship as Neo4jRelationship


T = TypeVar("T", bound="ChildGraphNode")
U = TypeVar("U", bound="GraphNode")


class GraphNode:
    def __init__(self, node: Neo4jNode) -> None:
        self.node = node

    def __hash__(self) -> int:
        return hash(self.node)

    @property
    def id(self) -> str:
        return str(self.node.get("uuid"))

    @property
    def db_id(self) -> str:
        return self.node.element_id

    @property
    def labels(self) -> list[str]:
        return list(self.node.labels)

    def display(self, indent_str: str = "    ") -> str:  # pylint: disable=unused-argument
        labels = "-".join(self.node.labels)
        return f"[{labels}]({self.node.element_id})"


class ChildGraphNode(GraphNode, Generic[U]):
    def __init__(self, upstream_graph_node: U, relationship: Neo4jRelationship, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.upstream_graph_node = upstream_graph_node
        self.relationship = relationship

    @property
    def changed_at(self) -> Timestamp:
        return Timestamp(self.relationship.get("from"))

    @property
    def from_time(self) -> str:
        return str(self.relationship.get("from"))

    @property
    def status(self) -> RelationshipStatus:
        return RelationshipStatus(self.relationship.get("status"))

    @property
    def relationship_type(self) -> str:
        return self.relationship.type

    @property
    def relationship_id(self) -> str:
        return self.relationship.element_id

    @property
    def branch_name(self) -> str:
        return str(self.relationship.get("branch"))


class ParentGraphNode(GraphNode, Generic[T]):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._edge_map: dict[Neo4jRelationship, T] = {}

    def get_edge_map(self) -> dict[Neo4jRelationship, T]:
        return self._edge_map

    def add_edge(self, edge: Neo4jRelationship, other_node: Neo4jNode) -> T:
        raise NotImplementedError()

    def display(self, indent_str: str = "    ") -> str:
        labels = "-".join(self.node.labels)
        this_repr = f"[{labels}]({self.node.element_id})"
        downstream_reprs = "\n".join([gnp.display() for gnp in self._edge_map.values()])
        display_str = this_repr
        if downstream_reprs:
            display_str += "\n" + indent(text=downstream_reprs, prefix=indent_str)
        return display_str


class PropertyPath(ChildGraphNode["AttributePath"]):
    @property
    def value(self) -> Any:
        if "Node" in self.node.labels:
            return self.node.get("uuid")
        return self.node.get("value")


class AttributePath(ParentGraphNode[PropertyPath], ChildGraphNode["NodePath"]):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # {branch: {property_type: [PropertyPath, ...]}}
        self._property_paths_map: dict[str, dict[str, list[PropertyPath]]] = {}

    @property
    def is_relationship(self) -> bool:
        return "Relationship" in self.node.labels

    @property
    def name(self) -> str:
        return str(self.node.get("name"))

    def add_edge(self, edge: Neo4jRelationship, other_node: Neo4jNode) -> PropertyPath:
        if edge not in self._edge_map:
            self._edge_map[edge] = PropertyPath(upstream_graph_node=self, relationship=edge, node=other_node)
            self._index_property_path(property_path=self._edge_map[edge])
        return self._edge_map[edge]

    def _index_property_path(self, property_path: PropertyPath) -> None:
        branch = property_path.branch_name
        property_type = property_path.relationship_type
        if branch not in self._property_paths_map:
            self._property_paths_map[branch] = {}
        if property_type not in self._property_paths_map[branch]:
            self._property_paths_map[branch][property_type] = []
        bisect.insort(self._property_paths_map[branch][property_type], property_path, key=lambda pp: pp.changed_at)

    def get_property_branches(self) -> list[str]:
        return list(self._property_paths_map.keys())

    def get_property_types(self, branch: Optional[str] = None) -> set[str]:
        if branch:
            return set(self._property_paths_map.get(branch, {}).keys())
        property_types: set[str] = set()
        for property_paths_by_type in self._property_paths_map.values():
            property_types.update(property_paths_by_type.keys())
        return property_types

    def get_latest_property_paths_by_branch(
        self, property_type: str, from_time: Optional[Timestamp]
    ) -> dict[str, PropertyPath]:
        property_path_by_branch: dict[str, PropertyPath] = {}
        for branch, property_paths_by_type in self._property_paths_map.items():
            property_paths = property_paths_by_type.get(property_type)
            if not property_paths:
                continue
            property_path = property_paths[-1]
            if from_time and property_path.changed_at < from_time:
                continue
            property_path_by_branch[branch] = property_path
        return property_path_by_branch

    def get_latest_property_path(self, branch: str, property_type: str) -> Optional[PropertyPath]:
        try:
            return self._property_paths_map[branch][property_type][-1]
        except (KeyError, IndexError):
            return None

    def get_earliest_property_path(self, branch: str, property_type: str) -> Optional[PropertyPath]:
        try:
            return self._property_paths_map[branch][property_type][0]
        except (KeyError, IndexError):
            return None


class NodePath(ParentGraphNode[AttributePath], ChildGraphNode["RootPath"]):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # {branch: {attribute_name: [AttributePath, ...]}}
        self._attribute_paths_map: dict[str, dict[str, list[AttributePath]]] = {}

    @property
    def kind(self) -> str:
        return str(self.node.get("kind"))

    def add_edge(self, edge: Neo4jRelationship, other_node: Neo4jNode) -> AttributePath:
        if edge not in self._edge_map:
            self._edge_map[edge] = AttributePath(upstream_graph_node=self, relationship=edge, node=other_node)
            self._index_attribute_path(attribute_path=self._edge_map[edge])
        return self._edge_map[edge]

    def get_attribute_paths(self) -> list[AttributePath]:
        return list(self._edge_map.values())

    def get_latest_attribute_path(self, branch: str, attribute_name: str) -> Optional[AttributePath]:
        try:
            return self._attribute_paths_map[branch][attribute_name][-1]
        except (KeyError, IndexError):
            return None

    def get_earliest_attribute_path(self, branch: str, attribute_name: str) -> Optional[AttributePath]:
        try:
            return self._attribute_paths_map[branch][attribute_name][0]
        except (KeyError, IndexError):
            return None

    def get_attribute_path_names(self) -> set[str]:
        return {ap.name for ap in self._edge_map.values()}

    def get_attribute_branches(self) -> list[str]:
        return list(self._attribute_paths_map.keys())

    def get_attribute_names(self, branch: Optional[str] = None) -> list[str]:
        if branch:
            return list(self._attribute_paths_map.get(branch, {}).keys())
        attribute_names = []
        for attribute_paths_by_name in self._attribute_paths_map.values():
            attribute_names += list(attribute_paths_by_name.keys())
        return attribute_names

    def _index_attribute_path(self, attribute_path: AttributePath) -> None:
        branch = attribute_path.branch_name
        attribute_name = attribute_path.name
        if branch not in self._attribute_paths_map:
            self._attribute_paths_map[branch] = {}
        if attribute_name not in self._attribute_paths_map[branch]:
            self._attribute_paths_map[branch][attribute_name] = []
        bisect.insort(self._attribute_paths_map[branch][attribute_name], attribute_path, key=lambda ap: ap.changed_at)


class RootPath(ParentGraphNode[NodePath]):
    def add_edge(self, edge: Neo4jRelationship, other_node: Neo4jNode) -> NodePath:
        if edge not in self._edge_map:
            self._edge_map[edge] = NodePath(upstream_graph_node=self, relationship=edge, node=other_node)
        return self._edge_map[edge]

    def get_node_paths(self) -> list[NodePath]:
        return list(self._edge_map.values())


# identify conflicts
# get summary
# serialize for end-user
# identify schema vs data changes
# allow merging two branches
