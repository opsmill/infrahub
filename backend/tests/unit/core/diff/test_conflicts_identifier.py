from unittest.mock import AsyncMock
from uuid import uuid4

from infrahub.core.branch import Branch
from infrahub.core.constants import PathType
from infrahub.core.diff.conflicts_identifier import ConflictsIdentifier
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.model.diff import BranchChanges, DataConflict, ModifiedPathType
from infrahub.core.timestamp import Timestamp

from .factories import EnrichedAttributeFactory, EnrichedNodeFactory, EnrichedPropertyFactory, EnrichedRootFactory


class TestConflictsIdentifier:
    def setup_method(self):
        self.base_branch = Branch(name="main")
        self.diff_branch = Branch(name="branch")
        self.from_time = Timestamp("2024-07-28T13:45:22Z")
        self.to_time = Timestamp()
        self.diff_coordinator = AsyncMock(spec=DiffCoordinator)
        self.conflicts_identifier = ConflictsIdentifier(
            diff_coordinator=self.diff_coordinator, base_branch=self.base_branch, diff_branch=self.diff_branch
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

        assert self.diff_coordinator.get_diff.awaited_once_with(
            base_branch=self.base_branch, diff_branch=self.base_branch, from_time=self.from_time, to_time=self.to_time
        )
        assert self.diff_coordinator.get_diff.awaited_once_with(
            base_branch=self.base_branch, diff_branch=self.diff_branch, from_time=self.from_time, to_time=self.to_time
        )
        assert diff_conflicts == []

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
            EnrichedNodeFactory.build(uuid=node_uuid, kind=node_kind, attributes=base_attributes, relationships=set()),
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
                uuid=node_uuid, kind=node_kind, attributes=branch_attributes, relationships=set()
            ),
            EnrichedNodeFactory.build(relationships=set()),
        }
        self.branch_root = EnrichedRootFactory.build(nodes=branch_nodes)
        self.diff_coordinator.get_diff.side_effect = [self.base_root, self.branch_root]

        diff_conflicts = await self.__call_system_under_test()

        assert self.diff_coordinator.get_diff.awaited_once_with(
            base_branch=self.base_branch, diff_branch=self.base_branch, from_time=self.from_time, to_time=self.to_time
        )
        assert self.diff_coordinator.get_diff.awaited_once_with(
            base_branch=self.base_branch, diff_branch=self.diff_branch, from_time=self.from_time, to_time=self.to_time
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
