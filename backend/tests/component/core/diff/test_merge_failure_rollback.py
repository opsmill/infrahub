"""Rollback behavior when a branch merge fails partway through the merge queries.

A database error during one of the batched merge queries leaves the earlier
batches committed on the destination branch. The merge must roll those changes
back on its own before surfacing the failure, and a rollback requested before
the merge ever wrote anything must leave the graph untouched.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

from infrahub import lock
from infrahub.core import registry
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.data_check_synchronizer import DiffDataCheckSynchronizer
from infrahub.core.diff.diff_locker import DiffLocker
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.diff.merger.serializer import DiffMergeSerializer
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.merge.branch_merger import BranchMerger
from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp
from infrahub.dependencies.registry import get_component_registry
from infrahub.exceptions import MergeFailedError
from tests.conftest import do_car_person_schema_unregistered
from tests.helpers.db_validation import verify_graph

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


class InducedMergeError(Exception):
    pass


async def _count_branch_edges_at(db: InfrahubDatabase, branch: Branch, at: Timestamp) -> int:
    result = await db.execute_query(
        query="MATCH ()-[r {from: $at, branch: $branch}]->() RETURN count(r) AS c",
        params={"at": at.to_string(), "branch": branch.name},
    )
    return result[0].get("c")


class FailingPropertiesMergeDiffMerger(DiffMerger):
    """Fails on the properties merge query, after node merge batches have committed.

    Records how many merge-stamped edges the earlier batches committed to the
    destination branch so the test can prove the failure happened mid-merge.
    """

    edge_count_at_failure: int | None = None

    async def _merge_properties(
        self, at: Timestamp, property_diff_dicts: list[dict], migrated_kinds_id_map: dict[str, str]
    ) -> None:
        self.edge_count_at_failure = await _count_branch_edges_at(db=self.db, branch=self.destination_branch, at=at)
        raise InducedMergeError()


@dataclass
class StagedMerge:
    branch: Branch
    new_person_id: str
    car_id: str
    original_nbr_seats: int


class TestMergeFailureRollback:
    @pytest.fixture(scope="class", autouse=True)
    async def car_person_schema_class(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> SchemaBranch:
        return registry.schema.register_schema(
            schema=do_car_person_schema_unregistered(), branch=default_branch_scope_class.name
        )

    @pytest.fixture(scope="class")
    async def staged(self, db: InfrahubDatabase, default_branch_scope_class: Branch) -> StagedMerge:
        lock.initialize_lock(local_only=True)

        john = await Node.init(db=db, schema="TestPerson", branch=default_branch_scope_class)
        await john.new(db=db, name="John", height=175)
        await john.save(db=db)

        car = await Node.init(db=db, schema="TestCar", branch=default_branch_scope_class)
        await car.new(db=db, name="accord", nbr_seats=5, is_electric=False, owner=john.id)
        await car.save(db=db)

        branch = await create_branch(branch_name="merge-fail-rollback", db=db)

        new_person = await Node.init(db=db, schema="TestPerson", branch=branch)
        await new_person.new(db=db, name="Newcomer", height=170)
        await new_person.save(db=db)

        car_branch = await NodeManager.get_one(db=db, id=car.id, branch=branch, raise_on_error=True)
        car_branch.get_attribute("nbr_seats").value = 2
        car_branch.get_attribute("color").value = "#123456"
        await car_branch.save(db=db)

        return StagedMerge(
            branch=branch,
            new_person_id=new_person.id,
            car_id=car.id,
            original_nbr_seats=5,
        )

    @pytest.fixture
    async def diff_repository(self, db: InfrahubDatabase, staged: StagedMerge) -> DiffRepository:
        component_registry = get_component_registry()
        return await component_registry.get_component(DiffRepository, db=db, branch=staged.branch)

    @pytest.fixture
    async def diff_coordinator(self, db: InfrahubDatabase, staged: StagedMerge) -> DiffCoordinator:
        component_registry = get_component_registry()
        coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=staged.branch)
        coordinator.data_check_synchronizer = AsyncMock(spec=DiffDataCheckSynchronizer)
        return coordinator

    def _build_branch_merger(
        self,
        db: InfrahubDatabase,
        source_branch: Branch,
        destination_branch: Branch,
        diff_merger: DiffMerger,
        diff_coordinator: DiffCoordinator,
        diff_repository: DiffRepository,
    ) -> BranchMerger:
        return BranchMerger(
            db=db,
            source_branch=source_branch,
            destination_branch=destination_branch,
            diff_coordinator=diff_coordinator,
            diff_merger=diff_merger,
            diff_repository=diff_repository,
            diff_locker=DiffLocker(),
        )

    async def test_branch_merger_rolls_back_on_merge_query_failure(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        staged: StagedMerge,
        diff_coordinator: DiffCoordinator,
        diff_repository: DiffRepository,
    ) -> None:
        failing_diff_merger = FailingPropertiesMergeDiffMerger(
            db=db,
            source_branch=staged.branch,
            destination_branch=default_branch_scope_class,
            diff_repository=diff_repository,
            serializer=DiffMergeSerializer(db=db, max_batch_size=100),
        )
        merger = self._build_branch_merger(
            db=db,
            source_branch=staged.branch,
            destination_branch=default_branch_scope_class,
            diff_merger=failing_diff_merger,
            diff_coordinator=diff_coordinator,
            diff_repository=diff_repository,
        )

        merge_at = Timestamp()
        with pytest.raises(MergeFailedError) as exc_info:
            await merger.merge(at=merge_at)
        assert isinstance(exc_info.value.__cause__, InducedMergeError), (
            "The merge failure must originate from the induced merge error"
        )

        assert failing_diff_merger.edge_count_at_failure is not None
        assert failing_diff_merger.edge_count_at_failure > 0, (
            "The merge queries that ran before the failure must have committed edges"
        )

        edges_after = await _count_branch_edges_at(db=db, branch=default_branch_scope_class, at=merge_at)
        assert edges_after == 0, "The merge must remove every edge committed by the partial merge before raising"

        person_on_main = await NodeManager.get_one(db=db, id=staged.new_person_id, branch=default_branch_scope_class)
        assert person_on_main is None, "The branch-created node must not exist on the destination branch"

        car_on_main = await NodeManager.get_one(
            db=db, id=staged.car_id, branch=default_branch_scope_class, raise_on_error=True
        )
        assert car_on_main.get_attribute("nbr_seats").value == staged.original_nbr_seats

        await verify_graph(db=db)

    async def test_rollback_before_merge_is_a_noop(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        staged: StagedMerge,
        diff_coordinator: DiffCoordinator,
        diff_repository: DiffRepository,
    ) -> None:
        at_existing = Timestamp()
        bystander = await Node.init(db=db, schema="TestPerson", branch=default_branch_scope_class)
        await bystander.new(db=db, name="Bystander", height=180)
        await bystander.save(db=db, at=at_existing)

        diff_merger = DiffMerger(
            db=db,
            source_branch=staged.branch,
            destination_branch=default_branch_scope_class,
            diff_repository=diff_repository,
            serializer=DiffMergeSerializer(db=db, max_batch_size=100),
        )
        merger = self._build_branch_merger(
            db=db,
            source_branch=staged.branch,
            destination_branch=default_branch_scope_class,
            diff_merger=diff_merger,
            diff_coordinator=diff_coordinator,
            diff_repository=diff_repository,
        )

        await merger.rollback()
        await diff_merger.rollback(at=at_existing)

        bystander_after = await NodeManager.get_one(db=db, id=bystander.id, branch=default_branch_scope_class)
        assert bystander_after is not None, "Rollback before any merge must not delete data at the given timestamp"
        assert bystander_after.get_attribute("name").value == "Bystander"

    async def test_failed_merge_rollback_preserves_metadata_of_earlier_merge(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        staged: StagedMerge,
        diff_coordinator: DiffCoordinator,
        diff_repository: DiffRepository,
    ) -> None:
        """A failed merge must not rewind updated_at/by metadata written by an earlier successful merge.

        previous_updated_at/by snapshots survive successful merges, so the rollback of a later failed
        merge over the same nodes must only restore metadata stamped with its own merge timestamp.
        """
        # the overlap merge changes an attribute the staged branch does not touch, so the staged
        # branch's later merge fails on the induced error rather than on an unresolved conflict
        overlap_branch = await create_branch(branch_name="overlap-merged-first", db=db)
        car_overlap = await NodeManager.get_one(db=db, id=staged.car_id, branch=overlap_branch, raise_on_error=True)
        car_overlap.get_attribute("transmission").value = "manual"
        await car_overlap.save(db=db)
        merger = self._build_branch_merger(
            db=db,
            source_branch=overlap_branch,
            destination_branch=default_branch_scope_class,
            diff_merger=await self._build_diff_merger(db=db, branch=overlap_branch),
            diff_coordinator=await self._build_diff_coordinator(db=db, branch=overlap_branch),
            diff_repository=await self._build_diff_repository(db=db, branch=overlap_branch),
        )
        await merger.merge(at=Timestamp())

        metadata_before = await self._get_node_metadata(db=db, node_uuid=staged.car_id)
        assert metadata_before["previous_updated_at"] is not None, (
            "The successful merge must leave a previous_updated_at snapshot in place"
        )

        failing_diff_merger = FailingPropertiesMergeDiffMerger(
            db=db,
            source_branch=staged.branch,
            destination_branch=default_branch_scope_class,
            diff_repository=diff_repository,
            serializer=DiffMergeSerializer(db=db, max_batch_size=100),
        )
        merger = self._build_branch_merger(
            db=db,
            source_branch=staged.branch,
            destination_branch=default_branch_scope_class,
            diff_merger=failing_diff_merger,
            diff_coordinator=diff_coordinator,
            diff_repository=diff_repository,
        )
        with pytest.raises(MergeFailedError) as exc_info:
            await merger.merge(at=Timestamp())
        assert isinstance(exc_info.value.__cause__, InducedMergeError), (
            "The merge must fail on the induced mid-merge error, not an earlier validation step"
        )
        assert failing_diff_merger.edge_count_at_failure is not None, (
            "The merge must reach the graph write phase before failing"
        )

        metadata_after = await self._get_node_metadata(db=db, node_uuid=staged.car_id)
        assert metadata_after["updated_at"] == metadata_before["updated_at"], (
            "The failed merge's rollback must not rewind updated_at written by the earlier successful merge"
        )
        assert metadata_after["previous_updated_at"] == metadata_before["previous_updated_at"], (
            "The failed merge's rollback must not consume the earlier merge's previous_updated_at snapshot"
        )

    @staticmethod
    async def _build_diff_merger(db: InfrahubDatabase, branch: Branch) -> DiffMerger:
        component_registry = get_component_registry()
        return await component_registry.get_component(DiffMerger, db=db, branch=branch)

    @staticmethod
    async def _build_diff_coordinator(db: InfrahubDatabase, branch: Branch) -> DiffCoordinator:
        component_registry = get_component_registry()
        coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
        coordinator.data_check_synchronizer = AsyncMock(spec=DiffDataCheckSynchronizer)
        return coordinator

    @staticmethod
    async def _build_diff_repository(db: InfrahubDatabase, branch: Branch) -> DiffRepository:
        component_registry = get_component_registry()
        return await component_registry.get_component(DiffRepository, db=db, branch=branch)

    @staticmethod
    async def _get_node_metadata(db: InfrahubDatabase, node_uuid: str) -> dict[str, str | None]:
        result = await db.execute_query(
            query=(
                "MATCH (n:Node {uuid: $uuid}) "
                "RETURN n.updated_at AS updated_at, n.previous_updated_at AS previous_updated_at"
            ),
            params={"uuid": node_uuid},
        )
        return {
            "updated_at": result[0].get("updated_at"),
            "previous_updated_at": result[0].get("previous_updated_at"),
        }
