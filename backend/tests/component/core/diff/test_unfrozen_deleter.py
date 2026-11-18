import asyncio
from collections.abc import Callable
from dataclasses import dataclass

import pytest

from infrahub.core.branch.enums import BranchStatus
from infrahub.core.diff.diff_locker import DiffLocker
from infrahub.core.diff.model.path import (
    BranchTrackingId,
    EnrichedDiffs,
    FrozenTrackingId,
    NameTrackingId,
    TrackingId,
)
from infrahub.core.diff.parent_node_adder import DiffParentNodeAdder
from infrahub.core.diff.repository.deserializer import EnrichedDiffDeserializer
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.diff.unfrozen_deleter import (
    UnfrozenDiffDeleter,
    UnfrozenDiffDeletionPlan,
    UnfrozenDiffDeletionPlanner,
)
from infrahub.core.initialization import create_branch, create_root_node
from infrahub.core.merge.merge_locker import MergeLocker
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.lock import InfrahubLock
from tests.helpers.diff_factories import EnrichedRootFactory

from .repository.base import DiffRepositoryTestBase

DIFF_VERTEX_LABELS = [
    "DiffRoot",
    "DiffNode",
    "DiffAttribute",
    "DiffRelationship",
    "DiffRelationshipElement",
    "DiffProperty",
    "DiffConflict",
]


@dataclass
class FrozenPartnerCase:
    name: str
    branch_root_frozen: bool
    base_root_frozen: bool


FROZEN_PARTNER_CASES = [
    FrozenPartnerCase(name="frozen_branch_root", branch_root_frozen=True, base_root_frozen=False),
    FrozenPartnerCase(name="frozen_base_root", branch_root_frozen=False, base_root_frozen=True),
]


@dataclass
class HeldLockCase:
    name: str
    hold_lock: Callable[[DiffLocker, MergeLocker], InfrahubLock]
    tracking_id: TrackingId
    expected_events: list[str]


WAITED_ON = ["lock released", "delete"]
NOT_WAITED_ON = ["delete", "lock released"]

HELD_LOCK_CASES = [
    HeldLockCase(
        name="incremental_diff_update_lock",
        hold_lock=lambda diff_locker, _: diff_locker.acquire_lock(
            target_branch_name="main", source_branch_name="branch-a", is_incremental=True
        ),
        tracking_id=NameTrackingId(name="named"),
        expected_events=WAITED_ON,
    ),
    HeldLockCase(
        name="full_diff_update_lock",
        hold_lock=lambda diff_locker, _: diff_locker.acquire_lock(
            target_branch_name="main", source_branch_name="branch-a", is_incremental=False
        ),
        tracking_id=NameTrackingId(name="named"),
        expected_events=WAITED_ON,
    ),
    HeldLockCase(
        name="merge_lock_with_branch_diff",
        hold_lock=lambda _, merge_locker: merge_locker.acquire_global_lock(),
        tracking_id=BranchTrackingId(name="branch-a"),
        expected_events=WAITED_ON,
    ),
    HeldLockCase(
        name="merge_lock_with_named_diff",
        hold_lock=lambda _, merge_locker: merge_locker.acquire_global_lock(),
        tracking_id=NameTrackingId(name="named"),
        expected_events=NOT_WAITED_ON,
    ),
]


class RecordingDiffRepository(DiffRepository):
    def __init__(self, db: InfrahubDatabase, deserializer: EnrichedDiffDeserializer, events: list[str]) -> None:
        super().__init__(db=db, deserializer=deserializer)
        self.events = events

    async def delete_diff_roots(self, diff_root_uuids: list[str], include_frozen: bool = False) -> None:
        self.events.append("delete")
        await super().delete_diff_roots(diff_root_uuids=diff_root_uuids, include_frozen=include_frozen)


def planned_diffs(plan: UnfrozenDiffDeletionPlan) -> list[tuple[str, str, set[frozenset[str]], bool]]:
    return [
        (
            batch.base_branch_name,
            batch.diff_branch_name,
            {frozenset(diff) for diff in batch.diffs},
            batch.has_branch_diffs,
        )
        for batch in plan.batches
    ]


def root_pair(diffs: EnrichedDiffs) -> frozenset[str]:
    return frozenset({diffs.diff_branch_diff.uuid, diffs.base_branch_diff.uuid})


class TestUnfrozenDiffDeleter(DiffRepositoryTestBase):
    from_time = Timestamp("2024-06-15T18:35:20Z")
    to_time = Timestamp("2024-06-15T18:49:40Z")

    @pytest.fixture
    def diff_repository(self, db: InfrahubDatabase) -> DiffRepository:
        return DiffRepository(db=db, deserializer=EnrichedDiffDeserializer(parent_adder=DiffParentNodeAdder()))

    @pytest.fixture
    def diff_locker(self) -> DiffLocker:
        return DiffLocker()

    @pytest.fixture
    def merge_locker(self) -> MergeLocker:
        return MergeLocker()

    @pytest.fixture
    def planner(self, db: InfrahubDatabase, diff_repository: DiffRepository) -> UnfrozenDiffDeletionPlanner:
        return UnfrozenDiffDeletionPlanner(db=db, diff_repository=diff_repository)

    @pytest.fixture
    def deleter(
        self, diff_repository: DiffRepository, diff_locker: DiffLocker, merge_locker: MergeLocker
    ) -> UnfrozenDiffDeleter:
        return UnfrozenDiffDeleter(diff_repository=diff_repository, diff_locker=diff_locker, merge_locker=merge_locker)

    async def _save_diff(
        self,
        diff_repository: DiffRepository,
        branch_name: str,
        tracking_id: TrackingId | None = None,
        branch_root_frozen: bool = False,
        base_root_frozen: bool = False,
    ) -> EnrichedDiffs:
        tracking_id = tracking_id or BranchTrackingId(name=branch_name)
        branch_root = EnrichedRootFactory.build(
            base_branch_name=self.base_branch_name,
            diff_branch_name=branch_name,
            from_time=self.from_time,
            to_time=self.to_time,
            nodes=self._build_nodes(num_nodes=2, num_sub_fields=2),
            tracking_id=tracking_id,
            is_frozen=branch_root_frozen,
        )
        base_root = EnrichedRootFactory.build(
            base_branch_name=self.base_branch_name,
            diff_branch_name=self.base_branch_name,
            from_time=self.from_time,
            to_time=self.to_time,
            nodes=self._build_nodes(num_nodes=1, num_sub_fields=2),
            tracking_id=tracking_id,
            is_frozen=base_root_frozen,
            partner_uuid=branch_root.uuid,
        )
        branch_root.partner_uuid = base_root.uuid
        enriched_diffs = EnrichedDiffs(
            base_branch_name=self.base_branch_name,
            diff_branch_name=branch_name,
            base_branch_diff=base_root,
            diff_branch_diff=branch_root,
        )
        await diff_repository.save(enriched_diffs=enriched_diffs, do_summary_counts=False)
        return enriched_diffs

    async def _count_diff_vertices(self, db: InfrahubDatabase) -> int:
        results = await db.execute_query(
            query="MATCH (n) WHERE any(label IN labels(n) WHERE label IN $labels) RETURN count(n) AS num",
            params={"labels": DIFF_VERTEX_LABELS},
        )
        return results[0]["num"]

    async def _root_uuids(self, diff_repository: DiffRepository) -> set[str]:
        return {root.uuid for root in await diff_repository.get_roots_metadata(exclude_merged=False)}

    async def test_plans_only_the_named_diffs_by_default(
        self, diff_repository: DiffRepository, planner: UnfrozenDiffDeletionPlanner, reset_database: None
    ) -> None:
        await self._save_diff(diff_repository=diff_repository, branch_name="branch-a")
        branch_a_named = await self._save_diff(
            diff_repository=diff_repository, branch_name="branch-a", tracking_id=NameTrackingId(name="named")
        )
        main_named = await self._save_diff(
            diff_repository=diff_repository, branch_name="main", tracking_id=NameTrackingId(name="capture")
        )

        plan = await planner.plan(branch_name=None, include_branch_diffs=False)

        assert planned_diffs(plan=plan) == [
            ("main", "branch-a", {root_pair(diffs=branch_a_named)}, False),
            ("main", "main", {root_pair(diffs=main_named)}, False),
        ]
        assert plan.num_diffs == 2
        assert plan.kept_root_uuids == ()

    async def test_plans_the_branch_diffs_too_when_included(
        self, diff_repository: DiffRepository, planner: UnfrozenDiffDeletionPlanner, reset_database: None
    ) -> None:
        branch_a = await self._save_diff(diff_repository=diff_repository, branch_name="branch-a")
        branch_a_named = await self._save_diff(
            diff_repository=diff_repository, branch_name="branch-a", tracking_id=NameTrackingId(name="named")
        )
        branch_b = await self._save_diff(diff_repository=diff_repository, branch_name="branch-b")
        await diff_repository.mark_tracking_ids_merged(tracking_ids=[BranchTrackingId(name="branch-b")])
        main_named = await self._save_diff(
            diff_repository=diff_repository, branch_name="main", tracking_id=NameTrackingId(name="capture")
        )
        await self._save_diff(
            diff_repository=diff_repository,
            branch_name="branch-c",
            tracking_id=FrozenTrackingId(name="branch-c"),
            branch_root_frozen=True,
            base_root_frozen=True,
        )

        plan = await planner.plan(branch_name=None, include_branch_diffs=True)

        assert planned_diffs(plan=plan) == [
            ("main", "branch-a", {root_pair(diffs=branch_a), root_pair(diffs=branch_a_named)}, True),
            ("main", "branch-b", {root_pair(diffs=branch_b)}, True),
            ("main", "main", {root_pair(diffs=main_named)}, False),
        ]
        assert plan.kept_root_uuids == ()

    async def test_plans_only_the_diffs_of_the_given_branch(
        self, diff_repository: DiffRepository, planner: UnfrozenDiffDeletionPlanner, reset_database: None
    ) -> None:
        branch_a = await self._save_diff(diff_repository=diff_repository, branch_name="branch-a")
        branch_a_named = await self._save_diff(
            diff_repository=diff_repository, branch_name="branch-a", tracking_id=NameTrackingId(name="named")
        )
        await self._save_diff(
            diff_repository=diff_repository, branch_name="branch-b", tracking_id=NameTrackingId(name="other")
        )
        main_named = await self._save_diff(
            diff_repository=diff_repository, branch_name="main", tracking_id=NameTrackingId(name="capture")
        )

        branch_plan = await planner.plan(branch_name="branch-a", include_branch_diffs=True)
        main_plan = await planner.plan(branch_name="main", include_branch_diffs=True)

        assert planned_diffs(plan=branch_plan) == [
            ("main", "branch-a", {root_pair(diffs=branch_a), root_pair(diffs=branch_a_named)}, True)
        ]
        assert planned_diffs(plan=main_plan) == [("main", "main", {root_pair(diffs=main_named)}, False)]

    async def test_plans_a_base_root_left_without_its_branch_root_under_the_default_branch(
        self, diff_repository: DiffRepository, planner: UnfrozenDiffDeletionPlanner, reset_database: None
    ) -> None:
        diffs = await self._save_diff(diff_repository=diff_repository, branch_name="branch-a")
        await diff_repository.delete_diff_roots(diff_root_uuids=[diffs.diff_branch_diff.uuid])
        assert await self._root_uuids(diff_repository=diff_repository) == {diffs.base_branch_diff.uuid}

        assert (await planner.plan(branch_name="branch-a", include_branch_diffs=True)).batches == ()
        assert (await planner.plan(branch_name=None, include_branch_diffs=False)).batches == ()
        assert planned_diffs(plan=await planner.plan(branch_name="main", include_branch_diffs=True)) == [
            ("main", "main", {frozenset({diffs.base_branch_diff.uuid})}, True)
        ]

    @pytest.mark.parametrize("case", FROZEN_PARTNER_CASES, ids=lambda case: case.name)
    async def test_keeps_an_unfrozen_root_paired_with_a_frozen_root(
        self,
        diff_repository: DiffRepository,
        planner: UnfrozenDiffDeletionPlanner,
        reset_database: None,
        case: FrozenPartnerCase,
    ) -> None:
        diffs = await self._save_diff(
            diff_repository=diff_repository,
            branch_name="branch-a",
            tracking_id=NameTrackingId(name="named"),
            branch_root_frozen=case.branch_root_frozen,
            base_root_frozen=case.base_root_frozen,
        )
        unfrozen_root = diffs.base_branch_diff if case.branch_root_frozen else diffs.diff_branch_diff

        for branch_name in (None, "branch-a"):
            plan = await planner.plan(branch_name=branch_name, include_branch_diffs=False)

            assert plan.batches == ()
            assert plan.kept_root_uuids == (unfrozen_root.uuid,)

    async def test_keeps_the_branch_diffs_of_a_merged_branch(
        self,
        db: InfrahubDatabase,
        diff_repository: DiffRepository,
        planner: UnfrozenDiffDeletionPlanner,
        reset_database: None,
    ) -> None:
        await create_root_node(db=db)
        merged_branch = await create_branch(branch_name="branch-merged", db=db)
        merged_branch.status = BranchStatus.MERGED
        await merged_branch.save(db=db)
        merged = await self._save_diff(diff_repository=diff_repository, branch_name="branch-merged")
        merged_named = await self._save_diff(
            diff_repository=diff_repository, branch_name="branch-merged", tracking_id=NameTrackingId(name="named")
        )

        for branch_name in (None, "branch-merged"):
            plan = await planner.plan(branch_name=branch_name, include_branch_diffs=True)

            assert planned_diffs(plan=plan) == [("main", "branch-merged", {root_pair(diffs=merged_named)}, False)]
            assert set(plan.kept_merged_branch_root_uuids) == root_pair(diffs=merged)

    async def test_deletes_the_planned_diffs_and_leaves_the_others_intact(
        self,
        db: InfrahubDatabase,
        diff_repository: DiffRepository,
        planner: UnfrozenDiffDeletionPlanner,
        deleter: UnfrozenDiffDeleter,
        reset_database: None,
    ) -> None:
        frozen = await self._save_diff(
            diff_repository=diff_repository,
            branch_name="branch-frozen",
            tracking_id=FrozenTrackingId(name="branch-frozen"),
            branch_root_frozen=True,
            base_root_frozen=True,
        )
        branch_a = await self._save_diff(diff_repository=diff_repository, branch_name="branch-a")
        num_kept_vertices = await self._count_diff_vertices(db=db)
        await self._save_diff(
            diff_repository=diff_repository, branch_name="branch-a", tracking_id=NameTrackingId(name="named")
        )
        await self._save_diff(
            diff_repository=diff_repository, branch_name="main", tracking_id=NameTrackingId(name="capture")
        )
        plan = await planner.plan(branch_name=None, include_branch_diffs=False)

        await deleter.delete(plan=plan)

        assert await self._root_uuids(diff_repository=diff_repository) == root_pair(diffs=frozen) | root_pair(
            diffs=branch_a
        )
        assert await self._count_diff_vertices(db=db) == num_kept_vertices

    async def test_keeps_a_diff_frozen_after_the_plan_was_made(
        self,
        diff_repository: DiffRepository,
        planner: UnfrozenDiffDeletionPlanner,
        deleter: UnfrozenDiffDeleter,
        reset_database: None,
    ) -> None:
        diffs = await self._save_diff(diff_repository=diff_repository, branch_name="branch-a")
        plan = await planner.plan(branch_name=None, include_branch_diffs=True)
        await diff_repository.freeze_diffs_for_branch(branch_name="branch-a")

        await deleter.delete(plan=plan)

        assert await self._root_uuids(diff_repository=diff_repository) == root_pair(diffs=diffs)

    @pytest.mark.parametrize("case", HELD_LOCK_CASES, ids=lambda case: case.name)
    async def test_waits_for_the_diff_update_or_merge_in_progress(
        self,
        db: InfrahubDatabase,
        diff_repository: DiffRepository,
        diff_locker: DiffLocker,
        merge_locker: MergeLocker,
        planner: UnfrozenDiffDeletionPlanner,
        reset_database: None,
        case: HeldLockCase,
    ) -> None:
        await self._save_diff(diff_repository=diff_repository, branch_name="branch-a", tracking_id=case.tracking_id)
        events: list[str] = []
        deleter = UnfrozenDiffDeleter(
            diff_repository=RecordingDiffRepository(
                db=db, deserializer=EnrichedDiffDeserializer(parent_adder=DiffParentNodeAdder()), events=events
            ),
            diff_locker=diff_locker,
            merge_locker=merge_locker,
        )
        plan = await planner.plan(branch_name="branch-a", include_branch_diffs=True)
        lock_held = asyncio.Event()
        lock_may_be_released = asyncio.Event()

        async def hold_lock() -> None:
            async with case.hold_lock(diff_locker, merge_locker):
                lock_held.set()
                await lock_may_be_released.wait()
                events.append("lock released")

        holder = asyncio.create_task(hold_lock())
        await lock_held.wait()
        deletion = asyncio.create_task(deleter.delete(plan=plan))
        for _ in range(10):
            await asyncio.sleep(0)
        lock_may_be_released.set()
        await holder
        await deletion

        assert events == case.expected_events
        assert await self._root_uuids(diff_repository=diff_repository) == set()
