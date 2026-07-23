from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.components import ComponentType
from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.merger.exclusion_plan import MergeExclusionPlan, MergeExclusionPlanBuilder
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.merge.failure_recoverer import RecoveryOutcome
from infrahub.core.merge.write_blocker import MergeProtectionState, MergeWriteBlocker
from infrahub.core.node import Node
from infrahub.core.rollback import GraphRollbacker
from infrahub.core.timestamp import Timestamp
from infrahub.dependencies.registry import get_component_registry
from infrahub.services.component import InfrahubComponent
from tests.adapters.cache import MemoryCache
from tests.adapters.message_bus import BusRecorder
from tests.helpers.db_validation import count_branch_edges_at, get_node_metadata, verify_graph

from .conftest import FailAtBranchResetRecoverer, build_identifier, build_recovery

if TYPE_CHECKING:
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


async def _branch_edge_fingerprint(db: InfrahubDatabase, branch_name: str) -> list[tuple]:
    """Snapshot every edge on a branch, keyed on endpoints and timestamps.

    Two snapshots compare equal only when the graph is byte-for-byte identical for that branch, so
    an empty diff between a pre-merge and a post-recovery snapshot proves the rollback restored the
    branch exactly (new edges deleted, closed edges reopened to their original open state).

    This branch-scoped edge fingerprint is used instead of a whole-DB snapshot: a whole-DB snapshot
    hashes every node property, so the ``Branch`` vertex's ``merge_started_at`` (set at merge start
    and deliberately left in place after recovery) would make a pre-merge vs post-recovery snapshot
    differ even when the graph rollback was exact.
    """
    result = await db.execute_query(
        query=(
            "MATCH (src)-[r {branch: $branch}]->(dst) "
            "RETURN type(r) AS edge_type, elementId(src) AS src, elementId(dst) AS dst, "
            "r.from AS edge_from, r.to AS edge_to, r.status AS status"
        ),
        params={"branch": branch_name},
    )
    return sorted(
        (
            row.get("edge_type"),
            row.get("src"),
            row.get("dst"),
            row.get("edge_from"),
            row.get("edge_to"),
            row.get("status"),
        )
        for row in result
    )


class _MidMergeFailingDiffMerger(DiffMerger):
    """A real DiffMerger that commits the earlier bulk edges then raises before finishing.

    Reproduces a worker dying partway through the graph write phase: the earlier bulk queries have
    already committed on the default branch when a later one fails, leaving partially merged data with
    no in-process rollback for recovery to clean up.
    """

    async def _bulk_merge_relationship_property_edges(self, at: Timestamp, plan: MergeExclusionPlan) -> None:
        await super()._bulk_merge_relationship_property_edges(at=at, plan=plan)
        raise ValueError("mid-merge failure injected")


@dataclass
class _MergeDataset:
    """Data loaded once for the ordered fail->recover cycles that share a single branch."""

    branch: Branch
    alice_id: str
    bob_id: str
    original_branched_from: str


class TestRecoveryRollback:
    """Recovery of a failed merge restores the pre-merge default branch and is idempotent (real db).

    The tests intentionally run in definition order against the SAME branch: the class-scoped
    ``merge_dataset`` fixture loads the data once, and each test drives a full merge -> fail -> recover
    cycle on that branch. This exercises that a branch can fail to merge and be recovered repeatedly,
    always leaving the branch OPEN with its data intact so the next test can re-merge it. Because the
    default branch changes with every merge/recover, each test recomputes the branch diff before its
    merge. ``branched_from`` is set only at branch creation, so neither the merge nor the recovery
    touches it; each test asserts it still equals its original value as an invariant guard.
    """

    @pytest.fixture
    async def cache(self) -> MemoryCache:
        return MemoryCache()

    @pytest.fixture
    async def component(
        self, db: InfrahubDatabase, cache: MemoryCache, default_branch_scope_class: Branch
    ) -> InfrahubComponent:
        component = InfrahubComponent(
            cache=cache, db=db, message_bus=BusRecorder(), component_type=ComponentType.API_SERVER
        )
        await component.refresh_heartbeat()
        return component

    @pytest.fixture(scope="class")
    async def merge_dataset(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
        car_person_schema_scope_class: SchemaBranch,
    ) -> _MergeDataset:
        alice = await Node.init(db=db, schema="TestPerson", branch=default_branch_scope_class)
        await alice.new(db=db, name="Alice", height=170)
        await alice.save(db=db)

        branch = await create_branch(branch_name="recover-shared", db=db)
        original_branched_from = branch.get_branched_from()

        alice_on_branch = await NodeManager.get_one(db=db, id=alice.id, branch=branch, raise_on_error=True)
        alice_on_branch.get_attribute("height").value = 200
        await alice_on_branch.save(db=db)
        bob = await Node.init(db=db, schema="TestPerson", branch=branch)
        await bob.new(db=db, name="Bob", height=150)
        await bob.save(db=db)

        return _MergeDataset(
            branch=branch,
            alice_id=alice.id,
            bob_id=bob.id,
            original_branched_from=original_branched_from,
        )

    async def _flag_merge_failed(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        merge_at: Timestamp,
        cache: MemoryCache,
    ) -> MergeWriteBlocker:
        """Hand-set the failed-merge marker the orchestrator would persist, then raise the write block.

        Keys the marker on the timestamp the merge wrote at so recovery can find and roll back the
        partially merged data.
        """
        branch.merge_started_at = merge_at.to_string()
        branch.status = BranchStatus.MERGE_FAILED
        await branch.save(db=db)
        blocker = MergeWriteBlocker(cache=cache)
        await blocker.set(branch=branch.name, state=MergeProtectionState.MERGE_FAILED)
        return blocker

    async def test_recover_restores_graph_and_metadata(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        cache: MemoryCache,
        component: InfrahubComponent,
        merge_dataset: _MergeDataset,
    ) -> None:
        default_branch = default_branch_scope_class
        branch = await Branch.get_by_name(db=db, name=merge_dataset.branch.name)

        component_registry = get_component_registry()
        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
        diff_merger = await component_registry.get_component(DiffMerger, db=db, branch=branch)
        await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)

        pre_merge_fingerprint = await _branch_edge_fingerprint(db=db, branch_name=default_branch.name)
        alice_metadata_before = await get_node_metadata(db=db, node_uuid=merge_dataset.alice_id)

        merge_at = Timestamp()
        await diff_merger.merge_graph(at=merge_at)

        # The merge really landed on the default branch before we flag it as failed.
        assert await count_branch_edges_at(db=db, branch_name=default_branch.name, at=merge_at.to_string()) > 0
        alice_after_merge = await NodeManager.get_one(db=db, id=merge_dataset.alice_id, raise_on_error=True)
        assert alice_after_merge.get_attribute("height").value == 200
        assert (await get_node_metadata(db=db, node_uuid=merge_dataset.alice_id))["previous_updated_at"] is not None
        # Bob is new to the default branch: the merge stamps his vertex without a restore snapshot
        # (there was no earlier default-branch value to snapshot).
        bob_after_merge = await get_node_metadata(db=db, node_uuid=merge_dataset.bob_id)
        assert bob_after_merge["updated_at"] is not None
        assert bob_after_merge["previous_updated_at"] is None

        # The merge does not touch branched_from; it stays at its branch-creation value.
        after_merge = await Branch.get_by_name(db=db, name=branch.name)
        assert after_merge.branched_from == merge_dataset.original_branched_from

        blocker = await self._flag_merge_failed(
            db=db,
            branch=after_merge,
            merge_at=merge_at,
            cache=cache,
        )

        recovery = build_recovery(db=db, cache=cache, component=component, default_branch=default_branch)
        report = await recovery.recover()

        assert report.outcome == RecoveryOutcome.RECOVERED
        assert report.branch == branch.name
        assert report.merge_started_at == merge_at.to_string()

        # Graph diff versus the pre-merge snapshot is empty.
        assert await _branch_edge_fingerprint(db=db, branch_name=default_branch.name) == pre_merge_fingerprint
        assert await count_branch_edges_at(db=db, branch_name=default_branch.name, at=merge_at.to_string()) == 0

        # Touched-node updated_at/by is restored to its pre-merge value.
        assert await get_node_metadata(db=db, node_uuid=merge_dataset.alice_id) == alice_metadata_before

        # A vertex stamped by the merge without a snapshot must have its merge-time stamps cleared
        assert await get_node_metadata(db=db, node_uuid=merge_dataset.bob_id) == {
            "updated_at": None,
            "previous_updated_at": None,
        }

        # Data on the default branch is reverted.
        alice_main = await NodeManager.get_one(db=db, id=merge_dataset.alice_id, raise_on_error=True)
        assert alice_main.get_attribute("height").value == 170
        assert await NodeManager.get_one(db=db, id=merge_dataset.bob_id) is None

        # The branch is reopened and the write protection is lifted; branched_from was never touched by
        # the merge or the recovery, so it still equals its branch-creation value.
        reloaded = await Branch.get_by_name(db=db, name=branch.name)
        assert reloaded.status == BranchStatus.OPEN
        assert reloaded.branched_from == merge_dataset.original_branched_from
        assert await blocker.get() is None

        await verify_graph(db=db)

        # A second run after a completed recovery finds nothing to do and leaves the graph unchanged.
        second = await recovery.recover()
        assert second.outcome == RecoveryOutcome.NOTHING_TO_RECOVER
        assert await _branch_edge_fingerprint(db=db, branch_name=default_branch.name) == pre_merge_fingerprint

    async def test_interrupted_recovery_is_idempotent(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        cache: MemoryCache,
        component: InfrahubComponent,
        merge_dataset: _MergeDataset,
    ) -> None:
        default_branch = default_branch_scope_class
        branch = await Branch.get_by_name(db=db, name=merge_dataset.branch.name)

        component_registry = get_component_registry()
        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
        diff_merger = await component_registry.get_component(DiffMerger, db=db, branch=branch)
        # The prior test's merge/recover cycle left new edges on the default branch, so the persisted
        # diff and the fingerprint must both be recomputed against the current default-branch state
        # before this cycle's merge.
        await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)

        pre_merge_fingerprint = await _branch_edge_fingerprint(db=db, branch_name=default_branch.name)

        merge_at = Timestamp()
        await diff_merger.merge_graph(at=merge_at)

        after_merge = await Branch.get_by_name(db=db, name=branch.name)
        blocker = await self._flag_merge_failed(
            db=db,
            branch=after_merge,
            merge_at=merge_at,
            cache=cache,
        )

        # First run: the rollback lands, then the branch reset fails, so the branch stays flagged.
        failing = FailAtBranchResetRecoverer(
            db=db,
            merge_write_blocker=blocker,
            identifier=build_identifier(db=db, cache=cache, component=component, default_branch=default_branch),
            default_branch=default_branch,
            cache=cache,
            rollbacker=GraphRollbacker(db=db),
        )
        first = await failing.recover()

        assert first.outcome == RecoveryOutcome.FAILED
        # The rollback already restored the graph, but the branch stays flagged and protected.
        assert await _branch_edge_fingerprint(db=db, branch_name=default_branch.name) == pre_merge_fingerprint
        reloaded = await Branch.get_by_name(db=db, name=branch.name)
        assert reloaded.status == BranchStatus.MERGE_FAILED
        assert await blocker.get() is not None

        # A full re-run re-detects the branch; the second rollback is a safe no-op and it finishes.
        recovery = build_recovery(db=db, cache=cache, component=component, default_branch=default_branch)
        second = await recovery.recover()

        assert second.outcome == RecoveryOutcome.RECOVERED
        assert await _branch_edge_fingerprint(db=db, branch_name=default_branch.name) == pre_merge_fingerprint
        assert await count_branch_edges_at(db=db, branch_name=default_branch.name, at=merge_at.to_string()) == 0
        assert await NodeManager.get_one(db=db, id=merge_dataset.bob_id) is None
        # Alice's default-branch value is reverted to its pre-merge height, undoing the merged change.
        alice_main = await NodeManager.get_one(db=db, id=merge_dataset.alice_id, raise_on_error=True)
        assert alice_main.get_attribute("height").value == 170
        reloaded = await Branch.get_by_name(db=db, name=branch.name)
        assert reloaded.status == BranchStatus.OPEN
        assert reloaded.branched_from == merge_dataset.original_branched_from
        assert await blocker.get() is None

        await verify_graph(db=db)

    async def test_recover_restores_partial_graph_after_mid_merge_failure(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        cache: MemoryCache,
        component: InfrahubComponent,
        merge_dataset: _MergeDataset,
    ) -> None:
        default_branch = default_branch_scope_class
        branch = await Branch.get_by_name(db=db, name=merge_dataset.branch.name)

        component_registry = get_component_registry()
        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
        diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=branch)
        diff_merger = _MidMergeFailingDiffMerger(
            db=db,
            source_branch=branch,
            destination_branch=default_branch,
            diff_repository=diff_repository,
            exclusion_plan_builder=MergeExclusionPlanBuilder(),
            rollbacker=GraphRollbacker(db=db),
        )
        await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)

        pre_merge_fingerprint = await _branch_edge_fingerprint(db=db, branch_name=default_branch.name)

        merge_at = Timestamp()
        with pytest.raises(ValueError, match=r"^mid-merge failure injected$"):
            await diff_merger.merge_graph(at=merge_at)

        # The earlier bulk queries committed partial data on the default branch before the failure.
        assert await count_branch_edges_at(db=db, branch_name=default_branch.name, at=merge_at.to_string()) > 0

        after_merge = await Branch.get_by_name(db=db, name=branch.name)
        blocker = await self._flag_merge_failed(
            db=db,
            branch=after_merge,
            merge_at=merge_at,
            cache=cache,
        )

        recovery = build_recovery(db=db, cache=cache, component=component, default_branch=default_branch)
        report = await recovery.recover()

        assert report.outcome == RecoveryOutcome.RECOVERED

        # The partially merged graph is fully reverted to its pre-merge state.
        assert await _branch_edge_fingerprint(db=db, branch_name=default_branch.name) == pre_merge_fingerprint
        assert await count_branch_edges_at(db=db, branch_name=default_branch.name, at=merge_at.to_string()) == 0
        # Bob (added on the branch) never lands on the default branch, and Alice's height is reverted.
        assert await NodeManager.get_one(db=db, id=merge_dataset.bob_id) is None
        alice_main = await NodeManager.get_one(db=db, id=merge_dataset.alice_id, raise_on_error=True)
        assert alice_main.get_attribute("height").value == 170

        reloaded = await Branch.get_by_name(db=db, name=branch.name)
        assert reloaded.status == BranchStatus.OPEN
        assert reloaded.branched_from == merge_dataset.original_branched_from
        assert await blocker.get() is None

        await verify_graph(db=db)
