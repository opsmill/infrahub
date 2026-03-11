"""
Tests for Migration 066: Freeze orphaned branch-tracking diffs.

The migration freezes DiffRoots (and their partners) whose tracking_id starts with "branch."
when the associated Branch no longer exists, has been merged, or has a different branched_from
time (indicating a new branch was created with the same name).

Test scenarios (all validated in a single test, plus idempotency check):
1. Active branch with matching branched_from - diffs should NOT be frozen
2. Deleted branch (no Branch node) - diffs SHOULD be frozen
3. Merged branch (status=MERGED) - diffs SHOULD be frozen
4. Branch with different branched_from time (name reuse) - old diffs SHOULD be frozen, new diffs NOT
5. Already-frozen diffs - should remain unchanged
6. Branch merged, deleted, then new branch created with the same name - old diffs frozen, new diffs untouched
"""

from dataclasses import dataclass
from uuid import uuid4

import pytest
from infrahub_sdk.timestamp import Timestamp

from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.diff.model.path import BranchTrackingId, EnrichedDiffs, FrozenTrackingId
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.migrations.graph.m066_freeze_orphaned_branch_tracking_diffs import Migration066
from infrahub.core.migrations.shared import MigrationInput
from infrahub.database import InfrahubDatabase
from infrahub.dependencies.registry import get_component_registry
from tests.component.core.diff.factories import EnrichedRootFactory


@dataclass
class DiffExpectation:
    name: str
    uuids: list[str]
    expected_tracking_id: str
    expected_frozen: bool


class TestMigration066:
    @pytest.fixture
    async def diff_repository(self, db: InfrahubDatabase, default_branch: Branch) -> DiffRepository:
        component_registry = get_component_registry()
        return await component_registry.get_component(DiffRepository, db=db, branch=default_branch)

    async def _create_diff_pair(
        self,
        diff_repository: DiffRepository,
        branch_name: str,
        from_time: Timestamp,
        to_time: Timestamp,
    ) -> tuple[str, str]:
        """Create a branch-tracking diff pair. Returns (branch_diff_uuid, base_diff_uuid)."""
        tracking_id = BranchTrackingId(name=branch_name)

        diff_root = EnrichedRootFactory.build(
            base_branch_name="main",
            diff_branch_name=branch_name,
            from_time=from_time,
            to_time=to_time,
            nodes=set(),
            tracking_id=tracking_id,
            uuid=str(uuid4()),
        )
        base_root = EnrichedRootFactory.build(
            base_branch_name="main",
            diff_branch_name="main",
            from_time=from_time,
            to_time=to_time,
            nodes=set(),
            tracking_id=tracking_id,
            uuid=str(uuid4()),
        )
        diff_root.partner_uuid = base_root.uuid
        base_root.partner_uuid = diff_root.uuid

        enriched_diffs = EnrichedDiffs(
            base_branch_name="main",
            diff_branch_name=branch_name,
            diff_branch_diff=diff_root,
            base_branch_diff=base_root,
        )
        await diff_repository.save(enriched_diffs=enriched_diffs, do_summary_counts=False)
        return diff_root.uuid, base_root.uuid

    async def _validate_expectations(
        self,
        diff_repository: DiffRepository,
        expectations: list[DiffExpectation],
    ) -> None:
        """Validate tracking_id and is_frozen for groups of diff uuids."""
        all_roots = await diff_repository.get_roots_metadata(exclude_merged=False)
        roots_by_uuid = {r.uuid: r for r in all_roots}

        for expectation in expectations:
            for uuid in expectation.uuids:
                assert uuid in roots_by_uuid, f"[{expectation.name}] uuid={uuid}: not found in diff roots"
                metadata = roots_by_uuid[uuid]
                assert metadata.tracking_id.serialize() == expectation.expected_tracking_id, (
                    f"[{expectation.name}] uuid={uuid}: expected tracking_id={expectation.expected_tracking_id}, "
                    f"got {metadata.tracking_id.serialize()}"
                )
                assert metadata.is_frozen is expectation.expected_frozen, (
                    f"[{expectation.name}] uuid={uuid}: expected is_frozen={expectation.expected_frozen}, "
                    f"got {metadata.is_frozen}"
                )

    async def test_migration_066(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        diff_repository: DiffRepository,
    ) -> None:
        """All migration scenarios validated together, with idempotency check."""
        expectations: list[DiffExpectation] = []

        # --- Scenario 1: Active branch - diffs should NOT be frozen ---
        active_branch = await create_branch(db=db, branch_name="active-branch")
        active_from = Timestamp(active_branch.get_branched_from())
        active_diff, active_base = await self._create_diff_pair(
            diff_repository=diff_repository,
            branch_name=active_branch.name,
            from_time=active_from,
            to_time=active_from.add(seconds=60),
        )
        expectations.append(
            DiffExpectation(
                name="active branch not frozen",
                uuids=[active_diff, active_base],
                expected_tracking_id=BranchTrackingId(name=active_branch.name).serialize(),
                expected_frozen=False,
            )
        )

        # --- Scenario 2: Deleted branch - diffs SHOULD be frozen ---
        deleted_branch = await create_branch(db=db, branch_name="deleted-branch")
        deleted_from = Timestamp(deleted_branch.get_branched_from())
        deleted_diff, deleted_base = await self._create_diff_pair(
            diff_repository=diff_repository,
            branch_name=deleted_branch.name,
            from_time=deleted_from,
            to_time=deleted_from.add(seconds=60),
        )
        await deleted_branch.delete(db=db)
        expectations.append(
            DiffExpectation(
                name="deleted branch frozen",
                uuids=[deleted_diff, deleted_base],
                expected_tracking_id=FrozenTrackingId(name=deleted_branch.name).serialize(),
                expected_frozen=True,
            )
        )

        # --- Scenario 3: Merged branch - diffs SHOULD be frozen ---
        merged_branch = await create_branch(db=db, branch_name="merged-branch")
        merged_from = Timestamp(merged_branch.get_branched_from())
        merged_diff, merged_base = await self._create_diff_pair(
            diff_repository=diff_repository,
            branch_name=merged_branch.name,
            from_time=merged_from,
            to_time=merged_from.add(seconds=60),
        )
        merged_branch.status = BranchStatus.MERGED
        await merged_branch.save(db=db)
        await diff_repository.mark_tracking_ids_merged(tracking_ids=[BranchTrackingId(name=merged_branch.name)])
        expectations.append(
            DiffExpectation(
                name="merged branch frozen",
                uuids=[merged_diff, merged_base],
                expected_tracking_id=FrozenTrackingId(name=merged_branch.name).serialize(),
                expected_frozen=True,
            )
        )

        # --- Scenario 4: Branch name reuse - old diffs frozen, new diffs not ---
        reused_name = "reused-branch"
        reused_v1 = await create_branch(db=db, branch_name=reused_name)
        v1_from = Timestamp(reused_v1.get_branched_from())
        reused_v1_diff, reused_v1_base = await self._create_diff_pair(
            diff_repository=diff_repository,
            branch_name=reused_name,
            from_time=v1_from,
            to_time=v1_from.add(seconds=60),
        )
        await reused_v1.delete(db=db)
        reused_v2 = await create_branch(db=db, branch_name=reused_name)
        v2_from = Timestamp(reused_v2.get_branched_from())
        reused_v2_diff, reused_v2_base = await self._create_diff_pair(
            diff_repository=diff_repository,
            branch_name=reused_name,
            from_time=v2_from,
            to_time=v2_from.add(seconds=60),
        )
        expectations.extend(
            [
                DiffExpectation(
                    name="reused name v1 frozen",
                    uuids=[reused_v1_diff, reused_v1_base],
                    expected_tracking_id=FrozenTrackingId(name=reused_name).serialize(),
                    expected_frozen=True,
                ),
                DiffExpectation(
                    name="reused name v2 not frozen",
                    uuids=[reused_v2_diff, reused_v2_base],
                    expected_tracking_id=BranchTrackingId(name=reused_name).serialize(),
                    expected_frozen=False,
                ),
            ]
        )

        # --- Scenario 5: Already-frozen diffs - should remain unchanged ---
        frozen_branch = await create_branch(db=db, branch_name="already-frozen-branch")
        frozen_from = Timestamp(frozen_branch.get_branched_from())
        frozen_diff, frozen_base = await self._create_diff_pair(
            diff_repository=diff_repository,
            branch_name=frozen_branch.name,
            from_time=frozen_from,
            to_time=frozen_from.add(seconds=60),
        )
        await diff_repository.freeze_diffs_for_branch(branch_name=frozen_branch.name)
        await frozen_branch.delete(db=db)
        expectations.append(
            DiffExpectation(
                name="already frozen unchanged",
                uuids=[frozen_diff, frozen_base],
                expected_tracking_id=FrozenTrackingId(name=frozen_branch.name).serialize(),
                expected_frozen=True,
            )
        )

        # --- Scenario 6: Merged, deleted, then recreated with same name ---
        lifecycle_name = "lifecycle-branch"
        lifecycle_v1 = await create_branch(db=db, branch_name=lifecycle_name)
        lc_v1_from = Timestamp(lifecycle_v1.get_branched_from())
        lc_v1_diff, lc_v1_base = await self._create_diff_pair(
            diff_repository=diff_repository,
            branch_name=lifecycle_name,
            from_time=lc_v1_from,
            to_time=lc_v1_from.add(seconds=60),
        )
        lifecycle_v1.status = BranchStatus.MERGED
        await lifecycle_v1.save(db=db)
        await diff_repository.mark_tracking_ids_merged(tracking_ids=[BranchTrackingId(name=lifecycle_name)])
        await lifecycle_v1.delete(db=db)
        lifecycle_v2 = await create_branch(db=db, branch_name=lifecycle_name)
        lc_v2_from = Timestamp(lifecycle_v2.get_branched_from())
        lc_v2_diff, lc_v2_base = await self._create_diff_pair(
            diff_repository=diff_repository,
            branch_name=lifecycle_name,
            from_time=lc_v2_from,
            to_time=lc_v2_from.add(seconds=60),
        )
        expectations.extend(
            [
                DiffExpectation(
                    name="lifecycle v1 frozen",
                    uuids=[lc_v1_diff, lc_v1_base],
                    expected_tracking_id=FrozenTrackingId(name=lifecycle_name).serialize(),
                    expected_frozen=True,
                ),
                DiffExpectation(
                    name="lifecycle v2 not frozen",
                    uuids=[lc_v2_diff, lc_v2_base],
                    expected_tracking_id=BranchTrackingId(name=lifecycle_name).serialize(),
                    expected_frozen=False,
                ),
            ]
        )

        # --- Run migration and validate ---
        migration = Migration066()
        await migration.execute(MigrationInput(db=db))
        await self._validate_expectations(diff_repository, expectations)

        # --- Run again for idempotency and validate same expectations ---
        await migration.execute(MigrationInput(db=db))
        await self._validate_expectations(diff_repository, expectations)
