import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from infrahub import config, lock
from infrahub.core.branch import Branch
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.diff_locker import DiffLocker
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.diff.merger.serializer import DiffMergeSerializer
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.merge import BranchMerger
from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase, get_db
from infrahub.dependencies.registry import get_component_registry


class TestDiffCoordinatorLocks:
    @pytest.fixture(autouse=True)
    async def _setup_core_schema(self, register_core_models_schema) -> None:
        return

    @pytest.fixture
    async def branch_with_data(self, db: InfrahubDatabase, default_branch: Branch, car_person_schema) -> Branch:
        lock.initialize_lock(local_only=True)
        branch_1 = await create_branch(branch_name="branch_1", db=db)
        for _ in range(10):
            person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
            await person.new(db=db, name=str(uuid4()), height=180)
            await person.save(db=db)
        for _ in range(10):
            person = await Node.init(db=db, schema="TestPerson", branch=branch_1)
            await person.new(db=db, name=str(uuid4()), height=180)
            await person.save(db=db)

        return branch_1

    @pytest.fixture
    async def diff_repository(self, db: InfrahubDatabase, default_branch: Branch) -> DiffRepository:
        component_registry = get_component_registry()
        return await component_registry.get_component(DiffRepository, db=db, branch=default_branch)

    async def get_diff_coordinator(self, db: InfrahubDatabase, diff_branch: Branch) -> DiffCoordinator:
        config.SETTINGS.database.max_depth_search_hierarchy = 10
        component_registry = get_component_registry()
        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=diff_branch)
        wrapped_repo = AsyncMock(wraps=diff_coordinator.diff_repo)
        diff_coordinator.diff_repo = wrapped_repo
        wrapped_calculator = AsyncMock(wraps=diff_coordinator.diff_calculator)
        diff_coordinator.diff_calculator = wrapped_calculator
        return diff_coordinator

    async def test_incremental_diff_locks_do_not_queue_up(
        self, db: InfrahubDatabase, default_branch: Branch, branch_with_data: Branch
    ) -> None:
        diff_branch = branch_with_data
        diff_coordinator = await self.get_diff_coordinator(db=db, diff_branch=diff_branch)

        results = await asyncio.gather(
            diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=diff_branch),
            diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=diff_branch),
        )
        assert len(results) == 2
        assert results[0].uuid == results[1].uuid
        assert len(diff_coordinator.diff_calculator.calculate_diff.call_args_list) == 1
        # called instead of calculating the diff again
        diff_coordinator.diff_repo.get_one.assert_awaited_once()

    async def test_arbitrary_diff_locks_queue_up(
        self, db: InfrahubDatabase, default_branch: Branch, diff_repository: DiffRepository, branch_with_data: Branch
    ) -> None:
        diff_branch = branch_with_data
        diff_coordinator = await self.get_diff_coordinator(db=db, diff_branch=diff_branch)

        arbitrary_diff_name = str(uuid4())
        results = await asyncio.gather(
            diff_coordinator.create_or_update_arbitrary_timeframe_diff(
                base_branch=default_branch,
                diff_branch=diff_branch,
                from_time=Timestamp(branch_with_data.branched_from),
                to_time=Timestamp(),
                name=arbitrary_diff_name,
            ),
            diff_coordinator.create_or_update_arbitrary_timeframe_diff(
                base_branch=default_branch,
                diff_branch=diff_branch,
                from_time=Timestamp(branch_with_data.branched_from),
                to_time=Timestamp(),
                name=arbitrary_diff_name,
            ),
        )
        assert len(results) == 2
        assert results[0].to_time != results[1].to_time
        assert results[0].uuid == results[1].uuid
        assert results[0].partner_uuid == results[1].partner_uuid
        # second diff uses first diff for its data and is not calculated
        assert len(diff_coordinator.diff_calculator.calculate_diff.call_args_list) == 1
        full_diff_0 = await diff_repository.get_one(
            diff_branch_name=results[0].diff_branch_name, diff_id=results[0].uuid
        )
        full_diff_1 = await diff_repository.get_one(
            diff_branch_name=results[1].diff_branch_name, diff_id=results[1].uuid
        )
        assert full_diff_0.nodes == full_diff_1.nodes

    async def test_arbitrary_diff_blocks_incremental_diff(
        self, db: InfrahubDatabase, default_branch: Branch, diff_repository: DiffRepository, branch_with_data: Branch
    ) -> None:
        diff_branch = branch_with_data
        diff_coordinator = await self.get_diff_coordinator(db=db, diff_branch=diff_branch)

        results = await asyncio.gather(
            diff_coordinator.create_or_update_arbitrary_timeframe_diff(
                base_branch=default_branch,
                diff_branch=diff_branch,
                from_time=Timestamp(branch_with_data.branched_from),
                to_time=Timestamp(),
                name=str(uuid4()),
            ),
            diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=diff_branch),
        )
        assert len(results) == 2
        assert results[0].to_time != results[1].to_time
        assert results[0].uuid != results[1].uuid
        assert results[0].partner_uuid != results[1].partner_uuid
        assert results[0].tracking_id != results[1].tracking_id
        full_arbitrary_diff = await diff_repository.get_one(
            diff_branch_name=results[0].diff_branch_name, diff_id=results[0].uuid
        )
        full_branch_diff = await diff_repository.get_one(
            diff_branch_name=results[1].diff_branch_name, diff_id=results[1].uuid
        )
        assert full_branch_diff.nodes == full_arbitrary_diff.nodes
        # arbitrary diff is calculated separately from the branch-tracking diff
        assert len(diff_coordinator.diff_calculator.calculate_diff.call_args_list) == 2

    async def test_incremental_diff_blocks_arbitrary_diff(
        self, db: InfrahubDatabase, default_branch: Branch, diff_repository: DiffRepository, branch_with_data: Branch
    ) -> None:
        diff_branch = branch_with_data
        diff_coordinator = await self.get_diff_coordinator(db=db, diff_branch=diff_branch)

        results = await asyncio.gather(
            diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=diff_branch),
            diff_coordinator.create_or_update_arbitrary_timeframe_diff(
                base_branch=default_branch,
                diff_branch=diff_branch,
                from_time=Timestamp(branch_with_data.branched_from),
                to_time=Timestamp(),
                name=str(uuid4()),
            ),
        )
        assert len(results) == 2
        assert results[0].to_time != results[1].to_time
        assert results[0].uuid != results[1].uuid
        assert results[0].partner_uuid != results[1].partner_uuid
        assert results[0].tracking_id != results[1].tracking_id
        full_branch_diff = await diff_repository.get_one(
            diff_branch_name=results[0].diff_branch_name, diff_id=results[0].uuid
        )
        full_arbitrary_diff = await diff_repository.get_one(
            diff_branch_name=results[1].diff_branch_name, diff_id=results[1].uuid
        )
        assert full_branch_diff.nodes == full_arbitrary_diff.nodes
        # arbitrary diff is calculated separately from the branch-tracking diff
        assert len(diff_coordinator.diff_calculator.calculate_diff.call_args_list) == 2

    async def test_diff_update_blocks_merge(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        diff_repository: DiffRepository,
        branch_with_data: Branch,
    ) -> None:
        diff_branch = branch_with_data
        diff_coordinator = await self.get_diff_coordinator(db=db, diff_branch=diff_branch)
        branch_merger = BranchMerger(
            db=db,
            diff_coordinator=diff_coordinator,
            diff_merger=DiffMerger(
                db=db,
                source_branch=diff_branch,
                destination_branch=default_branch,
                diff_repository=diff_repository,
                serializer=DiffMergeSerializer(db=db, max_batch_size=50),
            ),
            diff_repository=diff_repository,
            source_branch=diff_branch,
            diff_locker=DiffLocker(),
        )

        results = await asyncio.gather(
            diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=diff_branch),
            branch_merger.merge(),
        )
        assert len(results) == 2
        assert results[0].to_time == results[1].to_time
        assert results[0].uuid == results[1].uuid
        assert results[0].partner_uuid == results[1].partner_uuid
        assert results[0].tracking_id == results[1].tracking_id

    async def test_merge_blocks_diff_update(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        diff_repository: DiffRepository,
        branch_with_data: Branch,
    ) -> None:
        diff_branch = branch_with_data
        diff_coordinator = await self.get_diff_coordinator(db=db, diff_branch=diff_branch)

        # need a separate database connection or the driver raises an error
        # which is fine, b/c this is closer to the real issue
        db2 = InfrahubDatabase(driver=await get_db(retry=5))
        component_registry = get_component_registry()
        diff_repository_2 = await component_registry.get_component(DiffRepository, db=db2, branch=default_branch)
        diff_coordinator_2 = await self.get_diff_coordinator(db=db2, diff_branch=diff_branch)

        branch_merger = BranchMerger(
            db=db2,
            diff_coordinator=diff_coordinator_2,
            diff_merger=DiffMerger(
                db=db2,
                source_branch=diff_branch,
                destination_branch=default_branch,
                diff_repository=diff_repository_2,
                serializer=DiffMergeSerializer(db=db2, max_batch_size=50),
            ),
            diff_repository=diff_repository_2,
            source_branch=diff_branch,
            diff_locker=DiffLocker(),
        )

        results = await asyncio.gather(
            branch_merger.merge(),
            diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=diff_branch),
        )
        assert len(results) == 2
        assert results[0].to_time == results[1].to_time
        assert results[0].uuid == results[1].uuid
        assert results[0].partner_uuid == results[1].partner_uuid
        assert results[0].tracking_id == results[1].tracking_id

    async def test_proposed_change_linked_when_waiting_for_lock(
        self, db: InfrahubDatabase, default_branch: Branch, diff_repository: DiffRepository, branch_with_data: Branch
    ) -> None:
        """Test that when a diff update with proposed_change_id waits for an in-progress update,
        the proposed change still gets linked to the diff.

        This tests the race condition scenario:
        1. Request A starts diff update (acquires lock)
        2. Request B starts diff update with proposed_change_id, detects lock is held, waits
        3. Request A completes and releases lock
        4. Request B should link the proposed_change to the cached diff
        """
        diff_branch = branch_with_data
        diff_coordinator = await self.get_diff_coordinator(db=db, diff_branch=diff_branch)

        # Create a mock proposed change node in the database
        proposed_change_id = str(uuid4())
        await db.execute_query(query="CREATE (pc:Node {uuid: $uuid})", params={"uuid": proposed_change_id})

        # Run two concurrent updates - one without proposed_change_id, one with
        results = await asyncio.gather(
            diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=diff_branch),
            diff_coordinator.update_branch_diff(
                base_branch=default_branch, diff_branch=diff_branch, proposed_change_id=proposed_change_id
            ),
        )

        # Both should return the same diff
        assert len(results) == 2
        assert results[0].uuid == results[1].uuid
        assert results[1].proposed_change_id == proposed_change_id

        # Verify via diff_repository.get_roots_metadata that the diff is linked to the proposed change
        metadata = await diff_repository.get_roots_metadata(
            diff_branch_names=[diff_branch.name], proposed_change_id=proposed_change_id
        )
        diff_uuids = {m.uuid for m in metadata}
        assert results[0].uuid in diff_uuids, "Diff should be retrievable by proposed_change_id"
