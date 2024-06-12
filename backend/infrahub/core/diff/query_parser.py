from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from infrahub.core.constants import DiffAction, RelationshipCardinality, RelationshipStatus
from infrahub.core.timestamp import Timestamp

from .model.path import (
    DatabasePath,
    DiffAttribute,
    DiffNode,
    DiffProperty,
    DiffRoot,
    DiffValue,
)

if TYPE_CHECKING:
    from infrahub.core.query.diff import DiffAllPathsQuery
    from infrahub.core.schema_manager import SchemaManager


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
        self._diff_root_by_branch: dict[str, DiffRoot] = {}

    def get_branches(self) -> set[str]:
        return set(self._diff_root_by_branch.keys())

    def get_diff_root_for_branch(self, branch: str) -> Optional[DiffRoot]:
        return self._diff_root_by_branch.get(branch)

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

    def _parse_path(self, database_path: DatabasePath) -> None:
        diff_root = self._get_diff_root(database_path=database_path)
        diff_node = self._get_diff_node(database_path=database_path, diff_root=diff_root)
        self._update_attribute_level(database_path=database_path, diff_node=diff_node)

    def _get_diff_root(self, database_path: DatabasePath) -> DiffRoot:
        branch = database_path.deepest_branch
        if branch not in self._diff_root_by_branch:
            self._diff_root_by_branch[branch] = DiffRoot(uuid=database_path.root_id, branch=branch)
        return self._diff_root_by_branch[branch]

    def _get_diff_action(self, changed_at: Timestamp, edge_status: RelationshipStatus) -> DiffAction:
        if changed_at >= self.from_time:
            if edge_status == RelationshipStatus.DELETED:
                return DiffAction.REMOVED
            return DiffAction.ADDED
        return DiffAction.UPDATED

    def _get_diff_node(self, database_path: DatabasePath, diff_root: DiffRoot) -> DiffNode:
        node_id = database_path.node_id
        if node_id not in diff_root.nodes_by_id:
            changed_at = database_path.node_changed_at
            action = DiffAction.UPDATED
            if changed_at >= self.from_time:
                if database_path.node_status is RelationshipStatus.DELETED:
                    action = DiffAction.REMOVED
                action = DiffAction.ADDED
            diff_root.nodes_by_id[node_id] = DiffNode(
                uuid=node_id, kind=database_path.node_kind, changed_at=changed_at, action=action
            )
        return diff_root.nodes_by_id[node_id]

    def _update_attribute_level(self, database_path: DatabasePath, diff_node: DiffNode) -> None:
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
        if relationship_schema.cardinality == RelationshipCardinality.ONE:
            return
        return

    def _get_diff_attribute(self, database_path: DatabasePath, diff_node: DiffNode) -> DiffAttribute:
        attribute_name = database_path.attribute_name
        if attribute_name not in diff_node.attributes_by_name:
            diff_node.attributes_by_name[attribute_name] = DiffAttribute(
                uuid=database_path.attribute_id,
                name=attribute_name,
                changed_at=database_path.attribute_changed_at,
                action=self._get_diff_action(
                    changed_at=database_path.attribute_changed_at, edge_status=database_path.attribute_status
                ),
            )
        return diff_node.attributes_by_name[attribute_name]

    def _update_attribute_property(self, database_path: DatabasePath, diff_attribute: DiffAttribute) -> None:
        property_type = database_path.property_type
        if property_type not in diff_attribute.properties_by_type:
            diff_attribute.properties_by_type[property_type] = DiffProperty(
                db_id=database_path.property_id, property_type=property_type
            )
        diff_property = diff_attribute.properties_by_type[property_type]
        diff_property.add_value(
            diff_value=DiffValue(changed_at=database_path.property_changed_at, value=database_path.property_value)
        )

    def _apply_base_branch_previous_values(self) -> None:
        base_diff_root = self.get_diff_root_for_branch(branch=self.base_branch_name)
        if not base_diff_root:
            return
        other_branches = self.get_branches() - {self.base_branch_name}
        for branch in other_branches:
            branch_diff_root = self.get_diff_root_for_branch(branch=branch)
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
                        base_previous_diff_value = base_diff_property.previous_diff_value
                        if base_previous_diff_value:
                            diff_property.add_value(diff_value=base_previous_diff_value)

    def _remove_empty_base_diff_root(self) -> None:
        base_diff_root = self.get_diff_root_for_branch(branch=self.base_branch_name)
        if not base_diff_root:
            return
        for node_diff in base_diff_root.nodes_by_id.values():
            for attribute_diff in node_diff.attributes_by_name.values():
                for property_diff in attribute_diff.properties_by_type.values():
                    newest_diff_change_timestamp = property_diff.new_value_changed_at
                    if newest_diff_change_timestamp > self.from_time:
                        return
        del self._diff_root_by_branch[self.base_branch_name]
