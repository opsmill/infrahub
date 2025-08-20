from uuid import uuid4

from infrahub.core.constants import NULL_VALUE, DiffAction, RelationshipCardinality
from infrahub.core.constants.database import DatabaseEdgeType

from .model.path import (
    EnrichedDiffAttribute,
    EnrichedDiffConflict,
    EnrichedDiffNode,
    EnrichedDiffProperty,
    EnrichedDiffRelationship,
    EnrichedDiffRoot,
    EnrichedDiffSingleRelationship,
)


class ConflictsEnricher:
    def __init__(self) -> None:
        self._base_branch_name: str | None = None
        self._diff_branch_name: str | None = None

    @property
    def base_branch_name(self) -> str:
        if not self._base_branch_name:
            raise RuntimeError("could not identify base branch")
        return self._base_branch_name

    @property
    def diff_branch_name(self) -> str:
        if not self._diff_branch_name:
            raise RuntimeError("could not identify diff branch")
        return self._diff_branch_name

    async def add_conflicts_to_branch_diff(
        self, base_diff_root: EnrichedDiffRoot, branch_diff_root: EnrichedDiffRoot
    ) -> None:
        self._base_branch_name = branch_diff_root.base_branch_name
        self._diff_branch_name = branch_diff_root.diff_branch_name

        base_node_map = {n.uuid: n for n in base_diff_root.nodes}
        branch_node_map = {n.uuid: n for n in branch_diff_root.nodes}
        branch_node_map_uuids = set(branch_node_map.keys())
        common_node_uuids = set(base_node_map.keys()) & branch_node_map_uuids
        for node_uuid in common_node_uuids:
            base_node = base_node_map[node_uuid]
            branch_node = branch_node_map[node_uuid]
            self._add_node_conflicts(base_node=base_node, branch_node=branch_node)
        # remove conflicts from branch nodes that have been manually corrected on the base branch
        for branch_only_node_uuid in branch_node_map_uuids - common_node_uuids:
            branch_node = branch_node_map[branch_only_node_uuid]
            branch_node.clear_conflicts()

    def _add_node_conflicts(self, base_node: EnrichedDiffNode, branch_node: EnrichedDiffNode) -> None:
        if base_node.action != branch_node.action and DiffAction.UNCHANGED not in {
            base_node.action,
            branch_node.action,
        }:
            self._add_node_conflict(base_node=base_node, branch_node=branch_node)
        elif branch_node.conflict:
            branch_node.conflict = None
        # adding attr/rel conflicts when there is an unresolvable node-level conflict is pointless
        if branch_node.conflict and branch_node.conflict.resolvable is False:
            return
        base_attribute_map = {a.name: a for a in base_node.attributes}
        branch_attribute_map = {a.name: a for a in branch_node.attributes}
        common_attribute_names = set(base_attribute_map.keys()) & set(branch_attribute_map.keys())
        for branch_attribute in branch_node.attributes:
            if branch_attribute.name in common_attribute_names:
                base_attribute = base_attribute_map[branch_attribute.name]
                self._add_attribute_conflicts(base_attribute=base_attribute, branch_attribute=branch_attribute)
            else:
                branch_attribute.clear_conflicts()
        base_relationship_map = {r.name: r for r in base_node.relationships}
        branch_relationship_map = {r.name: r for r in branch_node.relationships}
        common_relationship_names = set(base_relationship_map.keys()) & set(branch_relationship_map.keys())
        for branch_relationship in branch_node.relationships:
            if branch_relationship.name in common_relationship_names:
                base_relationship = base_relationship_map[branch_relationship.name]
                self._add_relationship_conflicts(
                    base_relationship=base_relationship,
                    branch_relationship=branch_relationship,
                )
            else:
                branch_relationship.clear_conflicts()

    def _add_node_conflict(self, base_node: EnrichedDiffNode, branch_node: EnrichedDiffNode) -> None:
        if branch_node.conflict:
            conflict_uuid = branch_node.conflict.uuid
            selected_branch = branch_node.conflict.selected_branch
        else:
            conflict_uuid = str(uuid4())
            selected_branch = None
        resolvable = True
        # this condition should always be true, but it's good to be explicit
        if DiffAction.REMOVED in [base_node.action, branch_node.action]:
            resolvable = False
        branch_node.conflict = EnrichedDiffConflict(
            uuid=conflict_uuid,
            base_branch_action=base_node.action,
            base_branch_value=None,
            base_branch_changed_at=base_node.changed_at,
            diff_branch_action=branch_node.action,
            diff_branch_value=None,
            diff_branch_changed_at=branch_node.changed_at,
            selected_branch=selected_branch,
            resolvable=resolvable,
        )

    def _add_attribute_conflicts(
        self,
        base_attribute: EnrichedDiffAttribute,
        branch_attribute: EnrichedDiffAttribute,
    ) -> None:
        base_property_map = {p.property_type: p for p in base_attribute.properties}
        branch_property_map = {p.property_type: p for p in branch_attribute.properties}
        common_property_types = set(base_property_map.keys()) & set(branch_property_map.keys())
        for branch_property in branch_attribute.properties:
            if branch_property.property_type not in common_property_types:
                branch_property.conflict = None
                continue
            base_property = base_property_map[branch_property.property_type]
            property_actions = {branch_property.action, base_property.action}
            if DiffAction.UNCHANGED in property_actions:
                branch_property.conflict = None
                continue
            same_value = self._have_same_value(base_property=base_property, branch_property=branch_property)
            if same_value:
                branch_property.conflict = None
                continue
            self._add_property_conflict(
                base_property=base_property,
                branch_property=branch_property,
            )

    def _add_relationship_conflicts(
        self,
        base_relationship: EnrichedDiffRelationship,
        branch_relationship: EnrichedDiffRelationship,
    ) -> None:
        is_cardinality_one = branch_relationship.cardinality is RelationshipCardinality.ONE
        if is_cardinality_one:
            if not base_relationship.relationships or not branch_relationship.relationships:
                branch_relationship.clear_conflicts()
                return
            base_element = next(iter(base_relationship.relationships))
            branch_element = next(iter(branch_relationship.relationships))
            self._add_relationship_conflicts_for_one_peer(
                base_element=base_element,
                branch_element=branch_element,
                is_cardinality_one=is_cardinality_one,
            )
            return
        base_peer_id_map = {element.peer_id: element for element in base_relationship.relationships}
        branch_peer_id_map = {element.peer_id: element for element in branch_relationship.relationships}
        common_peer_ids = set(base_peer_id_map.keys()) & set(branch_peer_id_map.keys())
        for branch_element in branch_relationship.relationships:
            if branch_element.peer_id not in common_peer_ids:
                branch_element.clear_conflicts()
                continue
            base_element = base_peer_id_map[branch_element.peer_id]
            self._add_relationship_conflicts_for_one_peer(
                base_element=base_element,
                branch_element=branch_element,
                is_cardinality_one=is_cardinality_one,
            )

    def _add_relationship_conflicts_for_one_peer(
        self,
        base_element: EnrichedDiffSingleRelationship,
        branch_element: EnrichedDiffSingleRelationship,
        is_cardinality_one: bool,
    ) -> None:
        base_properties_by_type = {p.property_type: p for p in base_element.properties}
        branch_properties_by_type = {p.property_type: p for p in branch_element.properties}
        common_property_types = set(base_properties_by_type.keys()) & set(branch_properties_by_type.keys())
        for branch_property in branch_element.properties:
            if branch_property.property_type not in common_property_types:
                branch_property.conflict = None
                continue
            base_property = base_properties_by_type[branch_property.property_type]
            includes_unchanged = DiffAction.UNCHANGED in {branch_property.action, base_property.action}
            same_value = self._have_same_value(base_property=base_property, branch_property=branch_property)
            # special handling for cardinality-one peer ID conflict
            if branch_property.property_type is DatabaseEdgeType.IS_RELATED and is_cardinality_one:
                if same_value or includes_unchanged:
                    branch_element.conflict = None
                    branch_property.conflict = None
                    continue
                if branch_element.conflict:
                    conflict_uuid = branch_element.conflict.uuid
                    selected_branch = branch_element.conflict.selected_branch
                else:
                    conflict_uuid = str(uuid4())
                    selected_branch = None
                conflict = EnrichedDiffConflict(
                    uuid=conflict_uuid,
                    base_branch_action=base_element.action,
                    base_branch_value=base_property.new_value,
                    base_branch_changed_at=base_property.changed_at,
                    diff_branch_action=branch_element.action,
                    diff_branch_value=branch_property.new_value,
                    diff_branch_changed_at=branch_property.changed_at,
                    selected_branch=selected_branch,
                )
                branch_element.conflict = conflict
                continue
            if same_value or includes_unchanged:
                branch_property.conflict = None
                continue
            if branch_property.conflict:
                conflict_uuid = branch_property.conflict.uuid
                selected_branch = branch_property.conflict.selected_branch
            else:
                conflict_uuid = str(uuid4())
                selected_branch = None
            branch_property.conflict = EnrichedDiffConflict(
                uuid=conflict_uuid,
                base_branch_action=base_property.action,
                base_branch_value=base_property.new_value,
                base_branch_changed_at=base_property.changed_at,
                diff_branch_action=branch_property.action,
                diff_branch_value=branch_property.new_value,
                diff_branch_changed_at=branch_property.changed_at,
                selected_branch=selected_branch,
            )

    def _add_property_conflict(
        self,
        base_property: EnrichedDiffProperty,
        branch_property: EnrichedDiffProperty,
    ) -> None:
        if branch_property.conflict:
            conflict_uuid = branch_property.conflict.uuid
            selected_branch = branch_property.conflict.selected_branch
        else:
            conflict_uuid = str(uuid4())
            selected_branch = None
        branch_property.conflict = EnrichedDiffConflict(
            uuid=conflict_uuid,
            base_branch_action=base_property.action,
            base_branch_value=base_property.new_value,
            base_branch_changed_at=base_property.changed_at,
            diff_branch_action=branch_property.action,
            diff_branch_value=branch_property.new_value,
            diff_branch_changed_at=branch_property.changed_at,
            selected_branch=selected_branch,
        )

    def _have_same_value(self, base_property: EnrichedDiffProperty, branch_property: EnrichedDiffProperty) -> bool:
        if base_property.new_value == branch_property.new_value:
            return True
        if {base_property.new_value, branch_property.new_value} <= {NULL_VALUE, None}:
            return True
        if (
            base_property.action is DiffAction.UNCHANGED
            and base_property.previous_value == branch_property.previous_value
        ):
            return True
        return False
