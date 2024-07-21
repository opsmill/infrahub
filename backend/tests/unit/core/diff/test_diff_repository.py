from datetime import UTC

import pytest
from pendulum.datetime import DateTime
from polyfactory.factories import DataclassFactory

from infrahub import config
from infrahub.core.constants import DiffAction
from infrahub.core.diff.model.path import (
    EnrichedDiffAttribute,
    EnrichedDiffNode,
    EnrichedDiffProperty,
    EnrichedDiffPropertyConflict,
    EnrichedDiffRelationship,
    EnrichedDiffRoot,
    EnrichedDiffSingleRelationship,
)
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import delete_all_nodes
from infrahub.database import InfrahubDatabase


class ConflictFactory(DataclassFactory[EnrichedDiffPropertyConflict]): ...


class PropertyFactory(DataclassFactory[EnrichedDiffProperty]): ...


class AttributeFactory(DataclassFactory[EnrichedDiffAttribute]): ...


class RelationshipGroupFactory(DataclassFactory[EnrichedDiffRelationship]): ...


class RelationshipElementFactory(DataclassFactory[EnrichedDiffSingleRelationship]): ...


class NodeFactory(DataclassFactory[EnrichedDiffNode]): ...


class RootFactory(DataclassFactory[EnrichedDiffRoot]): ...


class TestDiffRepository:
    @pytest.fixture(scope="class")
    async def reset_database(self, db: InfrahubDatabase):
        await delete_all_nodes(db=db)

    @pytest.fixture(scope="class")
    def diff_repository(self, db: InfrahubDatabase) -> DiffRepository:
        config.SETTINGS.database.max_depth_search_hierarchy = 10
        return DiffRepository(db=db)

    def setup_method(self):
        self.base_branch_name = "main"
        self.diff_branch_name = "diff"
        self.diff_from_time = DateTime(2024, 6, 15, 18, 35, 20, tzinfo=UTC)
        self.diff_to_time = DateTime(2024, 6, 15, 18, 49, 40, tzinfo=UTC)
        self.enriched_diff = RootFactory.build(
            base_branch_name=self.base_branch_name,
            diff_branch_name=self.diff_branch_name,
            from_time=Timestamp(self.diff_from_time),
            to_time=Timestamp(self.diff_to_time),
            nodes=set(),
        )
        self.updated_node_diff = NodeFactory.build(action=DiffAction.UPDATED, attributes=set(), relationships=set())

        self.removed_attr_prop_1 = PropertyFactory.build(new_value=None, action=DiffAction.REMOVED)
        self.removed_attribute = AttributeFactory.build(
            action=DiffAction.REMOVED, properties={self.removed_attr_prop_1}
        )
        self.updated_attr_prop_1 = PropertyFactory.build(action=DiffAction.UPDATED)
        self.updated_attribute = AttributeFactory.build(
            action=DiffAction.UPDATED, properties={self.updated_attr_prop_1}
        )
        self.updated_rel_group_1_owner_conflict = ConflictFactory.build()

        self.updated_rel_group_1_elem_owner_property = PropertyFactory.build(
            action=DiffAction.UPDATED, conflict=ConflictFactory.build()
        )
        self.updated_rel_group_1_elem = RelationshipElementFactory.build(
            action=DiffAction.UPDATED, properties={self.updated_rel_group_1_elem_owner_property}, conflict=None
        )
        self.updated_rel_group = RelationshipGroupFactory.build(
            action=DiffAction.UPDATED, relationships={self.updated_rel_group_1_elem}, nodes=set()
        )

    async def test_get_non_existent_diff(self, diff_repository: DiffRepository):
        right_now = Timestamp()
        enriched_diffs = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[self.diff_branch_name],
            from_time=right_now,
            to_time=right_now.add_delta(hours=1),
        )
        assert len(enriched_diffs) == 0

    async def test_save_and_retrieve(self, diff_repository: DiffRepository, reset_database):
        self.enriched_diff.nodes = {self.updated_node_diff}
        self.updated_node_diff.attributes = {self.removed_attribute, self.updated_attribute}
        self.updated_node_diff.relationships = {self.updated_rel_group}
        await diff_repository.save(enriched_diff=self.enriched_diff)

        retrieved = await diff_repository.get(
            base_branch_name=self.base_branch_name,
            diff_branch_names=[self.diff_branch_name],
            from_time=Timestamp(self.diff_from_time),
            to_time=Timestamp(self.diff_to_time),
        )
        assert len(retrieved) == 1
        diff_root = retrieved[0]
        assert diff_root == self.enriched_diff

        # relationship conflict element
        # node parents
        # multiples of everything
        # filtering
