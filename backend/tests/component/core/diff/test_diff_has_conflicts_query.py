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


class TestDiffHasConflictsCheck:
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
            await diff_repository.diff_has_conflicts(diff_branch_name="a")

        with pytest.raises(ValueError, match=r"requires one and only one of `tracking_id` or `diff_id`"):
            await diff_repository.diff_has_conflicts(
                diff_branch_name="a", tracking_id=BranchTrackingId(name="abc"), diff_id="123"
            )

    async def test_has_conflicts_false(self, diff_repository: DiffRepository) -> None:
        enriched_diffs = self._get_enriched_diffs()
        await diff_repository.save(enriched_diffs=enriched_diffs)

        has_conflicts = await diff_repository.diff_has_conflicts(
            diff_branch_name=enriched_diffs.diff_branch_name,
            tracking_id=BranchTrackingId(name=enriched_diffs.diff_branch_name),
        )
        assert has_conflicts is False

    async def test_has_conflicts_true_node(self, diff_repository: DiffRepository) -> None:
        enriched_diffs = self._get_enriched_diffs()
        node = enriched_diffs.diff_branch_diff.nodes.pop()
        node.conflict = EnrichedConflictFactory.build()
        enriched_diffs.diff_branch_diff.nodes.add(node)
        await diff_repository.save(enriched_diffs=enriched_diffs)

        has_conflicts = await diff_repository.diff_has_conflicts(
            diff_branch_name=enriched_diffs.diff_branch_name,
            tracking_id=BranchTrackingId(name=enriched_diffs.diff_branch_name),
        )
        assert has_conflicts is True

        has_conflicts = await diff_repository.diff_has_conflicts(
            diff_branch_name=enriched_diffs.diff_branch_name, diff_id=enriched_diffs.diff_branch_diff.uuid
        )
        assert has_conflicts is True

    async def test_has_conflicts_true_attribute_property(self, diff_repository: DiffRepository) -> None:
        enriched_diffs = self._get_enriched_diffs()
        node = enriched_diffs.diff_branch_diff.nodes.pop()
        node.attributes.add(
            EnrichedAttributeFactory.build(
                properties={EnrichedPropertyFactory.build(conflict=EnrichedConflictFactory.build())}
            )
        )
        enriched_diffs.diff_branch_diff.nodes.add(node)
        await diff_repository.save(enriched_diffs=enriched_diffs)

        has_conflicts = await diff_repository.diff_has_conflicts(
            diff_branch_name=enriched_diffs.diff_branch_name,
            tracking_id=BranchTrackingId(name=enriched_diffs.diff_branch_name),
        )
        assert has_conflicts is True

        has_conflicts = await diff_repository.diff_has_conflicts(
            diff_branch_name=enriched_diffs.diff_branch_name, diff_id=enriched_diffs.diff_branch_diff.uuid
        )
        assert has_conflicts is True

    async def test_has_conflicts_true_relationship(self, diff_repository: DiffRepository) -> None:
        enriched_diffs = self._get_enriched_diffs()
        node = enriched_diffs.diff_branch_diff.nodes.pop()
        node.relationships.add(
            EnrichedRelationshipGroupFactory.build(
                relationships={EnrichedRelationshipElementFactory.build(conflict=EnrichedConflictFactory.build())}
            )
        )
        enriched_diffs.diff_branch_diff.nodes.add(node)
        await diff_repository.save(enriched_diffs=enriched_diffs)

        has_conflicts = await diff_repository.diff_has_conflicts(
            diff_branch_name=enriched_diffs.diff_branch_name,
            tracking_id=BranchTrackingId(name=enriched_diffs.diff_branch_name),
        )
        assert has_conflicts is True

        has_conflicts = await diff_repository.diff_has_conflicts(
            diff_branch_name=enriched_diffs.diff_branch_name, diff_id=enriched_diffs.diff_branch_diff.uuid
        )
        assert has_conflicts is True

    async def test_has_conflicts_true_relationship_property(self, diff_repository: DiffRepository) -> None:
        enriched_diffs = self._get_enriched_diffs()
        node = enriched_diffs.diff_branch_diff.nodes.pop()
        node.relationships.add(
            EnrichedRelationshipGroupFactory.build(
                relationships={
                    EnrichedRelationshipElementFactory.build(
                        properties={EnrichedPropertyFactory.build(conflict=EnrichedConflictFactory.build())}
                    )
                }
            )
        )
        enriched_diffs.diff_branch_diff.nodes.add(node)
        await diff_repository.save(enriched_diffs=enriched_diffs)

        has_conflicts = await diff_repository.diff_has_conflicts(
            diff_branch_name=enriched_diffs.diff_branch_name,
            tracking_id=BranchTrackingId(name=enriched_diffs.diff_branch_name),
        )
        assert has_conflicts is True

        has_conflicts = await diff_repository.diff_has_conflicts(
            diff_branch_name=enriched_diffs.diff_branch_name, diff_id=enriched_diffs.diff_branch_diff.uuid
        )
        assert has_conflicts is True
