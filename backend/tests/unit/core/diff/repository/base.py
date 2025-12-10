import random

import pytest

from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.model.path import (
    EnrichedDiffNode,
    EnrichedDiffRoot,
    EnrichedDiffs,
)
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import initialize_registry
from infrahub.core.utils import delete_all_nodes
from infrahub.database import InfrahubDatabase

from ..factories import (
    EnrichedAttributeFactory,
    EnrichedNodeFactory,
    EnrichedPropertyFactory,
    EnrichedRelationshipElementFactory,
    EnrichedRelationshipGroupFactory,
    EnrichedRootFactory,
)


class DiffRepositoryTestBase:
    base_branch_name = "main"
    diff_branch_name = "branch"

    @pytest.fixture(scope="class", autouse=True)
    async def _initialize_registry(self, db: InfrahubDatabase):
        await initialize_registry(db=db, initialize=True)

    @pytest.fixture
    async def reset_database(self, db: InfrahubDatabase, default_branch) -> None:
        await delete_all_nodes(db=db)

    def build_diff_node(self, num_sub_fields=2, no_recurse=False) -> EnrichedDiffNode:
        enriched_node = EnrichedNodeFactory.build(
            attributes={
                EnrichedAttributeFactory.build(
                    properties={
                        EnrichedPropertyFactory.build(property_type=det)
                        for det in random.sample(list(DatabaseEdgeType), num_sub_fields)
                    }
                )
                for _ in range(num_sub_fields)
            },
            relationships={
                EnrichedRelationshipGroupFactory.build(
                    relationships={
                        EnrichedRelationshipElementFactory.build(
                            properties={
                                EnrichedPropertyFactory.build(property_type=det)
                                for det in random.sample(list(DatabaseEdgeType), num_sub_fields)
                            }
                        )
                        for _ in range(num_sub_fields)
                    },
                    nodes=set(),
                )
                for _ in range(num_sub_fields)
            },
        )
        if no_recurse:
            return enriched_node
        if num_sub_fields > 1 and len(enriched_node.relationships) > 0:
            for relationship_group in enriched_node.relationships:
                relationship_group.nodes = {self.build_diff_node(num_sub_fields=num_sub_fields - 1)}
                break
        return enriched_node

    def _build_nodes(self, num_nodes: int, num_sub_fields: int) -> set[EnrichedDiffNode]:
        nodes = {self.build_diff_node(num_sub_fields=num_sub_fields) for _ in range(num_nodes)}

        # need to associate the generated child nodes with the DiffRoot directly
        # b/c that is how the data will actually be shaped
        nodes_to_check = list(nodes)
        all_nodes = set()
        while len(nodes_to_check) > 0:
            this_node = nodes_to_check.pop(0)
            all_nodes.add(this_node)
            for rel in this_node.relationships:
                nodes_to_check.extend(rel.nodes)
        return all_nodes

    async def _save_single_diff(
        self, diff_repository: DiffRepository, enriched_diff: EnrichedDiffRoot, do_summary_counts: bool = True
    ) -> EnrichedDiffs:
        base_diff = EnrichedRootFactory.build(
            base_branch_name=enriched_diff.base_branch_name,
            diff_branch_name=enriched_diff.base_branch_name,
            from_time=enriched_diff.from_time,
            to_time=enriched_diff.to_time,
            nodes=self._build_nodes(num_nodes=2, num_sub_fields=1),
            tracking_id=enriched_diff.tracking_id,
            partner_uuid=enriched_diff.uuid,
        )
        enriched_diff.partner_uuid = base_diff.uuid
        enriched_diffs = EnrichedDiffs(
            base_branch_name=self.base_branch_name,
            diff_branch_name=self.diff_branch_name,
            diff_branch_diff=enriched_diff,
            base_branch_diff=base_diff,
        )
        await diff_repository.save(enriched_diffs=enriched_diffs, do_summary_counts=do_summary_counts)
        return enriched_diffs
