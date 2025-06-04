from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from infrahub.core.constants import (
    NULL_VALUE,
    BranchSupportType,
    DiffAction,
    RelationshipCardinality,
    RelationshipStatus,
)
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.timestamp import Timestamp

from .model.field_specifiers_map import NodeFieldSpecifierMap
from .model.path import (
    DatabasePath,
    DiffAttribute,
    DiffNode,
    DiffProperty,
    DiffRelationship,
    DiffRoot,
    DiffSingleRelationship,
    NodeIdentifier,
)

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.query import QueryResult
    from infrahub.core.schema.manager import SchemaManager
    from infrahub.core.schema.relationship_schema import RelationshipSchema


class DiffNoChildPathError(Exception): ...


class DiffNoPeerIdError(Exception): ...


class DiffNotFoundError(Exception): ...


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
        return hash("|".join(str(v) for v in (self.changed_at.to_string(), self.status.value, self.value)))


@dataclass
class DiffPropertyIntermediate:
    property_type: DatabaseEdgeType
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
    def earliest_diff_value(self) -> DiffValueIntermediate | None:
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
        earliest_value = ordered_values[0]
        new_diff_value = ordered_values[-1]
        new_value = new_diff_value.value
        new_status = new_diff_value.status
        action = DiffAction.UPDATED
        previous_value = earliest_value.value
        if earliest_value.changed_at > from_time:
            action = DiffAction.ADDED
            previous_value = None
        elif earliest_value.value in (None, NULL_VALUE) and new_value not in (None, NULL_VALUE):
            action = DiffAction.ADDED
        elif (earliest_value.value not in (None, NULL_VALUE) and new_value in (None, NULL_VALUE)) or (
            earliest_value.status,
            new_status,
        ) == (RelationshipStatus.ACTIVE, RelationshipStatus.DELETED):
            action = DiffAction.REMOVED
            if new_value != NULL_VALUE:
                new_value = None
        elif earliest_value.value == new_value or {earliest_value.value, new_value} <= {None, NULL_VALUE}:
            action = DiffAction.UNCHANGED
        return (action, new_diff_value.changed_at, previous_value, new_value)

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
    from_time: Timestamp
    properties_by_type: dict[DatabaseEdgeType, DiffPropertyIntermediate] = field(default_factory=dict)

    def track_database_path(self, database_path: DatabasePath) -> None:
        if database_path.attribute_changed_at in self.timestamp_status_map:
            return
        self.timestamp_status_map[database_path.attribute_changed_at] = database_path.attribute_status

    def to_diff_attribute(self, include_unchanged: bool) -> DiffAttribute:
        properties = []
        for prop in self.properties_by_type.values():
            diff_prop = prop.to_diff_property(from_time=self.from_time)
            if include_unchanged or diff_prop.action is not DiffAction.UNCHANGED:
                properties.append(diff_prop)
        action, changed_at = self.get_action_and_timestamp(from_time=self.from_time)
        if not properties or all(p.action is DiffAction.UNCHANGED for p in properties):
            action = DiffAction.UNCHANGED
        return DiffAttribute(
            uuid=self.uuid, name=self.name, changed_at=changed_at, action=action, properties=properties
        )


@dataclass
class DiffRelationshipPropertyIntermediate:
    property_type: DatabaseEdgeType
    db_id: str
    changed_at: Timestamp
    status: RelationshipStatus
    value: Any

    def __hash__(self) -> int:
        return hash(
            "|".join(
                (self.property_type.value, self.db_id, self.changed_at.to_string(), self.status.value, str(self.value))
            )
        )


@dataclass
class DiffSingleRelationshipIntermediate:
    peer_id: str
    last_changed_at: Timestamp
    ordered_properties_by_type: dict[DatabaseEdgeType, list[DiffRelationshipPropertyIntermediate]] = field(
        default_factory=dict
    )

    @classmethod
    def from_properties(
        cls, properties: list[DiffRelationshipPropertyIntermediate]
    ) -> DiffSingleRelationshipIntermediate:
        if not properties:
            raise DiffNoChildPathError()
        peer_id = None
        for diff_property in properties:
            if diff_property.property_type == DatabaseEdgeType.IS_RELATED:
                peer_id = diff_property.value
                break
        if not peer_id:
            raise DiffNoPeerIdError(f"Cannot identify peer ID for relationship property {(properties[0]).db_id}")

        ordered_properties_by_type: dict[DatabaseEdgeType, list[DiffRelationshipPropertyIntermediate]] = {}
        # tiebreaker for simultaneous updates is to prefer the DELETED relationship
        chronological_properties = sorted(
            properties, key=lambda p: (p.changed_at, p.status is RelationshipStatus.ACTIVE)
        )
        last_changed_at = chronological_properties[-1].changed_at
        for chronological_property in chronological_properties:
            property_key = DatabaseEdgeType(chronological_property.property_type)
            if chronological_property.property_type not in ordered_properties_by_type:
                ordered_properties_by_type[property_key] = []
            ordered_properties_by_type[property_key].append(chronological_property)
        return cls(
            peer_id=peer_id,
            last_changed_at=last_changed_at,
            ordered_properties_by_type=ordered_properties_by_type,
        )

    def _get_single_relationship_final_property(
        self, chronological_properties: list[DiffRelationshipPropertyIntermediate], from_time: Timestamp
    ) -> DiffProperty:
        property_type = DatabaseEdgeType(chronological_properties[0].property_type)
        changed_at = chronological_properties[-1].changed_at
        previous_value = None
        first_diff_prop = chronological_properties[0]
        if first_diff_prop.status is RelationshipStatus.DELETED or first_diff_prop.changed_at < from_time:
            previous_value = first_diff_prop.value
        new_value = None
        last_diff_prop = chronological_properties[-1]
        changed_at = last_diff_prop.changed_at
        if last_diff_prop is first_diff_prop:
            if last_diff_prop.status is RelationshipStatus.DELETED:
                previous_value = last_diff_prop.value
            else:
                new_value = last_diff_prop.value
        elif last_diff_prop.status != RelationshipStatus.DELETED:
            new_value = last_diff_prop.value
        action = DiffAction.UPDATED
        if last_diff_prop.changed_at < from_time:
            action = DiffAction.UNCHANGED
        elif previous_value in (None, NULL_VALUE) and new_value not in (None, NULL_VALUE):
            action = DiffAction.ADDED
        elif previous_value not in (None, NULL_VALUE) and new_value in (None, NULL_VALUE):
            action = DiffAction.REMOVED
        elif previous_value == new_value or {previous_value, new_value} <= {None, NULL_VALUE}:
            action = DiffAction.UNCHANGED
        return DiffProperty(
            property_type=property_type,
            changed_at=changed_at,
            previous_value=previous_value,
            new_value=new_value,
            action=action,
        )

    def get_final_single_relationship(self, from_time: Timestamp, include_unchanged: bool) -> DiffSingleRelationship:
        final_properties = []
        peer_id_properties = self.ordered_properties_by_type[DatabaseEdgeType.IS_RELATED]
        peer_final_property = self._get_single_relationship_final_property(
            chronological_properties=peer_id_properties, from_time=from_time
        )
        peer_id = peer_final_property.new_value or peer_final_property.previous_value
        other_final_properties = []
        for property_type, property_list in self.ordered_properties_by_type.items():
            if property_type is DatabaseEdgeType.IS_RELATED:
                continue
            final_prop = self._get_single_relationship_final_property(
                chronological_properties=property_list, from_time=from_time
            )
            if include_unchanged or final_prop.action is not DiffAction.UNCHANGED:
                other_final_properties.append(final_prop)
        final_properties = [peer_final_property] + other_final_properties
        last_changed_property = max(final_properties, key=lambda fp: fp.changed_at)
        last_changed_at = last_changed_property.changed_at
        # handle case when peer has been deleted on another branch, but the properties of the relationship are updated
        if (
            last_changed_property.property_type is not DatabaseEdgeType.IS_RELATED
            and any(p.action is not DiffAction.REMOVED for p in other_final_properties)
            and peer_final_property.action is DiffAction.REMOVED
        ):
            peer_final_property.action = DiffAction.UNCHANGED
            peer_final_property.new_value = peer_id
        if last_changed_at < from_time or all(fp.action is DiffAction.UNCHANGED for fp in final_properties):
            action = DiffAction.UNCHANGED
        elif peer_final_property.action in (DiffAction.ADDED, DiffAction.REMOVED):
            action = peer_final_property.action
        else:
            action = DiffAction.UPDATED
        return DiffSingleRelationship(
            peer_id=peer_id, changed_at=last_changed_at, action=action, properties=final_properties
        )


@dataclass
class DiffRelationshipIntermediate:
    name: str
    identifier: str
    cardinality: RelationshipCardinality
    from_time: Timestamp
    properties_by_db_id: dict[str, set[DiffRelationshipPropertyIntermediate]] = field(default_factory=dict)
    _single_relationship_list: list[DiffSingleRelationshipIntermediate] = field(default_factory=list)

    def add_path(self, database_path: DatabasePath, diff_from_time: Timestamp, diff_to_time: Timestamp) -> None:
        if database_path.property_type in [
            DatabaseEdgeType.IS_RELATED,
            DatabaseEdgeType.HAS_OWNER,
            DatabaseEdgeType.HAS_SOURCE,
        ]:
            value = database_path.peer_id
        else:
            value = database_path.property_value
        db_id = database_path.attribute_node.element_id
        if db_id not in self.properties_by_db_id:
            self.properties_by_db_id[db_id] = set()
        self.properties_by_db_id[db_id].add(
            DiffRelationshipPropertyIntermediate(
                db_id=db_id,
                property_type=database_path.property_type,
                changed_at=database_path.property_from_time,
                status=database_path.property_status,
                value=value,
            )
        )
        to_time = database_path.property_to_time
        # if the to time was set in the time frame, then it is effectively a delete
        if (
            to_time
            and database_path.property_from_time < diff_from_time <= to_time <= diff_to_time
            and database_path.property_status is RelationshipStatus.ACTIVE
        ):
            self.properties_by_db_id[db_id].add(
                DiffRelationshipPropertyIntermediate(
                    db_id=db_id,
                    property_type=database_path.property_type,
                    changed_at=to_time,
                    status=RelationshipStatus.DELETED,
                    value=value,
                )
            )

    def _index_relationships(self) -> None:
        self._single_relationship_list = [
            DiffSingleRelationshipIntermediate.from_properties(list(single_relationship_properties))
            for single_relationship_properties in self.properties_by_db_id.values()
        ]

    def to_diff_relationship(self, include_unchanged: bool) -> DiffRelationship:
        self._index_relationships()
        single_relationships = [
            sr.get_final_single_relationship(from_time=self.from_time, include_unchanged=include_unchanged)
            for sr in self._single_relationship_list
        ]
        last_changed_relationship = max(single_relationships, key=lambda r: r.changed_at)
        last_changed_at = last_changed_relationship.changed_at
        action = DiffAction.UPDATED
        if last_changed_at < self.from_time or all(sr.action is DiffAction.UNCHANGED for sr in single_relationships):
            action = DiffAction.UNCHANGED
        # bubble up action, excluding UNCHANGED
        if self.cardinality is RelationshipCardinality.ONE:
            actions = {sr.action for sr in single_relationships if sr.action is not DiffAction.UNCHANGED}
            if len(actions) == 1:
                action = actions.pop()
        return DiffRelationship(
            name=self.name,
            identifier=self.identifier,
            changed_at=last_changed_at,
            action=action,
            relationships=single_relationships,
            cardinality=self.cardinality,
        )


@dataclass
class DiffNodeIntermediate(TrackedStatusUpdates):
    force_action: DiffAction | None
    identifier: NodeIdentifier
    db_id: str
    from_time: Timestamp
    status: RelationshipStatus
    attributes_by_name: dict[str, DiffAttributeIntermediate] = field(default_factory=dict)
    # {(name, identifier): DiffRelationshipIntermediate}
    relationships_by_identifier: dict[tuple[str, str], DiffRelationshipIntermediate] = field(default_factory=dict)

    @property
    def uuid(self) -> str:
        return self.identifier.uuid

    @property
    def kind(self) -> str:
        return self.identifier.kind

    def to_diff_node(self, from_time: Timestamp, include_unchanged: bool) -> DiffNode:
        attributes = []
        for attr in self.attributes_by_name.values():
            diff_attr = attr.to_diff_attribute(include_unchanged=include_unchanged)
            if include_unchanged or diff_attr.action is not DiffAction.UNCHANGED:
                attributes.append(diff_attr)
        action, changed_at = self.get_action_and_timestamp(from_time=from_time)
        relationships = []
        for rel in self.relationships_by_identifier.values():
            diff_rel = rel.to_diff_relationship(include_unchanged=include_unchanged)
            if include_unchanged or diff_rel.action is not DiffAction.UNCHANGED:
                relationships.append(diff_rel)
        if not attributes and not relationships:
            action = DiffAction.UNCHANGED
        if all(a.action is DiffAction.UNCHANGED for a in attributes) and all(
            r.action is DiffAction.UNCHANGED for r in relationships
        ):
            action = DiffAction.UNCHANGED
        if self.force_action:
            action = self.force_action
        return DiffNode(
            identifier=self.identifier,
            changed_at=changed_at,
            action=action,
            attributes=attributes,
            relationships=relationships,
        )

    @property
    def is_empty(self) -> bool:
        return len(self.attributes_by_name) == 0 and len(self.relationships_by_identifier) == 0


@dataclass
class DiffRootIntermediate:
    uuid: str
    branch: str
    nodes_by_identifier: dict[NodeIdentifier, DiffNodeIntermediate] = field(default_factory=dict)

    def to_diff_root(self, from_time: Timestamp, to_time: Timestamp, include_unchanged: bool) -> DiffRoot:
        nodes = []
        for node in self.nodes_by_identifier.values():
            if node.is_empty:
                continue
            diff_node = node.to_diff_node(from_time=from_time, include_unchanged=include_unchanged)
            if include_unchanged or diff_node.action is not DiffAction.UNCHANGED:
                nodes.append(diff_node)
        return DiffRoot(uuid=self.uuid, branch=self.branch, nodes=nodes, from_time=from_time, to_time=to_time)


class DiffQueryParser:
    def __init__(
        self,
        base_branch: Branch,
        diff_branch: Branch,
        schema_manager: SchemaManager,
        from_time: Timestamp,
        to_time: Timestamp | None = None,
        previous_node_field_specifiers: NodeFieldSpecifierMap | None = None,
    ) -> None:
        self.base_branch_name = base_branch.name
        self.diff_branch_name = diff_branch.name
        self.schema_manager = schema_manager
        self.from_time = from_time
        self.to_time = to_time or Timestamp()
        # if this diff is for the base branch, use from_time b/c create_time would be too much
        if diff_branch.name == base_branch.name:
            self.diff_branched_from_time = from_time
        else:
            self.diff_branched_from_time = Timestamp(diff_branch.get_branched_from())
        self._diff_root_by_branch: dict[str, DiffRootIntermediate] = {}
        self._final_diff_root_by_branch: dict[str, DiffRoot] = {}
        self._previous_node_field_specifiers = previous_node_field_specifiers or NodeFieldSpecifierMap()
        self._new_node_field_specifiers: NodeFieldSpecifierMap | None = None
        self._current_node_field_specifiers: NodeFieldSpecifierMap | None = None

    def get_branches(self) -> set[str]:
        return set(self._final_diff_root_by_branch.keys())

    def get_diff_root_for_branch(self, branch: str) -> DiffRoot:
        if branch not in (self.base_branch_name, self.diff_branch_name):
            raise DiffNotFoundError(f"No diff found for branch {branch}")
        if branch in self._final_diff_root_by_branch:
            return self._final_diff_root_by_branch[branch]
        return DiffRoot(from_time=self.from_time, to_time=self.to_time, uuid=str(uuid4()), branch=branch, nodes=[])

    def get_diff_node_field_specifiers(self) -> NodeFieldSpecifierMap:
        node_field_specifiers_map = NodeFieldSpecifierMap()
        if self.diff_branch_name not in self._diff_root_by_branch:
            return node_field_specifiers_map
        diff_root = self._diff_root_by_branch[self.diff_branch_name]
        for node in diff_root.nodes_by_identifier.values():
            for attribute_name in node.attributes_by_name:
                node_field_specifiers_map.add_entry(node_uuid=node.uuid, kind=node.kind, field_name=attribute_name)
            for relationship_diff in node.relationships_by_identifier.values():
                node_field_specifiers_map.add_entry(
                    node_uuid=node.uuid, kind=node.kind, field_name=relationship_diff.identifier
                )
        return node_field_specifiers_map

    def get_new_node_field_specifiers(self) -> NodeFieldSpecifierMap:
        if self._new_node_field_specifiers is not None:
            return self._new_node_field_specifiers
        branch_node_specifiers = self.get_diff_node_field_specifiers()
        self._new_node_field_specifiers = branch_node_specifiers - self._previous_node_field_specifiers
        return self._new_node_field_specifiers

    def get_current_node_field_specifiers(self) -> NodeFieldSpecifierMap:
        if self._current_node_field_specifiers is not None:
            return self._current_node_field_specifiers
        new_node_field_specifiers = self.get_new_node_field_specifiers()
        self._current_node_field_specifiers = self._previous_node_field_specifiers - new_node_field_specifiers
        return self._current_node_field_specifiers

    def read_result(self, query_result: QueryResult) -> None:
        try:
            path = query_result.get_path(label="diff_path")
        except ValueError:
            # the path was null, so nothing to read
            return
        database_path = DatabasePath.from_cypher_path(cypher_path=path)
        self._parse_path(database_path=database_path)
        self._current_node_field_specifiers = None
        self._new_node_field_specifiers = None

    def parse(self, include_unchanged: bool = False) -> None:
        self._new_node_field_specifiers = None
        self._current_node_field_specifiers = None
        if len(self._diff_root_by_branch) > 1:
            self._apply_base_branch_previous_values()
            self._remove_empty_base_diff_root()
        self._finalize(include_unchanged=include_unchanged)

    def _parse_path(self, database_path: DatabasePath) -> None:
        to_time = database_path.property_to_time
        # this path was added and removed within the timeframe, so we ignore it
        if to_time and self.from_time <= database_path.property_from_time <= to_time <= self.to_time:
            return

        diff_root = self._get_diff_root(database_path=database_path)
        diff_node = self._get_diff_node(database_path=database_path, diff_root=diff_root)
        self._update_attribute_level(database_path=database_path, diff_node=diff_node)

    def _get_diff_root(self, database_path: DatabasePath) -> DiffRootIntermediate:
        branch = database_path.deepest_branch
        if branch not in self._diff_root_by_branch:
            self._diff_root_by_branch[branch] = DiffRootIntermediate(uuid=str(uuid4()), branch=branch)
        return self._diff_root_by_branch[branch]

    def _get_diff_node(self, database_path: DatabasePath, diff_root: DiffRootIntermediate) -> DiffNodeIntermediate:
        identifier = NodeIdentifier(
            uuid=database_path.node_id, kind=database_path.node_kind, db_id=database_path.node_db_id
        )
        if identifier not in diff_root.nodes_by_identifier:
            diff_root.nodes_by_identifier[identifier] = DiffNodeIntermediate(
                identifier=identifier,
                db_id=database_path.node_db_id,
                from_time=database_path.node_changed_at,
                status=database_path.node_status,
                force_action=DiffAction.UPDATED
                if database_path.node_branch_support is BranchSupportType.AGNOSTIC
                else None,
            )
        diff_node = diff_root.nodes_by_identifier[identifier]
        diff_node.track_database_path(database_path=database_path)
        return diff_node

    def _get_relationship_schema(self, database_path: DatabasePath) -> RelationshipSchema | None:
        branches_to_check = [database_path.deepest_branch]
        if database_path.deepest_branch == self.diff_branch_name:
            branches_to_check.append(self.base_branch_name)
        for schema_branch_name in branches_to_check:
            node_schema = self.schema_manager.get(
                name=database_path.node_kind, branch=schema_branch_name, duplicate=False
            )
            relationship_schemas = node_schema.get_relationships_by_identifier(id=database_path.attribute_name)
            if len(relationship_schemas) == 1:
                return relationship_schemas[0]
            possible_path_directions = database_path.possible_relationship_directions
            for rel_schema in relationship_schemas:
                if rel_schema.direction in possible_path_directions:
                    return rel_schema
        return None

    def _update_attribute_level(self, database_path: DatabasePath, diff_node: DiffNodeIntermediate) -> None:
        if "Attribute" in database_path.attribute_node.labels:
            diff_attribute = self._get_diff_attribute(database_path=database_path, diff_node=diff_node)
            self._update_attribute_property(database_path=database_path, diff_attribute=diff_attribute)
            return
        relationship_schema = self._get_relationship_schema(database_path=database_path)
        if not relationship_schema:
            return
        diff_relationship = self._get_diff_relationship(
            diff_node=diff_node, relationship_schema=relationship_schema, database_path=database_path
        )
        diff_relationship.add_path(
            database_path=database_path, diff_from_time=self.from_time, diff_to_time=self.to_time
        )

    def _get_diff_attribute(
        self, database_path: DatabasePath, diff_node: DiffNodeIntermediate
    ) -> DiffAttributeIntermediate:
        attribute_name = database_path.attribute_name
        branch_name = database_path.deepest_branch
        from_time = self.from_time
        if branch_name == self.base_branch_name:
            new_node_field_specifiers = self.get_new_node_field_specifiers()
            if new_node_field_specifiers.has_entry(
                node_uuid=diff_node.uuid, kind=diff_node.kind, field_name=attribute_name
            ):
                from_time = self.diff_branched_from_time
        if attribute_name not in diff_node.attributes_by_name:
            diff_node.attributes_by_name[attribute_name] = DiffAttributeIntermediate(
                uuid=database_path.attribute_id,
                name=attribute_name,
                from_time=from_time,
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
        value = database_path.property_value
        if database_path.property_is_peer:
            value = database_path.peer_id
        diff_property.add_value(
            diff_value=DiffValueIntermediate(
                changed_at=database_path.property_from_time,
                status=database_path.property_status,
                value=value,
            )
        )

    def _get_diff_relationship(
        self,
        diff_node: DiffNodeIntermediate,
        relationship_schema: RelationshipSchema,
        database_path: DatabasePath,
    ) -> DiffRelationshipIntermediate:
        diff_relationship = diff_node.relationships_by_identifier.get(
            (relationship_schema.name, relationship_schema.get_identifier())
        )
        if not diff_relationship:
            branch_name = database_path.deepest_branch
            from_time = self.from_time
            if branch_name == self.base_branch_name:
                new_node_field_specifiers = self.get_new_node_field_specifiers()
                if new_node_field_specifiers.has_entry(
                    node_uuid=diff_node.uuid, kind=diff_node.kind, field_name=relationship_schema.get_identifier()
                ):
                    from_time = self.diff_branched_from_time
            diff_relationship = DiffRelationshipIntermediate(
                name=relationship_schema.name,
                cardinality=relationship_schema.cardinality,
                identifier=relationship_schema.get_identifier(),
                from_time=from_time,
            )
            diff_node.relationships_by_identifier[relationship_schema.name, relationship_schema.get_identifier()] = (
                diff_relationship
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
            base_diff_nodes_by_uuid = {n.uuid: n for n in base_diff_root.nodes_by_identifier.values()}
            for identifier, diff_node in branch_diff_root.nodes_by_identifier.items():
                # changes on a base branch node with a given UUID should apply to all diff branch nodes with that UUID
                base_diff_node = base_diff_nodes_by_uuid.get(identifier.uuid)
                if not base_diff_node:
                    continue
                self._apply_attribute_previous_values(diff_node=diff_node, base_diff_node=base_diff_node)
                self._apply_relationship_previous_values(diff_node=diff_node, base_diff_node=base_diff_node)

    def _apply_attribute_previous_values(
        self, diff_node: DiffNodeIntermediate, base_diff_node: DiffNodeIntermediate
    ) -> None:
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

    def _apply_relationship_previous_values(
        self, diff_node: DiffNodeIntermediate, base_diff_node: DiffNodeIntermediate
    ) -> None:
        for relationship_key, diff_relationship in diff_node.relationships_by_identifier.items():
            base_diff_relationship = base_diff_node.relationships_by_identifier.get(relationship_key)
            if not base_diff_relationship:
                continue
            for db_id, property_set in diff_relationship.properties_by_db_id.items():
                base_property_set = base_diff_relationship.properties_by_db_id.get(db_id)
                if not base_property_set:
                    continue
                base_diff_property_by_type: dict[DatabaseEdgeType, DiffRelationshipPropertyIntermediate | None] = {
                    DatabaseEdgeType(p.property_type): None for p in property_set
                }
                base_diff_property_by_type[DatabaseEdgeType.IS_RELATED] = None
                latest_diff_property_times_by_type: dict[DatabaseEdgeType, Timestamp] = {}
                for diff_property in property_set:
                    if (
                        diff_property.property_type not in latest_diff_property_times_by_type
                        or diff_property.changed_at > latest_diff_property_times_by_type[diff_property.property_type]
                    ):
                        latest_diff_property_times_by_type[diff_property.property_type] = diff_property.changed_at

                for base_diff_property in base_property_set:
                    prop_type = DatabaseEdgeType(base_diff_property.property_type)
                    if (
                        prop_type not in base_diff_property_by_type
                        or (
                            base_diff_property.status is RelationshipStatus.ACTIVE
                            and base_diff_property.changed_at >= self.from_time
                        )
                        or (
                            prop_type in latest_diff_property_times_by_type
                            and base_diff_property.changed_at > latest_diff_property_times_by_type[prop_type]
                        )
                    ):
                        continue
                    if base_diff_property_by_type[prop_type] is None:
                        base_diff_property_by_type[prop_type] = base_diff_property
                        continue
                    current_property = base_diff_property_by_type.get(prop_type)
                    if current_property and base_diff_property.changed_at < current_property.changed_at:
                        base_diff_property_by_type[prop_type] = base_diff_property
                property_set.update({bdp for bdp in base_diff_property_by_type.values() if bdp})

    def _remove_empty_base_diff_root(self) -> None:
        base_diff_root = self._diff_root_by_branch.get(self.base_branch_name)
        if not base_diff_root:
            return
        for node_diff in base_diff_root.nodes_by_identifier.values():
            for attribute_diff in node_diff.attributes_by_name.values():
                for property_diff in attribute_diff.properties_by_type.values():
                    ordered_diff_values = property_diff.get_ordered_values_asc()
                    if not ordered_diff_values:
                        continue
                    if ordered_diff_values[-1].changed_at >= self.diff_branched_from_time:
                        return
            for relationship_diff in node_diff.relationships_by_identifier.values():
                for diff_relationship_property_list in relationship_diff.properties_by_db_id.values():
                    for diff_relationship_property in diff_relationship_property_list:
                        if diff_relationship_property.changed_at >= self.diff_branched_from_time:
                            return
        del self._diff_root_by_branch[self.base_branch_name]

    def _finalize(self, include_unchanged: bool) -> None:
        for branch, diff_root_intermediate in self._diff_root_by_branch.items():
            if branch == self.base_branch_name:
                from_time = self.diff_branched_from_time
            else:
                from_time = self.from_time
            self._final_diff_root_by_branch[branch] = diff_root_intermediate.to_diff_root(
                from_time=from_time,
                to_time=self.to_time,
                include_unchanged=include_unchanged,
            )
