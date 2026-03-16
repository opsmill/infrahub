"""
Tests for Migration 061: Link ProposedChanges to DiffRoots.

Test scenarios:
1. DiffRoots with no appropriate proposed change - should remain unlinked
2. Proposed changes with no appropriate diff - should remain unlinked
3. Open proposed changes with multiple diffs on the same branch - all diffs should be linked
4. Merged proposed changes with multiple diffs on the same branch - only diffs in merge window linked
5. Canceled proposed changes - should not be linked
6. Closed proposed changes - should not be linked
7. Proposed changes stuck in merging state - should not be linked (not open, not merged)
"""

from typing import Generator
from uuid import uuid4

import pytest

from infrahub import config
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.diff.model.path import BranchTrackingId, EnrichedDiffs, NameTrackingId, TrackingId
from infrahub.core.diff.parent_node_adder import DiffParentNodeAdder
from infrahub.core.diff.repository.deserializer import EnrichedDiffDeserializer
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.migrations.graph.m061_link_proposed_changes_to_diff_roots import Migration061
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from tests.component.core.diff.factories import EnrichedNodeFactory, EnrichedRootFactory


class TestMigration061:
    """Test migration 061 that links ProposedChanges to DiffRoots."""

    @pytest.fixture
    def diff_repository(self, db: InfrahubDatabase) -> Generator[DiffRepository, None, None]:
        original_depth = config.SETTINGS.database.max_depth_search_hierarchy
        original_size = config.SETTINGS.database.query_size_limit
        config.SETTINGS.database.max_depth_search_hierarchy = 10
        config.SETTINGS.database.query_size_limit = 50
        diff_repository = DiffRepository(
            db=db, deserializer=EnrichedDiffDeserializer(DiffParentNodeAdder()), max_save_batch_size=30
        )
        yield diff_repository
        config.SETTINGS.database.max_depth_search_hierarchy = original_depth
        config.SETTINGS.database.query_size_limit = original_size

    async def _create_proposed_change(
        self,
        db: InfrahubDatabase,
        name: str,
        source_branch: str,
        state: str = "open",
    ) -> Node:
        """Create a ProposedChange using proper Node API."""
        pc = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
        await pc.new(
            db=db,
            name=name,
            source_branch=source_branch,
            destination_branch="main",
            state=state,
        )
        await pc.save(db=db)
        return pc

    async def _update_proposed_change_state(
        self,
        db: InfrahubDatabase,
        pc: Node,
        new_state: str,
    ) -> None:
        """Update the state of a ProposedChange."""
        pc.state.value = new_state
        await pc.save(db=db)

    def _build_nodes(self) -> set:
        """Build a minimal set of diff nodes for testing."""
        return {EnrichedNodeFactory.build(relationships=set(), attributes=set())}

    async def _create_diff_pair(
        self,
        diff_repository: DiffRepository,
        diff_branch_name: str,
        base_branch_name: str,
        from_time: Timestamp,
        to_time: Timestamp,
        is_merged: bool = False,
        tracking_id: TrackingId | None = None,
    ) -> tuple[str, str]:
        """
        Create a pair of DiffRoots using the proper DiffRepository API.

        Returns tuple of (diff_branch_root_uuid, base_branch_root_uuid).
        """
        if tracking_id is None:
            tracking_id = BranchTrackingId(name=diff_branch_name)

        # Create diff branch root
        diff_root = EnrichedRootFactory.build(
            base_branch_name=base_branch_name,
            diff_branch_name=diff_branch_name,
            from_time=from_time,
            to_time=to_time,
            nodes=self._build_nodes(),
            tracking_id=tracking_id,
            uuid=str(uuid4()),
        )

        # Create base branch root (partner)
        base_root = EnrichedRootFactory.build(
            base_branch_name=base_branch_name,
            diff_branch_name=base_branch_name,
            from_time=from_time,
            to_time=to_time,
            nodes=self._build_nodes(),
            tracking_id=tracking_id,
            uuid=str(uuid4()),
        )

        # Link partners
        diff_root.partner_uuid = base_root.uuid
        base_root.partner_uuid = diff_root.uuid

        # Create EnrichedDiffs wrapper
        enriched_diffs = EnrichedDiffs(
            base_branch_name=base_branch_name,
            diff_branch_name=diff_branch_name,
            diff_branch_diff=diff_root,
            base_branch_diff=base_root,
        )

        # Save to database
        await diff_repository.save(enriched_diffs=enriched_diffs, do_summary_counts=False)

        # Set is_merged flag if needed
        if is_merged is True:
            await self._set_diff_root_merged(diff_repository.db, [diff_root.uuid, base_root.uuid])

        return diff_root.uuid, base_root.uuid

    async def _set_diff_root_merged(self, db: InfrahubDatabase, diff_root_uuids: list[str]) -> None:
        """Set is_merged=TRUE on DiffRoot nodes with the given UUIDs."""
        query = """
        MATCH (dr:DiffRoot)
        WHERE dr.uuid IN $uuids
        SET dr.is_merged = TRUE
        """
        await db.execute_query(query=query, params={"uuids": diff_root_uuids})

    async def _get_linked_diff_roots(self, diff_repository: DiffRepository, pc_uuid: str) -> list[str]:
        """Get all DiffRoot UUIDs linked to a proposed change."""
        roots_metadata = await diff_repository.get_roots_metadata(proposed_change_id=pc_uuid, exclude_merged=False)
        return sorted([r.uuid for r in roots_metadata])

    async def _get_unlinked_diff_roots(self, diff_repository: DiffRepository) -> list[str]:
        """Get all DiffRoot UUIDs that are not linked to any proposed change."""
        all_roots = await diff_repository.get_roots_metadata(exclude_merged=False)
        return sorted([r.uuid for r in all_roots if r.proposed_change_id is None])

    async def test_migration_061_comprehensive(
        self,
        db: InfrahubDatabase,
        register_core_models_schema: SchemaBranch,
        default_branch: Branch,
        diff_repository: DiffRepository,
    ) -> None:
        """
        Comprehensive test covering all scenarios for migration 061.
        """
        # Create timestamps for testing
        base_time = Timestamp()
        t0 = base_time.add(seconds=-600)
        t1 = base_time.add(seconds=-500)
        t2 = base_time.add(seconds=-400)

        # =========================================================================
        # SETUP: Create test data
        # =========================================================================

        # ----- Scenario 1: DiffRoots with no appropriate proposed change -----
        # Create a branch with no PC
        orphan_branch = await create_branch(db=db, branch_name="orphan-branch")
        orphan_diff_uuid, orphan_base_uuid = await self._create_diff_pair(
            diff_repository=diff_repository,
            diff_branch_name=orphan_branch.name,
            base_branch_name="main",
            from_time=t0,
            to_time=t1,
        )

        # ----- Scenario 2: Proposed changes with no appropriate diff -----
        no_diff_branch = await create_branch(db=db, branch_name="no-diff-branch")
        pc_no_diff = await self._create_proposed_change(
            db=db,
            name="pc-no-diff",
            source_branch=no_diff_branch.name,
            state="open",
        )

        # ----- Scenario 3: Open PC with different diff types on the same branch -----
        # Only the unmerged diff with BranchTrackingId should be linked
        feature_a_branch = await create_branch(db=db, branch_name="feature-a")
        pc_open = await self._create_proposed_change(
            db=db,
            name="pc-open",
            source_branch=feature_a_branch.name,
            state="open",
        )
        # Unmerged DiffRoot with BranchTrackingId (should be linked)
        open_branch_diff_uuid, open_branch_base_uuid = await self._create_diff_pair(
            diff_repository=diff_repository,
            diff_branch_name=feature_a_branch.name,
            base_branch_name="main",
            from_time=t0,
            to_time=t1,
        )
        # Merged DiffRoot with BranchTrackingId (should NOT be linked - PC is open, not merged)
        merged_branch_diff_uuid, merged_branch_base_uuid = await self._create_diff_pair(
            diff_repository=diff_repository,
            diff_branch_name=feature_a_branch.name,
            base_branch_name="main",
            from_time=t1,
            to_time=t2,
            is_merged=True,
        )
        # Unmerged DiffRoot with NameTrackingId (should NOT be linked - wrong tracking_id type)
        name_tracking_diff_uuid, name_tracking_base_uuid = await self._create_diff_pair(
            diff_repository=diff_repository,
            diff_branch_name=feature_a_branch.name,
            base_branch_name="main",
            from_time=t0,
            to_time=t1,
            tracking_id=NameTrackingId(name="some-named-diff"),
        )

        # ----- Scenario 4: Merged PC with multiple diffs - only those in window should link -----
        feature_b_branch = await create_branch(db=db, branch_name="feature-b")
        pc_merged_multi = await self._create_proposed_change(
            db=db,
            name="pc-merged-multi",
            source_branch=feature_b_branch.name,
            state="open",
        )
        # Simulate state transitions: open -> merging -> merged
        await self._update_proposed_change_state(db, pc_merged_multi, "merging")
        time_during_merge = Timestamp()
        await self._update_proposed_change_state(db, pc_merged_multi, "merged")

        # DiffRoots for merged PC scenario
        # Before merge window (should NOT be linked)
        before_merge_diff_uuid, before_merge_base_uuid = await self._create_diff_pair(
            diff_repository=diff_repository,
            diff_branch_name=feature_b_branch.name,
            base_branch_name="main",
            from_time=t0,
            to_time=t0.add(seconds=10),  # Before any state change
            is_merged=True,
        )
        # In merge window (should be linked)
        in_merge_diff_uuid, in_merge_base_uuid = await self._create_diff_pair(
            diff_repository=diff_repository,
            diff_branch_name=feature_b_branch.name,
            base_branch_name="main",
            from_time=t1,
            to_time=time_during_merge,
            is_merged=True,
        )

        # ----- Scenario 5: Canceled proposed change -----
        feature_canceled_branch = await create_branch(db=db, branch_name="feature-canceled")
        pc_canceled = await self._create_proposed_change(
            db=db,
            name="pc-canceled",
            source_branch=feature_canceled_branch.name,
            state="canceled",
        )
        canceled_diff_uuid, canceled_base_uuid = await self._create_diff_pair(
            diff_repository=diff_repository,
            diff_branch_name=feature_canceled_branch.name,
            base_branch_name="main",
            from_time=t0,
            to_time=t1,
        )

        # ----- Scenario 6: Closed proposed change -----
        feature_closed_branch = await create_branch(db=db, branch_name="feature-closed")
        pc_closed = await self._create_proposed_change(
            db=db,
            name="pc-closed",
            source_branch=feature_closed_branch.name,
            state="closed",
        )
        closed_diff_uuid, closed_base_uuid = await self._create_diff_pair(
            diff_repository=diff_repository,
            diff_branch_name=feature_closed_branch.name,
            base_branch_name="main",
            from_time=t0,
            to_time=t1,
        )

        # ----- Scenario 7: Proposed change stuck in merging state -----
        feature_merging_branch = await create_branch(db=db, branch_name="feature-merging")
        pc_merging = await self._create_proposed_change(
            db=db,
            name="pc-merging",
            source_branch=feature_merging_branch.name,
            state="merging",
        )
        merging_diff_uuid, merging_base_uuid = await self._create_diff_pair(
            diff_repository=diff_repository,
            diff_branch_name=feature_merging_branch.name,
            base_branch_name="main",
            from_time=t0,
            to_time=t1,
        )

        # =========================================================================
        # EXECUTE: Run the migration
        # =========================================================================
        migration = Migration061()
        await migration.execute(MigrationInput(db=db))
        result = await migration.validate_migration(db=db)
        assert result.success

        # =========================================================================
        # VERIFY: Check results for each scenario
        # =========================================================================

        unlinked = await self._get_unlinked_diff_roots(diff_repository)

        # ----- Scenario 1: Orphan DiffRoots should remain unlinked -----
        assert orphan_diff_uuid in unlinked, "Orphan DiffRoot (diff perspective) should remain unlinked"
        assert orphan_base_uuid in unlinked, "Orphan DiffRoot (base perspective) should remain unlinked"

        # ----- Scenario 2: PC with no diff should have no linked DiffRoots -----
        pc_no_diff_links = await self._get_linked_diff_roots(diff_repository, pc_no_diff.id)
        assert pc_no_diff_links == [], "PC with no matching DiffRoot should have no links"

        # ----- Scenario 3: Open PC should only be linked to unmerged DiffRoot with BranchTrackingId -----
        pc_open_links = await self._get_linked_diff_roots(diff_repository, pc_open.id)
        # Unmerged with BranchTrackingId should be linked
        assert open_branch_diff_uuid in pc_open_links, "Unmerged BranchTrackingId DiffRoot should be linked"
        assert open_branch_base_uuid in pc_open_links, "Unmerged BranchTrackingId partner should be linked"
        # Merged with BranchTrackingId should NOT be linked (PC is open, not merged)
        assert merged_branch_diff_uuid not in pc_open_links, "Merged DiffRoot should not be linked to open PC"
        assert merged_branch_base_uuid not in pc_open_links, "Merged partner should not be linked to open PC"
        # NameTrackingId should NOT be linked (wrong tracking_id type)
        assert name_tracking_diff_uuid not in pc_open_links, "NameTrackingId DiffRoot should not be linked"
        assert name_tracking_base_uuid not in pc_open_links, "NameTrackingId partner should not be linked"
        assert len(pc_open_links) == 2, "Open PC should have exactly 2 linked DiffRoots (1 pair)"
        # Verify the others are unlinked
        assert merged_branch_diff_uuid in unlinked, "Merged DiffRoot should be unlinked"
        assert name_tracking_diff_uuid in unlinked, "NameTrackingId DiffRoot should be unlinked"

        # ----- Scenario 4: Merged PC should only be linked to DiffRoots in merge window -----
        pc_merged_links = await self._get_linked_diff_roots(diff_repository, pc_merged_multi.id)
        assert before_merge_diff_uuid not in pc_merged_links, "DiffRoot before merge window should not be linked"
        assert before_merge_base_uuid not in pc_merged_links, "Partner before merge window should not be linked"
        assert in_merge_diff_uuid in pc_merged_links, "DiffRoot in merge window should be linked"
        assert in_merge_base_uuid in pc_merged_links, "Partner in merge window should be linked"
        assert len(pc_merged_links) == 2, "Merged PC should have exactly 2 linked DiffRoots (1 pair in window)"

        # ----- Scenario 5: Canceled PC should not be linked -----
        pc_canceled_links = await self._get_linked_diff_roots(diff_repository, pc_canceled.id)
        assert pc_canceled_links == [], "Canceled PC should have no links"
        assert canceled_diff_uuid in unlinked, "DiffRoot for canceled PC should remain unlinked"
        assert canceled_base_uuid in unlinked, "Partner for canceled PC should remain unlinked"

        # ----- Scenario 6: Closed PC should not be linked -----
        pc_closed_links = await self._get_linked_diff_roots(diff_repository, pc_closed.id)
        assert pc_closed_links == [], "Closed PC should have no links"
        assert closed_diff_uuid in unlinked, "DiffRoot for closed PC should remain unlinked"
        assert closed_base_uuid in unlinked, "Partner for closed PC should remain unlinked"

        # ----- Scenario 7: Merging PC should not be linked -----
        pc_merging_links = await self._get_linked_diff_roots(diff_repository, pc_merging.id)
        assert pc_merging_links == [], "PC stuck in merging state should have no links"
        assert merging_diff_uuid in unlinked, "DiffRoot for merging PC should remain unlinked"
        assert merging_base_uuid in unlinked, "Partner for merging PC should remain unlinked"
