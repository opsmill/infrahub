from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional, Union

from infrahub.core.constants import DiffAction, RelationshipCardinality, RelationshipStatus
from infrahub.core.timestamp import Timestamp

from .model.path import DatabasePath, DiffAttribute, DiffNode, DiffProperty, DiffRoot

if TYPE_CHECKING:
    from infrahub.core.query.diff import DiffAllPathsQuery
    from infrahub.core.schema.relationship_schema import RelationshipSchema
    from infrahub.core.schema_manager import SchemaManager


class DiffNoChildPathError(Exception): ...


@dataclass
class TrackedStatusUpdates:
    timestamp_status_map: dict[Timestamp, RelationshipStatus] = field(kw_only=True, default_factory=dict)
    _ordered_timestamps: list[Timestamp] = field(kw_only=True, default_factory=list)

    def track_database_path(self, database_path: DatabasePath) -> None:
        if database_path.node_changed_at in self.timestamp_status_map:
            return
        self.timestamp_status_map[database_path.node_changed_at] = database_path.node_status

    def get_ordered_timestamps_asc(self) -> list[Timestamp]:
        if self._ordered_timestamps:
            return self._ordered_timestamps
        if not self.timestamp_status_map:
            return []
        self._ordered_timestamps = sorted(self.timestamp_status_map.keys())
        return self._ordered_timestamps

    def get_action_and_timestamp(self, from_time: Timestamp) -> tuple[DiffAction, Timestamp]:
        ordered_timestamps = self.get_ordered_timestamps_asc()
        if len(ordered_timestamps) == 0:
            raise DiffNoChildPathError()
        latest_timestamp = ordered_timestamps[-1]
        if latest_timestamp < from_time:
            return (DiffAction.UPDATED, latest_timestamp)
        latest_status = self.timestamp_status_map[latest_timestamp]
        action = DiffAction.REMOVED if latest_status is RelationshipStatus.DELETED else DiffAction.ADDED
        return (action, latest_timestamp)


@dataclass
class DiffValueIntermediate:
    changed_at: Timestamp
    status: RelationshipStatus
    value: Any

    def __hash__(self) -> int:
        return hash(f"{self.changed_at.to_string()}|{self.status.value}|{self.value}")


@dataclass
class DiffPropertyIntermediate:
    property_type: str
    diff_values: set[DiffValueIntermediate] = field(default_factory=set)
    _ordered_values: list[DiffValueIntermediate] = field(default_factory=list)

    def add_value(self, diff_value: DiffValueIntermediate) -> None:
        self.diff_values.add(diff_value)

    def get_ordered_values_asc(self) -> list[DiffValueIntermediate]:
        if self._ordered_values:
            return self._ordered_values
        if not self.diff_values:
            return []
        self._ordered_values = sorted(self.diff_values, key=lambda df: df.changed_at)
        return self._ordered_values

    @property
    def earliest_diff_value(self) -> Optional[DiffValueIntermediate]:
        ordered_values = self.get_ordered_values_asc()
        if not ordered_values:
            return None
        return ordered_values[0]

    def get_property_details(self, from_time: Timestamp) -> tuple[DiffAction, Timestamp, Any, Any]:
        """Returns action, timestamp, previous_value, new_value"""
        ordered_values = self.get_ordered_values_asc()
        previous: Any = None
        new: Any = None
        if len(ordered_values) == 0:
            raise DiffNoChildPathError()
        if len(ordered_values) == 1:
            lone_value = ordered_values[0]
            if lone_value.changed_at < from_time:
                action = DiffAction.UNCHANGED
                previous = new = lone_value.value
            elif lone_value.status is RelationshipStatus.ACTIVE:
                action = DiffAction.ADDED
                new = lone_value.value
            else:
                action = DiffAction.REMOVED
                previous = lone_value.value
            return (action, lone_value.changed_at, previous, new)
        previous_diff_value = ordered_values[0]
        new_diff_value = ordered_values[-1]
        action = DiffAction.UPDATED
        if previous_diff_value.value in (None, "NULL") and new_diff_value.value:
            action = DiffAction.ADDED
        if previous_diff_value.value and new_diff_value.value in (None, "NULL"):
            action = DiffAction.REMOVED
        if previous_diff_value.value == new_diff_value.value:
            action = DiffAction.UNCHANGED
        return (action, new_diff_value.changed_at, previous_diff_value.value, new_diff_value.value)

    def to_diff_property(self, from_time: Timestamp) -> DiffProperty:
        action, changed_at, previous_value, new_value = self.get_property_details(from_time=from_time)
        return DiffProperty(
            property_type=self.property_type,
            changed_at=changed_at,
            action=action,
            previous_value=previous_value,
            new_value=new_value,
        )


@dataclass
class DiffAttributeIntermediate(TrackedStatusUpdates):
    uuid: str
    name: str
    properties_by_type: dict[str, DiffPropertyIntermediate] = field(default_factory=dict)

    def to_diff_attribute(self, from_time: Timestamp) -> DiffAttribute:
        properties = [prop.to_diff_property(from_time=from_time) for prop in self.properties_by_type.values()]
        action, changed_at = self.get_action_and_timestamp(from_time=from_time)
        return DiffAttribute(
            uuid=self.uuid, name=self.name, changed_at=changed_at, action=action, properties=properties
        )


@dataclass
class DiffSingleRelationshipIntermediate:
    uuid: str
    changed_at: Timestamp
    action: DiffAction
    properties_by_type: dict[str, DiffPropertyIntermediate] = field(default_factory=dict)

    def __hash__(self) -> int:
        return hash(self.uuid)


@dataclass
class DiffRelationshipOneIntermediate:
    name: str
    changed_at: Timestamp
    action: DiffAction
    properties_by_type: dict[str, DiffPropertyIntermediate] = field(default_factory=dict)


@dataclass
class DiffRelationshipManyIntermediate:
    name: str
    changed_at: Timestamp
    action: DiffAction
    relationships: set[DiffSingleRelationshipIntermediate] = field(default_factory=set)


@dataclass
class DiffNodeIntermediate(TrackedStatusUpdates):
    uuid: str
    kind: str
    attributes_by_name: dict[str, DiffAttributeIntermediate] = field(default_factory=dict)
    one_relationships_by_name: dict[str, DiffRelationshipOneIntermediate] = field(default_factory=dict)
    many_relationships_by_name: dict[str, DiffRelationshipManyIntermediate] = field(default_factory=dict)

    def to_diff_node(self, from_time: Timestamp) -> DiffNode:
        attributes = [attr.to_diff_attribute(from_time=from_time) for attr in self.attributes_by_name.values()]
        action, changed_at = self.get_action_and_timestamp(from_time=from_time)
        return DiffNode(
            uuid=self.uuid,
            kind=self.kind,
            changed_at=changed_at,
            action=action,
            attributes=attributes,
            one_relationships=[],
            many_relationships=[],
        )


@dataclass
class DiffRootIntermediate:
    uuid: str
    branch: str
    nodes_by_id: dict[str, DiffNodeIntermediate] = field(default_factory=dict)

    def to_diff_root(self, from_time: Timestamp) -> DiffRoot:
        nodes = [node.to_diff_node(from_time=from_time) for node in self.nodes_by_id.values()]
        return DiffRoot(uuid=self.uuid, branch=self.branch, nodes=nodes)


class DiffQueryParser:
    def __init__(
        self,
        diff_query: DiffAllPathsQuery,
        base_branch_name: str,
        schema_manager: SchemaManager,
        from_time: Timestamp,
        to_time: Optional[Timestamp] = None,
    ) -> None:
        self.diff_query = diff_query
        self.base_branch_name = base_branch_name
        self.schema_manager = schema_manager
        self.from_time = from_time
        self.to_time = to_time or Timestamp()
        self._diff_root_by_branch: dict[str, DiffRootIntermediate] = {}
        self._final_diff_root_by_branch: dict[str, DiffRoot] = {}

    def get_branches(self) -> set[str]:
        return set(self._final_diff_root_by_branch.keys())

    def get_diff_root_for_branch(self, branch: str) -> Optional[DiffRoot]:
        return self._final_diff_root_by_branch.get(branch)

    def parse(self) -> None:
        if not self.diff_query.has_been_executed:
            raise RuntimeError("query must be executed before indexing")

        for query_result in self.diff_query.get_results():
            paths = query_result.get_paths(label="full_diff_paths")
            for path in paths:
                database_path = DatabasePath.from_cypher_path(cypher_path=path)
                self._parse_path(database_path=database_path)
        self._apply_base_branch_previous_values()
        self._remove_empty_base_diff_root()
        self._finalize()

    def _parse_path(self, database_path: DatabasePath) -> None:
        diff_root = self._get_diff_root(database_path=database_path)
        diff_node = self._get_diff_node(database_path=database_path, diff_root=diff_root)
        self._update_attribute_level(database_path=database_path, diff_node=diff_node)

    def _get_diff_root(self, database_path: DatabasePath) -> DiffRootIntermediate:
        branch = database_path.deepest_branch
        if branch not in self._diff_root_by_branch:
            self._diff_root_by_branch[branch] = DiffRootIntermediate(uuid=database_path.root_id, branch=branch)
        return self._diff_root_by_branch[branch]

    def _get_diff_node(self, database_path: DatabasePath, diff_root: DiffRootIntermediate) -> DiffNodeIntermediate:
        node_id = database_path.node_id
        if node_id not in diff_root.nodes_by_id:
            diff_root.nodes_by_id[node_id] = DiffNodeIntermediate(
                uuid=node_id,
                kind=database_path.node_kind,
            )
        diff_node = diff_root.nodes_by_id[node_id]
        diff_node.track_database_path(database_path=database_path)
        return diff_node

    def _update_attribute_level(self, database_path: DatabasePath, diff_node: DiffNodeIntermediate) -> None:
        node_schema = self.schema_manager.get(
            name=database_path.node_kind, branch=database_path.deepest_branch, duplicate=False
        )
        if "Attribute" in database_path.attribute_node.labels:
            diff_attribute = self._get_diff_attribute(database_path=database_path, diff_node=diff_node)
            self._update_attribute_property(database_path=database_path, diff_attribute=diff_attribute)
            return
        relationship_schema = node_schema.get_relationship_by_identifier(
            id=database_path.attribute_name, raise_on_error=False
        )
        if not relationship_schema:
            return

    def _get_diff_attribute(
        self, database_path: DatabasePath, diff_node: DiffNodeIntermediate
    ) -> DiffAttributeIntermediate:
        attribute_name = database_path.attribute_name
        if attribute_name not in diff_node.attributes_by_name:
            diff_node.attributes_by_name[attribute_name] = DiffAttributeIntermediate(
                uuid=database_path.attribute_id,
                name=attribute_name,
            )
        diff_attribute = diff_node.attributes_by_name[attribute_name]
        diff_attribute.track_database_path(database_path=database_path)
        return diff_attribute

    def _update_attribute_property(
        self, database_path: DatabasePath, diff_attribute: DiffAttributeIntermediate
    ) -> None:
        property_type = database_path.property_type
        if property_type not in diff_attribute.properties_by_type:
            diff_attribute.properties_by_type[property_type] = DiffPropertyIntermediate(property_type=property_type)
        diff_property = diff_attribute.properties_by_type[property_type]
        diff_property.add_value(
            diff_value=DiffValueIntermediate(
                changed_at=database_path.property_changed_at,
                status=database_path.property_status,
                value=database_path.property_value,
            )
        )

    def _get_diff_relationship(
        self, database_path: DatabasePath, diff_node: DiffNodeIntermediate, relationship_schema: RelationshipSchema
    ) -> Union[DiffRelationshipOneIntermediate, DiffRelationshipManyIntermediate]:
        is_cardinality_one = relationship_schema.cardinality == RelationshipCardinality.ONE
        diff_relationship: Optional[Union[DiffRelationshipOneIntermediate, DiffRelationshipManyIntermediate]] = None
        if is_cardinality_one:
            diff_relationship = diff_node.one_relationships_by_name.get(relationship_schema.name, None)
        else:
            diff_relationship = diff_node.many_relationships_by_name.get(relationship_schema.name, None)
        if not diff_relationship:
            changed_at = database_path.attribute_changed_at
            action = DiffAction.ADDED
            if is_cardinality_one:
                diff_relationship = DiffRelationshipOneIntermediate(
                    name=relationship_schema.name, changed_at=changed_at, action=action
                )
            else:
                diff_relationship = DiffRelationshipManyIntermediate(
                    name=relationship_schema.name, changed_at=changed_at, action=action
                )
        return diff_relationship

    def _apply_base_branch_previous_values(self) -> None:
        base_diff_root = self._diff_root_by_branch.get(self.base_branch_name)
        if not base_diff_root:
            return
        other_branches = set(self._diff_root_by_branch.keys()) - {self.base_branch_name}
        for branch in other_branches:
            branch_diff_root = self._diff_root_by_branch.get(branch)
            if not branch_diff_root:
                continue
            for node_id, diff_node in branch_diff_root.nodes_by_id.items():
                base_diff_node = base_diff_root.nodes_by_id.get(node_id)
                if not base_diff_node:
                    continue
                for attribute_name, diff_attribute in diff_node.attributes_by_name.items():
                    base_diff_attribute = base_diff_node.attributes_by_name.get(attribute_name)
                    if not base_diff_attribute:
                        continue
                    for property_type, diff_property in diff_attribute.properties_by_type.items():
                        base_diff_property = base_diff_attribute.properties_by_type.get(property_type)
                        if not base_diff_property:
                            return
                        base_previous_diff_value = base_diff_property.earliest_diff_value
                        if base_previous_diff_value:
                            diff_property.add_value(diff_value=base_previous_diff_value)

    def _remove_empty_base_diff_root(self) -> None:
        base_diff_root = self._diff_root_by_branch.get(self.base_branch_name)
        if not base_diff_root:
            return
        for node_diff in base_diff_root.nodes_by_id.values():
            for attribute_diff in node_diff.attributes_by_name.values():
                for property_diff in attribute_diff.properties_by_type.values():
                    ordered_diff_values = property_diff.get_ordered_values_asc()
                    if not ordered_diff_values:
                        continue
                    if ordered_diff_values[-1].changed_at >= self.from_time:
                        return
        del self._diff_root_by_branch[self.base_branch_name]

    def _finalize(self) -> None:
        for branch, diff_root_intermediate in self._diff_root_by_branch.items():
            self._final_diff_root_by_branch[branch] = diff_root_intermediate.to_diff_root(from_time=self.from_time)
