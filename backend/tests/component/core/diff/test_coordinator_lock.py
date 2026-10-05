import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from infrahub import config, lock
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.diff_locker import DiffLocker
from infrahub.core.diff.merger.exclusion_plan import MergeExclusionPlanBuilder
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.diff.model.path import BranchTrackingId
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.merge.constraints import MergeConstraintValidator
from infrahub.core.merge.graph_merger import GraphMerger
from infrahub.core.merge.schema_analyzer import MergeSchemaAnalyzer
from infrahub.core.node import Node
from infrahub.core.rollback import GraphRollbacker
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.core.validators.constraint_merge import build_constraint_info_merger
from infrahub.core.validators.determiner import build_constraint_validator_determiner
from infrahub.core.validators.tasks import schema_validate_migrations
from infrahub.database import InfrahubDatabase
from infrahub.dependencies.registry import get_component_registry


class TestDiffCoordinatorLocks:
    @pytest.fixture(autouse=True)
    async def _setup_core_schema(self, register_core_models_schema: SchemaBranch) -> None:
        return

    @pytest.fixture
    async def branch_with_data(
        self, db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch
    ) -> Branch:
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

    @asynccontextmanager
    async def requesting_coordinator(
        self, db: InfrahubDatabase, diff_branch: Branch
    ) -> AsyncGenerator[DiffCoordinator, None]:
        """Build a coordinator on a database session of its own.

        A session carries a single connection that cannot serve two coroutines at once, so each
        request racing in these tests needs one.
        """
        async with db.start_session() as session_db:
            yield await self.get_diff_coordinator(db=session_db, diff_branch=diff_branch)

    @asynccontextmanager
    async def requesting_merger(
        self, db: InfrahubDatabase, diff_branch: Branch, default_branch: Branch
    ) -> AsyncGenerator[GraphMerger, None]:
        """Build a merger on a database session of its own."""
        async with db.start_session() as session_db:
            component_registry = get_component_registry()
            diff_repository = await component_registry.get_component(
                DiffRepository, db=session_db, branch=default_branch
            )
            yield GraphMerger(
                db=session_db,
                diff_coordinator=await self.get_diff_coordinator(db=session_db, diff_branch=diff_branch),
                diff_merger=DiffMerger(
                    db=session_db,
                    source_branch=diff_branch,
                    destination_branch=default_branch,
                    diff_repository=diff_repository,
                    exclusion_plan_builder=MergeExclusionPlanBuilder(),
                    rollbacker=GraphRollbacker(db=session_db),
                ),
                diff_repository=diff_repository,
                source_branch=diff_branch,
                destination_branch=default_branch,
                diff_locker=DiffLocker(),
                schema_analyzer=MergeSchemaAnalyzer(
                    db=session_db,
                    source_branch=diff_branch,
                    destination_branch=default_branch,
                    diff_repository=diff_repository,
                    schema_manager=registry.schema,
                ),
                constraint_validator=MergeConstraintValidator(
                    branch=diff_branch,
                    diff_repository=diff_repository,
                    determiner=build_constraint_validator_determiner(db=session_db, branch=diff_branch),
                    constraint_info_merger=build_constraint_info_merger(),
                    migration_validator=schema_validate_migrations,
                ),
            )

    @staticmethod
    def count_calculated_diffs(*coordinators: DiffCoordinator) -> int:
        return sum(len(coordinator.diff_calculator.calculate_diff.call_args_list) for coordinator in coordinators)

    @staticmethod
    def count_stored_diff_reads(*coordinators: DiffCoordinator) -> int:
        return sum(coordinator.diff_repo.get_one.await_count for coordinator in coordinators)

    async def test_incremental_diff_locks_do_not_queue_up(
        self, db: InfrahubDatabase, default_branch: Branch, branch_with_data: Branch
    ) -> None:
        diff_branch = branch_with_data

        async with (
            self.requesting_coordinator(db=db, diff_branch=diff_branch) as coordinator_1,
            self.requesting_coordinator(db=db, diff_branch=diff_branch) as coordinator_2,
        ):
            results = await asyncio.gather(
                coordinator_1.update_branch_diff(base_branch=default_branch, diff_branch=diff_branch),
                coordinator_2.update_branch_diff(base_branch=default_branch, diff_branch=diff_branch),
            )
            assert len(results) == 2
            assert results[0].uuid == results[1].uuid
            assert self.count_calculated_diffs(coordinator_1, coordinator_2) == 1
            # called instead of calculating the diff again
            assert self.count_stored_diff_reads(coordinator_1, coordinator_2) == 1

    async def test_arbitrary_diff_locks_queue_up(
        self, db: InfrahubDatabase, default_branch: Branch, diff_repository: DiffRepository, branch_with_data: Branch
    ) -> None:
        diff_branch = branch_with_data

        arbitrary_diff_name = str(uuid4())
        async with (
            self.requesting_coordinator(db=db, diff_branch=diff_branch) as coordinator_1,
            self.requesting_coordinator(db=db, diff_branch=diff_branch) as coordinator_2,
        ):
            results = await asyncio.gather(
                coordinator_1.create_or_update_arbitrary_timeframe_diff(
                    base_branch=default_branch,
                    diff_branch=diff_branch,
                    from_time=Timestamp(branch_with_data.branched_from),
                    to_time=Timestamp(),
                    name=arbitrary_diff_name,
                ),
                coordinator_2.create_or_update_arbitrary_timeframe_diff(
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
            assert self.count_calculated_diffs(coordinator_1, coordinator_2) == 1
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

        async with (
            self.requesting_coordinator(db=db, diff_branch=diff_branch) as arbitrary_coordinator,
            self.requesting_coordinator(db=db, diff_branch=diff_branch) as incremental_coordinator,
        ):
            results = await asyncio.gather(
                arbitrary_coordinator.create_or_update_arbitrary_timeframe_diff(
                    base_branch=default_branch,
                    diff_branch=diff_branch,
                    from_time=Timestamp(branch_with_data.branched_from),
                    to_time=Timestamp(),
                    name=str(uuid4()),
                ),
                incremental_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=diff_branch),
            )
            assert len(results) == 2
            assert results[0].to_time != results[1].to_time
            assert results[0].uuid != results[1].uuid
            assert results[0].partner_uuid != results[1].partner_uuid
            assert results[0].tracking_id != results[1].tracking_id
            # arbitrary diff is calculated separately from the branch-tracking diff
            assert self.count_calculated_diffs(arbitrary_coordinator, incremental_coordinator) == 2
        full_arbitrary_diff = await diff_repository.get_one(
            diff_branch_name=results[0].diff_branch_name, diff_id=results[0].uuid
        )
        full_branch_diff = await diff_repository.get_one(
            diff_branch_name=results[1].diff_branch_name, diff_id=results[1].uuid
        )
        assert full_branch_diff.nodes == full_arbitrary_diff.nodes

    async def test_incremental_diff_blocks_arbitrary_diff(
        self, db: InfrahubDatabase, default_branch: Branch, diff_repository: DiffRepository, branch_with_data: Branch
    ) -> None:
        diff_branch = branch_with_data

        async with (
            self.requesting_coordinator(db=db, diff_branch=diff_branch) as incremental_coordinator,
            self.requesting_coordinator(db=db, diff_branch=diff_branch) as arbitrary_coordinator,
        ):
            results = await asyncio.gather(
                incremental_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=diff_branch),
                arbitrary_coordinator.create_or_update_arbitrary_timeframe_diff(
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
            # arbitrary diff is calculated separately from the branch-tracking diff
            assert self.count_calculated_diffs(incremental_coordinator, arbitrary_coordinator) == 2
        full_branch_diff = await diff_repository.get_one(
            diff_branch_name=results[0].diff_branch_name, diff_id=results[0].uuid
        )
        full_arbitrary_diff = await diff_repository.get_one(
            diff_branch_name=results[1].diff_branch_name, diff_id=results[1].uuid
        )
        assert full_branch_diff.nodes == full_arbitrary_diff.nodes

    async def test_diff_update_blocks_merge(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        diff_repository: DiffRepository,
        branch_with_data: Branch,
    ) -> None:
        diff_branch = branch_with_data

        async with (
            self.requesting_coordinator(db=db, diff_branch=diff_branch) as diff_coordinator,
            self.requesting_merger(db=db, diff_branch=diff_branch, default_branch=default_branch) as graph_merger,
        ):
            results = await asyncio.gather(
                diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=diff_branch),
                graph_merger.merge(at=Timestamp()),
            )
        diff_result = results[0]
        merge_diff = await diff_repository.get_one(diff_branch_name=diff_branch.name)
        assert diff_result.to_time == merge_diff.to_time
        assert diff_result.uuid == merge_diff.uuid
        assert diff_result.partner_uuid == merge_diff.partner_uuid
        assert diff_result.tracking_id == merge_diff.tracking_id

    async def test_merge_blocks_diff_update(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        diff_repository: DiffRepository,
        branch_with_data: Branch,
    ) -> None:
        diff_branch = branch_with_data

        async with (
            self.requesting_merger(db=db, diff_branch=diff_branch, default_branch=default_branch) as graph_merger,
            self.requesting_coordinator(db=db, diff_branch=diff_branch) as diff_coordinator,
        ):
            results = await asyncio.gather(
                graph_merger.merge(at=Timestamp()),
                diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=diff_branch),
            )
        diff_result = results[1]
        merge_diff = await diff_repository.get_one(diff_branch_name=diff_branch.name)
        assert merge_diff.to_time == diff_result.to_time
        assert merge_diff.uuid == diff_result.uuid
        assert merge_diff.partner_uuid == diff_result.partner_uuid
        assert merge_diff.tracking_id == diff_result.tracking_id

    async def test_diff_update_computes_when_lock_holder_saved_no_diff(
        self, db: InfrahubDatabase, default_branch: Branch, branch_with_data: Branch
    ) -> None:
        """A held incremental lock is no promise that a diff was saved."""
        diff_branch = branch_with_data
        diff_coordinator = await self.get_diff_coordinator(db=db, diff_branch=diff_branch)
        diff_locker = DiffLocker()
        lock_held = asyncio.Event()
        update_checked_lock = asyncio.Event()

        async def hold_incremental_lock_like_a_reader() -> None:
            async with diff_locker.acquire_lock(
                target_branch_name=default_branch.name, source_branch_name=diff_branch.name, is_incremental=True
            ):
                lock_held.set()
                await update_checked_lock.wait()

        # a separate task, because the lock is reentrant within one context
        reader = asyncio.create_task(hold_incremental_lock_like_a_reader())
        await lock_held.wait()

        incremental_lock = diff_locker.get_existing_lock(
            target_branch_name=default_branch.name, source_branch_name=diff_branch.name, is_incremental=True
        )
        assert incremental_lock is not None
        lock_is_held = incremental_lock.locked

        async def locked_then_let_reader_go() -> bool:
            held = await lock_is_held()
            update_checked_lock.set()
            return held

        # releasing only after the update has read the lock keeps scheduling order out of the result
        with patch.object(incremental_lock, "locked", new=locked_then_let_reader_go):
            diff_root = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=diff_branch)
        await reader

        # the in-progress shortcut was taken, found nothing stored, and computed the diff anyway
        diff_coordinator.diff_repo.get_one.assert_awaited_once()
        assert len(diff_coordinator.diff_calculator.calculate_diff.call_args_list) == 1
        assert diff_root.tracking_id == BranchTrackingId(name=diff_branch.name)
        stored_diff = await diff_coordinator.diff_repo.get_one(
            tracking_id=BranchTrackingId(name=diff_branch.name), diff_branch_name=diff_branch.name
        )
        assert stored_diff.uuid == diff_root.uuid
        assert len(stored_diff.nodes) == 10

    async def test_proposed_change_linked_when_waiting_for_lock(
        self, db: InfrahubDatabase, default_branch: Branch, diff_repository: DiffRepository, branch_with_data: Branch
    ) -> None:
        """Test that when a diff update with proposed_change_id waits for an in-progress update,.

        the proposed change still gets linked to the diff.

        This tests the race condition scenario:
        1. Request A starts diff update (acquires lock)
        2. Request B starts diff update with proposed_change_id, detects lock is held, waits
        3. Request A completes and releases lock
        4. Request B should link the proposed_change to the cached diff
        """
        diff_branch = branch_with_data

        # Create a proposed change node in the database
        proposed_change_id = str(uuid4())
        await db.execute_query(query="CREATE (pc:Node {uuid: $uuid})", params={"uuid": proposed_change_id})

        # Run two concurrent updates - one without proposed_change_id, one with
        async with (
            self.requesting_coordinator(db=db, diff_branch=diff_branch) as coordinator_1,
            self.requesting_coordinator(db=db, diff_branch=diff_branch) as coordinator_2,
        ):
            results = await asyncio.gather(
                coordinator_1.update_branch_diff(base_branch=default_branch, diff_branch=diff_branch),
                coordinator_2.update_branch_diff(
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
