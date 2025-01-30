from typing import AsyncGenerator

from infrahub.core.constants import NULL_VALUE, DiffAction, RelationshipCardinality
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.schema import MainSchemaTypes
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import SchemaNotFoundError
from infrahub.types import ATTRIBUTE_PYTHON_TYPES

from ..model.path import (
    ConflictSelection,
    EnrichedDiffAttribute,
    EnrichedDiffConflict,
    EnrichedDiffProperty,
    EnrichedDiffRoot,
    EnrichedDiffSingleRelationship,
)
from .model import (
    AttributeMergeDict,
    AttributePropertyMergeDict,
    NodeMergeDict,
    PropertyMergeDict,
    RelationshipMergeDict,
    RelationshipPropertyMergeDict,
)

Primitives = str | bool | int | float


class DiffMergeSerializer:
    def __init__(self, db: InfrahubDatabase, max_batch_size: int) -> None:
        self.db = db
        self.max_batch_size = max_batch_size
        self._attribute_type_cache: dict[tuple[str, str], type] = {}
        self._source_branch_name: str | None = None
        self._target_branch_name: str | None = None
        # {(node_id, relationship_id, peer_id)}
        self._conflicted_cardinality_one_relationships: set[tuple[str, str, str]] = set()

    def _reset_caches(self) -> None:
        self._attribute_type_cache = {}

    @property
    def source_branch_name(self) -> str:
        if self._source_branch_name is None:
            raise RuntimeError("source_branch_name not set")
        return self._source_branch_name

    @property
    def target_branch_name(self) -> str:
        if self._target_branch_name is None:
            raise RuntimeError("target_branch_name not set")
        return self._target_branch_name

    def _get_schema(self, kind: str, branch_name: str) -> MainSchemaTypes:
        schema_branch = self.db.schema.get_schema_branch(name=branch_name)
        return schema_branch.get(name=kind, duplicate=False)

    def _get_action(self, action: DiffAction, conflict: EnrichedDiffConflict | None) -> DiffAction:
        if not conflict:
            return action
        if conflict.selected_branch is ConflictSelection.BASE_BRANCH:
            return conflict.base_branch_action
        if conflict.selected_branch is ConflictSelection.DIFF_BRANCH:
            return conflict.diff_branch_action
        raise ValueError(f"conflict {conflict.uuid} does not have a branch selection")

    def _to_action_str(self, action: DiffAction) -> str:
        return str(action.value).upper()

    def _get_property_type_for_attribute_value(self, schema_kind: str, attribute_name: str) -> type:
        cache_key = (schema_kind, attribute_name)
        if cache_key in self._attribute_type_cache:
            return self._attribute_type_cache[cache_key]
        try:
            node_schema = self._get_schema(kind=schema_kind, branch_name=self.source_branch_name)
            attribute_schema = node_schema.get_attribute(name=attribute_name)
        except (SchemaNotFoundError, ValueError):
            node_schema = self._get_schema(kind=schema_kind, branch_name=self.target_branch_name)
            attribute_schema = node_schema.get_attribute(name=attribute_name)
        python_type = ATTRIBUTE_PYTHON_TYPES[attribute_schema.kind]
        final_python_type: type = str
        if python_type in (str, int, float, bool):
            final_python_type = python_type
        self._attribute_type_cache[cache_key] = final_python_type
        return final_python_type

    def _convert_property_value(
        self, property_type: DatabaseEdgeType, raw_value: str | None, value_type: type | None = None
    ) -> Primitives | None:
        # peer IDs are strings
        if property_type in (DatabaseEdgeType.HAS_OWNER, DatabaseEdgeType.HAS_SOURCE, DatabaseEdgeType.IS_RELATED):
            return raw_value
        # these are boolean
        if (property_type in (DatabaseEdgeType.IS_VISIBLE, DatabaseEdgeType.IS_PROTECTED)) and isinstance(
            raw_value, str
        ):
            return raw_value.lower() == "true"
        # this must be HAS_VALUE
        if raw_value in (None, NULL_VALUE):
            return NULL_VALUE
        if value_type:
            if value_type is bool and isinstance(raw_value, str):
                return raw_value.lower() == "true"
            return value_type(raw_value)
        return raw_value

    def _cache_conflicted_cardinality_one_relationships(self, diff: EnrichedDiffRoot) -> None:
        for node in diff.nodes:
            for rel in node.relationships:
                if rel.cardinality is not RelationshipCardinality.ONE:
                    continue
                for element in rel.relationships:
                    if element.conflict is None:
                        continue
                    for prop in element.properties:
                        if prop.property_type is not DatabaseEdgeType.IS_RELATED:
                            continue
                        if prop.previous_value:
                            self._conflicted_cardinality_one_relationships.add(
                                (node.uuid, rel.identifier, prop.previous_value)
                            )
                        if prop.new_value:
                            self._conflicted_cardinality_one_relationships.add(
                                (node.uuid, rel.identifier, prop.new_value)
                            )

    async def serialize_diff(
        self, diff: EnrichedDiffRoot
    ) -> AsyncGenerator[
        tuple[list[NodeMergeDict], list[AttributePropertyMergeDict | RelationshipPropertyMergeDict]], None
    ]:
        self._reset_caches()
        self._source_branch_name = diff.diff_branch_name
        self._target_branch_name = diff.base_branch_name
        self._cache_conflicted_cardinality_one_relationships(diff=diff)
        serialized_node_diffs = []
        serialized_property_diffs: list[AttributePropertyMergeDict | RelationshipPropertyMergeDict] = []
        for node in diff.nodes:
            # if there is a node-level conflict and the base branch version is selected
            # then we don't need to alter this node during the merge
            if node.conflict and node.conflict.selected_branch is ConflictSelection.BASE_BRANCH:
                continue
            node_action = self._get_action(action=node.action, conflict=node.conflict)
            if node_action is DiffAction.REMOVED:
                serialized_node_diffs.append(
                    NodeMergeDict(
                        uuid=node.uuid,
                        action=self._to_action_str(action=node_action),
                        attributes=[],
                        relationships=[],
                    )
                )
                continue
            serial_attr_diffs = []
            for attr_diff in node.attributes:
                serial_attr_diff, attribute_property_diff = self._serialize_attribute(
                    attribute_diff=attr_diff, node_uuid=node.uuid, node_kind=node.kind
                )
                if serial_attr_diff:
                    serial_attr_diffs.append(serial_attr_diff)
                serialized_property_diffs.append(attribute_property_diff)
            relationship_diffs: list[RelationshipMergeDict] = []
            for rel_diff in node.relationships:
                for relationship_element_diff in rel_diff.relationships:
                    element_diffs, relationship_property_diffs = self._serialize_relationship_element(
                        relationship_diff=relationship_element_diff,
                        relationship_identifier=rel_diff.identifier,
                        node_uuid=node.uuid,
                    )
                    relationship_diffs.extend(element_diffs)
                    serialized_property_diffs.extend(relationship_property_diffs)
            if node_action in (DiffAction.ADDED, DiffAction.REMOVED) or serial_attr_diffs or relationship_diffs:
                serialized_node_diffs.append(
                    NodeMergeDict(
                        uuid=node.uuid,
                        action=self._to_action_str(action=node_action),
                        attributes=serial_attr_diffs,
                        relationships=relationship_diffs,
                    )
                )
            if len(serialized_node_diffs) == self.max_batch_size:
                yield (serialized_node_diffs, serialized_property_diffs)
                serialized_node_diffs, serialized_property_diffs = [], []
        yield (serialized_node_diffs, serialized_property_diffs)

    def _get_property_actions_and_values(
        self, property_diff: EnrichedDiffProperty, python_value_type: type
    ) -> list[tuple[DiffAction, Primitives]]:
        action = property_diff.action
        new_value = property_diff.new_value
        if property_diff.conflict and property_diff.conflict.selected_branch is ConflictSelection.BASE_BRANCH:
            action = property_diff.conflict.base_branch_action
            if property_diff.conflict.base_branch_value:
                new_value = property_diff.conflict.base_branch_value
        actions = [action]
        if property_diff.action is DiffAction.UPDATED:
            actions = [DiffAction.ADDED, DiffAction.REMOVED]
        actions_and_values: list[tuple[DiffAction, Primitives]] = []
        for action in actions:
            if action not in (DiffAction.ADDED, DiffAction.REMOVED):
                continue
            if action is DiffAction.REMOVED and new_value == NULL_VALUE:
                actions_and_values.append((DiffAction.ADDED, NULL_VALUE))
                continue
            if action is DiffAction.ADDED:
                raw_value = new_value
            else:
                raw_value = property_diff.previous_value
            final_value = self._convert_property_value(
                property_type=property_diff.property_type, raw_value=raw_value, value_type=python_value_type
            )
            if final_value is not None:
                actions_and_values.append((action, final_value))
        return actions_and_values

    def _serialize_attribute(
        self, attribute_diff: EnrichedDiffAttribute, node_uuid: str, node_kind: str
    ) -> tuple[AttributeMergeDict | None, AttributePropertyMergeDict]:
        prop_dicts: list[PropertyMergeDict] = []
        python_type = self._get_property_type_for_attribute_value(
            schema_kind=node_kind, attribute_name=attribute_diff.name
        )
        for property_diff in attribute_diff.properties:
            actions_and_values = self._get_property_actions_and_values(
                property_diff=property_diff, python_value_type=python_type
            )
            for action, value in actions_and_values:
                # we only delete attributes when the whole attribute is deleted
                if action is DiffAction.REMOVED and attribute_diff.action is not DiffAction.REMOVED:
                    continue
                prop_dicts.append(
                    PropertyMergeDict(
                        property_type=property_diff.property_type.value,
                        action=self._to_action_str(action=action),
                        value=value,
                    )
                )
        attr_dict = None
        if attribute_diff.action in (DiffAction.ADDED, DiffAction.REMOVED):
            attr_dict = AttributeMergeDict(
                name=attribute_diff.name,
                action=self._to_action_str(action=attribute_diff.action),
            )
        attr_prop_dict = AttributePropertyMergeDict(
            node_uuid=node_uuid, attribute_name=attribute_diff.name, properties=prop_dicts
        )
        return attr_dict, attr_prop_dict

    def _get_default_property_merge_dicts(self, action: DiffAction) -> dict[DatabaseEdgeType, PropertyMergeDict]:
        # start with default values for IS_VISIBLE and IS_PROTECTED b/c we always want to update them during a merge
        return {
            DatabaseEdgeType.IS_VISIBLE: PropertyMergeDict(
                property_type=DatabaseEdgeType.IS_VISIBLE.value,
                action=self._to_action_str(action),
                value=None,
            ),
            DatabaseEdgeType.IS_PROTECTED: PropertyMergeDict(
                property_type=DatabaseEdgeType.IS_PROTECTED.value,
                action=self._to_action_str(action),
                value=None,
            ),
        }

    def _get_actions_and_peers(self, relationship_diff: EnrichedDiffSingleRelationship) -> list[tuple[DiffAction, str]]:
        is_related_prop = [p for p in relationship_diff.properties if p.property_type is DatabaseEdgeType.IS_RELATED][0]
        actions_and_values = self._get_property_actions_and_values(property_diff=is_related_prop, python_value_type=str)
        actions_and_peers: list[tuple[DiffAction, str]] = []
        for action, peer_id in actions_and_values:
            if action is DiffAction.ADDED:
                actions_and_peers.append((DiffAction.ADDED, str(peer_id)))
            elif action is DiffAction.REMOVED:
                actions_and_peers.append((DiffAction.REMOVED, str(peer_id)))

        conflict = relationship_diff.conflict
        if (
            conflict
            and conflict.selected_branch
            and conflict.selected_branch is ConflictSelection.DIFF_BRANCH
            and conflict.base_branch_value
            and conflict.base_branch_action in (DiffAction.ADDED, DiffAction.UPDATED)
        ):
            actions_and_peers.append((DiffAction.REMOVED, conflict.base_branch_value))
        return actions_and_peers

    def _serialize_relationship_element(
        self, relationship_diff: EnrichedDiffSingleRelationship, relationship_identifier: str, node_uuid: str
    ) -> tuple[list[RelationshipMergeDict], list[RelationshipPropertyMergeDict]]:
        # if there is a relationship-element conflict and we are keeping the base branch version
        # then we do not need to do anything special
        if relationship_diff.conflict and relationship_diff.conflict.selected_branch is ConflictSelection.BASE_BRANCH:
            return ([], [])
        relationship_dicts = []
        actions_and_peers = self._get_actions_and_peers(relationship_diff=relationship_diff)
        added_peer_ids = [peer_id for action, peer_id in actions_and_peers if action is DiffAction.ADDED]
        removed_peer_ids = [peer_id for action, peer_id in actions_and_peers if action is DiffAction.REMOVED]
        for action, peer_id in actions_and_peers:
            if (
                peer_id
                and (peer_id, relationship_identifier, node_uuid) not in self._conflicted_cardinality_one_relationships
            ):
                relationship_dicts.append(
                    RelationshipMergeDict(
                        peer_id=peer_id, name=relationship_identifier, action=self._to_action_str(action=action)
                    )
                )
        relationship_property_dicts = self._serialize_relationship_properties(
            node_uuid=node_uuid,
            relationship_identifier=relationship_identifier,
            relationship_diff_properties=relationship_diff.properties,
            added_peer_ids=added_peer_ids,
            removed_peer_ids=removed_peer_ids,
            unchanged_peer_id=relationship_diff.peer_id,
        )
        return relationship_dicts, relationship_property_dicts

    def _serialize_relationship_properties(
        self,
        node_uuid: str,
        relationship_identifier: str,
        relationship_diff_properties: set[EnrichedDiffProperty],
        added_peer_ids: list[str],
        removed_peer_ids: list[str],
        unchanged_peer_id: str,
    ) -> list[RelationshipPropertyMergeDict]:
        added_property_dicts = {}
        removed_property_dicts = {}
        if added_peer_ids:
            added_property_dicts = self._get_default_property_merge_dicts(action=DiffAction.ADDED)
        if removed_peer_ids:
            removed_property_dicts = self._get_default_property_merge_dicts(action=DiffAction.REMOVED)
        for property_diff in relationship_diff_properties:
            if property_diff.property_type is DatabaseEdgeType.IS_RELATED:
                # handled above
                continue
            python_value_type: type = str
            if property_diff.property_type in (DatabaseEdgeType.IS_VISIBLE, DatabaseEdgeType.IS_PROTECTED):
                python_value_type = bool
            actions_and_values = self._get_property_actions_and_values(
                property_diff=property_diff, python_value_type=python_value_type
            )
            for action, value in actions_and_values:
                property_dict = PropertyMergeDict(
                    property_type=property_diff.property_type.value,
                    action=self._to_action_str(action=action),
                    value=value,
                )
                if action is DiffAction.ADDED:
                    added_property_dicts[property_diff.property_type] = property_dict
                elif action is DiffAction.REMOVED:
                    removed_property_dicts[property_diff.property_type] = property_dict
        relationship_property_dicts = []
        peers_and_property_dicts: list[tuple[str, dict[DatabaseEdgeType, PropertyMergeDict]]] = []
        if added_property_dicts:
            peers_and_property_dicts += [
                (peer_id, added_property_dicts) for peer_id in (added_peer_ids or [unchanged_peer_id])
            ]
        if removed_property_dicts:
            peers_and_property_dicts += [
                (peer_id, removed_property_dicts) for peer_id in (removed_peer_ids or [unchanged_peer_id])
            ]
        for peer_id, property_dicts in peers_and_property_dicts:
            if (
                peer_id
                and property_dicts
                and (peer_id, relationship_identifier, node_uuid) not in self._conflicted_cardinality_one_relationships
            ):
                relationship_property_dicts.append(
                    RelationshipPropertyMergeDict(
                        node_uuid=node_uuid,
                        relationship_id=relationship_identifier,
                        peer_uuid=peer_id,
                        properties=list(property_dicts.values()),
                    )
                )
        return relationship_property_dicts
