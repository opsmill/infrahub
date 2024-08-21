from infrahub.core.constants import PathType, RelationshipCardinality
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.model.diff import BranchChanges, DataConflict, ModifiedPathType
from infrahub.database import InfrahubDatabase

from .model.path import (
    EnrichedDiffAttribute,
    EnrichedDiffNode,
    EnrichedDiffProperty,
    EnrichedDiffRelationship,
    EnrichedDiffRoot,
    EnrichedDiffSingleRelationship,
)


class DiffConflictsExtractor:
    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db
        self._base_branch_name: str | None = None
        self._diff_branch_name: str | None = None
        self._conflict_ids: set[str] | None = None

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

    @property
    def conflict_ids(self) -> set[str] | None:
        return self._conflict_ids

    async def get_data_conflicts(
        self, enriched_diff_root: EnrichedDiffRoot, conflict_ids: set[str] | None = None
    ) -> list[DataConflict]:
        self._base_branch_name = enriched_diff_root.base_branch_name
        self._diff_branch_name = enriched_diff_root.diff_branch_name
        self._conflict_ids = conflict_ids
        conflicts: list[DataConflict] = []
        for node in enriched_diff_root.nodes:
            conflicts.extend(self._build_node_conflicts(diff_node=node))
        return conflicts

    def _build_node_conflicts(self, diff_node: EnrichedDiffNode) -> list[DataConflict]:
        conflicts: list[DataConflict] = []
        node_conflict = self._get_node_conflict(diff_node=diff_node)
        if node_conflict:
            conflicts.append(node_conflict)
        for diff_attribute in diff_node.attributes:
            conflicts.extend(self._build_attribute_conflicts(diff_node=diff_node, diff_attribute=diff_attribute))
        for diff_relationship in diff_node.relationships:
            conflicts.extend(
                self._build_relationship_conflicts(
                    diff_node=diff_node,
                    diff_relationship=diff_relationship,
                )
            )
        return conflicts

    def _get_node_conflict(self, diff_node: EnrichedDiffNode) -> DataConflict | None:
        if not diff_node.conflict:
            return None
        if self.conflict_ids and diff_node.conflict.uuid not in self.conflict_ids:
            return None
        path = f"{ModifiedPathType.DATA.value}/{diff_node.uuid}"
        branch_changes = [
            BranchChanges(
                branch=self.base_branch_name,
                action=diff_node.conflict.base_branch_action,
            ),
            BranchChanges(
                branch=self.diff_branch_name,
                action=diff_node.conflict.diff_branch_action,
            ),
        ]
        return DataConflict(
            name="",
            type=ModifiedPathType.DATA.value,
            kind=diff_node.kind,
            id=diff_node.uuid,
            change_type=PathType.NODE.value,
            path=path,
            conflict_path=path,
            path_type=PathType.NODE,
            property_name=None,
            changes=branch_changes,
            conflict_id=diff_node.conflict.uuid,
        )

    def _build_attribute_conflicts(
        self,
        diff_node: EnrichedDiffNode,
        diff_attribute: EnrichedDiffAttribute,
    ) -> list[DataConflict]:
        conflicts: list[DataConflict] = []
        for diff_property in diff_attribute.properties:
            property_conflict = self._get_property_conflict(
                diff_node=diff_node,
                diff_property=diff_property,
                parent_name=diff_attribute.name,
                path_type=PathType.ATTRIBUTE,
            )
            if property_conflict:
                conflicts.append(property_conflict)
        return conflicts

    def _build_relationship_conflicts(
        self,
        diff_node: EnrichedDiffNode,
        diff_relationship: EnrichedDiffRelationship,
    ) -> list[DataConflict]:
        conflicts: list[DataConflict] = []
        if not diff_relationship.relationships:
            return conflicts
        node_schema = self.db.schema.get(name=diff_node.kind, branch=self.diff_branch_name, duplicate=False)
        relationship_schema = node_schema.get_relationship(name=diff_relationship.name)
        is_cardinality_one = relationship_schema.cardinality is RelationshipCardinality.ONE
        for diff_element in diff_relationship.relationships:
            conflicts.extend(
                self._add_relationship_conflicts_for_one_peer(
                    diff_node=diff_node,
                    diff_relationship=diff_relationship,
                    diff_element=diff_element,
                    is_cardinality_one=is_cardinality_one,
                )
            )
        return conflicts

    def _add_relationship_conflicts_for_one_peer(
        self,
        diff_node: EnrichedDiffNode,
        diff_relationship: EnrichedDiffRelationship,
        diff_element: EnrichedDiffSingleRelationship,
        is_cardinality_one: bool,
    ) -> list[DataConflict]:
        conflicts: list[DataConflict] = []
        if is_cardinality_one:
            path_type = PathType.RELATIONSHIP_ONE
        else:
            path_type = PathType.RELATIONSHIP_MANY
        peer_conflict = self._get_peer_conflict(
            diff_node=diff_node,
            diff_element=diff_element,
            relationship_name=diff_relationship.name,
            path_type=path_type,
        )
        if peer_conflict:
            conflicts.append(peer_conflict)
        for diff_property in diff_element.properties:
            property_conflict = self._get_property_conflict(
                diff_node=diff_node,
                diff_property=diff_property,
                parent_name=diff_relationship.name,
                path_type=path_type,
            )
            if property_conflict:
                conflicts.append(property_conflict)
        return conflicts

    def _get_peer_conflict(
        self,
        diff_element: EnrichedDiffSingleRelationship,
        diff_node: EnrichedDiffNode,
        relationship_name: str,
        path_type: PathType,
    ) -> DataConflict | None:
        if not diff_element.conflict:
            return None
        if self.conflict_ids and diff_element.conflict not in self.conflict_ids:
            return None
        try:
            peer_property = diff_element.get_property(property_type=DatabaseEdgeType.IS_RELATED)
            previous_peer_id = peer_property.previous_value
        except ValueError:
            previous_peer_id = None
        branch_changes = [
            BranchChanges(
                branch=self.base_branch_name,
                action=diff_element.conflict.base_branch_action,
                previous=previous_peer_id,
                new=diff_element.conflict.base_branch_value,
            ),
            BranchChanges(
                branch=self.diff_branch_name,
                action=diff_element.conflict.diff_branch_action,
                previous=previous_peer_id,
                new=diff_element.conflict.diff_branch_value,
            ),
        ]
        return DataConflict(
            name=relationship_name,
            type=ModifiedPathType.DATA.value,
            id=diff_node.uuid,
            kind=diff_node.kind,
            change_type=f"{path_type.value}_value",
            path=diff_element.path_identifier,
            conflict_path=diff_element.path_identifier,
            path_type=path_type,
            property_name=None,
            changes=branch_changes,
            conflict_id=diff_element.conflict.uuid,
        )

    def _get_property_conflict(
        self,
        diff_node: EnrichedDiffNode,
        diff_property: EnrichedDiffProperty,
        parent_name: str,
        path_type: PathType,
    ) -> DataConflict | None:
        if not diff_property.conflict:
            return None
        change_type = PathType.ATTRIBUTE.value
        if diff_property.property_type in (DatabaseEdgeType.HAS_VALUE, DatabaseEdgeType.IS_RELATED):
            change_type = f"{path_type.value}_value"
        else:
            change_type = f"{path_type.value}_property"
        branch_changes = [
            BranchChanges(
                branch=self.base_branch_name,
                action=diff_property.conflict.base_branch_action,
                previous=diff_property.previous_value,
                new=diff_property.conflict.base_branch_value,
            ),
            BranchChanges(
                branch=self.diff_branch_name,
                action=diff_property.conflict.diff_branch_action,
                previous=diff_property.previous_value,
                new=diff_property.conflict.diff_branch_value,
            ),
        ]
        return DataConflict(
            name=parent_name,
            type=ModifiedPathType.DATA.value,
            id=diff_node.uuid,
            kind=diff_node.kind,
            change_type=change_type,
            path=diff_property.path_identifier,
            conflict_path=diff_property.path_identifier,
            path_type=path_type,
            property_name=None
            if diff_property.property_type is DatabaseEdgeType.IS_RELATED
            else diff_property.property_type.value,
            changes=branch_changes,
            conflict_id=diff_property.conflict.uuid,
        )
