from datetime import UTC

import pytest
from pendulum.datetime import DateTime
from polyfactory.factories import DataclassFactory

from infrahub import config
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


class TestDiffRepositorySaveAndLoad:
    @pytest.fixture(scope="class")
    async def reset_database(self, db: InfrahubDatabase):
        await delete_all_nodes(db=db)

    @pytest.fixture(scope="class")
    def diff_repository(self, db: InfrahubDatabase) -> DiffRepository:
        config.SETTINGS.database.max_depth_search_hierarchy = 10
        return DiffRepository(db=db)

    def build_diff_node(self, num_sub_fields=2) -> EnrichedDiffNode:
        enriched_node = NodeFactory.build(
            attributes={
                AttributeFactory.build(properties={PropertyFactory.build() for _ in range(num_sub_fields)})
                for _ in range(num_sub_fields)
            },
            relationships={
                RelationshipGroupFactory.build(
                    relationships={
                        RelationshipElementFactory.build(
                            properties={PropertyFactory.build() for _ in range(num_sub_fields)},
                        )
                        for _ in range(num_sub_fields)
                    },
                    nodes=set(),
                )
                for _ in range(num_sub_fields)
            },
        )
        if num_sub_fields > 1 and len(enriched_node.relationships) > 0:
            for relationship_group in enriched_node.relationships:
                relationship_group.nodes = {
                    self.build_diff_node(num_sub_fields=num_sub_fields - 1) for _ in range(num_sub_fields - 1)
                }
                break
        return enriched_node

    def setup_method(self):
        self.base_branch_name = "main"
        self.diff_branch_name = "diff"
        self.diff_from_time = DateTime(2024, 6, 15, 18, 35, 20, tzinfo=UTC)
        self.diff_to_time = DateTime(2024, 6, 15, 18, 49, 40, tzinfo=UTC)
        nodes = {self.build_diff_node(num_sub_fields=3) for _ in range(2)}

        # need to associate the generated child nodes with the DiffRoot directly
        # b/c that is how the data will actually be shaped
        nodes_to_check = list(nodes)
        all_nodes = set()
        while len(nodes_to_check) > 0:
            this_node = nodes_to_check.pop(0)
            all_nodes.add(this_node)
            for rel in this_node.relationships:
                for child_node in rel.nodes:
                    nodes_to_check.append(child_node)

        self.enriched_diff = RootFactory.build(
            base_branch_name=self.base_branch_name,
            diff_branch_name=self.diff_branch_name,
            from_time=Timestamp(self.diff_from_time),
            to_time=Timestamp(self.diff_to_time),
            nodes=all_nodes,
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
