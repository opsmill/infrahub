from typing import AsyncGenerator

from infrahub.core.constants import DiffAction
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.schema.schema_branch import SchemaBranch

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


class DiffMergeSerializer:
    def __init__(self, schema_branch: SchemaBranch, max_batch_size: int) -> None:
        self.schema_branch = schema_branch
        self.max_batch_size = max_batch_size
        self._relationship_id_cache: dict[tuple[str, str], str] = {}

    def _reset_caches(self) -> None:
        self._relationship_id_cache = {}

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

    def _get_relationship_identifier(self, schema_kind_str: str, relationship_name: str) -> str:
        cache_key = (schema_kind_str, relationship_name)
        if cache_key in self._relationship_id_cache:
            return self._relationship_id_cache[cache_key]
        node_schema = self.schema_branch.get(name=schema_kind_str, duplicate=False)
        relationship_schema = node_schema.get_relationship(name=relationship_name)
        relationship_identifier = relationship_schema.get_identifier()
        self._relationship_id_cache[cache_key] = relationship_identifier
        return relationship_identifier

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
                    attribute_diff=attr_diff, node_uuid=node.uuid
                )
                attribute_diffs.append(attribute_diff)
                serialized_property_diffs.append(attribute_property_diff)
            relationship_diffs = []
            for rel_diff in node.relationships:
                relationship_identifier = self._get_relationship_identifier(
                    schema_kind_str=node.kind, relationship_name=rel_diff.name
                )
                for relationship_element_diff in rel_diff.relationships:
                    element_diffs, relationship_property_diffs = self._serialize_relationship_element(
                        relationship_diff=relationship_element_diff, relationship_identifier=relationship_identifier
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
        self, property_diff: EnrichedDiffProperty
    ) -> list[tuple[DiffAction, str | int | float | bool]]:
        action = property_diff.action
        new_value = property_diff.new_value
        if property_diff.conflict and property_diff.conflict.selected_branch is ConflictSelection.BASE_BRANCH:
            action = property_diff.conflict.base_branch_action
            if property_diff.conflict.base_branch_value:
                new_value = property_diff.conflict.base_branch_value
        actions = [action]
        if property_diff.action is DiffAction.UPDATED:
            actions = [DiffAction.ADDED, DiffAction.REMOVED]
        actions_and_values: list[tuple[DiffAction, str | int | float | bool]] = []
        for action in actions:
            if action is DiffAction.ADDED and new_value:
                actions_and_values.append((action, new_value))
            elif action is DiffAction.REMOVED and property_diff.previous_value:
                actions_and_values.append((action, property_diff.previous_value))
        return actions_and_values

    def _serialize_attribute(
        self, attribute_diff: EnrichedDiffAttribute, node_uuid: str
    ) -> tuple[AttributeMergeDict, AttributePropertyMergeDict]:
        prop_dicts: list[PropertyMergeDict] = []
        for property_diff in attribute_diff.properties:
            actions_and_values = self._get_property_actions_and_values(property_diff=property_diff)
            for action, value in actions_and_values:
                prop_dicts.append(
                    PropertyMergeDict(
                        property_type=property_diff.property_type.value,
                        action=self._to_action_str(action=action),
                        value=value,
                        is_peer_id=property_diff.property_type
                        in (DatabaseEdgeType.HAS_OWNER, DatabaseEdgeType.HAS_SOURCE),
                    )
                )
        attr_dict = AttributeMergeDict(
            name=attribute_diff.name,
            action=self._to_action_str(action=attribute_diff.action),
        )
        attr_prop_dict = AttributePropertyMergeDict(
            node_uuid=node_uuid, attribute_name=attribute_diff.name, properties=prop_dicts
        )
        return attr_dict, attr_prop_dict

    def _serialize_relationship_element(
        self, relationship_diff: EnrichedDiffSingleRelationship, relationship_identifier: str
    ) -> tuple[list[RelationshipMergeDict], list[RelationshipPropertyMergeDict]]:
        relationship_dicts = []
        for property_diff in relationship_diff.properties:
            if property_diff.property_type is not DatabaseEdgeType.IS_RELATED:
                continue
            actions_and_values = self._get_property_actions_and_values(property_diff=property_diff)

            for action, value in actions_and_values:
                relationship_dicts.append(
                    RelationshipMergeDict(
                        peer_id=str(value), name=relationship_identifier, action=self._to_action_str(action=action)
                    )
                )
        return relationship_dicts, []
