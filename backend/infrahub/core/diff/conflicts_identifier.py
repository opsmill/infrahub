from infrahub.core.branch import Branch
from infrahub.core.constants import PathType, RelationshipCardinality
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.schema_manager import SchemaManager
from infrahub.core.timestamp import Timestamp

from .coordinator import DiffCoordinator
from .model.diff import BranchChanges, DataConflict, ModifiedPathType
from .model.path import (
    EnrichedDiffAttribute,
    EnrichedDiffNode,
    EnrichedDiffProperty,
    EnrichedDiffRelationship,
    EnrichedDiffSingleRelationship,
)


class ConflictsIdentifier:
    def __init__(
        self, diff_coordinator: DiffCoordinator, base_branch: Branch, diff_branch: Branch, schema_manager: SchemaManager
    ) -> None:
        self.base_branch = base_branch
        self.diff_branch = diff_branch
        self.diff_coordinator = diff_coordinator
        self.schema_manager = schema_manager

    async def get_conflicts(
        self,
        from_time: Timestamp | None = None,
        to_time: Timestamp | None = None,
    ) -> list[DataConflict]:
        from_time = from_time or Timestamp(self.diff_branch.created_at)
        to_time = to_time or Timestamp()
        base_diff_root = await self.diff_coordinator.get_diff(
            base_branch=self.base_branch, diff_branch=self.base_branch, from_time=from_time, to_time=to_time
        )
        branch_diff_root = await self.diff_coordinator.get_diff(
            base_branch=self.base_branch, diff_branch=self.diff_branch, from_time=from_time, to_time=to_time
        )

        conflicts = []
        base_node_map = {n.uuid: n for n in base_diff_root.nodes}
        branch_node_map = {n.uuid: n for n in branch_diff_root.nodes}
        common_node_uuids = set(base_node_map.keys()) & set(branch_node_map.keys())
        for node_uuid in common_node_uuids:
            base_node = base_node_map[node_uuid]
            branch_node = branch_node_map[node_uuid]
            conflicts.extend(self._build_node_conflicts(base_node=base_node, branch_node=branch_node))

        return conflicts

    def _build_node_conflicts(self, base_node: EnrichedDiffNode, branch_node: EnrichedDiffNode) -> list[DataConflict]:
        conflicts: list[DataConflict] = []
        if base_node.action != branch_node.action:
            conflicts.append(self._add_node_conflict(base_node=base_node, branch_node=branch_node))
        base_attribute_map = {a.name: a for a in base_node.attributes}
        branch_attribute_map = {a.name: a for a in branch_node.attributes}
        common_attribute_names = set(base_attribute_map.keys()) & set(branch_attribute_map.keys())
        for attr_name in common_attribute_names:
            base_attribute = base_attribute_map[attr_name]
            branch_attribute = branch_attribute_map[attr_name]
            conflicts.extend(
                self._build_attribute_conflicts(
                    branch_node=branch_node, base_attribute=base_attribute, branch_attribute=branch_attribute
                )
            )
        base_relationship_map = {r.name: r for r in base_node.relationships}
        branch_relationship_map = {r.name: r for r in branch_node.relationships}
        common_relationship_names = set(base_relationship_map.keys()) & set(branch_relationship_map.keys())
        for relationship_name in common_relationship_names:
            base_relationship = base_relationship_map[relationship_name]
            branch_relationship = branch_relationship_map[relationship_name]
            conflicts.extend(
                self._build_relationship_conflicts(
                    branch_node=branch_node,
                    base_relationship=base_relationship,
                    branch_relationship=branch_relationship,
                )
            )
        return conflicts

    def _add_node_conflict(self, base_node: EnrichedDiffNode, branch_node: EnrichedDiffNode) -> DataConflict:
        path = f"{ModifiedPathType.DATA.value}/{branch_node.uuid}"
        branch_changes = [
            BranchChanges(
                branch=self.base_branch.name,
                action=base_node.action,
            ),
            BranchChanges(
                branch=self.diff_branch.name,
                action=branch_node.action,
            ),
        ]
        return DataConflict(
            name="",
            type=ModifiedPathType.DATA.value,
            kind=branch_node.kind,
            id=branch_node.uuid,
            change_type=PathType.NODE.value,
            path=path,
            conflict_path=path,
            path_type=PathType.NODE,
            property_name=None,
            changes=branch_changes,
        )

    def _build_attribute_conflicts(
        self,
        branch_node: EnrichedDiffNode,
        base_attribute: EnrichedDiffAttribute,
        branch_attribute: EnrichedDiffAttribute,
    ) -> list[DataConflict]:
        conflicts = []
        base_property_map = {p.property_type: p for p in base_attribute.properties}
        branch_property_map = {p.property_type: p for p in branch_attribute.properties}
        common_property_types = set(base_property_map.keys()) & set(branch_property_map.keys())
        for property_type in common_property_types:
            base_property = base_property_map[property_type]
            branch_property = branch_property_map[property_type]
            if base_property.new_value != branch_property.new_value:
                conflict = self._add_property_conflict(
                    branch_node=branch_node,
                    branch_attribute=branch_attribute,
                    base_property=base_property,
                    branch_property=branch_property,
                )
                conflicts.append(conflict)
        return conflicts

    def _build_relationship_conflicts(
        self,
        branch_node: EnrichedDiffNode,
        base_relationship: EnrichedDiffRelationship,
        branch_relationship: EnrichedDiffRelationship,
    ) -> list[DataConflict]:
        conflicts: list[DataConflict] = []
        node_schema = self.schema_manager.get_node_schema(
            name=branch_node.kind, branch=self.diff_branch, duplicate=False
        )
        relationship_schema = node_schema.get_relationship(name=branch_relationship.name)
        is_cardinality_one = relationship_schema.cardinality is RelationshipCardinality.ONE
        if is_cardinality_one:
            base_element = next(iter(base_relationship.relationships))
            branch_element = next(iter(branch_relationship.relationships))
            conflicts.extend(
                self._add_relationship_peer_conflicts(
                    branch_node=branch_node,
                    branch_relationship=branch_relationship,
                    base_element=base_element,
                    branch_element=branch_element,
                )
            )

        # base_peer_id_map = {element.peer_id: element for element in base_relationship.relationships}
        # branch_peer_id_map = {element.peer_id: element for element in branch_relationship.relationships}
        # common_peer_ids = set(base_peer_id_map.keys()) & set(branch_peer_id_map.keys())

        return conflicts

    def _add_relationship_peer_conflicts(
        self,
        branch_node: EnrichedDiffNode,
        branch_relationship: EnrichedDiffRelationship,
        base_element: EnrichedDiffSingleRelationship,
        branch_element: EnrichedDiffSingleRelationship,
    ) -> list[DataConflict]:
        base_peer_property = base_element.get_property(property_type=DatabaseEdgeType.IS_RELATED)
        branch_peer_property = branch_element.get_property(property_type=DatabaseEdgeType.IS_RELATED)
        if base_peer_property.new_value == branch_peer_property.new_value:
            return []

        base_path = f"{ModifiedPathType.DATA.value}/{branch_node.uuid}/{branch_relationship.name}/peer"
        branch_changes = [
            BranchChanges(
                branch=self.base_branch.name,
                action=base_peer_property.action,
                previous=base_peer_property.previous_value,
                new=base_peer_property.new_value,
            ),
            BranchChanges(
                branch=self.diff_branch.name,
                action=branch_peer_property.action,
                previous=branch_peer_property.previous_value,
                new=branch_peer_property.new_value,
            ),
        ]

        data_conflicts = []
        for element in (base_element, branch_element):
            data_conflicts.append(
                DataConflict(
                    name=branch_relationship.name,
                    type=ModifiedPathType.DATA.value,
                    id=branch_node.uuid,
                    kind=branch_node.kind,
                    change_type=f"{PathType.RELATIONSHIP_ONE.value}_value",
                    path=base_path,
                    conflict_path=f"{base_path}/{element.peer_id}",
                    path_type=PathType.RELATIONSHIP_ONE,
                    property_name=None,
                    changes=branch_changes,
                )
            )
        return data_conflicts

    def _add_property_conflict(
        self,
        branch_node: EnrichedDiffNode,
        branch_attribute: EnrichedDiffAttribute,
        base_property: EnrichedDiffProperty,
        branch_property: EnrichedDiffProperty,
    ) -> DataConflict:
        change_type = PathType.ATTRIBUTE.value
        is_value_diff = branch_property.property_type == DatabaseEdgeType.HAS_VALUE
        if is_value_diff:
            change_type += "_value"
        else:
            change_type += "_property"
        branch_changes = [
            BranchChanges(
                branch=self.base_branch.name,
                action=base_property.action,
                previous=base_property.previous_value,
                new=base_property.new_value,
            ),
            BranchChanges(
                branch=self.diff_branch.name,
                action=branch_property.action,
                previous=branch_property.previous_value,
                new=branch_property.new_value,
            ),
        ]
        path = f"{ModifiedPathType.DATA.value}/{branch_node.uuid}/{branch_attribute.name}/"
        if is_value_diff:
            path += "value"
        else:
            path += f"property/{branch_property.property_type.value}"
        return DataConflict(
            name=branch_attribute.name,
            type=ModifiedPathType.DATA.value,
            id=branch_node.uuid,
            kind=branch_node.kind,
            change_type=change_type,
            path=path,
            conflict_path=path,
            path_type=PathType.ATTRIBUTE,
            property_name=branch_property.property_type.value,
            changes=branch_changes,
        )
