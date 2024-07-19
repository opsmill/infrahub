from datetime import UTC
from uuid import uuid4

import pytest
from pendulum.datetime import DateTime

from infrahub import config
from infrahub.core.constants import DiffAction
from infrahub.core.diff.model.path import (
    EnrichedDiffAttribute,
    EnrichedDiffNode,
    EnrichedDiffProperty,
    EnrichedDiffRelationship,
    EnrichedDiffRoot,
    EnrichedDiffSingleRelationship,
)
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import delete_all_nodes
from infrahub.database import InfrahubDatabase


class TestDiffRepository:
    @pytest.fixture(scope="class")
    async def reset_database(self, db: InfrahubDatabase):
        await delete_all_nodes(db=db)

    @pytest.fixture(scope="class")
    def diff_repository(self, db: InfrahubDatabase) -> DiffRepository:
        config.SETTINGS.database.max_depth_search_hierarchy = 10
        return DiffRepository(db=db)

    def setup_method(self):
        self.diff_from_time = DateTime(2024, 6, 15, 18, 35, 20, tzinfo=UTC)
        self.diff_to_time = DateTime(2024, 6, 15, 18, 45, 30, tzinfo=UTC)
        self.base_branch_name = "main"
        self.diff_branch_name = "diff"
        self.diff_uuid = str(uuid4())
        self.enriched_diff = EnrichedDiffRoot(
            base_branch_name=self.base_branch_name,
            diff_branch_name=self.diff_branch_name,
            from_time=Timestamp(self.diff_from_time),
            to_time=Timestamp(self.diff_to_time),
            uuid=str(self.diff_uuid),
        )
        self.updated_node_uuid = str(uuid4())
        self.updated_node_kind = "ThisKind"
        self.updated_node_label = "This is the node"
        self.updated_node_change_time = DateTime(2024, 6, 15, 18, 36, 0, tzinfo=UTC)
        self.updated_node_diff = EnrichedDiffNode(
            uuid=str(self.updated_node_uuid),
            kind=self.updated_node_kind,
            label=self.updated_node_label,
            changed_at=Timestamp(self.updated_node_change_time),
            action=DiffAction.UPDATED,
        )

        self.removed_attr_prop_1_change_time = DateTime(2024, 6, 15, 18, 35, 50, tzinfo=UTC)
        self.removed_attr_prop_1_property_type = "HAS_VALUE"
        self.removed_attr_prop_1_previous_value = "some stuff"
        self.removed_attr_prop_1 = EnrichedDiffProperty(
            property_type=self.removed_attr_prop_1_property_type,
            changed_at=Timestamp(self.removed_attr_prop_1_change_time),
            previous_value=self.removed_attr_prop_1_previous_value,
            new_value=None,
            action=DiffAction.REMOVED,
            conflict=None,
        )
        self.removed_attr_name = "all_gone"
        self.removed_attr_change_time = self.removed_attr_prop_1_change_time
        self.removed_attribute = EnrichedDiffAttribute(
            name=self.removed_attr_name,
            changed_at=Timestamp(self.removed_attr_change_time),
            action=DiffAction.REMOVED,
            properties=[self.removed_attr_prop_1],
        )
        self.updated_attr_name = "something_new"
        self.updated_attr_change_time = DateTime(2024, 6, 15, 18, 35, 55, tzinfo=UTC)
        self.updated_attribute = EnrichedDiffAttribute(
            name=self.updated_attr_name,
            changed_at=Timestamp(self.updated_attr_change_time),
            action=DiffAction.UPDATED,
        )
        self.updated_rel_group_1_rel_change_time = DateTime(2024, 6, 15, 18, 36, 2, tzinfo=UTC)
        self.updated_rel_group_1_rel_peer_id = str(uuid4())
        self.updated_rel_group_1_rel = EnrichedDiffSingleRelationship(
            changed_at=Timestamp(self.updated_rel_group_1_rel_change_time),
            action=DiffAction.UPDATED,
            peer_id=self.updated_rel_group_1_rel_peer_id,
            conflict=None,
        )
        self.updated_rel_group_change_time = self.updated_rel_group_1_rel_change_time
        self.updated_rel_group_name = "first_relationship"
        self.updated_rel_group = EnrichedDiffRelationship(
            name=self.updated_rel_group_name,
            changed_at=Timestamp(self.updated_rel_group_change_time),
            action=DiffAction.UPDATED,
            relationships=[self.updated_rel_group_1_rel],
        )

    async def test_get_non_existent_diff(self, diff_repository: DiffRepository):
        right_now = Timestamp()
        enriched_diffs = await diff_repository.get(
            base_branch_name="main",
            diff_branch_names=["nobranch"],
            from_time=right_now,
            to_time=right_now.add_delta(hours=1),
        )
        assert len(enriched_diffs) == 0

    async def test_save_and_retrieve(self, diff_repository: DiffRepository, reset_database):
        self.enriched_diff.nodes = [self.updated_node_diff]
        self.updated_node_diff.attributes = [self.removed_attribute, self.updated_attribute]
        self.updated_node_diff.relationships = [self.updated_rel_group]
        await diff_repository.save(enriched_diff=self.enriched_diff)

        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[self.diff_branch_name],
            from_time=Timestamp(self.diff_from_time),
            to_time=Timestamp(self.diff_to_time),
        )
        assert len(retrieved) == 1
        diff_root = retrieved[0]
        assert diff_root.uuid == self.diff_uuid
        assert diff_root.base_branch_name == self.base_branch_name
        assert diff_root.diff_branch_name == self.diff_branch_name
        assert diff_root.from_time == Timestamp(self.diff_from_time)
        assert diff_root.to_time == Timestamp(self.diff_to_time)
        assert len(diff_root.nodes) == 1
        diff_node = diff_root.nodes[0]
        assert diff_node
        assert diff_node.uuid == self.updated_node_uuid
        assert diff_node.kind == self.updated_node_kind
        assert diff_node.label == self.updated_node_label
        assert diff_node.changed_at.obj == self.updated_node_change_time
        assert diff_node.action is DiffAction.UPDATED
        assert len(diff_node.attributes) == 2
        attrs_by_name = {attr.name: attr for attr in diff_node.attributes}
        removed_attr = attrs_by_name[self.removed_attr_name]
        assert removed_attr.name == self.removed_attr_name
        assert removed_attr.changed_at.obj == self.removed_attr_change_time
        assert removed_attr.action is DiffAction.REMOVED
        assert len(removed_attr.properties) == 1
        removed_attr_prop_1 = removed_attr.properties[0]
        assert removed_attr_prop_1.property_type == self.removed_attr_prop_1_property_type
        assert removed_attr_prop_1.previous_value == self.removed_attr_prop_1_previous_value
        assert removed_attr_prop_1.new_value is None
        assert removed_attr_prop_1.changed_at.obj == self.removed_attr_prop_1_change_time
        assert removed_attr_prop_1.action is DiffAction.REMOVED
        assert removed_attr_prop_1.conflict is None
        updated_attr = attrs_by_name[self.updated_attr_name]
        assert updated_attr.name == self.updated_attr_name
        assert updated_attr.changed_at.obj == self.updated_attr_change_time
        assert updated_attr.action is DiffAction.UPDATED
        assert len(updated_attr.properties) == 0
        assert len(diff_node.relationships) == 1
        updated_rel_group = diff_node.relationships[0]
        assert updated_rel_group.name == self.updated_rel_group_name
        assert updated_rel_group.changed_at.obj == self.updated_rel_group_change_time
        assert updated_rel_group.action is DiffAction.UPDATED
        assert len(updated_rel_group.relationships) == 1
        updated_rel_group_1_rel = updated_rel_group.relationships[0]
        assert updated_rel_group_1_rel.changed_at.obj == self.updated_rel_group_1_rel_change_time
        assert updated_rel_group_1_rel.peer_id == self.updated_rel_group_1_rel_peer_id
        assert updated_rel_group_1_rel.conflict is None
        assert len(updated_rel_group_1_rel.properties) == 0
        assert len(updated_rel_group.nodes) == 0
