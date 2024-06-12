# from dataclasses import dataclass

# from infrahub.core.constants import DiffAction, PathType, RelationshipCardinality, RelationshipStatus
# from infrahub.core.schema_manager import SchemaManager
# from infrahub.core.timestamp import Timestamp

# from .model.diff import BranchChanges, DataConflict
# from .model.path import AttributePath, NodePath, PropertyPath, RootPath


# @dataclass
# class RelationshipPeerChangeDetails:
#     peer_id: str
#     property_paths_by_status: dict[RelationshipStatus, list[PropertyPath]]

#     @property
#     def has_conflicting_updates(self) -> bool:
#         # conflicting status updates for a single peer ID, eg added and removed
#         return len(self.property_paths_by_status) > 1

#     @property
#     def is_added(self) -> bool:
#         return RelationshipStatus.ACTIVE in self.property_paths_by_status

#     @property
#     def property_paths(self) -> list[PropertyPath]:
#         property_paths = []
#         for property_path_list in self.property_paths_by_status.values():
#             property_paths += property_path_list
#         return property_paths


# @dataclass
# class RelationshipChangeDetails:
#     relationship_id: str
#     peer_changes: list[RelationshipPeerChangeDetails]

#     @property
#     def has_conflicting_updates(self) -> bool:
#         # different peer IDs added for this relationship on different branches
#         count_added = 0
#         for peer_change in self.peer_changes:
#             if peer_change.has_conflicting_updates:
#                 return True
#             if peer_change.is_added:
#                 count_added += 1
#         return count_added > 1


# class RelationshipPropertyPathIndex:
#     def __init__(self) -> None:
#         # {rel_id: {peer_id: {status: [property_path, ...]}}}
#         self._relationship_peer_property_map: dict[str, dict[str, dict[RelationshipStatus, list[PropertyPath]]]] = {}

#     def index(self, relationship_id: str, peer_id: str, property_path: PropertyPath) -> None:
#         if relationship_id not in self._relationship_peer_property_map:
#             self._relationship_peer_property_map[relationship_id] = {}
#         if peer_id not in self._relationship_peer_property_map[relationship_id]:
#             self._relationship_peer_property_map[relationship_id][peer_id] = {}
#         if property_path.status not in self._relationship_peer_property_map[relationship_id][peer_id]:
#             self._relationship_peer_property_map[relationship_id][peer_id][property_path.status] = []
#         self._relationship_peer_property_map[relationship_id][peer_id][property_path.status].append(property_path)

#     def get_relationship_change_details_list(self) -> list[RelationshipChangeDetails]:
#         relationship_change_details_list = []
#         for relationship_id, peer_details in self._relationship_peer_property_map.items():
#             peer_change_details_list = []
#             for peer_id, property_paths_by_status in peer_details.items():
#                 peer_change_details_list.append(
#                     RelationshipPeerChangeDetails(peer_id=peer_id, property_paths_by_status=property_paths_by_status)
#                 )
#             relationship_change_details_list.append(
#                 RelationshipChangeDetails(relationship_id=relationship_id, peer_changes=peer_change_details_list)
#             )
#         return relationship_change_details_list


# class DiffConflictsIdentifier:
#     def __init__(self, schema_manager: SchemaManager, base_branch: str, from_time: Timestamp) -> None:
#         self.schema_manager = schema_manager
#         self.base_branch = base_branch
#         self.from_time = from_time

#     def get_conflicts_for_path(self, root_path: RootPath) -> list[DataConflict]:
#         conflicting_paths = []
#         for node_path in root_path.get_node_paths():
#             conflicting_paths += self._get_conflicts_for_node_path(node_path=node_path)
#         return conflicting_paths

#     def _get_conflicts_for_node_path(self, node_path: NodePath) -> list[DataConflict]:
#         conflicting_paths = self._get_relationship_conflicts(node_path=node_path)
#         for attribute_path in node_path.get_attribute_paths():
#             conflicting_paths += self._get_conflicts_for_attribute_path(attribute_path=attribute_path)
#         return conflicting_paths

#     def _get_relationship_conflicts(self, node_path: NodePath) -> list[DataConflict]:
#         relationship_index = RelationshipPropertyPathIndex()
#         updated_cardinality_one_attribute_paths = [
#             attribute_path
#             for attribute_path in node_path.get_attribute_paths()
#             if self._is_cardinality_one_relationship(attribute_path=attribute_path)
#         ]
#         if not updated_cardinality_one_attribute_paths:
#             return []
#         for attribute_path in updated_cardinality_one_attribute_paths:
#             branch = attribute_path.branch_name
#             # get the peer, if it has been changed
#             latest_peer_property = attribute_path.get_latest_property_path(branch=branch, property_type="IS_RELATED")
#             if not latest_peer_property:
#                 continue
#             if latest_peer_property.changed_at < self.from_time:
#                 continue
#             peer_id = latest_peer_property.value
#             if not peer_id:
#                 continue
#             relationship_index.index(
#                 relationship_id=attribute_path.name, peer_id=peer_id, property_path=latest_peer_property
#             )
#         data_conflicts = []
#         relationship_change_details_list = relationship_index.get_relationship_change_details_list()
#         for relationship_change_details in relationship_change_details_list:
#             if relationship_change_details.has_conflicting_updates:
#                 data_conflicts.extend(
#                     self._build_relationship_data_conflicts(
#                         node_path=node_path, relationship_change_details=relationship_change_details
#                     )
#                 )
#         return data_conflicts

#     def _get_conflicts_for_attribute_path(self, attribute_path: AttributePath) -> list[DataConflict]:
#         data_conflicts = []
#         for property_type in attribute_path.get_property_types():
#             property_type_by_branch = attribute_path.get_latest_property_paths_by_branch(
#                 property_type=property_type, from_time=self.from_time
#             )
#             # it's only a conflict if there are multiple updates for the same property_type on different branches
#             if len(property_type_by_branch) < 2:
#                 continue
#             data_conflicts.append(
#                 self._build_attribute_data_conflict(
#                     attribute_path=attribute_path,
#                     property_type=property_type,
#                     property_paths=list(property_type_by_branch.values()),
#                 )
#             )
#         return data_conflicts

#     def _is_cardinality_one_relationship(self, attribute_path: AttributePath) -> bool:
#         node_path = attribute_path.upstream_graph_node
#         node_schema = self.schema_manager.get(name=node_path.kind, branch=node_path.branch_name, duplicate=False)
#         relationship_schema = node_schema.get_relationship_by_identifier(id=attribute_path.name, raise_on_error=False)
#         if not relationship_schema:
#             return False
#         return relationship_schema.cardinality == RelationshipCardinality.ONE

#     def _build_relationship_data_conflicts(
#         self, node_path: NodePath, relationship_change_details: RelationshipChangeDetails
#     ) -> list[DataConflict]:
#         node_schema = self.schema_manager.get(name=node_path.kind, branch=node_path.branch_name, duplicate=False)
#         relationship_id = relationship_change_details.relationship_id
#         relationship_schema = node_schema.get_relationship_by_identifier(id=relationship_id)
#         branch_changes = []
#         base_property_path = None
#         base_attribute_path = node_path.get_earliest_attribute_path(
#             branch=self.base_branch, attribute_name=relationship_id
#         )
#         if base_attribute_path:
#             base_property_path = base_attribute_path.get_earliest_property_path(
#                 branch=self.base_branch, property_type="IS_RELATED"
#             )
#         data_conflicts = []
#         for peer_change_details in relationship_change_details.peer_changes:
#             for property_path in peer_change_details.property_paths:
#                 branch_changes.append(
#                     BranchChanges(
#                         branch=property_path.branch_name,
#                         action=DiffAction.ADDED
#                         if property_path.status == RelationshipStatus.ACTIVE
#                         else DiffAction.REMOVED,
#                         new=property_path.value,
#                         previous=base_property_path.value if base_property_path else None,
#                     )
#                 )
#             data_conflicts.append(
#                 DataConflict(
#                     name=relationship_schema.name,
#                     type="data",
#                     id=node_path.id,
#                     kind=node_path.kind,
#                     change_type=f"{PathType.RELATIONSHIP_ONE.value}_property",
#                     path=self._build_path_str(property_path=peer_change_details.property_paths[0]),
#                     conflict_path=self._build_path_str(
#                         property_path=peer_change_details.property_paths[0], with_peer=False
#                     ),
#                     path_type=PathType.RELATIONSHIP_ONE,
#                     property_name="IS_RELATED",
#                     changes=branch_changes,
#                 )
#             )
#         return data_conflicts

#     def _build_attribute_data_conflict(
#         self, attribute_path: AttributePath, property_type: str, property_paths: list[PropertyPath]
#     ) -> DataConflict:
#         node_path = attribute_path.upstream_graph_node
#         branch_changes = []
#         previous_path = attribute_path.get_earliest_property_path(branch=self.base_branch, property_type=property_type)
#         for property_path in property_paths:
#             branch_changes.append(
#                 BranchChanges(
#                     branch=property_path.branch_name,
#                     action=DiffAction.ADDED
#                     if property_path.status == RelationshipStatus.ACTIVE
#                     else DiffAction.REMOVED,
#                     new=property_path.value,
#                     previous=previous_path.value if previous_path else None,
#                 )
#             )
#         if property_type == "HAS_VALUE":
#             change_type = f"{PathType.ATTRIBUTE.value}_value"
#         else:
#             change_type = f"{PathType.ATTRIBUTE.value}_property"
#         return DataConflict(
#             name=attribute_path.name,
#             type="data",
#             id=attribute_path.upstream_graph_node.id,
#             kind=node_path.kind,
#             change_type=change_type,
#             path=self._build_path_str(property_path=property_paths[0]),
#             conflict_path=self._build_path_str(property_path=property_paths[0], with_peer=False),
#             path_type=PathType.ATTRIBUTE,
#             property_name=property_paths[0].relationship_type,
#             changes=branch_changes,
#         )

#     def _build_path_str(self, property_path: PropertyPath, with_peer: bool = True) -> str:
#         attribute_path = property_path.upstream_graph_node
#         node_path = attribute_path.upstream_graph_node
#         is_cardinality_one = self._is_cardinality_one_relationship(attribute_path=attribute_path)

#         identifier = f"data/{node_path.id}/{attribute_path.name}"
#         if is_cardinality_one and property_path.relationship_type == "IS_RELATED":
#             identifier += "/peer"
#             if with_peer:
#                 identifier += f"/{property_path.value}"

#         if property_path.relationship_type == "HAS_VALUE":
#             identifier += "/value"
#         elif property_path.relationship_type != "IS_RELATED":
#             identifier += f"/property/{property_path.relationship_type}"

#         return identifier
