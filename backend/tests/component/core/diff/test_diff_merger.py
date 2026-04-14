"""Tests for the DiffMerger fallback path (conflicted nodes).

The DiffMerger routes conflicted nodes through the serializer-based fallback:
load the diff for conflicted UUIDs, serialize to batches, pass to DiffMergeQuery
and DiffMergePropertiesQuery. These tests create actual conflicts and verify
the fallback produces correct results.
"""

from unittest.mock import AsyncMock

import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import MetadataOptions
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.data_check_synchronizer import DiffDataCheckSynchronizer
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.diff.model.path import ConflictSelection
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.dependencies.registry import get_component_registry
from infrahub.exceptions import NodeNotFoundError
from tests.helpers.db_validation import verify_graph


class TestMergeDiffFallback:
    """Tests that exercise the serializer-based fallback path for conflicted nodes."""

    @pytest.fixture(autouse=True)
    async def _setup_core_schema(self, register_core_models_schema: SchemaBranch) -> None:
        return

    async def _get_diff_coordinator(self, db: InfrahubDatabase, branch: Branch) -> DiffCoordinator:
        component_registry = get_component_registry()
        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
        diff_coordinator.data_check_synchronizer = AsyncMock(spec=DiffDataCheckSynchronizer)
        return diff_coordinator

    async def _get_diff_merger(self, db: InfrahubDatabase, branch: Branch) -> DiffMerger:
        component_registry = get_component_registry()
        return await component_registry.get_component(DiffMerger, db=db, branch=branch)

    @pytest.fixture
    async def diff_repository(self, db: InfrahubDatabase, default_branch: Branch) -> DiffRepository:
        component_registry = get_component_registry()
        return await component_registry.get_component(DiffRepository, db=db, branch=default_branch)

    @pytest.mark.parametrize(
        "conflict_selection,expected_height,expected_user",
        [
            (ConflictSelection.DIFF_BRANCH, 150, "branch-user"),
            (ConflictSelection.BASE_BRANCH, 200, "main-user"),
        ],
    )
    async def test_attribute_value_conflict(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        diff_repository: DiffRepository,
        person_john_main: Node,
        car_person_schema: SchemaBranch,
        conflict_selection: ConflictSelection,
        expected_height: int,
        expected_user: str,
    ) -> None:
        """Attribute value changed on both branches, resolved as base or diff."""
        branch = await create_branch(db=db, branch_name="branch1")

        before_main_update = Timestamp()
        person_main = await NodeManager.get_one(db=db, id=person_john_main.id)
        person_main.height.value = 200
        await person_main.save(db=db, user_id="main-user")
        after_main_update = Timestamp()

        person_branch = await NodeManager.get_one(db=db, branch=branch, id=person_john_main.id)
        person_branch.height.value = 150
        await person_branch.save(db=db, user_id="branch-user")

        diff_coordinator = await self._get_diff_coordinator(db=db, branch=branch)
        enriched_diff_metadata = await diff_coordinator.update_branch_diff(
            base_branch=default_branch, diff_branch=branch
        )
        enriched_diff = await diff_repository.get_one(
            diff_branch_name=enriched_diff_metadata.diff_branch_name, diff_id=enriched_diff_metadata.uuid
        )
        conflicts_map = enriched_diff.get_all_conflicts()
        assert len(conflicts_map) >= 1
        for conflict in conflicts_map.values():
            await diff_repository.update_conflict_by_id(conflict_id=conflict.uuid, selection=conflict_selection)

        merge_at = Timestamp()
        diff_merger = await self._get_diff_merger(db=db, branch=branch)
        await diff_merger.merge_graph(at=merge_at)

        updated_person = await NodeManager.get_one(
            db=db, id=person_john_main.id, include_metadata=MetadataOptions.USER_TIMESTAMPS
        )
        assert updated_person.height.value == expected_height
        assert updated_person._get_updated_by() == expected_user
        if conflict_selection is ConflictSelection.DIFF_BRANCH:
            assert updated_person._get_updated_at() == merge_at
        else:
            assert before_main_update < updated_person._get_updated_at() < after_main_update

        await verify_graph(db=db)

    @pytest.mark.parametrize(
        "conflict_selection,expect_deleted",
        [(ConflictSelection.DIFF_BRANCH, True), (ConflictSelection.BASE_BRANCH, False)],
    )
    async def test_node_delete_conflict(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        diff_repository: DiffRepository,
        person_john_main: Node,
        car_person_schema: SchemaBranch,
        conflict_selection: ConflictSelection,
        expect_deleted: bool,
    ) -> None:
        """Node deleted on branch, updated on main. Resolved as base or diff."""
        branch = await create_branch(db=db, branch_name="branch1")

        person_main = await NodeManager.get_one(db=db, id=person_john_main.id)
        person_main.height.value = 200
        await person_main.save(db=db, user_id="main-user")

        person_branch = await NodeManager.get_one(db=db, branch=branch, id=person_john_main.id)
        await person_branch.delete(db=db, user_id="branch-user")

        diff_coordinator = await self._get_diff_coordinator(db=db, branch=branch)
        enriched_diff_metadata = await diff_coordinator.update_branch_diff(
            base_branch=default_branch, diff_branch=branch
        )
        enriched_diff = await diff_repository.get_one(
            diff_branch_name=enriched_diff_metadata.diff_branch_name, diff_id=enriched_diff_metadata.uuid
        )
        conflicts_map = enriched_diff.get_all_conflicts()
        assert len(conflicts_map) >= 1
        for conflict in conflicts_map.values():
            await diff_repository.update_conflict_by_id(conflict_id=conflict.uuid, selection=conflict_selection)

        merge_at = Timestamp()
        diff_merger = await self._get_diff_merger(db=db, branch=branch)
        await diff_merger.merge_graph(at=merge_at)

        if expect_deleted:
            with pytest.raises(NodeNotFoundError):
                await NodeManager.get_one(db=db, id=person_john_main.id, raise_on_error=True)
        else:
            updated_person = await NodeManager.get_one(db=db, id=person_john_main.id)
            assert updated_person is not None
            assert updated_person.height.value == 200

        await verify_graph(db=db)

    @pytest.mark.parametrize(
        "conflict_selection",
        [ConflictSelection.DIFF_BRANCH, ConflictSelection.BASE_BRANCH],
    )
    async def test_relationship_conflict(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        diff_repository: DiffRepository,
        person_john_main: Node,
        person_jane_main: Node,
        person_alfred_main: Node,
        car_accord_main: Node,
        car_person_schema: SchemaBranch,
        conflict_selection: ConflictSelection,
    ) -> None:
        """Cardinality-one relationship changed on both branches, resolved as base or diff."""
        branch = await create_branch(db=db, branch_name="branch1")

        car_main = await NodeManager.get_one(db=db, id=car_accord_main.id)
        await car_main.owner.update(db=db, data=person_alfred_main)
        await car_main.save(db=db, user_id="main-user")

        car_branch = await NodeManager.get_one(db=db, branch=branch, id=car_accord_main.id)
        await car_branch.owner.update(db=db, data=person_jane_main)
        await car_branch.save(db=db, user_id="branch-user")

        diff_coordinator = await self._get_diff_coordinator(db=db, branch=branch)
        enriched_diff_metadata = await diff_coordinator.update_branch_diff(
            base_branch=default_branch, diff_branch=branch
        )
        enriched_diff = await diff_repository.get_one(
            diff_branch_name=enriched_diff_metadata.diff_branch_name, diff_id=enriched_diff_metadata.uuid
        )
        conflicts_map = enriched_diff.get_all_conflicts()
        assert len(conflicts_map) == 1
        conflict = next(iter(conflicts_map.values()))
        await diff_repository.update_conflict_by_id(conflict_id=conflict.uuid, selection=conflict_selection)

        merge_at = Timestamp()
        diff_merger = await self._get_diff_merger(db=db, branch=branch)
        await diff_merger.merge_graph(at=merge_at)

        updated_car = await NodeManager.get_one(db=db, id=car_accord_main.id, prefetch_relationships=True)
        owner_rel = await updated_car.owner.get(db=db)
        if conflict_selection is ConflictSelection.DIFF_BRANCH:
            assert owner_rel.peer_id == person_jane_main.id
        else:
            assert owner_rel.peer_id == person_alfred_main.id

        await verify_graph(db=db)
