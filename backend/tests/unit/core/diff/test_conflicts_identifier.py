from unittest.mock import AsyncMock, MagicMock, call
from uuid import uuid4

from infrahub.core.branch import Branch
from infrahub.core.constants import DiffAction, PathType
from infrahub.core.diff.conflicts_identifier import ConflictsIdentifier
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.model.diff import BranchChanges, DataConflict, ModifiedPathType
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.core.schema_manager import SchemaManager
from infrahub.core.timestamp import Timestamp

from .factories import (
    EnrichedAttributeFactory,
    EnrichedNodeFactory,
    EnrichedPropertyFactory,
    EnrichedRelationshipElementFactory,
    EnrichedRelationshipGroupFactory,
    EnrichedRootFactory,
)


class TestConflictsIdentifier:
    def setup_method(self):
        self.base_branch = Branch(name="main")
        self.diff_branch = Branch(name="branch")
        self.from_time = Timestamp("2024-07-28T13:45:22Z")
        self.to_time = Timestamp()
        self.diff_coordinator = AsyncMock(spec=DiffCoordinator)
        self.schema_manager = AsyncMock(spec=SchemaManager)
        self.conflicts_identifier = ConflictsIdentifier(
            diff_coordinator=self.diff_coordinator,
            base_branch=self.base_branch,
            diff_branch=self.diff_branch,
            schema_manager=self.schema_manager,
        )

    async def __call_system_under_test(self) -> list[DataConflict]:
        return await self.conflicts_identifier.get_conflicts(from_time=self.from_time, to_time=self.to_time)

    async def test_no_conflicts(self):
        self.base_root = EnrichedRootFactory.build(nodes=[])
        self.branch_root = EnrichedRootFactory.build(nodes=[])
        for diff_root in (self.base_root, self.branch_root):
            properties = [EnrichedPropertyFactory.build() for _ in range(3)]
            attribute = EnrichedAttributeFactory.build(properties=properties)
            diff_root.nodes = [EnrichedNodeFactory.build(attributes=[attribute], relationships=[])]
        self.diff_coordinator.get_diff.side_effect = [self.base_root, self.branch_root]

        diff_conflicts = await self.__call_system_under_test()

        self.diff_coordinator.get_diff.assert_has_awaits(
            calls=[
                call(
                    base_branch=self.base_branch,
                    diff_branch=self.base_branch,
                    from_time=self.from_time,
                    to_time=self.to_time,
                ),
                call(
                    base_branch=self.base_branch,
                    diff_branch=self.diff_branch,
                    from_time=self.from_time,
                    to_time=self.to_time,
                ),
            ],
            any_order=True,
        )
        assert diff_conflicts == []

    async def test_one_node_conflict(self):
        node_uuid = str(uuid4())
        node_kind = "SomethingSmelly"
        base_nodes = {
            EnrichedNodeFactory.build(uuid=node_uuid, kind=node_kind, action=DiffAction.UPDATED, relationships=set()),
            EnrichedNodeFactory.build(relationships=set()),
        }
        branch_nodes = {
            EnrichedNodeFactory.build(uuid=node_uuid, kind=node_kind, action=DiffAction.REMOVED, relationships=set()),
            EnrichedNodeFactory.build(relationships=set()),
        }
        self.base_root = EnrichedRootFactory.build(nodes=base_nodes)
        self.branch_root = EnrichedRootFactory.build(nodes=branch_nodes)
        self.diff_coordinator.get_diff.side_effect = [self.base_root, self.branch_root]
        diff_conflicts = await self.__call_system_under_test()

        self.diff_coordinator.get_diff.assert_has_awaits(
            calls=[
                call(
                    base_branch=self.base_branch,
                    diff_branch=self.base_branch,
                    from_time=self.from_time,
                    to_time=self.to_time,
                ),
                call(
                    base_branch=self.base_branch,
                    diff_branch=self.diff_branch,
                    from_time=self.from_time,
                    to_time=self.to_time,
                ),
            ],
            any_order=True,
        )
        assert diff_conflicts == [
            DataConflict(
                name="",
                type=ModifiedPathType.DATA,
                id=node_uuid,
                kind=node_kind,
                change_type="node",
                path=f"data/{node_uuid}",
                conflict_path=f"data/{node_uuid}",
                path_type=PathType.NODE,
                property_name=None,
                changes=[
                    BranchChanges(
                        branch=self.base_branch.name,
                        action=DiffAction.UPDATED,
                    ),
                    BranchChanges(
                        branch=self.diff_branch.name,
                        action=DiffAction.REMOVED,
                    ),
                ],
            )
        ]

    async def test_one_attribute_conflict(self):
        property_type = "HAS_OWNER"
        attribute_name = "smell"
        node_uuid = str(uuid4())
        node_kind = "SomethingSmelly"
        base_properties = {EnrichedPropertyFactory.build() for _ in range(3)}
        base_conflict_property = EnrichedPropertyFactory.build(property_type=property_type)
        base_properties.add(base_conflict_property)
        base_attributes = {
            EnrichedAttributeFactory.build(),
            EnrichedAttributeFactory.build(properties=base_properties, name=attribute_name),
        }
        base_nodes = {
            EnrichedNodeFactory.build(
                uuid=node_uuid,
                kind=node_kind,
                action=DiffAction.UPDATED,
                attributes=base_attributes,
                relationships=set(),
            ),
            EnrichedNodeFactory.build(relationships=set()),
        }
        self.base_root = EnrichedRootFactory.build(nodes=base_nodes)
        branch_properties = {EnrichedPropertyFactory.build() for _ in range(3)}
        branch_conflict_property = EnrichedPropertyFactory.build(property_type=property_type)
        branch_properties.add(branch_conflict_property)
        branch_attributes = {
            EnrichedAttributeFactory.build(),
            EnrichedAttributeFactory.build(properties=branch_properties, name=attribute_name),
        }
        branch_nodes = {
            EnrichedNodeFactory.build(
                uuid=node_uuid,
                kind=node_kind,
                action=DiffAction.UPDATED,
                attributes=branch_attributes,
                relationships=set(),
            ),
            EnrichedNodeFactory.build(relationships=set()),
        }
        self.branch_root = EnrichedRootFactory.build(nodes=branch_nodes)
        self.diff_coordinator.get_diff.side_effect = [self.base_root, self.branch_root]

        diff_conflicts = await self.__call_system_under_test()

        self.diff_coordinator.get_diff.assert_has_awaits(
            calls=[
                call(
                    base_branch=self.base_branch,
                    diff_branch=self.base_branch,
                    from_time=self.from_time,
                    to_time=self.to_time,
                ),
                call(
                    base_branch=self.base_branch,
                    diff_branch=self.diff_branch,
                    from_time=self.from_time,
                    to_time=self.to_time,
                ),
            ],
            any_order=True,
        )
        assert diff_conflicts == [
            DataConflict(
                name=attribute_name,
                type=ModifiedPathType.DATA,
                id=node_uuid,
                kind=node_kind,
                change_type="attribute_property",
                path=f"data/{node_uuid}/{attribute_name}/property/{property_type}",
                conflict_path=f"data/{node_uuid}/{attribute_name}/property/{property_type}",
                path_type=PathType.ATTRIBUTE,
                property_name=property_type,
                changes=[
                    BranchChanges(
                        branch=self.base_branch.name,
                        action=base_conflict_property.action,
                        new=base_conflict_property.new_value,
                        previous=base_conflict_property.previous_value,
                    ),
                    BranchChanges(
                        branch=self.diff_branch.name,
                        action=branch_conflict_property.action,
                        new=branch_conflict_property.new_value,
                        previous=branch_conflict_property.previous_value,
                    ),
                ],
            )
        ]

    async def test_cardinality_one_peer_id_conflict(self, car_person_schema_unregistered: SchemaRoot):
        property_type = "IS_RELATED"
        relationship_name = "owner"
        node_uuid = str(uuid4())
        node_kind = "TestCar"
        previous_peer_id = str(uuid4())
        new_base_peer_id = str(uuid4())
        base_conflict_property = EnrichedPropertyFactory.build(
            property_type=property_type,
            previous_value=previous_peer_id,
            new_value=new_base_peer_id,
            action=DiffAction.UPDATED,
        )
        base_properties = {base_conflict_property, EnrichedPropertyFactory.build()}
        base_relationships = {
            EnrichedRelationshipGroupFactory.build(
                name=relationship_name,
                relationships={
                    EnrichedRelationshipElementFactory.build(peer_id=new_base_peer_id, properties=base_properties)
                },
            )
        }
        base_nodes = {
            EnrichedNodeFactory.build(
                uuid=node_uuid,
                kind=node_kind,
                action=DiffAction.UPDATED,
                relationships=base_relationships,
            ),
            EnrichedNodeFactory.build(relationships=set()),
        }
        self.base_root = EnrichedRootFactory.build(nodes=base_nodes)
        branch_conflict_property = EnrichedPropertyFactory.build(
            property_type=property_type, previous_value=previous_peer_id, new_value=None, action=DiffAction.REMOVED
        )
        branch_properties = {branch_conflict_property, EnrichedPropertyFactory.build()}
        branch_relationships = {
            EnrichedRelationshipGroupFactory.build(
                name=relationship_name,
                relationships={
                    EnrichedRelationshipElementFactory.build(peer_id=previous_peer_id, properties=branch_properties)
                },
            )
        }
        branch_nodes = {
            EnrichedNodeFactory.build(
                uuid=node_uuid,
                kind=node_kind,
                action=DiffAction.UPDATED,
                relationships=branch_relationships,
            ),
            EnrichedNodeFactory.build(relationships=set()),
        }
        self.branch_root = EnrichedRootFactory.build(nodes=branch_nodes)
        self.diff_coordinator.get_diff.side_effect = [self.base_root, self.branch_root]
        for node_schema in car_person_schema_unregistered.nodes:
            if node_schema.kind == "TestCar":
                car_schema = node_schema
                break

        def mock_get_node_schema(name, *args, **kwargs):
            if name == "TestCar":
                return car_schema
            return MagicMock(spec=NodeSchema)

        self.schema_manager.get_node_schema.side_effect = mock_get_node_schema

        diff_conflicts = await self.__call_system_under_test()

        assert len(diff_conflicts) == 2
        self.diff_coordinator.get_diff.assert_has_awaits(
            calls=[
                call(
                    base_branch=self.base_branch,
                    diff_branch=self.base_branch,
                    from_time=self.from_time,
                    to_time=self.to_time,
                ),
                call(
                    base_branch=self.base_branch,
                    diff_branch=self.diff_branch,
                    from_time=self.from_time,
                    to_time=self.to_time,
                ),
            ],
            any_order=True,
        )
        self.schema_manager.get_node_schema.assert_called_once_with(
            name="TestCar", branch=self.diff_branch, duplicate=False
        )
        assert (
            DataConflict(
                name=relationship_name,
                type=ModifiedPathType.DATA,
                id=node_uuid,
                kind=node_kind,
                change_type="relationship_one_value",
                path=f"data/{node_uuid}/{relationship_name}/peer",
                conflict_path=f"data/{node_uuid}/{relationship_name}/peer/{previous_peer_id}",
                path_type=PathType.RELATIONSHIP_ONE,
                property_name=None,
                changes=[
                    BranchChanges(
                        branch=self.base_branch.name,
                        action=base_conflict_property.action,
                        new=base_conflict_property.new_value,
                        previous=base_conflict_property.previous_value,
                    ),
                    BranchChanges(
                        branch=self.diff_branch.name,
                        action=branch_conflict_property.action,
                        new=branch_conflict_property.new_value,
                        previous=branch_conflict_property.previous_value,
                    ),
                ],
            )
            in diff_conflicts
        )
        assert (
            DataConflict(
                name=relationship_name,
                type=ModifiedPathType.DATA,
                id=node_uuid,
                kind=node_kind,
                change_type="relationship_one_value",
                path=f"data/{node_uuid}/{relationship_name}/peer",
                conflict_path=f"data/{node_uuid}/{relationship_name}/peer/{new_base_peer_id}",
                path_type=PathType.RELATIONSHIP_ONE,
                property_name=None,
                changes=[
                    BranchChanges(
                        branch=self.base_branch.name,
                        action=base_conflict_property.action,
                        new=base_conflict_property.new_value,
                        previous=base_conflict_property.previous_value,
                    ),
                    BranchChanges(
                        branch=self.diff_branch.name,
                        action=branch_conflict_property.action,
                        new=branch_conflict_property.new_value,
                        previous=branch_conflict_property.previous_value,
                    ),
                ],
            )
            in diff_conflicts
        )
