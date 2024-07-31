from datetime import UTC
from uuid import uuid4

import pytest
from pendulum.datetime import DateTime

from infrahub.core.constants import DiffAction
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.combiner import DiffCombiner
from infrahub.core.diff.model.path import EnrichedDiffAttribute, EnrichedDiffNode, EnrichedDiffProperty
from infrahub.core.timestamp import Timestamp

from .factories import (
    EnrichedAttributeFactory,
    EnrichedNodeFactory,
    EnrichedPropertyFactory,
    EnrichedRelationshipGroupFactory,
    EnrichedRootFactory,
)


class TestDiffCombiner:
    def setup_method(self):
        self.diff_from_1 = Timestamp(DateTime(2024, 3, 5, 7, 9, 11, tzinfo=UTC))
        self.diff_to_1 = Timestamp(DateTime(2024, 3, 5, 9, 11, 13, tzinfo=UTC))
        self.diff_from_2 = Timestamp(DateTime(2024, 3, 5, 7, 9, 14, tzinfo=UTC))
        self.diff_to_2 = Timestamp(DateTime(2024, 3, 5, 11, 13, 15, tzinfo=UTC))
        self.base_branch = "main"
        self.diff_branch = "branch"
        self.diff_root_1 = EnrichedRootFactory.build(
            base_branch_name=self.base_branch,
            diff_branch_name=self.diff_branch,
            from_time=self.diff_from_1,
            to_time=self.diff_to_1,
        )
        self.diff_root_2 = EnrichedRootFactory.build(
            base_branch_name=self.base_branch,
            diff_branch_name=self.diff_branch,
            from_time=self.diff_from_2,
            to_time=self.diff_to_2,
        )
        self.expected_combined = EnrichedRootFactory.build(
            base_branch_name=self.base_branch,
            diff_branch_name=self.diff_branch,
            from_time=self.diff_from_1,
            to_time=self.diff_to_2,
            nodes=set(),
        )
        self.combiner = DiffCombiner()

    async def __call_system_under_test(self, diff_1, diff_2):
        return await self.combiner.combine(earlier_diff=diff_1, later_diff=diff_2)

    @pytest.mark.parametrize(
        "action_1,action_2",
        [
            (DiffAction.ADDED, DiffAction.REMOVED),
            (DiffAction.REMOVED, DiffAction.ADDED),
            # unchanged in both diffs and no child nodes will be removed
            (DiffAction.UNCHANGED, DiffAction.UNCHANGED),
        ],
    )
    async def test_add_and_remove_node_cancel_one_another(self, action_1, action_2):
        diff_node_1 = EnrichedNodeFactory.build(action=action_1, attributes=set(), relationships=set())
        diff_node_2 = EnrichedNodeFactory.build(
            uuid=diff_node_1.uuid, kind=diff_node_1.kind, action=action_2, attributes=set(), relationships=set()
        )
        self.diff_root_1.nodes = {diff_node_1}
        self.diff_root_2.nodes = {diff_node_2}

        combined = await self.__call_system_under_test(self.diff_root_1, self.diff_root_2)

        self.expected_combined.uuid = combined.uuid
        assert combined == self.expected_combined

    @pytest.mark.parametrize(
        "action_1,action_2,expected_action",
        [
            (DiffAction.ADDED, DiffAction.UPDATED, DiffAction.ADDED),
            (DiffAction.ADDED, DiffAction.UNCHANGED, DiffAction.ADDED),
            (DiffAction.UPDATED, DiffAction.REMOVED, DiffAction.REMOVED),
            (DiffAction.UPDATED, DiffAction.UNCHANGED, DiffAction.UPDATED),
            (DiffAction.UPDATED, DiffAction.UPDATED, DiffAction.UPDATED),
            (DiffAction.UNCHANGED, DiffAction.REMOVED, DiffAction.REMOVED),
            (DiffAction.UNCHANGED, DiffAction.UPDATED, DiffAction.UPDATED),
        ],
    )
    async def test_node_action_addition(self, action_1, action_2, expected_action):
        diff_node_1 = EnrichedNodeFactory.build(action=action_1, attributes=set(), relationships=set())
        diff_node_2 = EnrichedNodeFactory.build(
            uuid=diff_node_1.uuid, kind=diff_node_1.kind, action=action_2, attributes=set(), relationships=set()
        )
        self.diff_root_1.nodes = {diff_node_1}
        self.diff_root_2.nodes = {diff_node_2}

        combined = await self.__call_system_under_test(self.diff_root_1, self.diff_root_2)

        self.expected_combined.uuid = combined.uuid
        self.expected_combined.nodes = {
            EnrichedDiffNode(
                uuid=diff_node_2.uuid,
                kind=diff_node_2.kind,
                label=diff_node_2.label,
                changed_at=diff_node_2.changed_at,
                action=expected_action,
                attributes=set(),
                relationships=set(),
            )
        }
        assert combined == self.expected_combined

    async def test_stale_parent_node_removed(self):
        child_node_1 = EnrichedNodeFactory.build(action=DiffAction.ADDED, relationships=set())
        relationship_1 = EnrichedRelationshipGroupFactory.build(
            name="smells",
            label="Olfactory essences",
            action=DiffAction.UPDATED,
            relationships=set(),
            nodes={child_node_1},
        )
        parent_node_1 = EnrichedNodeFactory.build(
            action=DiffAction.UNCHANGED, attributes=set(), relationships={relationship_1}
        )
        self.diff_root_1.nodes = {parent_node_1, child_node_1}
        child_node_2 = EnrichedNodeFactory.build(
            uuid=child_node_1.uuid, kind=child_node_1.kind, action=DiffAction.UPDATED, relationships=set()
        )
        relationship_2 = EnrichedRelationshipGroupFactory.build(
            name=relationship_1.name,
            label=relationship_1.label,
            action=DiffAction.UPDATED,
            relationships=set(),
            nodes={child_node_2},
        )
        parent_node_2 = EnrichedNodeFactory.build(
            action=DiffAction.UNCHANGED, attributes=set(), relationships={relationship_2}
        )
        self.diff_root_2.nodes = {parent_node_2, child_node_2}

        combined = await self.__call_system_under_test(self.diff_root_1, self.diff_root_2)

        self.expected_combined.uuid = combined.uuid
        self.expected_combined.nodes = {
            EnrichedNodeFactory.build(
                uuid=child_node_1.uuid,
                kind=child_node_1.kind,
                action=DiffAction.ADDED,
                changed_at=child_node_2.changed_at,
                relationships=set(),
                attributes=set(),
            ),
            EnrichedNodeFactory.build(action=DiffAction.UNCHANGED, attributes=set(), relationships=set()),
        }

    async def test_attributes_combined(self):
        added_attr_name = "width"
        added_attr_owner_property_1 = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.HAS_OWNER,
            action=DiffAction.ADDED,
            previous_value=None,
            new_value=str(uuid4()),
        )
        added_attr_owner_property_2 = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.HAS_OWNER,
            action=DiffAction.UPDATED,
            previous_value=added_attr_owner_property_1.new_value,
            new_value=str(uuid4()),
        )
        earlier_only_property = EnrichedPropertyFactory.build(property_type=DatabaseEdgeType.HAS_VALUE)
        added_attribute_1 = EnrichedAttributeFactory.build(
            name=added_attr_name,
            action=DiffAction.ADDED,
            properties={added_attr_owner_property_1, earlier_only_property},
        )
        later_only_property = EnrichedPropertyFactory.build(property_type=DatabaseEdgeType.HAS_SOURCE)
        added_attribute_2 = EnrichedAttributeFactory.build(
            name=added_attr_name, action=DiffAction.ADDED, properties={added_attr_owner_property_2, later_only_property}
        )
        attr_earlier_only = EnrichedAttributeFactory.build()
        attr_later_only = EnrichedAttributeFactory.build()
        earlier_node_1 = EnrichedNodeFactory.build(
            action=DiffAction.ADDED, attributes={added_attribute_1, attr_earlier_only}, relationships=set()
        )
        later_node_1 = EnrichedNodeFactory.build(
            uuid=earlier_node_1.uuid,
            kind=earlier_node_1.kind,
            action=DiffAction.UPDATED,
            attributes={added_attribute_2, attr_later_only},
            relationships=set(),
        )
        updated_attr_name = "length"
        updated_attr_value_property_1 = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.HAS_VALUE,
            action=DiffAction.UPDATED,
            previous_value=str(uuid4()),
            new_value=str(uuid4()),
        )
        updated_attr_value_property_2 = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.HAS_VALUE,
            action=DiffAction.UPDATED,
            previous_value=updated_attr_value_property_1.new_value,
            new_value=str(uuid4()),
        )
        updated_attribute_1 = EnrichedAttributeFactory.build(
            name=updated_attr_name,
            action=DiffAction.UPDATED,
            properties={updated_attr_value_property_1},
        )
        updated_attribute_2 = EnrichedAttributeFactory.build(
            name=updated_attr_name, action=DiffAction.UPDATED, properties={updated_attr_value_property_2}
        )
        earlier_node_2 = EnrichedNodeFactory.build(
            action=DiffAction.UPDATED, attributes={updated_attribute_1}, relationships=set()
        )
        later_node_2 = EnrichedNodeFactory.build(
            uuid=earlier_node_2.uuid,
            kind=earlier_node_2.kind,
            action=DiffAction.UPDATED,
            attributes={updated_attribute_2},
            relationships=set(),
        )

        self.diff_root_1.nodes = {earlier_node_1, earlier_node_2}
        self.diff_root_2.nodes = {later_node_1, later_node_2}

        expected_added_combined_property = EnrichedDiffProperty(
            property_type=added_attr_owner_property_2.property_type,
            changed_at=added_attr_owner_property_2.changed_at,
            previous_value=added_attr_owner_property_1.previous_value,
            new_value=added_attr_owner_property_2.new_value,
            action=DiffAction.ADDED,
        )
        expected_updated_combined_property = EnrichedDiffProperty(
            property_type=updated_attr_value_property_2.property_type,
            changed_at=updated_attr_value_property_2.changed_at,
            previous_value=updated_attr_value_property_1.previous_value,
            new_value=updated_attr_value_property_2.new_value,
            action=DiffAction.UPDATED,
        )
        expected_added_combined_attr = EnrichedDiffAttribute(
            name=added_attr_name,
            changed_at=added_attribute_2.changed_at,
            action=DiffAction.ADDED,
            properties={earlier_only_property, later_only_property, expected_added_combined_property},
        )
        expected_updated_combined_attr = EnrichedDiffAttribute(
            name=updated_attr_name,
            changed_at=updated_attribute_2.changed_at,
            action=DiffAction.UPDATED,
            properties={expected_updated_combined_property},
        )
        expected_nodes = {
            EnrichedDiffNode(
                uuid=later_node_1.uuid,
                kind=later_node_1.kind,
                label=later_node_1.label,
                changed_at=later_node_1.changed_at,
                action=DiffAction.ADDED,
                attributes={attr_earlier_only, attr_later_only, expected_added_combined_attr},
            ),
            EnrichedDiffNode(
                uuid=later_node_2.uuid,
                kind=later_node_2.kind,
                label=later_node_2.label,
                changed_at=later_node_2.changed_at,
                action=DiffAction.UPDATED,
                attributes={expected_updated_combined_attr},
            ),
        }
        self.expected_combined.nodes = expected_nodes

        combined = await self.__call_system_under_test(self.diff_root_1, self.diff_root_2)

        self.expected_combined.uuid = combined.uuid
        assert combined == self.expected_combined
