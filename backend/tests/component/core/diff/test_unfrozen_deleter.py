import asyncio
from dataclasses import dataclass

import pytest

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
from infrahub.core.diff.unfrozen_deleter import UnfrozenDiffDeleter
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
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


class RecordingDiffRepository(DiffRepository):
    def __init__(self, db: InfrahubDatabase, deserializer: EnrichedDiffDeserializer, events: list[str]) -> None:
        super().__init__(db=db, deserializer=deserializer)
        self.events = events

    async def delete_diff_roots(self, diff_root_uuids: list[str], include_frozen: bool = False) -> None:
        self.events.append("delete")
        await super().delete_diff_roots(diff_root_uuids=diff_root_uuids, include_frozen=include_frozen)


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
    def deleter(self, diff_repository: DiffRepository, diff_locker: DiffLocker) -> UnfrozenDiffDeleter:
        return UnfrozenDiffDeleter(diff_repository=diff_repository, diff_locker=diff_locker)

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

    async def test_deletes_the_unfrozen_diffs_of_every_branch(
        self,
        db: InfrahubDatabase,
        diff_repository: DiffRepository,
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
        num_frozen_vertices = await self._count_diff_vertices(db=db)
        branch_a = await self._save_diff(diff_repository=diff_repository, branch_name="branch-a")
        branch_b = await self._save_diff(diff_repository=diff_repository, branch_name="branch-b")
        await diff_repository.mark_tracking_ids_merged(tracking_ids=[BranchTrackingId(name="branch-b")])

        plan = await deleter.plan(branch_name=None)

        assert [batch.diff_branch_name for batch in plan.batches] == ["branch-a", "branch-b"]
        assert set(plan.batches[0].root_uuids) == {branch_a.diff_branch_diff.uuid, branch_a.base_branch_diff.uuid}
        assert set(plan.batches[1].root_uuids) == {branch_b.diff_branch_diff.uuid, branch_b.base_branch_diff.uuid}
        assert plan.num_diffs == 2
        assert plan.kept_root_uuids == ()

        for batch in plan.batches:
            await deleter.delete(batch=batch)

        assert await self._root_uuids(diff_repository=diff_repository) == {
            frozen.diff_branch_diff.uuid,
            frozen.base_branch_diff.uuid,
        }
        assert await self._count_diff_vertices(db=db) == num_frozen_vertices

    async def test_deletes_only_the_unfrozen_diffs_of_the_given_branch(
        self,
        db: InfrahubDatabase,
        diff_repository: DiffRepository,
        deleter: UnfrozenDiffDeleter,
        reset_database: None,
    ) -> None:
        branch_b = await self._save_diff(diff_repository=diff_repository, branch_name="branch-b")
        num_branch_b_vertices = await self._count_diff_vertices(db=db)
        await self._save_diff(diff_repository=diff_repository, branch_name="branch-a")
        await self._save_diff(
            diff_repository=diff_repository, branch_name="branch-a", tracking_id=NameTrackingId(name="named")
        )

        plan = await deleter.plan(branch_name="branch-a")

        assert [batch.diff_branch_name for batch in plan.batches] == ["branch-a"]
        assert plan.num_diffs == 2

        await deleter.delete(batch=plan.batches[0])

        assert await self._root_uuids(diff_repository=diff_repository) == {
            branch_b.diff_branch_diff.uuid,
            branch_b.base_branch_diff.uuid,
        }
        assert await self._count_diff_vertices(db=db) == num_branch_b_vertices

    @pytest.mark.parametrize("case", FROZEN_PARTNER_CASES, ids=lambda case: case.name)
    async def test_keeps_an_unfrozen_root_paired_with_a_frozen_root(
        self,
        diff_repository: DiffRepository,
        deleter: UnfrozenDiffDeleter,
        reset_database: None,
        case: FrozenPartnerCase,
    ) -> None:
        diffs = await self._save_diff(
            diff_repository=diff_repository,
            branch_name="branch-a",
            branch_root_frozen=case.branch_root_frozen,
            base_root_frozen=case.base_root_frozen,
        )
        unfrozen_root = diffs.base_branch_diff if case.branch_root_frozen else diffs.diff_branch_diff

        for branch_name in (None, "branch-a"):
            plan = await deleter.plan(branch_name=branch_name)

            assert plan.batches == ()
            assert plan.kept_root_uuids == (unfrozen_root.uuid,)

    async def test_deletes_a_base_root_left_without_its_branch_root_only_for_every_branch(
        self,
        diff_repository: DiffRepository,
        deleter: UnfrozenDiffDeleter,
        reset_database: None,
    ) -> None:
        diffs = await self._save_diff(diff_repository=diff_repository, branch_name="branch-a")
        await diff_repository.delete_diff_roots(diff_root_uuids=[diffs.diff_branch_diff.uuid])
        assert await self._root_uuids(diff_repository=diff_repository) == {diffs.base_branch_diff.uuid}

        assert (await deleter.plan(branch_name="branch-a")).batches == ()

        plan = await deleter.plan(branch_name=None)

        assert [(batch.base_branch_name, batch.diff_branch_name) for batch in plan.batches] == [
            (self.base_branch_name, self.base_branch_name)
        ]
        await deleter.delete(batch=plan.batches[0])
        assert await self._root_uuids(diff_repository=diff_repository) == set()

    @pytest.mark.parametrize("is_incremental", [True, False], ids=["incremental_lock", "full_lock"])
    async def test_waits_for_the_diff_update_of_the_branch_in_progress(
        self,
        db: InfrahubDatabase,
        diff_repository: DiffRepository,
        diff_locker: DiffLocker,
        reset_database: None,
        is_incremental: bool,
    ) -> None:
        await self._save_diff(diff_repository=diff_repository, branch_name="branch-a")
        events: list[str] = []
        deleter = UnfrozenDiffDeleter(
            diff_repository=RecordingDiffRepository(
                db=db, deserializer=EnrichedDiffDeserializer(parent_adder=DiffParentNodeAdder()), events=events
            ),
            diff_locker=diff_locker,
        )
        plan = await deleter.plan(branch_name="branch-a")
        update_started = asyncio.Event()
        update_may_finish = asyncio.Event()

        async def update_diff() -> None:
            async with diff_locker.acquire_lock(
                target_branch_name=self.base_branch_name, source_branch_name="branch-a", is_incremental=is_incremental
            ):
                update_started.set()
                await update_may_finish.wait()
                events.append("update finished")

        update = asyncio.create_task(update_diff())
        await update_started.wait()
        deletion = asyncio.create_task(deleter.delete(batch=plan.batches[0]))
        for _ in range(10):
            await asyncio.sleep(0)
        update_may_finish.set()
        await update
        await deletion

        assert events == ["update finished", "delete"]
        assert await self._root_uuids(diff_repository=diff_repository) == set()
