from infrahub.core.constants import DiffAction
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.schema.schema_branch import SchemaBranch

from ..model.path import (
    ConflictSelection,
    EnrichedDiffAttribute,
    EnrichedDiffConflict,
    EnrichedDiffRoot,
    EnrichedDiffSingleRelationship,
)
from .model import AttributeMergeDict, NodeMergeDict, RelationshipMergeDict


class DiffMergeSerializer:
    def __init__(self, schema_branch: SchemaBranch) -> None:
        self.schema_branch = schema_branch
        self._relationship_id_cache: dict[tuple[str, str], str] = {}

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

    async def serialize(self, diff: EnrichedDiffRoot) -> list[NodeMergeDict]:
        serialized_node_diffs = []
        for node in diff.nodes:
            node_action = self._get_action(action=node.action, conflict=node.conflict)
            attribute_diffs = [self._serialize_attribute(attribute_diff=attr_diff) for attr_diff in node.attributes]
            relationship_diffs = []
            for rel_diff in node.relationships:
                relationship_identifier = self._get_relationship_identifier(
                    schema_kind_str=node.kind, relationship_name=rel_diff.name
                )
                for relationship_element_diff in rel_diff.relationships:
                    relationship_diffs.extend(
                        self._serialize_relationship_element(
                            relationship_diff=relationship_element_diff, relationship_identifier=relationship_identifier
                        )
                    )
            serialized_node_diffs.append(
                NodeMergeDict(
                    uuid=node.uuid,
                    action=self._to_action_str(action=node_action),
                    attributes=attribute_diffs,
                    relationships=relationship_diffs,
                )
            )
        return serialized_node_diffs

    def _serialize_attribute(self, attribute_diff: EnrichedDiffAttribute) -> AttributeMergeDict:
        return AttributeMergeDict(
            name=attribute_diff.name,
            action=self._to_action_str(action=attribute_diff.action),
        )

    def _serialize_relationship_element(
        self, relationship_diff: EnrichedDiffSingleRelationship, relationship_identifier: str
    ) -> list[RelationshipMergeDict]:
        relationship_dicts = []
        for property_diff in relationship_diff.properties:
            if property_diff.property_type is not DatabaseEdgeType.IS_RELATED:
                continue
            action = property_diff.action
            new_value = relationship_diff.peer_id
            if property_diff.conflict and property_diff.conflict.selected_branch is ConflictSelection.BASE_BRANCH:
                action = property_diff.conflict.base_branch_action
                if property_diff.conflict.base_branch_value:
                    new_value = property_diff.conflict.base_branch_value
            actions = [action]
            if property_diff.action is DiffAction.UPDATED:
                actions = [DiffAction.ADDED, DiffAction.REMOVED]
            actions_and_values: list[tuple[DiffAction, str]] = []
            for action in actions:
                if action is DiffAction.ADDED:
                    actions_and_values.append((action, new_value))
                elif action is DiffAction.REMOVED and property_diff.previous_value:
                    actions_and_values.append((action, property_diff.previous_value))

        for action, value in actions_and_values:
            relationship_dicts.append(
                RelationshipMergeDict(
                    peer_id=value, name=relationship_identifier, action=self._to_action_str(action=action)
                )
            )
        return relationship_dicts
