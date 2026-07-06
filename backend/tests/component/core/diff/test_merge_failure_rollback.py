"""Rollback behavior when a branch merge fails partway through the bulk merge phase.

A database error during one of the bulk merge queries leaves the earlier bulk
queries committed on the destination branch. The merge must roll those changes
back on its own before surfacing the failure, and a rollback requested before
the merge ever wrote anything must leave the graph untouched.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

from infrahub import lock
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.data_check_synchronizer import DiffDataCheckSynchronizer
from infrahub.core.diff.diff_locker import DiffLocker
from infrahub.core.diff.merger.exclusion_plan import MergeExclusionPlanBuilder
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.merge.branch_merger import BranchMerger
from infrahub.core.merge.constraints import MergeConstraintValidator
from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp
from infrahub.dependencies.registry import get_component_registry
from infrahub.exceptions import MergeFailedError
from tests.helpers.db_validation import verify_graph

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.diff.merger.exclusion_plan import MergeExclusionPlan
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


class InducedBulkMergeError(Exception):
    pass


async def _count_branch_edges_at(db: InfrahubDatabase, branch: Branch, at: Timestamp) -> int:
    result = await db.execute_query(
        query="MATCH ()-[r {from: $at, branch: $branch}]->() RETURN count(r) AS c",
        params={"at": at.to_string(), "branch": branch.name},
    )
    return result[0].get("c")


class FailingBulkMergeDiffMerger(DiffMerger):
    """Fails on the last bulk merge query, after the earlier bulk queries have committed.

    Records how many merge-stamped edges the earlier bulk queries committed to the
    destination branch so the test can prove the failure happened mid-merge.
    """

    edge_count_at_failure: int | None = None

    async def _bulk_merge_relationship_property_edges(self, at: Timestamp, plan: MergeExclusionPlan) -> None:
        self.edge_count_at_failure = await _count_branch_edges_at(db=self.db, branch=self.destination_branch, at=at)
        raise InducedBulkMergeError()


@dataclass
class StagedMerge:
    branch: Branch
    new_person_id: str
    car_id: str
    original_nbr_seats: int


class TestMergeFailureRollback:
    @pytest.fixture(scope="class", autouse=True)
    async def _schema(
        self,
        register_core_models_schema_scope_class: SchemaBranch,
        car_person_schema_scope_class: SchemaBranch,
    ) -> None:
        return

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
        staged: StagedMerge,
        destination_branch: Branch,
        diff_merger: DiffMerger,
        diff_coordinator: DiffCoordinator,
        diff_repository: DiffRepository,
    ) -> BranchMerger:
        return BranchMerger(
            db=db,
            source_branch=staged.branch,
            destination_branch=destination_branch,
            diff_coordinator=diff_coordinator,
            diff_merger=diff_merger,
            diff_repository=diff_repository,
            diff_locker=DiffLocker(),
            constraint_validator=MergeConstraintValidator(db=db, branch=staged.branch, diff_repository=diff_repository),
        )

    async def test_branch_merger_rolls_back_on_bulk_merge_failure(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        staged: StagedMerge,
        diff_coordinator: DiffCoordinator,
        diff_repository: DiffRepository,
    ) -> None:
        failing_diff_merger = FailingBulkMergeDiffMerger(
            db=db,
            source_branch=staged.branch,
            destination_branch=default_branch_scope_class,
            diff_repository=diff_repository,
            exclusion_plan_builder=MergeExclusionPlanBuilder(),
        )
        merger = self._build_branch_merger(
            db=db,
            staged=staged,
            destination_branch=default_branch_scope_class,
            diff_merger=failing_diff_merger,
            diff_coordinator=diff_coordinator,
            diff_repository=diff_repository,
        )

        merge_at = Timestamp()
        with pytest.raises(MergeFailedError) as exc_info:
            await merger.merge(at=merge_at)
        assert isinstance(exc_info.value.__cause__, InducedBulkMergeError), (
            "The merge failure must originate from the induced bulk merge error"
        )

        assert failing_diff_merger.edge_count_at_failure is not None
        assert failing_diff_merger.edge_count_at_failure > 0, (
            "The bulk queries that ran before the failure must have committed edges"
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
            exclusion_plan_builder=MergeExclusionPlanBuilder(),
        )
        merger = self._build_branch_merger(
            db=db,
            staged=staged,
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
