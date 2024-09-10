from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional
from uuid import uuid4

from infrahub.core.constants import DiffAction, RelationshipCardinality, RelationshipDirection, RelationshipStatus
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.timestamp import Timestamp

from ..exceptions import InvalidCypherPathError

if TYPE_CHECKING:
    from neo4j.graph import Node as Neo4jNode
    from neo4j.graph import Path as Neo4jPath
    from neo4j.graph import Relationship as Neo4jRelationship

    from infrahub.graphql import GraphqlContext


@dataclass
class TimeRange:
    from_time: Timestamp
    to_time: Timestamp


class TrackingId:
    prefix = ""
    delimiter = "."

    def __init__(self, name: str) -> None:
        self.name = name

    def serialize(self) -> str:
        return f"{self.prefix}{self.delimiter}{self.name}"

    @classmethod
    def deserialize(cls, id_string: str) -> TrackingId:
        if not id_string.startswith(cls.prefix):
            raise ValueError(
                f"Cannot deserialize TrackingId with incorrect prefix '{id_string}', expected prefix '{cls.prefix}{cls.delimiter}'"
            )
        return cls(id_string.split(cls.delimiter)[1])

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, type(self)):
            return False
        return self.name == other.name

    def __hash__(self) -> int:
        return hash(self.serialize())

    def __str__(self) -> str:
        return self.serialize()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__} ({self.serialize()})"


class BranchTrackingId(TrackingId):
    prefix = "branch"


class NameTrackingId(TrackingId):
    prefix = "name"


def deserialize_tracking_id(tracking_id_str: str) -> TrackingId:
    for tracking_id_class in (BranchTrackingId, NameTrackingId):
        try:
            return tracking_id_class.deserialize(id_string=tracking_id_str)
        except ValueError:
            ...
    raise ValueError(f"{tracking_id_str} is not a valid TrackingId")


@dataclass
class BaseSummary:
    num_added: int = field(default=0, kw_only=True)
    num_updated: int = field(default=0, kw_only=True)
    num_removed: int = field(default=0, kw_only=True)
    num_conflicts: int = field(default=0, kw_only=True)
    contains_conflict: bool = field(default=False, kw_only=True)

    def reset_summaries(self) -> None:
        self.num_added = 0
        self.num_updated = 0
        self.num_removed = 0
        self.num_conflicts = 0
        self.contains_conflict = False


class ConflictSelection(Enum):
    BASE_BRANCH = "base"
    DIFF_BRANCH = "diff"


@dataclass
class EnrichedDiffConflict:
    uuid: str
    base_branch_action: DiffAction
    base_branch_value: str | None
    diff_branch_action: DiffAction
    diff_branch_value: str | None
    base_branch_label: str | None = field(default=None, kw_only=True)
    diff_branch_label: str | None = field(default=None, kw_only=True)
    base_branch_changed_at: Timestamp | None = field(default=None, kw_only=True)
    diff_branch_changed_at: Timestamp | None = field(default=None, kw_only=True)
    selected_branch: ConflictSelection | None = field(default=None)


@dataclass
class EnrichedDiffProperty:
    property_type: DatabaseEdgeType
    changed_at: Timestamp
    previous_value: str | None
    new_value: str | None
    action: DiffAction
    previous_label: str | None = field(default=None, kw_only=True)
    new_label: str | None = field(default=None, kw_only=True)
    path_identifier: str = field(default="", kw_only=True)
    conflict: EnrichedDiffConflict | None = field(default=None)

    def __hash__(self) -> int:
        return hash(self.property_type)

    @classmethod
    def from_calculated_property(cls, calculated_property: DiffProperty) -> EnrichedDiffProperty:
        return EnrichedDiffProperty(
            property_type=calculated_property.property_type,
            changed_at=calculated_property.changed_at,
            previous_value=str(calculated_property.previous_value)
            if calculated_property.previous_value is not None
            else None,
            new_value=str(calculated_property.new_value) if calculated_property.new_value is not None else None,
            action=calculated_property.action,
        )


@dataclass
class EnrichedDiffAttribute(BaseSummary):
    name: str
    path_identifier: str = field(default="", kw_only=True)
    changed_at: Timestamp
    action: DiffAction
    properties: set[EnrichedDiffProperty] = field(default_factory=set)

    def __hash__(self) -> int:
        return hash(self.name)

    def get_all_conflicts(self) -> list[EnrichedDiffConflict]:
        return [prop.conflict for prop in self.properties if prop.conflict]

    @classmethod
    def from_calculated_attribute(cls, calculated_attribute: DiffAttribute) -> EnrichedDiffAttribute:
        return EnrichedDiffAttribute(
            name=calculated_attribute.name,
            changed_at=calculated_attribute.changed_at,
            action=calculated_attribute.action,
            properties={
                EnrichedDiffProperty.from_calculated_property(calculated_property=prop)
                for prop in calculated_attribute.properties
            },
        )


@dataclass
class EnrichedDiffSingleRelationship(BaseSummary):
    changed_at: Timestamp
    action: DiffAction
    peer_id: str
    peer_label: str | None = field(default=None, kw_only=True)
    path_identifier: str = field(default="", kw_only=True)
    conflict: EnrichedDiffConflict | None = field(default=None)
    properties: set[EnrichedDiffProperty] = field(default_factory=set)

    def __hash__(self) -> int:
        return hash(self.peer_id)

    def get_all_conflicts(self) -> list[EnrichedDiffConflict]:
        all_conflicts = []
        if self.conflict:
            all_conflicts.append(self.conflict)
        all_conflicts.extend([prop.conflict for prop in self.properties if prop.conflict])
        return all_conflicts

    def get_property(self, property_type: DatabaseEdgeType) -> EnrichedDiffProperty:
        for prop in self.properties:
            if prop.property_type == property_type:
                return prop
        raise ValueError(f"Relationship element diff does not have property of type {property_type}")

    @classmethod
    def from_calculated_element(cls, calculated_element: DiffSingleRelationship) -> EnrichedDiffSingleRelationship:
        return EnrichedDiffSingleRelationship(
            changed_at=calculated_element.changed_at,
            action=calculated_element.action,
            peer_id=calculated_element.peer_id,
            properties={
                EnrichedDiffProperty.from_calculated_property(calculated_property=prop)
                for prop in calculated_element.properties
            },
        )


@dataclass
class EnrichedDiffRelationship(BaseSummary):
    name: str
    label: str
    cardinality: RelationshipCardinality
    path_identifier: str = field(default="", kw_only=True)
    changed_at: Timestamp | None = field(default=None, kw_only=True)
    action: DiffAction
    relationships: set[EnrichedDiffSingleRelationship] = field(default_factory=set)
    nodes: set[EnrichedDiffNode] = field(default_factory=set)

    def __hash__(self) -> int:
        return hash(self.name)

    def get_all_conflicts(self) -> list[EnrichedDiffConflict]:
        all_conflicts = []
        for element in self.relationships:
            all_conflicts.extend(element.get_all_conflicts())
        return all_conflicts

    @property
    def include_in_response(self) -> bool:
        if self.action == DiffAction.UNCHANGED and not self.relationships:
            return False
        return True

    @classmethod
    def from_calculated_relationship(cls, calculated_relationship: DiffRelationship) -> EnrichedDiffRelationship:
        return EnrichedDiffRelationship(
            name=calculated_relationship.name,
            label="",
            cardinality=calculated_relationship.cardinality,
            changed_at=calculated_relationship.changed_at,
            action=calculated_relationship.action,
            relationships={
                EnrichedDiffSingleRelationship.from_calculated_element(calculated_element=element)
                for element in calculated_relationship.relationships
            },
            nodes=set(),
        )


@dataclass
class ParentNodeInfo:
    node: EnrichedDiffNode
    relationship_name: str = "undefined"


@dataclass
class EnrichedDiffNode(BaseSummary):
    uuid: str
    kind: str
    label: str
    path_identifier: str = field(default="", kw_only=True)
    changed_at: Timestamp | None = field(default=None, kw_only=True)
    action: DiffAction
    conflict: EnrichedDiffConflict | None = field(default=None)
    attributes: set[EnrichedDiffAttribute] = field(default_factory=set)
    relationships: set[EnrichedDiffRelationship] = field(default_factory=set)

    def __hash__(self) -> int:
        return hash(self.uuid)

    def get_all_conflicts(self) -> list[EnrichedDiffConflict]:
        all_conflicts = []
        if self.conflict:
            all_conflicts.append(self.conflict)
        for attribute in self.attributes:
            all_conflicts.extend(attribute.get_all_conflicts())
        for relationship in self.relationships:
            all_conflicts.extend(relationship.get_all_conflicts())
        return all_conflicts

    def get_parent_info(self, context: GraphqlContext | None = None) -> ParentNodeInfo | None:
        for r in self.relationships:
            for n in r.nodes:
                relationship_name: str = "undefined"

                if not context:
                    return ParentNodeInfo(node=n, relationship_name=relationship_name)

                node_schema = context.db.schema.get(name=self.kind)
                rel_schema = node_schema.get_relationship(name=r.name)

                parent_schema = context.db.schema.get(name=n.kind)
                rels_parent = parent_schema.get_relationships_by_identifier(id=rel_schema.get_identifier())

                if rels_parent and len(rels_parent) == 1:
                    relationship_name = rels_parent[0].name
                elif rels_parent and len(rels_parent) > 1:
                    for rel_parent in rels_parent:
                        if (
                            rel_schema.direction == RelationshipDirection.INBOUND
                            and rel_parent.direction == RelationshipDirection.OUTBOUND
                        ) or (
                            rel_schema.direction == RelationshipDirection.OUTBOUND
                            and rel_parent.direction == RelationshipDirection.INBOUND
                        ):
                            relationship_name = rel_parent.name
                            break

                return ParentNodeInfo(node=n, relationship_name=relationship_name)
        return None

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

    def has_relationship(self, name: str) -> bool:
        try:
            self.get_relationship(name=name)
            return True
        except ValueError:
            return False

    @classmethod
    def from_calculated_node(cls, calculated_node: DiffNode) -> EnrichedDiffNode:
        return EnrichedDiffNode(
            uuid=calculated_node.uuid,
            kind=calculated_node.kind,
            label="",
            changed_at=calculated_node.changed_at,
            action=calculated_node.action,
            attributes={
                EnrichedDiffAttribute.from_calculated_attribute(calculated_attribute=attr)
                for attr in calculated_node.attributes
            },
            relationships={
                EnrichedDiffRelationship.from_calculated_relationship(calculated_relationship=rel)
                for rel in calculated_node.relationships
            },
        )


@dataclass
class EnrichedDiffRoot(BaseSummary):
    base_branch_name: str
    diff_branch_name: str
    from_time: Timestamp
    to_time: Timestamp
    uuid: str
    tracking_id: TrackingId | None = field(default=None, kw_only=True)
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

    def has_node(self, node_uuid: str) -> bool:
        try:
            self.get_node(node_uuid=node_uuid)
            return True
        except ValueError:
            return False

    def get_all_conflicts(self) -> list[EnrichedDiffConflict]:
        all_conflicts = []
        for node in self.nodes:
            all_conflicts.extend(node.get_all_conflicts())
        return all_conflicts

    @classmethod
    def from_calculated_diff(cls, calculated_diff: DiffRoot, base_branch_name: str) -> EnrichedDiffRoot:
        return EnrichedDiffRoot(
            base_branch_name=base_branch_name,
            diff_branch_name=calculated_diff.branch,
            from_time=calculated_diff.from_time,
            to_time=calculated_diff.to_time,
            uuid=str(uuid4()),
            nodes={EnrichedDiffNode.from_calculated_node(calculated_node=n) for n in calculated_diff.nodes},
        )

    def add_parent(
        self,
        node_id: str,
        parent_id: str,
        parent_kind: str,
        parent_label: str,
        parent_rel_name: str,
        parent_rel_cardinality: RelationshipCardinality,
        parent_rel_label: str = "",
    ) -> EnrichedDiffNode:
        node = self.get_node(node_uuid=node_id)
        if not self.has_node(node_uuid=parent_id):
            parent = EnrichedDiffNode(
                uuid=parent_id,
                kind=parent_kind,
                label=parent_label,
                action=DiffAction.UNCHANGED,
                changed_at=None,
            )
            self.nodes.add(parent)

        else:
            parent = self.get_node(node_uuid=parent_id)

        if node.has_relationship(name=parent_rel_name):
            rel = node.get_relationship(name=parent_rel_name)
            rel.nodes.add(parent)
        else:
            node.relationships.add(
                EnrichedDiffRelationship(
                    name=parent_rel_name,
                    label=parent_rel_label,
                    cardinality=parent_rel_cardinality,
                    changed_at=None,
                    action=DiffAction.UNCHANGED,
                    nodes={parent},
                )
            )

        return parent


@dataclass
class EnrichedDiffs:
    base_branch_name: str
    diff_branch_name: str
    base_branch_diff: EnrichedDiffRoot
    diff_branch_diff: EnrichedDiffRoot

    @classmethod
    def from_calculated_diffs(cls, calculated_diffs: CalculatedDiffs) -> EnrichedDiffs:
        base_branch_diff = EnrichedDiffRoot.from_calculated_diff(
            calculated_diff=calculated_diffs.base_branch_diff, base_branch_name=calculated_diffs.base_branch_name
        )
        diff_branch_diff = EnrichedDiffRoot.from_calculated_diff(
            calculated_diff=calculated_diffs.diff_branch_diff, base_branch_name=calculated_diffs.base_branch_name
        )
        return EnrichedDiffs(
            base_branch_name=calculated_diffs.base_branch_name,
            diff_branch_name=calculated_diffs.diff_branch_name,
            base_branch_diff=base_branch_diff,
            diff_branch_diff=diff_branch_diff,
        )


@dataclass
class CalculatedDiffs:
    base_branch_name: str
    diff_branch_name: str
    base_branch_diff: DiffRoot
    diff_branch_diff: DiffRoot


@dataclass
class DiffProperty:
    property_type: DatabaseEdgeType
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
    cardinality: RelationshipCardinality
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
    def property_type(self) -> DatabaseEdgeType:
        return DatabaseEdgeType(self.path_to_property.type)

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
