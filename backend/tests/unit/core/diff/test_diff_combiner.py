from datetime import UTC

import pytest
from pendulum.datetime import DateTime

from infrahub.core.constants import DiffAction
from infrahub.core.diff.combiner import DiffCombiner
from infrahub.core.diff.model.path import EnrichedDiffNode
from infrahub.core.timestamp import Timestamp

from .factories import EnrichedNodeFactory, EnrichedRelationshipGroupFactory, EnrichedRootFactory


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
