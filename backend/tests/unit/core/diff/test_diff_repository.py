from datetime import UTC
from uuid import uuid4

import pytest
from pendulum.datetime import DateTime

from infrahub import config
from infrahub.core.constants import DiffAction
from infrahub.core.diff.model.path import (
    EnrichedDiffAttribute,
    EnrichedDiffNode,
    EnrichedDiffRoot,
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
        self.removed_attr_name = "all_gone"
        self.removed_attr_change_time = DateTime(2024, 6, 15, 18, 35, 50, tzinfo=UTC)
        self.removed_attribute = EnrichedDiffAttribute(
            name=self.removed_attr_name,
            changed_at=Timestamp(self.removed_attr_change_time),
            action=DiffAction.REMOVED,
        )
        self.updated_attr_name = "something_new"
        self.updated_attr_change_time = DateTime(2024, 6, 15, 18, 35, 55, tzinfo=UTC)
        self.updated_attribute = EnrichedDiffAttribute(
            name=self.updated_attr_name,
            changed_at=Timestamp(self.updated_attr_change_time),
            action=DiffAction.UPDATED,
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
        updated_attr = attrs_by_name[self.updated_attr_name]
        assert updated_attr.name == self.updated_attr_name
        assert updated_attr.changed_at.obj == self.updated_attr_change_time
        assert updated_attr.action is DiffAction.UPDATED
        assert len(diff_node.relationships) == 0
