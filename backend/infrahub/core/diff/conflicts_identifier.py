from infrahub.core.branch import Branch
from infrahub.core.constants import PathType
from infrahub.core.timestamp import Timestamp

from .coordinator import DiffCoordinator
from .model.diff import BranchChanges, DataConflict, ModifiedPathType
from .model.path import EnrichedDiffAttribute, EnrichedDiffNode, EnrichedDiffProperty


class ConflictsIdentifier:
    def __init__(self, diff_coordinator: DiffCoordinator, base_branch: Branch, diff_branch: Branch) -> None:
        self.base_branch = base_branch
        self.diff_branch = diff_branch
        self.diff_coordinator = diff_coordinator

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
        if not common_attribute_names:
            return conflicts
        for attr_name in common_attribute_names:
            base_attribute = base_attribute_map[attr_name]
            branch_attribute = branch_attribute_map[attr_name]
            conflicts.extend(
                self._build_attribute_conflicts(
                    branch_node=branch_node, base_attribute=base_attribute, branch_attribute=branch_attribute
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
            type=ModifiedPathType.DATA,
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
            conflict = self._add_property_conflict(
                branch_node=branch_node,
                branch_attribute=branch_attribute,
                base_property=base_property,
                branch_property=branch_property,
            )
            if conflict:
                conflicts.append(conflict)
        return conflicts

    def _add_property_conflict(
        self,
        branch_node: EnrichedDiffNode,
        branch_attribute: EnrichedDiffAttribute,
        base_property: EnrichedDiffProperty,
        branch_property: EnrichedDiffProperty,
    ) -> DataConflict | None:
        if base_property.new_value == branch_property.new_value:
            return None
        change_type = PathType.ATTRIBUTE.value
        is_value_diff = branch_property.property_type == "HAS_VALUE"
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
            path += f"property/{branch_property.property_type}"
        return DataConflict(
            name=branch_attribute.name,
            type=ModifiedPathType.DATA.value,
            id=branch_node.uuid,
            kind=branch_node.kind,
            change_type=change_type,
            path=path,
            conflict_path=path,
            path_type=PathType.ATTRIBUTE,
            property_name=branch_property.property_type,
            changes=branch_changes,
        )
