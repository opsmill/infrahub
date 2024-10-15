from typing import AsyncGenerator

from infrahub.core.constants import DiffAction
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.schema.schema_branch import SchemaBranch
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
    def __init__(self, schema_branch: SchemaBranch, max_batch_size: int) -> None:
        self.schema_branch = schema_branch
        self.max_batch_size = max_batch_size
        self._relationship_id_cache: dict[tuple[str, str], str] = {}
        self._attribute_type_cache: dict[tuple[str, str], type] = {}

    def _reset_caches(self) -> None:
        self._relationship_id_cache = {}
        self._attribute_type_cache = {}

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

    def _get_relationship_identifier(self, schema_kind: str, relationship_name: str) -> str:
        cache_key = (schema_kind, relationship_name)
        if cache_key in self._relationship_id_cache:
            return self._relationship_id_cache[cache_key]
        node_schema = self.schema_branch.get(name=schema_kind, duplicate=False)
        relationship_schema = node_schema.get_relationship(name=relationship_name)
        relationship_identifier = relationship_schema.get_identifier()
        self._relationship_id_cache[cache_key] = relationship_identifier
        return relationship_identifier

    def _get_property_type_for_attribute_value(self, schema_kind: str, attribute_name: str) -> type:
        cache_key = (schema_kind, attribute_name)
        if cache_key in self._attribute_type_cache:
            return self._attribute_type_cache[cache_key]
        node_schema = self.schema_branch.get(name=schema_kind, duplicate=False)
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
        if raw_value is None:
            if property_type is DatabaseEdgeType.HAS_VALUE:
                return "NULL"
            return None
        # peer IDs are strings
        if property_type in (DatabaseEdgeType.HAS_OWNER, DatabaseEdgeType.HAS_SOURCE, DatabaseEdgeType.IS_RELATED):
            return raw_value
        # these are boolean
        if property_type in (DatabaseEdgeType.IS_VISIBLE, DatabaseEdgeType.IS_PROTECTED):
            return raw_value.lower() == "true"
        # this must be HAS_VALUE
        if value_type:
            return value_type(raw_value)
        return raw_value

    async def serialize_diff(
        self, diff: EnrichedDiffRoot
    ) -> AsyncGenerator[
        tuple[list[NodeMergeDict], list[AttributePropertyMergeDict | RelationshipPropertyMergeDict]], None
    ]:
        self._reset_caches()
        serialized_node_diffs = []
        serialized_property_diffs: list[AttributePropertyMergeDict | RelationshipPropertyMergeDict] = []
        for node in diff.nodes:
            node_action = self._get_action(action=node.action, conflict=node.conflict)
            attribute_diffs = []
            for attr_diff in node.attributes:
                attribute_diff, attribute_property_diff = self._serialize_attribute(
                    attribute_diff=attr_diff, node_uuid=node.uuid, node_kind=node.kind
                )
                if attribute_diff:
                    attribute_diffs.append(attribute_diff)
                serialized_property_diffs.append(attribute_property_diff)
            relationship_diffs = []
            for rel_diff in node.relationships:
                relationship_identifier = self._get_relationship_identifier(
                    schema_kind=node.kind, relationship_name=rel_diff.name
                )
                for relationship_element_diff in rel_diff.relationships:
                    element_diffs, relationship_property_diffs = self._serialize_relationship_element(
                        relationship_diff=relationship_element_diff,
                        relationship_identifier=relationship_identifier,
                        node_uuid=node.uuid,
                    )
                    relationship_diffs.extend(element_diffs)
                    serialized_property_diffs.extend(relationship_property_diffs)
            serialized_node_diffs.append(
                NodeMergeDict(
                    uuid=node.uuid,
                    action=self._to_action_str(action=node_action),
                    attributes=attribute_diffs,
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

    def _serialize_relationship_element(
        self, relationship_diff: EnrichedDiffSingleRelationship, relationship_identifier: str, node_uuid: str
    ) -> tuple[list[RelationshipMergeDict], list[RelationshipPropertyMergeDict]]:
        relationship_dicts = []
        # start with default values for IS_VISIBLE and IS_PROTECTED b/c we always want to update them during a merge
        added_property_dicts: dict[DatabaseEdgeType, PropertyMergeDict] = {
            DatabaseEdgeType.IS_VISIBLE: PropertyMergeDict(
                property_type=DatabaseEdgeType.IS_VISIBLE.value,
                action=self._to_action_str(DiffAction.ADDED),
                value=None,
            ),
            DatabaseEdgeType.IS_PROTECTED: PropertyMergeDict(
                property_type=DatabaseEdgeType.IS_PROTECTED.value,
                action=self._to_action_str(DiffAction.ADDED),
                value=None,
            ),
        }
        removed_property_dicts: dict[DatabaseEdgeType, PropertyMergeDict] = {
            DatabaseEdgeType.IS_VISIBLE: PropertyMergeDict(
                property_type=DatabaseEdgeType.IS_VISIBLE.value,
                action=self._to_action_str(DiffAction.REMOVED),
                value=None,
            ),
            DatabaseEdgeType.IS_PROTECTED: PropertyMergeDict(
                property_type=DatabaseEdgeType.IS_PROTECTED.value,
                action=self._to_action_str(DiffAction.REMOVED),
                value=None,
            ),
        }
        added_peer_id: str | None = None
        removed_peer_id: str | None = None
        for property_diff in relationship_diff.properties:
            python_value_type: type = str
            if property_diff.property_type in (DatabaseEdgeType.IS_VISIBLE, DatabaseEdgeType.IS_PROTECTED):
                python_value_type = bool
            actions_and_values = self._get_property_actions_and_values(
                property_diff=property_diff, python_value_type=python_value_type
            )
            if property_diff.property_type is DatabaseEdgeType.IS_RELATED:
                for action, value in actions_and_values:
                    peer_id = str(value)
                    if action is DiffAction.ADDED:
                        added_peer_id = peer_id
                    elif action is DiffAction.REMOVED:
                        removed_peer_id = peer_id
                    relationship_dicts.append(
                        RelationshipMergeDict(
                            peer_id=peer_id, name=relationship_identifier, action=self._to_action_str(action=action)
                        )
                    )
            else:
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
        if added_peer_id and added_property_dicts:
            relationship_property_dicts.append(
                RelationshipPropertyMergeDict(
                    node_uuid=node_uuid,
                    relationship_id=relationship_identifier,
                    peer_uuid=added_peer_id,
                    properties=list(added_property_dicts.values()),
                )
            )
        if removed_peer_id and removed_property_dicts:
            relationship_property_dicts.append(
                RelationshipPropertyMergeDict(
                    node_uuid=node_uuid,
                    relationship_id=relationship_identifier,
                    peer_uuid=removed_peer_id,
                    properties=list(removed_property_dicts.values()),
                )
            )
        return relationship_dicts, relationship_property_dicts
