import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from infrahub import config, lock
from infrahub.core.branch import Branch
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.data_check_synchronizer import DiffDataCheckSynchronizer
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.dependencies.registry import get_component_registry


class TestDiffCoordinatorLocks:
    @pytest.fixture
    async def branch_with_data(self, db: InfrahubDatabase, default_branch: Branch, car_person_schema) -> Branch:
        lock.initialize_lock(local_only=True)
        branch_1 = await create_branch(branch_name="branch_1", db=db)
        for _ in range(10):
            person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
            await person.new(db=db, name=str(uuid4), height=180)
            await person.save(db=db)
        for _ in range(10):
            person = await Node.init(db=db, schema="TestPerson", branch=branch_1)
            await person.new(db=db, name=str(uuid4), height=180)
            await person.save(db=db)

        return branch_1

    async def get_diff_coordinator(self, db: InfrahubDatabase, diff_branch: Branch) -> DiffCoordinator:
        config.SETTINGS.database.max_depth_search_hierarchy = 10
        component_registry = get_component_registry()
        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=diff_branch)
        mock_synchronizer = AsyncMock(spec=DiffDataCheckSynchronizer)
        diff_coordinator.data_check_synchronizer = mock_synchronizer
        wrapped_repo = AsyncMock(wraps=diff_coordinator.diff_repo)
        diff_coordinator.diff_repo = wrapped_repo
        wrapped_calculator = AsyncMock(wraps=diff_coordinator.diff_calculator)
        diff_coordinator.diff_calculator = wrapped_calculator
        return diff_coordinator

    async def test_incremental_diff_locks_do_not_queue_up(
        self, db: InfrahubDatabase, default_branch: Branch, branch_with_data: Branch
    ):
        diff_branch = branch_with_data
        diff_coordinator = await self.get_diff_coordinator(db=db, diff_branch=diff_branch)

        results = await asyncio.gather(
            diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=diff_branch),
            diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=diff_branch),
        )
        assert len(results) == 2
        assert results[0] == results[1]
        assert len(diff_coordinator.diff_calculator.calculate_diff.call_args_list) == 1
        # called instead of calculating the diff again
        diff_coordinator.diff_repo.get_one.assert_awaited_once()

    async def test_arbitrary_diff_locks_queue_up(
        self, db: InfrahubDatabase, default_branch: Branch, branch_with_data: Branch
    ):
        diff_branch = branch_with_data
        diff_coordinator = await self.get_diff_coordinator(db=db, diff_branch=diff_branch)

        results = await asyncio.gather(
            diff_coordinator.create_or_update_arbitrary_timeframe_diff(
                base_branch=default_branch,
                diff_branch=diff_branch,
                from_time=Timestamp(branch_with_data.branched_from),
                to_time=Timestamp(),
            ),
            diff_coordinator.create_or_update_arbitrary_timeframe_diff(
                base_branch=default_branch,
                diff_branch=diff_branch,
                from_time=Timestamp(branch_with_data.branched_from),
                to_time=Timestamp(),
            ),
        )
        assert len(results) == 2
        assert results[0].to_time != results[1].to_time
        assert results[0].uuid != results[1].uuid
        assert results[0].partner_uuid != results[1].partner_uuid
        results[0].to_time = results[1].to_time
        results[0].uuid = results[1].uuid
        results[0].partner_uuid = results[1].partner_uuid
        assert results[0] == results[1]
        # called once to calculate diff on main and once to calculate diff on the branch
        assert len(diff_coordinator.diff_calculator.calculate_diff.call_args_list) == 2
        # not called because diffs are calculated both times
        diff_coordinator.diff_repo.get_one.assert_not_awaited()

    async def test_arbitrary_diff_blocks_incremental_diff(
        self, db: InfrahubDatabase, default_branch: Branch, branch_with_data: Branch
    ):
        diff_branch = branch_with_data
        diff_coordinator = await self.get_diff_coordinator(db=db, diff_branch=diff_branch)

        results = await asyncio.gather(
            diff_coordinator.create_or_update_arbitrary_timeframe_diff(
                base_branch=default_branch,
                diff_branch=diff_branch,
                from_time=Timestamp(branch_with_data.branched_from),
                to_time=Timestamp(),
            ),
            diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=diff_branch),
        )
        assert len(results) == 2
        assert results[0].to_time != results[1].to_time
        assert results[0].uuid != results[1].uuid
        assert results[0].partner_uuid != results[1].partner_uuid
        assert results[0].tracking_id != results[1].tracking_id
        results[0].to_time = results[1].to_time
        results[0].uuid = results[1].uuid
        results[0].partner_uuid = results[1].partner_uuid
        results[0].tracking_id = results[1].tracking_id
        assert results[0] == results[1]
        # called once to calculate diff on main and once to calculate diff on the branch
        assert len(diff_coordinator.diff_calculator.calculate_diff.call_args_list) == 2
        # not called because diffs are calculated both times
        diff_coordinator.diff_repo.get_one.assert_not_awaited()

    async def test_incremental_diff_blocks_arbitrary_diff(
        self, db: InfrahubDatabase, default_branch: Branch, branch_with_data: Branch
    ):
        diff_branch = branch_with_data
        diff_coordinator = await self.get_diff_coordinator(db=db, diff_branch=diff_branch)

        results = await asyncio.gather(
            diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=diff_branch),
            diff_coordinator.create_or_update_arbitrary_timeframe_diff(
                base_branch=default_branch,
                diff_branch=diff_branch,
                from_time=Timestamp(branch_with_data.branched_from),
                to_time=Timestamp(),
            ),
        )
        assert len(results) == 2
        assert results[0].to_time != results[1].to_time
        assert results[0].uuid != results[1].uuid
        assert results[0].partner_uuid != results[1].partner_uuid
        assert results[0].tracking_id != results[1].tracking_id
        results[0].to_time = results[1].to_time
        results[0].uuid = results[1].uuid
        results[0].partner_uuid = results[1].partner_uuid
        results[0].tracking_id = results[1].tracking_id
        assert results[0] == results[1]
        # called once to calculate diff on main and once to calculate diff on the branch
        assert len(diff_coordinator.diff_calculator.calculate_diff.call_args_list) == 2
        # not called because diffs are calculated both times
        diff_coordinator.diff_repo.get_one.assert_not_awaited()
