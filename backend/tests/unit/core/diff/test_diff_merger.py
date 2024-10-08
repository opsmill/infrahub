from unittest.mock import AsyncMock, call
from uuid import uuid4

import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import DiffAction
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.diff.merger.serializer import DiffMergeSerializer
from infrahub.core.diff.model.path import (
    BranchTrackingId,
    ConflictSelection,
    EnrichedDiffNode,
    EnrichedDiffRoot,
)
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import NodeNotFoundError

from .factories import (
    EnrichedAttributeFactory,
    EnrichedConflictFactory,
    EnrichedNodeFactory,
    EnrichedPropertyFactory,
    EnrichedRelationshipElementFactory,
    EnrichedRelationshipGroupFactory,
    EnrichedRootFactory,
)


class TestMergeDiff:
    @pytest.fixture
    async def source_branch(self, db: InfrahubDatabase, default_branch: Branch) -> Branch:
        return await create_branch(db=db, branch_name="source")

    @pytest.fixture
    def mock_diff_repository(self) -> DiffRepository:
        return AsyncMock(spec=DiffRepository)

    @pytest.fixture
    def diff_merger(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        source_branch: Branch,
        mock_diff_repository: DiffRepository,
        car_person_schema: SchemaBranch,
    ) -> DiffMerger:
        return DiffMerger(
            db=db,
            source_branch=source_branch,
            destination_branch=default_branch,
            diff_repository=mock_diff_repository,
            serializer=DiffMergeSerializer(schema_branch=car_person_schema, max_batch_size=50),
        )

    @pytest.fixture
    async def person_node_branch(self, db: InfrahubDatabase, source_branch: Branch, car_person_schema) -> Node:
        new_node = await Node.init(db=db, schema="TestPerson", branch=source_branch)
        await new_node.new(db=db, name="Albert", height=172)
        await new_node.save(db=db)
        return new_node

    @pytest.fixture
    async def car_node_branch(
        self, db: InfrahubDatabase, source_branch: Branch, person_node_branch: Node, car_person_schema
    ) -> Node:
        new_node = await Node.init(db=db, schema="TestCar", branch=source_branch)
        await new_node.new(db=db, name="El Camino", color="black", nbr_seats=5, owner=person_node_branch)
        await new_node.save(db=db)
        return new_node

    @pytest.fixture
    async def person_node_main(self, db: InfrahubDatabase, default_branch: Branch, car_person_schema) -> Node:
        new_node = await Node.init(db=db, schema="TestPerson", branch=default_branch)
        await new_node.new(db=db, name="Albert", height=172)
        await new_node.save(db=db)
        return new_node

    @pytest.fixture
    def empty_diff_root(self, default_branch: Branch, source_branch: Branch) -> EnrichedDiffRoot:
        return EnrichedRootFactory.build(
            base_branch_name=default_branch.name,
            diff_branch_name=source_branch.name,
            from_time=Timestamp(source_branch.get_created_at()),
            to_time=Timestamp(),
            uuid=str(uuid4()),
            partner_uuid=str(uuid4()),
            tracking_id=BranchTrackingId(name=source_branch.name),
            nodes=set(),
        )

    def _get_empty_node_diff(self, node: Node, action: DiffAction) -> EnrichedDiffNode:
        return EnrichedNodeFactory.build(
            uuid=node.get_id(), action=action, kind=node.get_kind(), label="", attributes=set(), relationships=set()
        )

    async def test_merge_node_added(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        source_branch: Branch,
        person_node_branch: Node,
        car_node_branch: Node,
        mock_diff_repository: DiffRepository,
        diff_merger: DiffMerger,
        empty_diff_root: EnrichedDiffRoot,
    ):
        added_node_diff = self._get_empty_node_diff(node=person_node_branch, action=DiffAction.ADDED)
        added_height_value_property = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.HAS_VALUE,
            previous_value=None,
            new_value=person_node_branch.height.value,
            action=DiffAction.ADDED,
            conflict=None,
        )
        added_height_owner_property = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.HAS_OWNER,
            previous_value=None,
            new_value=person_node_branch.id,
            action=DiffAction.ADDED,
            conflict=None,
        )
        added_attribute_diff = EnrichedAttributeFactory.build(
            name="height",
            action=DiffAction.ADDED,
            properties={added_height_value_property, added_height_owner_property},
        )
        added_node_diff.attributes = {added_attribute_diff}
        added_is_related_property = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.IS_RELATED,
            previous_value=None,
            new_value=car_node_branch.id,
            action=DiffAction.ADDED,
            conflict=None,
        )
        added_relationship_element = EnrichedRelationshipElementFactory.build(
            action=DiffAction.ADDED, peer_id=car_node_branch.id, conflict=None, properties={added_is_related_property}
        )
        added_relationship = EnrichedRelationshipGroupFactory.build(
            name="cars",
            relationships={added_relationship_element},
            action=DiffAction.UPDATED,
        )
        added_node_diff.relationships = {added_relationship}
        empty_diff_root.nodes = {added_node_diff}
        mock_diff_repository.get_one.return_value = empty_diff_root
        at = Timestamp()

        await diff_merger.merge_graph(at=at)

        mock_diff_repository.get_one.assert_awaited_once_with(
            diff_branch_name=source_branch.name, tracking_id=BranchTrackingId(name=source_branch.name)
        )

    async def test_merge_node_added_idempotent(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        source_branch: Branch,
        person_node_branch: Node,
        mock_diff_repository: DiffRepository,
        diff_merger: DiffMerger,
        empty_diff_root: EnrichedDiffRoot,
    ):
        added_node_diff = self._get_empty_node_diff(node=person_node_branch, action=DiffAction.ADDED)
        empty_diff_root.nodes = {added_node_diff}
        mock_diff_repository.get_one.return_value = empty_diff_root
        at = Timestamp()

        await diff_merger.merge_graph(at=at)
        await diff_merger.merge_graph(at=at)

        assert mock_diff_repository.get_one.await_args_list == [
            call(diff_branch_name=source_branch.name, tracking_id=BranchTrackingId(name=source_branch.name)),
            call(diff_branch_name=source_branch.name, tracking_id=BranchTrackingId(name=source_branch.name)),
        ]
        target_car = await NodeManager.get_one(db=db, branch=default_branch, id=person_node_branch.id)
        assert target_car.id == person_node_branch.id
        assert target_car.get_updated_at() == at

    async def test_merge_node_deleted(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        person_node_main: Node,
        source_branch: Branch,
        mock_diff_repository: DiffRepository,
        diff_merger: DiffMerger,
        empty_diff_root: EnrichedDiffRoot,
    ):
        person_node_branch = await NodeManager.get_one(db=db, branch=source_branch, id=person_node_main.id)
        await person_node_branch.delete(db=db)
        deleted_node_diff = self._get_empty_node_diff(node=person_node_branch, action=DiffAction.REMOVED)
        empty_diff_root.nodes = {deleted_node_diff}
        mock_diff_repository.get_one.return_value = empty_diff_root
        at = Timestamp()

        await diff_merger.merge_graph(at=at)

        mock_diff_repository.get_one.assert_awaited_once_with(
            diff_branch_name=source_branch.name, tracking_id=BranchTrackingId(name=source_branch.name)
        )
        with pytest.raises(NodeNotFoundError):
            await NodeManager.get_one(db=db, branch=default_branch, id=person_node_main.id, raise_on_error=True)

    async def test_merge_node_deleted_idempotent(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        person_node_main: Node,
        source_branch: Branch,
        mock_diff_repository: DiffRepository,
        diff_merger: DiffMerger,
        empty_diff_root: EnrichedDiffRoot,
    ):
        person_node_branch = await NodeManager.get_one(db=db, branch=source_branch, id=person_node_main.id)
        await person_node_branch.delete(db=db)
        deleted_node_diff = self._get_empty_node_diff(node=person_node_branch, action=DiffAction.REMOVED)
        empty_diff_root.nodes = {deleted_node_diff}
        mock_diff_repository.get_one.return_value = empty_diff_root
        at = Timestamp()

        await diff_merger.merge_graph(at=at)
        await diff_merger.merge_graph(at=at)

        assert mock_diff_repository.get_one.await_args_list == [
            call(diff_branch_name=source_branch.name, tracking_id=BranchTrackingId(name=source_branch.name)),
            call(diff_branch_name=source_branch.name, tracking_id=BranchTrackingId(name=source_branch.name)),
        ]
        with pytest.raises(NodeNotFoundError):
            await NodeManager.get_one(db=db, branch=default_branch, id=person_node_main.id, raise_on_error=True)

    @pytest.mark.parametrize(
        "conflict_selection,expect_deleted",
        [(ConflictSelection.DIFF_BRANCH, True), (ConflictSelection.BASE_BRANCH, False)],
    )
    async def test_merge_node_deleted_with_conflict(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        person_node_main: Node,
        source_branch: Branch,
        mock_diff_repository: DiffRepository,
        diff_merger: DiffMerger,
        empty_diff_root: EnrichedDiffRoot,
        conflict_selection: ConflictSelection,
        expect_deleted: bool,
    ):
        person_node_branch = await NodeManager.get_one(db=db, branch=source_branch, id=person_node_main.id)
        await person_node_branch.delete(db=db)
        deleted_node_diff = self._get_empty_node_diff(node=person_node_branch, action=DiffAction.REMOVED)
        node_conflict = EnrichedConflictFactory.build(
            base_branch_action=DiffAction.UPDATED,
            diff_branch_action=DiffAction.REMOVED,
            selected_branch=conflict_selection,
        )
        deleted_node_diff.conflict = node_conflict
        empty_diff_root.nodes = {deleted_node_diff}
        mock_diff_repository.get_one.return_value = empty_diff_root
        at = Timestamp()

        await diff_merger.merge_graph(at=at)

        mock_diff_repository.get_one.assert_awaited_once_with(
            diff_branch_name=source_branch.name, tracking_id=BranchTrackingId(name=source_branch.name)
        )
        if expect_deleted:
            with pytest.raises(NodeNotFoundError):
                await NodeManager.get_one(db=db, branch=default_branch, id=person_node_main.id, raise_on_error=True)
        else:
            target_car = await NodeManager.get_one(db=db, branch=default_branch, id=person_node_branch.id)
            assert target_car.id == person_node_branch.id
            assert target_car.get_updated_at() < at
