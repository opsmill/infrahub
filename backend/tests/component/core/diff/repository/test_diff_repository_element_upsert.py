from dataclasses import replace
from uuid import uuid4

import pytest

from infrahub.core.diff.model.path import (
    EnrichedDiffNode,
    EnrichedDiffs,
    NameTrackingId,
)
from infrahub.core.diff.parent_node_adder import DiffParentNodeAdder
from infrahub.core.diff.repository.deserializer import EnrichedDiffDeserializer
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from tests.helpers.diff_factories import EnrichedRelationshipElementFactory, EnrichedRootFactory

from .base import DiffRepositoryTestBase

ELEMENT_COUNTS_QUERY = """
MATCH (:DiffRoot {uuid: $root_uuid})-[:DIFF_HAS_NODE]->(:DiffNode)-[:DIFF_HAS_RELATIONSHIP]->(r:DiffRelationship)
MATCH (r)-[:DIFF_HAS_ELEMENT]->(e:DiffRelationshipElement)
RETURN r.name AS rel_name, e.peer_id AS peer_id, count(*) AS num_elements
"""


class TestDiffRepositoryElementUpsert(DiffRepositoryTestBase):
    diff_from_time = Timestamp("2024-06-15T18:35:20Z")
    diff_to_time = Timestamp("2024-06-15T18:49:40Z")

    @pytest.fixture
    def diff_repository(self, db: InfrahubDatabase) -> DiffRepository:
        return DiffRepository(db=db, deserializer=EnrichedDiffDeserializer(DiffParentNodeAdder()))

    def _build_diffs(self, nodes: set[EnrichedDiffNode]) -> EnrichedDiffs:
        tracking_id = NameTrackingId(name=f"diff-{uuid4()}")
        branch_diff = EnrichedRootFactory.build(
            base_branch_name=self.base_branch_name,
            diff_branch_name=self.diff_branch_name,
            from_time=self.diff_from_time,
            to_time=self.diff_to_time,
            nodes=nodes,
            tracking_id=tracking_id,
        )
        base_diff = EnrichedRootFactory.build(
            base_branch_name=self.base_branch_name,
            diff_branch_name=self.base_branch_name,
            from_time=self.diff_from_time,
            to_time=self.diff_to_time,
            nodes=set(),
            tracking_id=tracking_id,
            partner_uuid=branch_diff.uuid,
        )
        branch_diff.partner_uuid = base_diff.uuid
        return EnrichedDiffs(
            base_branch_name=self.base_branch_name,
            diff_branch_name=self.diff_branch_name,
            diff_branch_diff=branch_diff,
            base_branch_diff=base_diff,
        )

    async def _get_element_counts(self, db: InfrahubDatabase, root_uuid: str) -> dict[tuple[str, str], int]:
        results = await db.execute_query(query=ELEMENT_COUNTS_QUERY, params={"root_uuid": root_uuid})
        return {(result["rel_name"], result["peer_id"]): result["num_elements"] for result in results}

    @staticmethod
    def _expected_elements(node: EnrichedDiffNode) -> set[tuple[str, str]]:
        return {(rel.name, element.peer_id) for rel in node.relationships for element in rel.relationships}

    async def test_resave_keeps_one_element_per_peer(
        self, db: InfrahubDatabase, diff_repository: DiffRepository, reset_database: None
    ) -> None:
        node = self.build_diff_node(no_recurse=True, num_sub_fields=3)
        enriched_diffs = self._build_diffs(nodes={node})
        root_uuid = enriched_diffs.diff_branch_diff.uuid
        await diff_repository.save(enriched_diffs=enriched_diffs, do_summary_counts=False)

        # an unchanged re-save must reuse every element
        await diff_repository.save(enriched_diffs=enriched_diffs, do_summary_counts=False)
        counts = await self._get_element_counts(db=db, root_uuid=root_uuid)
        assert set(counts) == self._expected_elements(node)
        assert set(counts.values()) == {1}

        # remove one element and add another to the same relationship group, then re-save
        rel_group = next(iter(node.relationships))
        rel_group.relationships.pop()
        rel_group.relationships.add(EnrichedRelationshipElementFactory.build(properties=set()))
        await diff_repository.save(enriched_diffs=enriched_diffs, do_summary_counts=False)

        counts = await self._get_element_counts(db=db, root_uuid=root_uuid)
        assert set(counts) == self._expected_elements(node)
        assert set(counts.values()) == {1}

    async def test_same_element_path_and_peer_in_two_diffs_stay_separate(
        self, db: InfrahubDatabase, diff_repository: DiffRepository, reset_database: None
    ) -> None:
        # the element lookup seeks (path_identifier, peer_id) across all diffs, so an element of another diff
        # with the same path and peer must never be reused
        node = self.build_diff_node(no_recurse=True, num_sub_fields=3)
        first_diffs = self._build_diffs(nodes={node})
        second_diffs = self._build_diffs(nodes={replace(node)})
        await diff_repository.save(enriched_diffs=first_diffs, do_summary_counts=False)
        await diff_repository.save(enriched_diffs=second_diffs, do_summary_counts=False)
        await diff_repository.save(enriched_diffs=first_diffs, do_summary_counts=False)

        for enriched_diffs in (first_diffs, second_diffs):
            counts = await self._get_element_counts(db=db, root_uuid=enriched_diffs.diff_branch_diff.uuid)
            assert set(counts) == self._expected_elements(node)
            assert set(counts.values()) == {1}

        retrieved = await diff_repository.get_one(
            diff_branch_name=self.diff_branch_name, diff_id=second_diffs.diff_branch_diff.uuid
        )
        retrieved_node = next(iter(retrieved.nodes))
        assert self._expected_elements(retrieved_node) == self._expected_elements(node)
