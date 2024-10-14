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
        new_node.height.is_protected = True
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
    async def person_node_main2(self, db: InfrahubDatabase, default_branch: Branch, car_person_schema) -> Node:
        new_node = await Node.init(db=db, schema="TestPerson", branch=default_branch)
        await new_node.new(db=db, name="Jermaine", height=165)
        await new_node.save(db=db)
        return new_node

    @pytest.fixture
    async def car_node_main(
        self, db: InfrahubDatabase, default_branch: Branch, person_node_main: Node, car_person_schema
    ) -> Node:
        new_node = await Node.init(db=db, schema="TestCar", branch=default_branch)
        await new_node.new(db=db, name="El Camino", color="black", nbr_seats=5, owner=person_node_main)
        await new_node.save(db=db)
        return new_node

    @pytest.fixture
    async def car_node_main2(
        self, db: InfrahubDatabase, default_branch: Branch, person_node_main2: Node, car_person_schema
    ) -> Node:
        new_node = await Node.init(db=db, schema="TestCar", branch=default_branch)
        await new_node.new(db=db, name="Civic", color="purple", nbr_seats=5, owner=person_node_main2)
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

    @pytest.fixture
    def deleted_person_node_diff(self, person_node_main, car_node_main) -> EnrichedDiffNode:
        deleted_node_diff = self._get_empty_node_diff(node=person_node_main, action=DiffAction.REMOVED)
        # attributes
        deleted_height_value_property = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.HAS_VALUE,
            previous_value=str(person_node_main.height.value),
            new_value=None,
            action=DiffAction.REMOVED,
            conflict=None,
        )
        deleted_height_owner_property = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.HAS_OWNER,
            previous_value=person_node_main.id,
            new_value=None,
            action=DiffAction.REMOVED,
            conflict=None,
        )
        deleted_height_visible_property = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.IS_VISIBLE,
            previous_value="True",
            new_value=None,
            action=DiffAction.REMOVED,
            conflict=None,
        )
        deleted_height_protected_property = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.IS_PROTECTED,
            previous_value="False",
            new_value=None,
            action=DiffAction.REMOVED,
            conflict=None,
        )
        deleted_attribute_diff = EnrichedAttributeFactory.build(
            name="height",
            action=DiffAction.REMOVED,
            properties={
                deleted_height_value_property,
                deleted_height_owner_property,
                deleted_height_visible_property,
                deleted_height_protected_property,
            },
        )
        deleted_node_diff.attributes = {deleted_attribute_diff}
        # relationships
        deleted_rel_is_visible_property = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.IS_VISIBLE,
            previous_value="True",
            new_value=None,
            action=DiffAction.REMOVED,
            conflict=None,
        )
        deleted_rel_is_protected_property = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.IS_PROTECTED,
            previous_value="False",
            new_value=None,
            action=DiffAction.REMOVED,
            conflict=None,
        )
        deleted_rel_source_property = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.HAS_SOURCE,
            previous_value=car_node_main.id,
            new_value=None,
            action=DiffAction.REMOVED,
            conflict=None,
        )
        deleted_is_related_property = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.IS_RELATED,
            previous_value=car_node_main.id,
            new_value=None,
            action=DiffAction.REMOVED,
            conflict=None,
        )
        deleted_relationship_element = EnrichedRelationshipElementFactory.build(
            action=DiffAction.REMOVED,
            peer_id=car_node_main.id,
            conflict=None,
            properties={
                deleted_is_related_property,
                deleted_rel_is_visible_property,
                deleted_rel_is_protected_property,
                deleted_rel_source_property,
            },
        )
        deleted_relationship = EnrichedRelationshipGroupFactory.build(
            name="cars",
            relationships={deleted_relationship_element},
            action=DiffAction.UPDATED,
        )
        deleted_node_diff.relationships = {deleted_relationship}
        return deleted_node_diff

    @pytest.fixture
    def added_person_node_diff(self, person_node_branch, car_node_branch) -> EnrichedDiffNode:
        added_node_diff = self._get_empty_node_diff(node=person_node_branch, action=DiffAction.ADDED)
        # attributes
        added_height_value_property = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.HAS_VALUE,
            previous_value=None,
            new_value=str(person_node_branch.height.value),
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
        added_height_visible_property = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.IS_VISIBLE,
            previous_value=None,
            new_value="True",
            action=DiffAction.ADDED,
            conflict=None,
        )
        added_height_protected_property = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.IS_PROTECTED,
            previous_value=None,
            new_value="True",
            action=DiffAction.ADDED,
            conflict=None,
        )
        added_attribute_diff = EnrichedAttributeFactory.build(
            name="height",
            action=DiffAction.ADDED,
            properties={
                added_height_value_property,
                added_height_owner_property,
                added_height_visible_property,
                added_height_protected_property,
            },
        )
        added_node_diff.attributes = {added_attribute_diff}
        # relationships
        added_rel_is_visible_property = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.IS_VISIBLE,
            previous_value=None,
            new_value="True",
            action=DiffAction.ADDED,
            conflict=None,
        )
        added_rel_is_protected_property = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.IS_PROTECTED,
            previous_value=None,
            new_value="False",
            action=DiffAction.ADDED,
            conflict=None,
        )
        added_rel_source_property = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.HAS_SOURCE,
            previous_value=None,
            new_value=car_node_branch.id,
            action=DiffAction.ADDED,
            conflict=None,
        )
        added_is_related_property = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.IS_RELATED,
            previous_value=None,
            new_value=car_node_branch.id,
            action=DiffAction.ADDED,
            conflict=None,
        )
        added_relationship_element = EnrichedRelationshipElementFactory.build(
            action=DiffAction.ADDED,
            peer_id=car_node_branch.id,
            conflict=None,
            properties={
                added_is_related_property,
                added_rel_is_visible_property,
                added_rel_is_protected_property,
                added_rel_source_property,
            },
        )
        added_relationship = EnrichedRelationshipGroupFactory.build(
            name="cars",
            relationships={added_relationship_element},
            action=DiffAction.UPDATED,
        )
        added_node_diff.relationships = {added_relationship}
        return added_node_diff

    def _get_empty_node_diff(self, node: Node, action: DiffAction) -> EnrichedDiffNode:
        return EnrichedNodeFactory.build(
            uuid=node.get_id(), action=action, kind=node.get_kind(), label="", attributes=set(), relationships=set()
        )

    @pytest.mark.parametrize("check_idempotent", [False, True])
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
        added_person_node_diff: EnrichedDiffNode,
        check_idempotent: bool,
    ):
        empty_diff_root.nodes = {added_person_node_diff}
        mock_diff_repository.get_one.return_value = empty_diff_root
        at = Timestamp()

        await diff_merger.merge_graph(at=at)
        if check_idempotent:
            await diff_merger.merge_graph(at=at)

        expected_awaits = [
            call(diff_branch_name=source_branch.name, tracking_id=BranchTrackingId(name=source_branch.name)),
        ]
        if check_idempotent:
            expected_awaits *= 2
        assert mock_diff_repository.get_one.await_args_list == expected_awaits

        retrieved_node = await NodeManager.get_one(
            db=db, id=person_node_branch.id, branch=default_branch, include_owner=True, include_source=True
        )
        assert retrieved_node.get_updated_at() == at
        assert retrieved_node.height.value == person_node_branch.height.value
        owner_node = await retrieved_node.height.get_owner(db=db)
        assert owner_node.id == retrieved_node.id
        assert retrieved_node.height.is_visible is True
        assert retrieved_node.height.is_protected is True
        car_rel_elements = await retrieved_node.cars.get(db=db)
        car_elements_by_peer_id = {c.get_peer_id(): c for c in car_rel_elements}
        assert set(car_elements_by_peer_id.keys()) == {car_node_branch.id}
        car_element = car_elements_by_peer_id[car_node_branch.id]
        assert car_element.source_id == car_node_branch.id

    @pytest.mark.parametrize("check_idempotent", [False, True])
    async def test_merge_node_deleted(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        person_node_main: Node,
        car_node_main: Node,
        source_branch: Branch,
        mock_diff_repository: DiffRepository,
        diff_merger: DiffMerger,
        empty_diff_root: EnrichedDiffRoot,
        deleted_person_node_diff: EnrichedDiffNode,
        check_idempotent: bool,
    ):
        person_branch = await NodeManager.get_one(db=db, branch=source_branch, id=person_node_main.id)
        await person_branch.delete(db=db)
        empty_diff_root.nodes = {deleted_person_node_diff}
        mock_diff_repository.get_one.return_value = empty_diff_root
        at = Timestamp()

        await diff_merger.merge_graph(at=at)
        if check_idempotent:
            await diff_merger.merge_graph(at=at)

        expected_awaits = [
            call(diff_branch_name=source_branch.name, tracking_id=BranchTrackingId(name=source_branch.name)),
        ]
        if check_idempotent:
            expected_awaits *= 2
        assert mock_diff_repository.get_one.await_args_list == expected_awaits

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
            target_person = await NodeManager.get_one(db=db, branch=default_branch, id=person_node_branch.id)
            assert target_person.id == person_node_branch.id
            assert target_person.get_updated_at() < at

    @pytest.fixture
    def updated_person_node_diff(
        self, person_node_main, car_node_main, person_node_main2, car_node_main2
    ) -> EnrichedDiffNode:
        updated_node_diff = self._get_empty_node_diff(node=person_node_main, action=DiffAction.UPDATED)
        # attributes
        updated_height_value_property = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.HAS_VALUE,
            previous_value=str(person_node_main.height.value),
            new_value=str(person_node_main.height.value + 1),
            action=DiffAction.UPDATED,
            conflict=None,
        )
        added_height_owner_property = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.HAS_OWNER,
            previous_value=None,
            new_value=str(person_node_main.id),
            action=DiffAction.ADDED,
            conflict=None,
        )
        updated_height_attribute_diff = EnrichedAttributeFactory.build(
            name="height",
            action=DiffAction.UPDATED,
            properties={updated_height_value_property, added_height_owner_property},
        )
        updated_name_value_property = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.HAS_VALUE,
            previous_value=str(person_node_main.name.value),
            new_value=str(person_node_main.name.value + "-branch"),
            action=DiffAction.UPDATED,
            conflict=EnrichedConflictFactory.build(
                base_branch_action=DiffAction.UPDATED,
                base_branch_value="whatever",
                diff_branch_action=DiffAction.UPDATED,
                diff_branch_value=str(person_node_main.name.value + "-branch"),
                selected_branch=ConflictSelection.DIFF_BRANCH,
            ),
        )
        updated_name_attribute_diff = EnrichedAttributeFactory.build(
            name="name",
            action=DiffAction.UPDATED,
            properties={updated_name_value_property},
        )
        updated_node_diff.attributes = {updated_height_attribute_diff, updated_name_attribute_diff}
        # relationships
        deleted_is_related_property = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.IS_RELATED,
            previous_value=car_node_main.id,
            new_value=None,
            action=DiffAction.REMOVED,
            conflict=None,
        )
        deleted_rel_is_visible_property = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.IS_VISIBLE,
            previous_value="True",
            new_value=None,
            action=DiffAction.REMOVED,
            conflict=None,
        )
        deleted_rel_is_protected_property = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.IS_PROTECTED,
            previous_value="False",
            new_value=None,
            action=DiffAction.REMOVED,
            conflict=None,
        )
        deleted_rel_source_property = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.HAS_SOURCE,
            previous_value=person_node_main2.id,
            new_value=None,
            action=DiffAction.REMOVED,
            conflict=None,
        )
        deleted_rel_owner_property = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.HAS_OWNER,
            previous_value=car_node_main2.id,
            new_value=None,
            action=DiffAction.REMOVED,
            conflict=None,
        )
        deleted_relationship_element = EnrichedRelationshipElementFactory.build(
            action=DiffAction.REMOVED,
            peer_id=car_node_main.id,
            conflict=None,
            properties={
                deleted_is_related_property,
                deleted_rel_is_visible_property,
                deleted_rel_is_protected_property,
                deleted_rel_source_property,
                deleted_rel_owner_property,
            },
        )
        deleted_relationship = EnrichedRelationshipGroupFactory.build(
            name="cars",
            relationships={deleted_relationship_element},
            action=DiffAction.UPDATED,
        )
        updated_node_diff.relationships = {deleted_relationship}
        return updated_node_diff

    @pytest.fixture
    def updated_car_diff(self, person_node_main, car_node_main, person_node_main2, car_node_main2) -> EnrichedDiffNode:
        updated_node_diff = self._get_empty_node_diff(node=car_node_main, action=DiffAction.UPDATED)
        # relationships
        updated_is_related_property = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.IS_RELATED,
            previous_value=person_node_main.id,
            new_value=person_node_main2.id,
            action=DiffAction.UPDATED,
            conflict=None,
        )
        updated_rel_source_property = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.HAS_SOURCE,
            previous_value=person_node_main2.id,
            new_value=person_node_main.id,
            action=DiffAction.UPDATED,
            conflict=None,
        )
        updated_rel_owner_property = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.HAS_OWNER,
            previous_value=car_node_main2.id,
            new_value=car_node_main.id,
            action=DiffAction.UPDATED,
            conflict=None,
        )
        updated_rel_is_protected_property = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.IS_PROTECTED,
            previous_value="False",
            new_value="True",
            action=DiffAction.UPDATED,
            conflict=None,
        )
        updated_relationship_element = EnrichedRelationshipElementFactory.build(
            action=DiffAction.UPDATED,
            peer_id=person_node_main2.id,
            conflict=None,
            properties={
                updated_is_related_property,
                updated_rel_source_property,
                updated_rel_owner_property,
                updated_rel_is_protected_property,
            },
        )
        updated_relationship = EnrichedRelationshipGroupFactory.build(
            name="owner",
            relationships={updated_relationship_element},
            action=DiffAction.UPDATED,
        )
        updated_node_diff.relationships = {updated_relationship}
        return updated_node_diff

    @pytest.mark.parametrize("check_idempotent", [False, True])
    async def test_merge_node_updated(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        person_node_main: Node,
        person_node_main2: Node,
        car_node_main: Node,
        car_node_main2: Node,
        mock_diff_repository: DiffRepository,
        diff_merger: DiffMerger,
        empty_diff_root: EnrichedDiffRoot,
        updated_person_node_diff: EnrichedDiffNode,
        updated_car_diff: EnrichedDiffNode,
        check_idempotent: bool,
    ):
        car_main = await NodeManager.get_one(db=db, branch=default_branch, id=car_node_main.id)
        await car_main.owner.update(
            db=db,
            data={
                "id": person_node_main.id,
                "_relation__owner": car_node_main2.id,
                "_relation__source": person_node_main2.id,
            },
        )
        await car_main.owner.save(db=db)

        source_branch = await create_branch(db=db, branch_name="source")

        person_branch = await NodeManager.get_one(db=db, branch=source_branch, id=person_node_main.id)
        person_branch.height.value += 1
        person_branch.height.set_owner(value=person_branch.id)
        person_branch.name.value += "-branch"
        await person_branch.save(db=db)

        car_branch = await NodeManager.get_one(db=db, branch=source_branch, id=car_node_main.id)
        await car_branch.owner.update(
            db=db,
            data={
                "id": person_node_main2.id,
                "_relation__owner": car_node_main.id,
                "_relation__source": person_node_main.id,
                "_relation__is_protected": True,
            },
        )
        await car_branch.save(db=db)

        empty_diff_root.nodes = {updated_person_node_diff, updated_car_diff}
        mock_diff_repository.get_one.return_value = empty_diff_root
        at = Timestamp()

        await diff_merger.merge_graph(at=at)
        if check_idempotent:
            await diff_merger.merge_graph(at=at)

        expected_awaits = [
            call(diff_branch_name=source_branch.name, tracking_id=BranchTrackingId(name=source_branch.name)),
        ]
        if check_idempotent:
            expected_awaits *= 2
        assert mock_diff_repository.get_one.await_args_list == expected_awaits
        updated_person = await NodeManager.get_one(
            db=db, branch=default_branch, id=person_node_main.id, include_owner=True
        )
        assert updated_person.get_updated_at() < at
        assert updated_person.height.value == person_node_main.height.value + 1
        owner_node = await updated_person.height.get_owner(db=db)
        assert owner_node.id == person_node_main.id
        assert updated_person.name.value == person_node_main.name.value + "-branch"
        car_rels = await updated_person.cars.get(db=db)
        assert len(car_rels) == 0
        updated_car = await NodeManager.get_one(
            db=db, branch=default_branch, id=car_node_main.id, include_owner=True, include_source=True
        )
        owner_rel = await updated_car.owner.get(db=db)
        assert owner_rel.is_protected is True
        assert owner_rel.is_visible is True
        assert owner_rel.peer_id == person_node_main2.id
        rel_owner_node = await owner_rel.get_owner(db=db)
        assert rel_owner_node.id == car_node_main.id
        rel_source_node = await owner_rel.get_source(db=db)
        assert rel_source_node.id == person_node_main.id
