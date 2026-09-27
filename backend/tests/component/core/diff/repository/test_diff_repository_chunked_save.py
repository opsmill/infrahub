from dataclasses import replace
from typing import Generator

import pytest

from infrahub import config
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.model.path import (
    EnrichedDiffNode,
    EnrichedDiffRoot,
    EnrichedDiffs,
    EnrichedDiffSingleRelationship,
    NameTrackingId,
)
from infrahub.core.diff.parent_node_adder import DiffParentNodeAdder
from infrahub.core.diff.repository.deserializer import EnrichedDiffDeserializer
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from tests.helpers.diff_factories import (
    EnrichedAttributeFactory,
    EnrichedNodeFactory,
    EnrichedPropertyFactory,
    EnrichedRelationshipElementFactory,
    EnrichedRelationshipGroupFactory,
    EnrichedRootFactory,
)

from .base import DiffRepositoryTestBase

ELEMENT_PROPERTY_TYPES = [DatabaseEdgeType.IS_RELATED, DatabaseEdgeType.IS_PROTECTED]


def build_element(path_identifier: str) -> EnrichedDiffSingleRelationship:
    return EnrichedRelationshipElementFactory.build(
        path_identifier=path_identifier,
        properties={EnrichedPropertyFactory.build(property_type=ptype) for ptype in ELEMENT_PROPERTY_TYPES},
    )


class TestDiffRepositoryChunkedSave(DiffRepositoryTestBase):
    """Nodes whose property count reaches max_save_batch_size are saved in several transactions."""

    base_branch_name = "main"
    diff_branch_name = "branch"
    from_time = Timestamp("2026-09-10T00:00:00Z")
    to_time = Timestamp("2026-09-12T00:00:00Z")

    @pytest.fixture
    def diff_repository(self, db: InfrahubDatabase) -> Generator[DiffRepository, None, None]:
        original_depth = config.SETTINGS.database.max_depth_search_hierarchy
        config.SETTINGS.database.max_depth_search_hierarchy = 10
        yield DiffRepository(
            db=db, deserializer=EnrichedDiffDeserializer(DiffParentNodeAdder()), max_save_batch_size=10
        )
        config.SETTINGS.database.max_depth_search_hierarchy = original_depth

    def build_big_node(self, relationship_sizes: list[int]) -> EnrichedDiffNode:
        node = EnrichedNodeFactory.build(
            attributes={
                EnrichedAttributeFactory.build(
                    properties={EnrichedPropertyFactory.build(property_type=DatabaseEdgeType.HAS_VALUE)}
                )
            },
            relationships=set(),
        )
        for index, size in enumerate(relationship_sizes):
            path = f"data/{node.uuid}/rel{index}"
            node.relationships.add(
                EnrichedRelationshipGroupFactory.build(
                    name=f"rel{index}",
                    path_identifier=path,
                    nodes=set(),
                    relationships={build_element(path_identifier=path) for _ in range(size)},
                )
            )
        return node

    def build_diffs(self, branch_nodes: set[EnrichedDiffNode]) -> EnrichedDiffs:
        branch_root: EnrichedDiffRoot = EnrichedRootFactory.build(
            base_branch_name=self.base_branch_name,
            diff_branch_name=self.diff_branch_name,
            from_time=self.from_time,
            to_time=self.to_time,
            nodes=branch_nodes,
            tracking_id=NameTrackingId(name="chunked"),
        )
        base_root: EnrichedDiffRoot = EnrichedRootFactory.build(
            base_branch_name=self.base_branch_name,
            diff_branch_name=self.base_branch_name,
            from_time=self.from_time,
            to_time=self.to_time,
            nodes=set(),
            tracking_id=NameTrackingId(name="chunked"),
            partner_uuid=branch_root.uuid,
        )
        branch_root.partner_uuid = base_root.uuid
        return EnrichedDiffs(
            base_branch_name=self.base_branch_name,
            diff_branch_name=self.diff_branch_name,
            base_branch_diff=base_root,
            diff_branch_diff=branch_root,
        )

    async def get_branch_diff(self, diff_repository: DiffRepository) -> EnrichedDiffRoot:
        retrieved = await diff_repository.get_pairs(
            base_branch_name=self.base_branch_name,
            diff_branch_name=self.diff_branch_name,
            from_time=self.from_time,
            to_time=self.to_time,
        )
        assert len(retrieved) == 1
        branch_diff = retrieved[0].diff_branch_diff
        branch_diff.exists_on_database = False
        return branch_diff

    async def test_oversized_node_round_trip(self, diff_repository: DiffRepository, reset_database: None) -> None:
        big_node = self.build_big_node(relationship_sizes=[60])
        small_node = self.build_diff_node(num_sub_fields=1, no_recurse=True)
        enriched_diffs = self.build_diffs(branch_nodes={big_node, small_node})

        await diff_repository.save(enriched_diffs=enriched_diffs, do_summary_counts=False)

        assert await self.get_branch_diff(diff_repository) == enriched_diffs.diff_branch_diff

    async def test_chunks_spanning_several_relationships(
        self, diff_repository: DiffRepository, reset_database: None
    ) -> None:
        big_node = self.build_big_node(relationship_sizes=[7, 13, 4])
        enriched_diffs = self.build_diffs(branch_nodes={big_node})

        await diff_repository.save(enriched_diffs=enriched_diffs, do_summary_counts=False)

        assert await self.get_branch_diff(diff_repository) == enriched_diffs.diff_branch_diff

    async def test_resave_removes_stale_elements_without_duplicates(
        self, diff_repository: DiffRepository, reset_database: None
    ) -> None:
        big_node = self.build_big_node(relationship_sizes=[40])
        enriched_diffs = self.build_diffs(branch_nodes={big_node})
        await diff_repository.save(enriched_diffs=enriched_diffs, do_summary_counts=False)

        relationship = next(iter(big_node.relationships))
        kept = sorted(relationship.relationships, key=lambda e: e.peer_id)[:25]
        added = {build_element(path_identifier=relationship.path_identifier) for _ in range(12)}
        updated_relationship = replace(relationship, relationships=set(kept) | added)
        updated_node = replace(big_node, relationships={updated_relationship})
        updated_diffs = self.build_diffs(branch_nodes={updated_node})
        updated_diffs.diff_branch_diff.uuid = enriched_diffs.diff_branch_diff.uuid
        updated_diffs.base_branch_diff.uuid = enriched_diffs.base_branch_diff.uuid
        updated_diffs.diff_branch_diff.partner_uuid = enriched_diffs.base_branch_diff.uuid
        updated_diffs.base_branch_diff.partner_uuid = enriched_diffs.diff_branch_diff.uuid
        await diff_repository.save(enriched_diffs=updated_diffs, do_summary_counts=False)

        retrieved = await self.get_branch_diff(diff_repository)
        retrieved_node = retrieved.get_node(node_identifier=big_node.identifier)
        retrieved_relationship = retrieved_node.get_relationship(name=relationship.name)
        peer_ids = [e.peer_id for e in retrieved_relationship.relationships]
        assert len(peer_ids) == len(set(peer_ids)) == 37
        assert set(peer_ids) == {e.peer_id for e in updated_relationship.relationships}
        assert retrieved == updated_diffs.diff_branch_diff
