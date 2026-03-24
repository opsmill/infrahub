import pytest

from infrahub.core.diff.model.path import (
    BranchTrackingId,
    EnrichedDiffs,
)
from infrahub.core.diff.parent_node_adder import DiffParentNodeAdder
from infrahub.core.diff.repository.deserializer import EnrichedDiffDeserializer
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.database import InfrahubDatabase

from .factories import (
    EnrichedAttributeFactory,
    EnrichedConflictFactory,
    EnrichedNodeFactory,
    EnrichedPropertyFactory,
    EnrichedRelationshipElementFactory,
    EnrichedRelationshipGroupFactory,
    EnrichedRootFactory,
)


class TestDiffGetAllConflicts:
    @pytest.fixture
    def diff_repository(self, db: InfrahubDatabase) -> DiffRepository:
        return DiffRepository(db=db, deserializer=EnrichedDiffDeserializer(DiffParentNodeAdder()))

    def _get_enriched_diffs(self) -> EnrichedDiffs:
        branch_diff_root = EnrichedRootFactory.build(
            base_branch_name="main", nodes={EnrichedNodeFactory.build() for _ in range(3)}
        )
        tracking_id = BranchTrackingId(name=branch_diff_root.diff_branch_name)
        branch_diff_root.tracking_id = tracking_id
        base_diff_root = EnrichedRootFactory.build(
            base_branch_name="main",
            diff_branch_name="main",
            partner_uuid=branch_diff_root.partner_uuid,
            tracking_id=tracking_id,
        )
        return EnrichedDiffs(
            base_branch_name="main",
            diff_branch_name=branch_diff_root.diff_branch_name,
            diff_branch_diff=branch_diff_root,
            base_branch_diff=base_diff_root,
        )

    async def test_query_initialization_failure(self, diff_repository: DiffRepository) -> None:
        with pytest.raises(ValueError, match=r"requires one and only one of `tracking_id` or `diff_id`"):
            [_ async for _ in diff_repository.get_all_conflicts_for_diff(diff_branch_name="a")]

        with pytest.raises(ValueError, match=r"requires one and only one of `tracking_id` or `diff_id`"):
            [
                _
                async for _ in diff_repository.get_all_conflicts_for_diff(
                    diff_branch_name="a", tracking_id=BranchTrackingId(name="abc"), diff_id="123"
                )
            ]

    async def test_no_conflicts(self, diff_repository: DiffRepository) -> None:
        enriched_diffs = self._get_enriched_diffs()
        await diff_repository.save(enriched_diffs=enriched_diffs)

        conflicts = {
            x: y
            async for x, y in diff_repository.get_all_conflicts_for_diff(
                diff_branch_name=enriched_diffs.diff_branch_name,
                tracking_id=BranchTrackingId(name=enriched_diffs.diff_branch_name),
            )
        }
        assert conflicts == {}

    async def test_get_node_level_conflict(self, diff_repository: DiffRepository) -> None:
        enriched_diffs = self._get_enriched_diffs()
        node = enriched_diffs.diff_branch_diff.nodes.pop()
        node.conflict = EnrichedConflictFactory.build()
        enriched_diffs.diff_branch_diff.nodes.add(node)
        await diff_repository.save(enriched_diffs=enriched_diffs)

        conflicts_map = {
            path_str: conflict
            async for path_str, conflict in diff_repository.get_all_conflicts_for_diff(
                diff_branch_name=enriched_diffs.diff_branch_name,
                tracking_id=BranchTrackingId(name=enriched_diffs.diff_branch_name),
            )
        }
        assert len(conflicts_map) == 1
        assert conflicts_map == {node.path_identifier: node.conflict}

        conflicts_map = {
            path_str: conflict
            async for path_str, conflict in diff_repository.get_all_conflicts_for_diff(
                diff_branch_name=enriched_diffs.diff_branch_name, diff_id=enriched_diffs.diff_branch_diff.uuid
            )
        }
        assert len(conflicts_map) == 1
        assert conflicts_map == {node.path_identifier: node.conflict}

    async def test_get_attribute_level_conflict(self, diff_repository: DiffRepository) -> None:
        enriched_diffs = self._get_enriched_diffs()
        node = enriched_diffs.diff_branch_diff.nodes.pop()
        diff_prop = EnrichedPropertyFactory.build(conflict=EnrichedConflictFactory.build())
        diff_attr = EnrichedAttributeFactory.build(properties={diff_prop})
        node.attributes.add(diff_attr)
        enriched_diffs.diff_branch_diff.nodes.add(node)
        await diff_repository.save(enriched_diffs=enriched_diffs)

        conflicts_map = {
            path_str: conflict
            async for path_str, conflict in diff_repository.get_all_conflicts_for_diff(
                diff_branch_name=enriched_diffs.diff_branch_name,
                tracking_id=BranchTrackingId(name=enriched_diffs.diff_branch_name),
            )
        }
        assert len(conflicts_map) == 1
        assert conflicts_map == {diff_prop.path_identifier: diff_prop.conflict}

        conflicts_map = {
            path_str: conflict
            async for path_str, conflict in diff_repository.get_all_conflicts_for_diff(
                diff_branch_name=enriched_diffs.diff_branch_name, diff_id=enriched_diffs.diff_branch_diff.uuid
            )
        }
        assert len(conflicts_map) == 1
        assert conflicts_map == {diff_prop.path_identifier: diff_prop.conflict}

    async def test_get_relationship_level_conflicts(self, diff_repository: DiffRepository) -> None:
        enriched_diffs = self._get_enriched_diffs()
        node = enriched_diffs.diff_branch_diff.nodes.pop()
        diff_rel_element = EnrichedRelationshipElementFactory.build(conflict=EnrichedConflictFactory.build())
        diff_rel = EnrichedRelationshipGroupFactory.build(relationships={diff_rel_element})
        node.relationships.add(diff_rel)
        enriched_diffs.diff_branch_diff.nodes.add(node)
        await diff_repository.save(enriched_diffs=enriched_diffs)

        conflicts_map = {
            path_str: conflict
            async for path_str, conflict in diff_repository.get_all_conflicts_for_diff(
                diff_branch_name=enriched_diffs.diff_branch_name,
                tracking_id=BranchTrackingId(name=enriched_diffs.diff_branch_name),
            )
        }
        assert len(conflicts_map) == 1
        assert conflicts_map == {diff_rel_element.path_identifier: diff_rel_element.conflict}

        conflicts_map = {
            path_str: conflict
            async for path_str, conflict in diff_repository.get_all_conflicts_for_diff(
                diff_branch_name=enriched_diffs.diff_branch_name, diff_id=enriched_diffs.diff_branch_diff.uuid
            )
        }
        assert len(conflicts_map) == 1
        assert conflicts_map == {diff_rel_element.path_identifier: diff_rel_element.conflict}

    async def test_get_relationship_property_level_conflicts(self, diff_repository: DiffRepository) -> None:
        enriched_diffs = self._get_enriched_diffs()
        node = enriched_diffs.diff_branch_diff.nodes.pop()
        diff_prop = EnrichedPropertyFactory.build(conflict=EnrichedConflictFactory.build())
        node.relationships.add(
            EnrichedRelationshipGroupFactory.build(
                relationships={EnrichedRelationshipElementFactory.build(properties={diff_prop})}
            )
        )
        enriched_diffs.diff_branch_diff.nodes.add(node)
        await diff_repository.save(enriched_diffs=enriched_diffs)

        conflicts_map = {
            path_str: conflict
            async for path_str, conflict in diff_repository.get_all_conflicts_for_diff(
                diff_branch_name=enriched_diffs.diff_branch_name,
                tracking_id=BranchTrackingId(name=enriched_diffs.diff_branch_name),
            )
        }
        assert len(conflicts_map) == 1
        assert conflicts_map == {diff_prop.path_identifier: diff_prop.conflict}

        conflicts_map = {
            path_str: conflict
            async for path_str, conflict in diff_repository.get_all_conflicts_for_diff(
                diff_branch_name=enriched_diffs.diff_branch_name, diff_id=enriched_diffs.diff_branch_diff.uuid
            )
        }
        assert len(conflicts_map) == 1
        assert conflicts_map == {diff_prop.path_identifier: diff_prop.conflict}
