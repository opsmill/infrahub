from typing import Literal
from unittest.mock import AsyncMock

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import (
    SYSTEM_USER_ID,
    DiffAction,
    MetadataOptions,
    RelationshipHierarchyDirection,
    SchemaPathType,
)
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.data_check_synchronizer import DiffDataCheckSynchronizer
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.diff.model.path import ConflictSelection
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.metadata.model import MetadataQueryOptions
from infrahub.core.metadata.query.node_metadata import NodeMetadataDefaultBranchQuery
from infrahub.core.migrations.schema.node_kind_update import NodeKindUpdateMigration
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.generic_schema import GenericSchema
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.dependencies.registry import get_component_registry
from infrahub.exceptions import NodeNotFoundError, SchemaNotFoundError
from tests.helpers.db_validation import verify_no_duplicate_paths
from tests.node_creation import create_and_save
from tests.unit.conftest import _build_hierarchical_location_data
from tests.unit.core.test_utils import verify_all_linked_edges_deleted

from .get_one_node import get_one_diff_node


class TestDiffAndMerge:
    @pytest.fixture
    async def diff_repository(self, db: InfrahubDatabase, default_branch: Branch) -> DiffRepository:
        component_registry = get_component_registry()
        return await component_registry.get_component(DiffRepository, db=db, branch=default_branch)

    async def _get_diff_coordinator(self, db: InfrahubDatabase, branch: Branch) -> DiffCoordinator:
        component_registry = get_component_registry()
        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
        diff_coordinator.data_check_synchronizer = AsyncMock(spec=DiffDataCheckSynchronizer)
        return diff_coordinator

    async def _get_diff_merger(self, db: InfrahubDatabase, branch: Branch) -> DiffMerger:
        component_registry = get_component_registry()
        return await component_registry.get_component(DiffMerger, db=db, branch=branch)

    async def test_diff_and_merge_with_list_attribute(
        self, db: InfrahubDatabase, default_branch: Branch, all_attribute_types_schema: NodeSchema
    ) -> None:
        new_node = await Node.init(db=db, schema=all_attribute_types_schema.kind)
        await new_node.new(db=db, mylist=["a", "b", 1, 2])
        before_create = Timestamp()
        await new_node.save(db=db, user_id="main-user")
        after_create = Timestamp()

        branch2 = await create_branch(db=db, branch_name="branch2")
        branch_node = await NodeManager.get_one(db=db, branch=branch2, id=new_node.id)
        branch_node.mylist.value = ["c", "d", 3, 4]
        await branch_node.save(db=db, user_id="branch-user")

        diff_coordinator = await self._get_diff_coordinator(db=db, branch=branch2)
        await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch2)
        diff_merger = await self._get_diff_merger(db=db, branch=branch2)
        merge_at = Timestamp()
        await diff_merger.merge_graph(at=merge_at)

        updated_node = await NodeManager.get_one(
            db=db, branch=default_branch, id=new_node.id, include_metadata=MetadataOptions.USER_TIMESTAMPS
        )
        assert updated_node.mylist.value == ["c", "d", 3, 4]

        # Verify Node vertex metadata
        # created_at/created_by should reflect the original creation on main
        assert before_create < updated_node._get_created_at() < after_create
        assert updated_node._get_created_by() == "main-user"
        assert updated_node._get_updated_at() == merge_at
        assert updated_node._get_updated_by() == "branch-user"

        # Verify Attribute vertex metadata
        mylist_attr = updated_node.mylist
        # created_at/created_by should reflect original creation on main
        assert before_create < mylist_attr._get_created_at() < after_create
        assert mylist_attr._get_created_by() == "main-user"
        # updated_at/updated_by should reflect the merge
        assert mylist_attr._get_updated_at() == merge_at
        assert mylist_attr._get_updated_by() == "branch-user"
        await verify_no_duplicate_paths(db=db)

    async def test_diff_and_merge_schema_with_default_values(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        car_person_schema: SchemaBranch,
    ) -> None:
        schema_main = registry.schema.get_schema_branch(name=default_branch.name)
        await registry.schema.update_schema_branch(
            db=db, branch=default_branch, schema=schema_main, limit=["TestCar", "TestPerson"], update_db=True
        )
        branch2 = await create_branch(db=db, branch_name="branch2")
        schema_branch = registry.schema.get_schema_branch(name=branch2.name)
        schema_branch.duplicate()
        car_schema_branch = schema_branch.get(name="TestCar")
        car_schema_branch.attributes.append(AttributeSchema(name="num_cupholders", kind="Number", default_value=15))
        car_schema_branch.attributes.append(AttributeSchema(name="is_cool", kind="Boolean", default_value=False))
        car_schema_branch.attributes.append(AttributeSchema(name="nickname", kind="Text", default_value="car"))
        schema_branch.set(name="TestCar", schema=car_schema_branch)
        schema_branch.process()
        await registry.schema.update_schema_branch(
            db=db, branch=branch2, schema=schema_branch, limit=["TestCar", "TestPerson"], update_db=True
        )

        at = Timestamp()
        diff_coordinator = await self._get_diff_coordinator(db=db, branch=branch2)
        await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch2)
        diff_merger = await self._get_diff_merger(db=db, branch=branch2)
        await diff_merger.merge_graph(at=at)

        updated_schema = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
        car_schema_main = updated_schema.get(name="TestCar", duplicate=False)
        new_int_attr = car_schema_main.get_attribute(name="num_cupholders")
        assert new_int_attr.default_value == 15
        new_bool_attr = car_schema_main.get_attribute(name="is_cool")
        assert new_bool_attr.default_value is False
        new_str_attr = car_schema_main.get_attribute(name="nickname")
        assert new_str_attr.default_value == "car"

        await diff_merger.rollback(at=at)

        rolled_back_schema = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
        car_schema_main = rolled_back_schema.get(name="TestCar", duplicate=False)
        attribute_names = car_schema_main.attribute_names
        assert "num_cupholders" not in attribute_names
        assert "is_cool" not in attribute_names
        assert "nickname" not in attribute_names
        await verify_no_duplicate_paths(db=db)

    @pytest.mark.parametrize(
        "base_action,diff_action,selection,expect_deleted",
        [
            # DELETE on base + UPDATE on diff: selecting BASE_BRANCH keeps the node deleted
            ("delete", "update", ConflictSelection.BASE_BRANCH, True),
            # UPDATE on base + DELETE on diff: selecting BASE_BRANCH keeps the node with base value
            ("update", "delete", ConflictSelection.BASE_BRANCH, False),
            # Note: DIFF_BRANCH selection for node-level conflicts involving deletion is not tested here
            # because un-deleting an object on the default branch is not supported
        ],
    )
    async def test_node_delete_update_conflict(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        diff_repository: DiffRepository,
        person_john_main: Node,
        base_action: str,
        diff_action: str,
        selection: ConflictSelection,
        expect_deleted: bool,
    ) -> None:
        """Test node-level conflicts between delete and update operations.

        This test covers scenarios where BASE_BRANCH is selected to resolve the conflict:
        1. DELETE on base + UPDATE on diff + select BASE_BRANCH = Node deleted
        2. UPDATE on base + DELETE on diff + select BASE_BRANCH = Node exists with base value

        Note: Selecting DIFF_BRANCH for node-level delete conflicts is not supported because
        un-deleting an object on the default branch is not allowed.
        """
        # Capture initial metadata
        person_before = await NodeManager.get_one(
            db=db, id=person_john_main.id, include_metadata=MetadataOptions.USER_TIMESTAMPS
        )
        person_created_at = person_before._get_created_at()
        person_created_by = person_before._get_created_by()

        branch2 = await create_branch(db=db, branch_name="branch2")

        # Perform actions based on test parameters
        before_base_update = Timestamp()
        if base_action == "delete":
            person_main = await NodeManager.get_one(db=db, id=person_john_main.id)
            await person_main.delete(db=db, user_id="main-user")
        else:  # base_action == "update"
            person_main = await NodeManager.get_one(db=db, id=person_john_main.id)
            person_main.height.value = 200
            await person_main.save(db=db, user_id="main-user")
        after_base_update = Timestamp()

        if diff_action == "delete":
            person_branch = await NodeManager.get_one(db=db, branch=branch2, id=person_john_main.id)
            await person_branch.delete(db=db, user_id="branch-user")
        else:  # diff_action == "update"
            person_branch = await NodeManager.get_one(db=db, branch=branch2, id=person_john_main.id)
            person_branch.height.value = 150
            await person_branch.save(db=db, user_id="branch-user")

        # Run diff coordinator to detect conflicts
        diff_coordinator = await self._get_diff_coordinator(db=db, branch=branch2)
        enriched_diff = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch2)

        # Assert a node-level conflict is detected
        conflicts_map = enriched_diff.get_all_conflicts()
        assert len(conflicts_map) >= 1
        conflict_node = get_one_diff_node(diff_root=enriched_diff, node_uuid=person_john_main.id)
        assert conflict_node.conflict is not None
        if base_action == "delete":
            assert conflict_node.conflict.base_branch_action is DiffAction.REMOVED
            assert conflict_node.conflict.diff_branch_action is DiffAction.UPDATED
        else:  # base_action == "update"
            assert conflict_node.conflict.base_branch_action is DiffAction.UPDATED
            assert conflict_node.conflict.diff_branch_action is DiffAction.REMOVED

        # Set conflict resolution
        await diff_repository.update_conflict_by_id(conflict_id=conflict_node.conflict.uuid, selection=selection)

        # Merge the branch
        merge_at = Timestamp()
        diff_merger = await self._get_diff_merger(db=db, branch=branch2)
        await diff_merger.merge_graph(at=merge_at)

        # Validate outcome
        if expect_deleted:
            # Node should be deleted
            with pytest.raises(NodeNotFoundError):
                await NodeManager.get_one(db=db, id=person_john_main.id, raise_on_error=True)
        else:
            # Node should exist
            updated_person = await NodeManager.get_one(
                db=db, id=person_john_main.id, include_metadata=MetadataOptions.USER_TIMESTAMPS
            )
            assert updated_person is not None

            # base_action must be "update" (since expect_deleted is False and selection is BASE_BRANCH)
            assert updated_person.height.value == 200
            # Metadata should reflect main-user's update
            assert before_base_update < updated_person._get_updated_at() < after_base_update
            assert updated_person._get_updated_by() == "main-user"

            # created_at/created_by should remain unchanged
            assert updated_person._get_created_at() == person_created_at
            assert updated_person._get_created_by() == person_created_by

        await verify_no_duplicate_paths(db=db)

    @pytest.mark.parametrize(
        "conflict_selection,expected_value",
        [
            (ConflictSelection.BASE_BRANCH, {"name": "John-main", "hfid": ["John-main"]}),
            (ConflictSelection.DIFF_BRANCH, {"name": "John-branch", "hfid": ["John-branch"]}),
        ],
    )
    async def test_diff_and_merge_with_attribute_value_conflict(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        diff_repository: DiffRepository,
        person_john_main: Node,
        person_jane_main: Node,
        person_alfred_main: Node,
        car_accord_main: Node,
        conflict_selection: ConflictSelection,
        expected_value: dict[Literal["name", "hfid"], str | list[str]],
    ) -> None:
        branch2 = await create_branch(db=db, branch_name="branch2")
        john_main = await NodeManager.get_one(db=db, id=person_john_main.id)
        john_main.name.value = "John-main"
        before_main_update = Timestamp()
        await john_main.save(db=db, user_id="main-user")
        after_main_update = Timestamp()
        john_branch = await NodeManager.get_one(db=db, branch=branch2, id=person_john_main.id)
        john_branch.name.value = "John-branch"
        await john_branch.save(db=db, user_id="branch-user")

        merge_at = Timestamp()
        diff_coordinator = await self._get_diff_coordinator(db=db, branch=branch2)
        enriched_diff_metadata = await diff_coordinator.update_branch_diff(
            base_branch=default_branch, diff_branch=branch2
        )
        enriched_diff = await diff_repository.get_one(
            diff_branch_name=enriched_diff_metadata.diff_branch_name, diff_id=enriched_diff_metadata.uuid
        )
        conflicts_map = enriched_diff.get_all_conflicts()
        assert len(conflicts_map) == 3
        for conflict in conflicts_map.values():
            await diff_repository.update_conflict_by_id(conflict_id=conflict.uuid, selection=conflict_selection)
        diff_merger = await self._get_diff_merger(db=db, branch=branch2)
        await diff_merger.merge_graph(at=merge_at)

        updated_john = await NodeManager.get_one(
            db=db, id=person_john_main.id, include_metadata=MetadataOptions.USER_TIMESTAMPS
        )
        assert updated_john.name.value == expected_value["name"]
        assert await updated_john.get_hfid(db=db) == expected_value["hfid"]
        assert updated_john._get_created_at() < before_main_update
        assert updated_john._get_created_by() == SYSTEM_USER_ID
        assert updated_john.name._get_created_at() < before_main_update
        assert updated_john.name._get_created_by() == SYSTEM_USER_ID

        # Verify Node and Attribute metadata
        if conflict_selection == ConflictSelection.DIFF_BRANCH:
            # Branch changes were merged
            assert updated_john._get_updated_at() == merge_at
            assert updated_john._get_updated_by() == "branch-user"
            # Attribute metadata should reflect the merge
            assert updated_john.name._get_updated_at() == merge_at
            assert updated_john.name._get_updated_by() == "branch-user"
        else:
            # Base branch was kept, no changes merged
            assert before_main_update < updated_john._get_updated_at() < after_main_update
            # Attribute metadata should reflect main branch update
            assert before_main_update < updated_john.name._get_updated_at() < after_main_update
            assert updated_john.name._get_updated_by() == "main-user"

        await diff_merger.rollback(at=merge_at)

        rolled_back_john = await NodeManager.get_one(
            db=db, id=person_john_main.id, include_metadata=MetadataOptions.USER_TIMESTAMPS
        )
        assert rolled_back_john.name.value == "John-main"
        # After rollback, Node metadata should be restored
        assert before_main_update < rolled_back_john._get_updated_at() < after_main_update
        assert rolled_back_john._get_updated_by() == "main-user"
        # After rollback, Attribute metadata should be restored
        assert before_main_update < rolled_back_john.name._get_updated_at() < after_main_update
        assert rolled_back_john.name._get_updated_by() == "main-user"
        await verify_no_duplicate_paths(db=db)

    @pytest.mark.parametrize(
        "conflict_selection",
        [ConflictSelection.BASE_BRANCH, ConflictSelection.DIFF_BRANCH],
    )
    async def test_diff_and_merge_with_relationship_conflict(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        diff_repository: DiffRepository,
        person_john_main: Node,
        person_jane_main: Node,
        person_alfred_main: Node,
        car_accord_main: Node,
        car_camry_main: Node,
        conflict_selection: ConflictSelection,
    ) -> None:
        branch2 = await create_branch(db=db, branch_name="branch2")
        car_main = await NodeManager.get_one(db=db, id=car_accord_main.id)
        await car_main.owner.update(db=db, data=person_alfred_main)
        before_main_update = Timestamp()
        await car_main.save(db=db, user_id="main-user")
        after_main_update = Timestamp()
        car_branch = await NodeManager.get_one(db=db, branch=branch2, id=car_accord_main.id)
        await car_branch.owner.update(db=db, data=person_jane_main)
        await car_branch.save(db=db, user_id="branch-user")

        merge_at = Timestamp()
        diff_coordinator = await self._get_diff_coordinator(db=db, branch=branch2)
        enriched_diff_metadata = await diff_coordinator.update_branch_diff(
            base_branch=default_branch, diff_branch=branch2
        )
        enriched_diff = await diff_repository.get_one(
            diff_branch_name=enriched_diff_metadata.diff_branch_name, diff_id=enriched_diff_metadata.uuid
        )
        conflicts_map = enriched_diff.get_all_conflicts()
        assert len(conflicts_map) == 1
        conflict = next(iter(conflicts_map.values()))
        await diff_repository.update_conflict_by_id(conflict_id=conflict.uuid, selection=conflict_selection)
        diff_merger = await self._get_diff_merger(db=db, branch=branch2)
        await diff_merger.merge_graph(at=merge_at)

        updated_car = await NodeManager.get_one(
            db=db, id=car_accord_main.id, include_metadata=MetadataOptions.USER_TIMESTAMPS, prefetch_relationships=True
        )
        owner_rel = await updated_car.owner.get(db=db)
        if conflict_selection is ConflictSelection.BASE_BRANCH:
            assert owner_rel.peer_id == person_alfred_main.id
            # Base branch was kept, no changes merged - Node metadata should reflect main update
            assert before_main_update < updated_car._get_updated_at() < after_main_update
            assert updated_car._get_updated_by() == "main-user"
            # Relationship metadata should reflect main branch update
            assert before_main_update < owner_rel._get_updated_at() < after_main_update
            assert owner_rel._get_updated_by() == "main-user"
            assert before_main_update < owner_rel._get_created_at() < after_main_update
            assert owner_rel._get_created_by() == "main-user"
        if conflict_selection is ConflictSelection.DIFF_BRANCH:
            assert owner_rel.peer_id == person_jane_main.id
            # Branch changes were merged - Node metadata should reflect the merge
            assert updated_car._get_updated_at() == merge_at
            assert updated_car._get_updated_by() == "branch-user"
            # Relationship metadata should reflect the merge
            assert owner_rel._get_created_at() == merge_at
            assert owner_rel._get_created_by() == "branch-user"
            assert owner_rel._get_updated_at() == merge_at
            assert owner_rel._get_updated_by() == "branch-user"

        await diff_merger.rollback(at=merge_at)

        rolled_back_car = await NodeManager.get_one(
            db=db, id=car_accord_main.id, include_metadata=MetadataOptions.USER_TIMESTAMPS, prefetch_relationships=True
        )
        owner_rel = await rolled_back_car.owner.get(db=db)
        assert owner_rel.peer_id == person_alfred_main.id
        # After rollback, Node metadata should be restored to pre-merge state
        assert before_main_update < rolled_back_car._get_updated_at() < after_main_update
        assert rolled_back_car._get_updated_by() == "main-user"
        # After rollback, Relationship metadata should be restored
        assert before_main_update < owner_rel._get_updated_at() < after_main_update
        assert owner_rel._get_updated_by() == "main-user"
        await verify_no_duplicate_paths(db=db)

    @pytest.mark.parametrize(
        "conflict_selection",
        [ConflictSelection.BASE_BRANCH, ConflictSelection.DIFF_BRANCH],
    )
    async def test_diff_and_merge_with_attribute_property_conflict(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        diff_repository: DiffRepository,
        person_john_main: Node,
        person_jane_main: Node,
        person_alfred_main: Node,
        car_accord_main: Node,
        conflict_selection: ConflictSelection,
    ) -> None:
        branch2 = await create_branch(db=db, branch_name="branch2")
        john_main = await NodeManager.get_one(db=db, id=person_john_main.id)
        john_main.name.source = person_alfred_main
        before_main_update = Timestamp()
        await john_main.save(db=db, user_id="main-user")
        after_main_update = Timestamp()
        john_branch = await NodeManager.get_one(db=db, branch=branch2, id=person_john_main.id)
        john_branch.name.source = person_jane_main
        await john_branch.save(db=db, user_id="branch-user")

        merge_at = Timestamp()
        diff_coordinator = await self._get_diff_coordinator(db=db, branch=branch2)
        enriched_diff_metadata = await diff_coordinator.update_branch_diff(
            base_branch=default_branch, diff_branch=branch2
        )
        enriched_diff = await diff_repository.get_one(
            diff_branch_name=enriched_diff_metadata.diff_branch_name, diff_id=enriched_diff_metadata.uuid
        )
        conflicts_map = enriched_diff.get_all_conflicts()
        assert len(conflicts_map) == 1
        conflict = next(iter(conflicts_map.values()))
        await diff_repository.update_conflict_by_id(conflict_id=conflict.uuid, selection=conflict_selection)
        diff_merger = await self._get_diff_merger(db=db, branch=branch2)
        await diff_merger.merge_graph(at=merge_at)

        updated_john = await NodeManager.get_one(
            db=db, id=person_john_main.id, include_metadata=MetadataOptions.SOURCE | MetadataOptions.USER_TIMESTAMPS
        )
        assert updated_john._get_created_at() < before_main_update
        assert updated_john._get_created_by() == SYSTEM_USER_ID
        assert updated_john.name._get_created_at() < before_main_update
        assert updated_john.name._get_created_by() == SYSTEM_USER_ID

        attr_source = await updated_john.name.get_source(db=db)
        if conflict_selection is ConflictSelection.BASE_BRANCH:
            assert attr_source.id == person_alfred_main.id
            # Base branch was kept, no changes merged - Node metadata
            assert before_main_update < updated_john._get_updated_at() < after_main_update
            assert updated_john._get_updated_by() == "main-user"
            # Attribute metadata should reflect main branch update
            assert before_main_update < updated_john.name._get_updated_at() < after_main_update
            assert updated_john.name._get_updated_by() == "main-user"
        if conflict_selection is ConflictSelection.DIFF_BRANCH:
            assert attr_source.id == person_jane_main.id
            # Branch changes were merged - Node metadata
            assert updated_john._get_updated_at() == merge_at
            assert updated_john._get_updated_by() == "branch-user"
            # Attribute metadata should reflect the merge
            assert updated_john.name._get_updated_at() == merge_at
            assert updated_john.name._get_updated_by() == "branch-user"

        await diff_merger.rollback(at=merge_at)

        rolled_back_john = await NodeManager.get_one(
            db=db, id=person_john_main.id, include_metadata=MetadataOptions.SOURCE | MetadataOptions.USER_TIMESTAMPS
        )
        attr_source = await rolled_back_john.name.get_source(db=db)
        assert attr_source.id == person_alfred_main.id
        # After rollback, Node metadata should be restored to pre-merge state
        assert before_main_update < rolled_back_john._get_updated_at() < after_main_update
        assert rolled_back_john._get_updated_by() == "main-user"
        # After rollback, Attribute metadata should be restored
        assert before_main_update < rolled_back_john.name._get_updated_at() < after_main_update
        assert rolled_back_john.name._get_updated_by() == "main-user"
        await verify_no_duplicate_paths(db=db)

    @pytest.mark.parametrize(
        "conflict_selection",
        [ConflictSelection.BASE_BRANCH, ConflictSelection.DIFF_BRANCH],
    )
    async def test_diff_and_merge_with_relationship_property_conflict(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        diff_repository: DiffRepository,
        person_john_main: Node,
        person_jane_main: Node,
        person_alfred_main: Node,
        car_accord_main: Node,
        car_camry_main: Node,
        conflict_selection: ConflictSelection,
    ) -> None:
        person_schema = db.schema.get(name="TestPerson", duplicate=False)
        cars_rel_schema = person_schema.get_relationship(name="cars")
        branch2 = await create_branch(db=db, branch_name="branch2")
        car_main = await NodeManager.get_one(db=db, id=car_accord_main.id)
        await car_main.owner.update(db=db, data={"id": person_john_main.id, "_relation__owner": person_alfred_main.id})
        before_main_update = Timestamp()
        await car_main.save(db=db, user_id="main-user")
        after_main_update = Timestamp()
        car_branch = await NodeManager.get_one(db=db, branch=branch2, id=car_accord_main.id)
        await car_branch.owner.update(db=db, data={"id": person_john_main.id, "_relation__owner": person_jane_main.id})
        await car_branch.save(db=db, user_id="branch-user")

        merge_at = Timestamp()
        diff_coordinator = await self._get_diff_coordinator(db=db, branch=branch2)
        enriched_diff_metadata = await diff_coordinator.update_branch_diff(
            base_branch=default_branch, diff_branch=branch2
        )
        enriched_diff = await diff_repository.get_one(
            diff_branch_name=enriched_diff_metadata.diff_branch_name, diff_id=enriched_diff_metadata.uuid
        )
        conflicts_map = enriched_diff.get_all_conflicts()
        # conflict on both sides of the relationship
        assert len(conflicts_map) == 2
        for conflict in conflicts_map.values():
            await diff_repository.update_conflict_by_id(conflict_id=conflict.uuid, selection=conflict_selection)
        diff_merger = await self._get_diff_merger(db=db, branch=branch2)
        await diff_merger.merge_graph(at=merge_at)

        updated_car_with_metadata = await NodeManager.get_one(
            db=db,
            id=car_accord_main.id,
            include_metadata=MetadataOptions.USER_TIMESTAMPS,
            prefetch_relationships=True,
        )
        owner_rel_with_metadata = await updated_car_with_metadata.owner.get(db=db)
        updated_car = await NodeManager.get_one(db=db, id=car_accord_main.id)
        owner_rel = await updated_car.owner.get(db=db)
        owner_prop = await owner_rel.get_owner(db=db)

        assert updated_car_with_metadata._get_created_at() < before_main_update
        assert updated_car_with_metadata._get_created_by() == SYSTEM_USER_ID
        assert owner_rel_with_metadata._get_created_at() < before_main_update
        assert owner_rel_with_metadata._get_created_by() == SYSTEM_USER_ID
        if conflict_selection is ConflictSelection.BASE_BRANCH:
            assert owner_prop.id == person_alfred_main.id
            # Base branch was kept, no changes merged - Node metadata should reflect main update
            assert before_main_update < updated_car_with_metadata._get_updated_at() < after_main_update
            assert updated_car_with_metadata._get_updated_by() == "main-user"
            # Relationship metadata should reflect main branch update
            assert before_main_update < owner_rel_with_metadata._get_updated_at() < after_main_update
            assert owner_rel_with_metadata._get_updated_by() == "main-user"
        if conflict_selection is ConflictSelection.DIFF_BRANCH:
            assert owner_prop.id == person_jane_main.id
            # Branch changes were merged - Node metadata should reflect the merge
            assert updated_car_with_metadata._get_updated_at() == merge_at
            assert updated_car_with_metadata._get_updated_by() == "branch-user"
            # Relationship metadata should reflect the merge
            assert owner_rel_with_metadata._get_updated_at() == merge_at
            assert owner_rel_with_metadata._get_updated_by() == "branch-user"

        john_car_count = await NodeManager.count_peers(
            db=db,
            ids=[person_john_main.id],
            source_kind="TestPerson",
            filters={},
            schema=cars_rel_schema,
            branch=branch2,
        )
        assert john_car_count == 1

        await diff_merger.rollback(at=merge_at)

        rolled_back_car = await NodeManager.get_one(
            db=db, id=car_accord_main.id, include_metadata=MetadataOptions.OWNER | MetadataOptions.USER_TIMESTAMPS
        )
        owner_rel = await rolled_back_car.owner.get(db=db)
        owner_prop = await owner_rel.get_owner(db=db)
        assert owner_prop.id == person_alfred_main.id
        # After rollback, Node metadata should be restored to pre-merge state
        assert before_main_update < rolled_back_car._get_updated_at() < after_main_update
        assert rolled_back_car._get_updated_by() == "main-user"
        await verify_no_duplicate_paths(db=db)

    @pytest.mark.parametrize("new_height", (0, 1000, None))
    async def test_single_attribute_update(
        self,
        db: InfrahubDatabase,
        diff_repository: DiffRepository,
        default_branch: Branch,
        person_john_main,
        person_jane_main,
        new_height,
    ) -> None:
        # Capture initial metadata before any changes
        person_before = await NodeManager.get_one(
            db=db, id=person_jane_main.id, include_metadata=MetadataOptions.USER_TIMESTAMPS
        )
        person_created_at = person_before._get_created_at()
        person_created_by = person_before._get_created_by()

        branch2 = await create_branch(db=db, branch_name="branch2")
        person_branch = await NodeManager.get_one(db=db, branch=branch2, id=person_jane_main.id)
        person_branch.height.value = new_height
        await person_branch.save(db=db, user_id="branch-user")

        diff_coordinator = await self._get_diff_coordinator(db=db, branch=branch2)
        enriched_diff_metadata = await diff_coordinator.update_branch_diff(
            base_branch=default_branch, diff_branch=branch2
        )
        enriched_diff = await diff_repository.get_one(
            diff_branch_name=enriched_diff_metadata.diff_branch_name, diff_id=enriched_diff_metadata.uuid
        )
        node = get_one_diff_node(diff_root=enriched_diff, node_uuid=person_jane_main.id)
        assert node.action is DiffAction.UPDATED

        diff_merger = await self._get_diff_merger(db=db, branch=branch2)
        at = Timestamp()
        await diff_merger.merge_graph(at=at)

        updated_person = await NodeManager.get_one(
            db=db, id=person_jane_main.id, include_metadata=MetadataOptions.USER_TIMESTAMPS
        )
        assert updated_person.height.value == new_height

        # Validate Node metadata
        # created_at/created_by should be unchanged (from fixture creation)
        assert updated_person._get_created_at() == person_created_at
        assert updated_person._get_created_by() == person_created_by
        # updated_at/updated_by should reflect the merge
        assert updated_person._get_updated_at() == at
        assert updated_person._get_updated_by() == "branch-user"

        # Validate the height attribute metadata
        height_attr = updated_person.height
        assert height_attr._get_created_at() == person_created_at
        assert height_attr._get_created_by() == person_created_by
        assert height_attr._get_updated_at() == at
        assert height_attr._get_updated_by() == "branch-user"

        # Validate other attributes were NOT updated (name attribute)
        name_attr = updated_person.name
        assert name_attr._get_created_at() == person_created_at
        assert name_attr._get_created_by() == person_created_by
        # name attribute should not have been updated by the merge
        assert name_attr._get_updated_at() == person_created_at
        assert name_attr._get_updated_by() == person_created_by

        await verify_no_duplicate_paths(db=db)

    async def test_one_many_relationship_added(
        self,
        db: InfrahubDatabase,
        diff_repository: DiffRepository,
        default_branch: Branch,
        person_john_main,
        person_jane_main,
        car_camry_main,
    ) -> None:
        # Capture person_jane's updated_at before adding the relationship
        person_jane_before = await NodeManager.get_one(
            db=db, id=person_jane_main.id, include_metadata=MetadataOptions.USER_TIMESTAMPS
        )
        person_jane_updated_at_before = person_jane_before._get_updated_at()
        person_jane_updated_by_before = person_jane_before._get_updated_by()

        branch2 = await create_branch(db=db, branch_name="branch2")
        branch_car = await Node.init(db=db, schema="TestCar", branch=branch2)
        await branch_car.new(db=db, name="new camry", nbr_seats=5, is_electric=False, owner=person_jane_main.id)
        await branch_car.save(db=db, user_id="branch-user")

        diff_coordinator = await self._get_diff_coordinator(db=db, branch=branch2)
        enriched_diff_metadata = await diff_coordinator.update_branch_diff(
            base_branch=default_branch, diff_branch=branch2
        )
        enriched_diff = await diff_repository.get_one(
            diff_branch_name=enriched_diff_metadata.diff_branch_name, diff_id=enriched_diff_metadata.uuid
        )
        car_node = get_one_diff_node(diff_root=enriched_diff, node_uuid=branch_car.id)
        assert car_node.action is DiffAction.ADDED
        person_node = get_one_diff_node(diff_root=enriched_diff, node_uuid=person_jane_main.id)
        assert person_node.action is DiffAction.UPDATED

        diff_merger = await self._get_diff_merger(db=db, branch=branch2)
        merge_at = Timestamp()
        await diff_merger.merge_graph(at=merge_at)

        # Verify car node and owner relationship metadata
        updated_car = await NodeManager.get_one(
            db=db, id=branch_car.id, include_metadata=MetadataOptions.USER_TIMESTAMPS, prefetch_relationships=True
        )
        assert updated_car.name.value == "new camry"
        assert updated_car.nbr_seats.value == 5
        assert updated_car.is_electric.value is False
        owner_rel = await updated_car.owner.get(db=db)
        assert owner_rel.peer_id == person_jane_main.id

        # Car Node metadata - created on branch, merged to main
        assert updated_car._get_created_at() == merge_at
        assert updated_car._get_created_by() == "branch-user"
        assert updated_car._get_updated_at() == merge_at
        assert updated_car._get_updated_by() == "branch-user"
        # Car owner relationship metadata
        assert owner_rel._get_created_at() == merge_at
        assert owner_rel._get_created_by() == "branch-user"
        assert owner_rel._get_updated_at() == merge_at
        assert owner_rel._get_updated_by() == "branch-user"

        # Verify person_jane node and cars relationship metadata
        updated_person = await NodeManager.get_one(
            db=db, id=person_jane_main.id, include_metadata=MetadataOptions.USER_TIMESTAMPS, prefetch_relationships=True
        )
        cars_rels = await updated_person.cars.get_relationships(db=db)
        # Find the relationship to the new car
        new_car_rel = next((r for r in cars_rels if r.peer_id == branch_car.id), None)
        assert new_car_rel is not None

        # Person Node metadata - updated_at should reflect the merge (rollup from new relationship)
        assert updated_person._get_created_at() == person_jane_updated_at_before
        assert updated_person._get_created_by() == SYSTEM_USER_ID
        assert updated_person._get_updated_at() == merge_at
        assert updated_person._get_updated_by() == "branch-user"
        # Person cars relationship metadata (the new relationship to branch_car)
        assert new_car_rel._get_created_at() == merge_at
        assert new_car_rel._get_created_by() == "branch-user"
        assert new_car_rel._get_updated_at() == merge_at
        assert new_car_rel._get_updated_by() == "branch-user"

        await verify_no_duplicate_paths(db=db)

        # Rollback the merge
        await diff_merger.rollback(at=merge_at)

        # Car should no longer exist on main after rollback
        rolled_back_car = await NodeManager.get_one(db=db, id=branch_car.id)
        assert rolled_back_car is None

        # Person should be restored to pre-merge state
        rolled_back_person = await NodeManager.get_one(
            db=db, id=person_jane_main.id, include_metadata=MetadataOptions.USER_TIMESTAMPS, prefetch_relationships=True
        )
        # Person Node metadata should be restored
        assert rolled_back_person._get_updated_at() == person_jane_updated_at_before
        assert rolled_back_person._get_updated_by() == person_jane_updated_by_before
        # The cars relationship to the new car should no longer exist
        rolled_back_cars_rels = await rolled_back_person.cars.get_relationships(db=db)
        rolled_back_new_car_rel = next((r for r in rolled_back_cars_rels if r.peer_id == branch_car.id), None)
        assert rolled_back_new_car_rel is None

        await verify_no_duplicate_paths(db=db)

    async def test_relationship_set_to_null(
        self, db: InfrahubDatabase, default_branch: Branch, diff_repository: DiffRepository, animal_person_schema
    ) -> None:
        person_main = await Node.init(db=db, schema="TestPerson")
        await person_main.new(db=db, name="Dude")
        await person_main.save(db=db, user_id="main-user-person")
        friend_main = await Node.init(db=db, schema="TestPerson")
        await friend_main.new(db=db, name="Friend")
        before_friend_create = Timestamp()
        await friend_main.save(db=db, user_id="main-user-friend")
        after_friend_create = Timestamp()
        dog_main = await Node.init(db=db, schema="TestDog")
        await dog_main.new(db=db, name="good dog", breed="mixed", owner=person_main, best_friend=friend_main)
        before_dog_create = Timestamp()
        await dog_main.save(db=db, user_id="main-user-dog")
        after_dog_create = Timestamp()

        branch2 = await create_branch(db=db, branch_name="branch2")
        dog_branch = await NodeManager.get_one(db=db, branch=branch2, id=dog_main.id)
        await dog_branch.best_friend.update(db=db, data=None, user_id="branch-user")
        await dog_branch.save(db=db, user_id="branch-user")

        diff_coordinator = await self._get_diff_coordinator(db=db, branch=branch2)
        enriched_diff_metadata = await diff_coordinator.update_branch_diff(
            base_branch=default_branch, diff_branch=branch2
        )
        enriched_diff = await diff_repository.get_one(
            diff_branch_name=enriched_diff_metadata.diff_branch_name, diff_id=enriched_diff_metadata.uuid
        )
        dog_node = get_one_diff_node(diff_root=enriched_diff, node_uuid=dog_main.id)
        assert dog_node.action is DiffAction.UPDATED
        friend_node = get_one_diff_node(diff_root=enriched_diff, node_uuid=friend_main.id)
        assert friend_node.action is DiffAction.UPDATED

        diff_merger = await self._get_diff_merger(db=db, branch=branch2)
        merge_at = Timestamp()
        await diff_merger.merge_graph(at=merge_at)

        # Verify dog node metadata - relationship was removed, so dog should be updated
        updated_dog = await NodeManager.get_one(
            db=db, id=dog_main.id, include_metadata=MetadataOptions.USER_TIMESTAMPS, prefetch_relationships=True
        )
        best_friend_rels = await updated_dog.best_friend.get_relationships(db=db)
        assert len(best_friend_rels) == 0
        assert before_dog_create < updated_dog._get_created_at() < after_dog_create
        assert updated_dog._get_created_by() == "main-user-dog"
        assert updated_dog._get_updated_at() == merge_at
        assert updated_dog._get_updated_by() == "branch-user"

        # Verify friend node metadata - relationship was removed from their side too
        updated_friend = await NodeManager.get_one(
            db=db, id=friend_main.id, include_metadata=MetadataOptions.USER_TIMESTAMPS, prefetch_relationships=True
        )
        best_friend_rels = await updated_friend.best_friends.get_relationships(db=db)
        assert len(best_friend_rels) == 0

        assert before_friend_create < updated_friend._get_created_at() < after_friend_create
        assert updated_friend._get_created_by() == "main-user-friend"
        assert updated_friend._get_updated_at() == merge_at
        assert updated_friend._get_updated_by() == "branch-user"

        # Verify metadata on deleted relationships using NodeMetadataDefaultBranchQuery
        node_metadata_query = await NodeMetadataDefaultBranchQuery.init(
            db=db,
            branch=default_branch,
            node_uuids=[dog_main.id, friend_main.id],
        )
        await node_metadata_query.execute(db=db)
        node_metadatas = node_metadata_query.get_metadatas()
        assert len(node_metadatas) == 2

        metadata_by_uuid = {m.uuid: m for m in node_metadatas}

        # Validate dog's relationship to friend (deleted)
        dog_meta = metadata_by_uuid[dog_main.id]
        assert dog_meta.is_deleted is False
        dog_rels_to_friend = [r for r in dog_meta.relationships if r.peer_uuid == friend_main.id]
        assert len(dog_rels_to_friend) == 1
        dog_rel_to_friend = dog_rels_to_friend[0]
        assert dog_rel_to_friend.is_deleted is True
        assert before_dog_create < dog_rel_to_friend.created_at < after_dog_create
        assert dog_rel_to_friend.created_by == "main-user-dog"
        assert dog_rel_to_friend.updated_at == merge_at
        assert dog_rel_to_friend.updated_by == "branch-user"

        # Validate friend's relationship to dog (deleted)
        friend_meta = metadata_by_uuid[friend_main.id]
        assert friend_meta.is_deleted is False
        friend_rels_to_dog = [r for r in friend_meta.relationships if r.peer_uuid == dog_main.id]
        assert len(friend_rels_to_dog) == 1
        friend_rel_to_dog = friend_rels_to_dog[0]
        assert friend_rel_to_dog.is_deleted is True
        assert before_dog_create < friend_rel_to_dog.created_at < after_dog_create
        assert friend_rel_to_dog.created_by == "main-user-dog"
        assert friend_rel_to_dog.updated_at == merge_at
        assert friend_rel_to_dog.updated_by == "branch-user"

        await verify_no_duplicate_paths(db=db)

        # Rollback the merge
        await diff_merger.rollback(at=merge_at)

        # Verify dog metadata after rollback
        rolled_back_dog = await NodeManager.get_one(
            db=db, id=dog_main.id, include_metadata=MetadataOptions.USER_TIMESTAMPS, prefetch_relationships=True
        )
        # Dog's best_friend relationship should be restored
        rolled_back_best_friend_rels = await rolled_back_dog.best_friend.get_relationships(db=db)
        assert len(rolled_back_best_friend_rels) == 1
        assert rolled_back_best_friend_rels[0].peer_id == friend_main.id
        # Dog Node metadata should be restored to pre-merge state
        assert before_dog_create < rolled_back_dog._get_updated_at() < after_dog_create
        assert rolled_back_dog._get_updated_by() == "main-user-dog"

        # Verify friend metadata after rollback
        rolled_back_friend = await NodeManager.get_one(
            db=db, id=friend_main.id, include_metadata=MetadataOptions.USER_TIMESTAMPS, prefetch_relationships=True
        )
        # Friend's best_friends relationship should be restored
        rolled_back_best_friends_rels = await rolled_back_friend.best_friends.get_relationships(db=db)
        assert len(rolled_back_best_friends_rels) == 1
        assert rolled_back_best_friends_rels[0].peer_id == dog_main.id
        # Friend Node metadata should be restored to pre-merge state
        assert before_friend_create < rolled_back_friend._get_created_at() < after_friend_create
        assert rolled_back_friend._get_created_by() == "main-user-friend"
        assert before_friend_create < rolled_back_friend._get_updated_at() < after_friend_create
        assert rolled_back_friend._get_updated_by() == "main-user-friend"

        await verify_no_duplicate_paths(db=db)

    async def test_local_and_aware_nodes_added_on_branch(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        diff_repository: DiffRepository,
        car_person_schema_branch_local: SchemaBranch,
    ) -> None:
        branch2 = await create_branch(db=db, branch_name="branch2")
        person = await Node.init(db=db, schema="TestPerson", branch=branch2)
        await person.new(db=db, name="Guy", height=180)
        await person.save(db=db, user_id="branch-user-person")
        car = await Node.init(db=db, schema="TestCar", branch=branch2)
        await car.new(db=db, name="camry", owner=person.id)
        before_car_create = Timestamp()
        await car.save(db=db, user_id="branch-user-car")
        after_car_create = Timestamp()

        diff_coordinator = await self._get_diff_coordinator(db=db, branch=branch2)
        enriched_diff_metadata = await diff_coordinator.update_branch_diff(
            base_branch=default_branch, diff_branch=branch2
        )
        enriched_diff = await diff_repository.get_one(
            diff_branch_name=enriched_diff_metadata.diff_branch_name, diff_id=enriched_diff_metadata.uuid
        )
        diff_person = get_one_diff_node(diff_root=enriched_diff, node_uuid=person.id)
        assert diff_person.action is DiffAction.ADDED
        # validate car is not in the diff
        with pytest.raises(ValueError, match=r"No nodes found"):
            get_one_diff_node(diff_root=enriched_diff, node_uuid=car.id)

        diff_merger = await self._get_diff_merger(db=db, branch=branch2)
        merge_at = Timestamp()
        await diff_merger.merge_graph(at=merge_at)

        # validate person update on main with metadata
        updated_person = await NodeManager.get_one(
            db=db, id=person.id, include_metadata=MetadataOptions.USER_TIMESTAMPS
        )
        assert updated_person.height.value == 180
        assert updated_person.name.value == "Guy"
        # Person Node metadata - created on branch, merged to main
        assert updated_person._get_created_at() == merge_at
        assert updated_person._get_created_by() == "branch-user-person"
        assert updated_person._get_updated_at() == merge_at
        assert updated_person._get_updated_by() == "branch-user-person"
        # Person Attribute metadata
        assert updated_person.name._get_created_at() == merge_at
        assert updated_person.name._get_created_by() == "branch-user-person"
        assert updated_person.name._get_updated_at() == merge_at
        assert updated_person.name._get_updated_by() == "branch-user-person"
        assert updated_person.height._get_created_at() == merge_at
        assert updated_person.height._get_created_by() == "branch-user-person"
        assert updated_person.height._get_updated_at() == merge_at
        assert updated_person.height._get_updated_by() == "branch-user-person"
        # validate car (branch=local) not merged to main
        updated_car = await NodeManager.get_one(db=db, id=car.id)
        assert updated_car is None
        person_schema = registry.schema.get(name="TestPerson", duplicate=False)
        cars_rel_schema = person_schema.get_relationship(name="cars")
        cars_rels = await NodeManager.query_peers(
            db=db, ids=[person.id], source_kind="TestPerson", schema=cars_rel_schema, filters={}, fetch_peers=True
        )
        assert len(cars_rels) == 0
        car_schema = registry.schema.get(name="TestCar", duplicate=False)
        owner_rel_schema = car_schema.get_relationship(name="owner")
        owner_rels = await NodeManager.query_peers(
            db=db, ids=[car.id], source_kind="TestCar", schema=owner_rel_schema, filters={}, fetch_peers=True
        )
        assert len(owner_rels) == 0
        # validate relationship still exists on branch
        cars_rels = await NodeManager.query_peers(
            db=db,
            branch=branch2,
            ids=[person.id],
            source_kind="TestPerson",
            schema=cars_rel_schema,
            filters={},
            fetch_peers=True,
        )
        assert len(cars_rels) == 1
        assert cars_rels[0].peer_id == car.id
        owner_rels = await NodeManager.query_peers(
            db=db,
            branch=branch2,
            ids=[car.id],
            source_kind="TestCar",
            schema=owner_rel_schema,
            filters={},
            fetch_peers=True,
            include_metadata=MetadataOptions.USER_TIMESTAMPS,
        )
        assert len(owner_rels) == 1
        assert owner_rels[0].peer_id == person.id
        assert before_car_create < owner_rels[0]._get_created_at() < after_car_create
        assert owner_rels[0]._get_created_by() == "branch-user-car"
        assert before_car_create < owner_rels[0]._get_updated_at() < after_car_create
        assert owner_rels[0]._get_updated_by() == "branch-user-car"
        await verify_no_duplicate_paths(db=db)

    async def test_agnostic_and_aware_nodes_added_on_branch(
        self, db: InfrahubDatabase, default_branch: Branch, diff_repository: DiffRepository, car_person_schema_global
    ) -> None:
        branch2 = await create_branch(db=db, branch_name="branch2")
        person = await Node.init(db=db, schema="TestPerson", branch=branch2)
        await person.new(db=db, name="Guy", height=180)
        before_person_create = Timestamp()
        await person.save(db=db, user_id="branch-user-person")
        after_person_create = Timestamp()
        car = await Node.init(db=db, schema="TestCar", branch=branch2)
        await car.new(db=db, name="camry", nbr_seats=3, is_electric=False, owner=person.id)
        before_car_create = Timestamp()
        await car.save(db=db, user_id="branch-user-car")
        after_car_create = Timestamp()

        diff_coordinator = await self._get_diff_coordinator(db=db, branch=branch2)
        enriched_diff_metadata = await diff_coordinator.update_branch_diff(
            base_branch=default_branch, diff_branch=branch2
        )
        enriched_diff = await diff_repository.get_one(
            diff_branch_name=enriched_diff_metadata.diff_branch_name, diff_id=enriched_diff_metadata.uuid
        )
        diff_person = get_one_diff_node(diff_root=enriched_diff, node_uuid=person.id)
        assert diff_person.action is DiffAction.UPDATED
        diff_car = get_one_diff_node(diff_root=enriched_diff, node_uuid=car.id)
        assert diff_car.action is DiffAction.ADDED

        diff_merger = await self._get_diff_merger(db=db, branch=branch2)
        merge_at = Timestamp()
        await diff_merger.merge_graph(at=merge_at)

        # validate person (agnostic) exists on main with metadata
        updated_person = await NodeManager.get_one(
            db=db, id=person.id, include_metadata=MetadataOptions.USER_TIMESTAMPS, prefetch_relationships=True
        )
        assert updated_person.height.value == 180
        assert updated_person.name.value == "Guy"
        # Person Node metadata - updated_at reflects merge (relationship added)
        assert before_person_create < updated_person._get_created_at() < after_person_create
        assert updated_person._get_created_by() == "branch-user-person"
        assert updated_person._get_updated_at() == merge_at
        assert updated_person._get_updated_by() == "branch-user-car"

        cars_rels = await updated_person.cars.get_relationships(db=db)
        assert len(cars_rels) == 1
        assert cars_rels[0].peer_id == car.id
        # Person cars relationship metadata
        assert cars_rels[0]._get_created_at() == merge_at
        assert cars_rels[0]._get_created_by() == "branch-user-car"
        assert cars_rels[0]._get_updated_at() == merge_at
        assert cars_rels[0]._get_updated_by() == "branch-user-car"

        # validate car merged to main with metadata
        updated_car = await NodeManager.get_one(
            db=db, id=car.id, include_metadata=MetadataOptions.USER_TIMESTAMPS, prefetch_relationships=True
        )
        assert updated_car.name.value == "camry"
        assert updated_car.nbr_seats.value == 3
        assert updated_car.is_electric.value is False
        owner_rel = await updated_car.owner.get(db=db)
        assert owner_rel.peer_id == person.id
        # Car Node metadata - created on branch, merged to main
        assert updated_car._get_created_at() == merge_at
        assert updated_car._get_created_by() == "branch-user-car"
        assert updated_car._get_updated_at() == merge_at
        assert updated_car._get_updated_by() == "branch-user-car"
        # Car owner relationship metadata
        assert owner_rel._get_created_at() == merge_at
        assert owner_rel._get_created_by() == "branch-user-car"
        assert owner_rel._get_updated_at() == merge_at
        assert owner_rel._get_updated_by() == "branch-user-car"
        # Car Attribute metadata
        assert updated_car.name._get_created_at() == merge_at
        assert updated_car.name._get_created_by() == "branch-user-car"

        # validate relationships on default branch
        person_schema = registry.schema.get(name="TestPerson", duplicate=False)
        cars_rel_schema = person_schema.get_relationship(name="cars")
        cars_rels = await NodeManager.query_peers(
            db=db,
            ids=[person.id],
            source_kind="TestPerson",
            schema=cars_rel_schema,
            filters={},
            fetch_peers=True,
            include_metadata=MetadataOptions.USER_TIMESTAMPS,
        )
        assert len(cars_rels) == 1
        assert cars_rels[0].peer_id == car.id
        assert cars_rels[0]._get_created_at() == merge_at
        assert cars_rels[0]._get_created_by() == "branch-user-car"
        assert cars_rels[0]._get_updated_at() == merge_at
        assert cars_rels[0]._get_updated_by() == "branch-user-car"

        car_schema = registry.schema.get(name="TestCar", duplicate=False)
        owner_rel_schema = car_schema.get_relationship(name="owner")
        owner_rels = await NodeManager.query_peers(
            db=db,
            ids=[car.id],
            source_kind="TestCar",
            schema=owner_rel_schema,
            filters={},
            fetch_peers=True,
            include_metadata=MetadataOptions.USER_TIMESTAMPS,
        )
        assert len(owner_rels) == 1
        assert owner_rels[0].peer_id == person.id
        assert owner_rels[0]._get_created_at() == merge_at
        assert owner_rels[0]._get_created_by() == "branch-user-car"
        assert owner_rels[0]._get_updated_at() == merge_at
        assert owner_rels[0]._get_updated_by() == "branch-user-car"

        # validate relationship still exists on branch
        cars_rels = await NodeManager.query_peers(
            db=db,
            branch=branch2,
            ids=[person.id],
            source_kind="TestPerson",
            schema=cars_rel_schema,
            filters={},
            fetch_peers=True,
            include_metadata=MetadataOptions.USER_TIMESTAMPS,
        )
        assert len(cars_rels) == 1
        assert cars_rels[0].peer_id == car.id
        assert before_car_create < cars_rels[0]._get_created_at() < after_car_create
        assert cars_rels[0]._get_created_by() == "branch-user-car"
        assert before_car_create < cars_rels[0]._get_updated_at() < after_car_create
        assert cars_rels[0]._get_updated_by() == "branch-user-car"

        owner_rels = await NodeManager.query_peers(
            db=db,
            branch=branch2,
            ids=[car.id],
            source_kind="TestCar",
            schema=owner_rel_schema,
            filters={},
            fetch_peers=True,
            include_metadata=MetadataOptions.USER_TIMESTAMPS,
        )
        assert len(owner_rels) == 1
        assert owner_rels[0].peer_id == person.id
        assert before_car_create < owner_rels[0]._get_created_at() < after_car_create
        assert owner_rels[0]._get_created_by() == "branch-user-car"
        assert before_car_create < owner_rels[0]._get_updated_at() < after_car_create
        assert owner_rels[0]._get_updated_by() == "branch-user-car"
        await verify_no_duplicate_paths(db=db)

    async def test_update_individual_relationship_properties_one_at_a_time(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        person_john_main,
        person_jane_main,
        car_accord_main,
        car_camry_main,
    ) -> None:
        before_test_start = Timestamp()
        person_schema = db.schema.get(name="TestPerson", duplicate=False)
        cars_rel_schema = person_schema.get_relationship(name="cars")
        branch2 = await create_branch(db=db, branch_name="branch2")
        car_branch = await NodeManager.get_one(db=db, branch=branch2, id=car_accord_main.id)
        await car_branch.owner.update(db=db, data={"id": person_john_main.id, "_relation__is_protected": True})
        await car_branch.save(db=db, user_id="branch-user-one")

        diff_coordinator = await self._get_diff_coordinator(db=db, branch=branch2)
        await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch2)

        car_branch = await NodeManager.get_one(db=db, branch=branch2, id=car_accord_main.id)
        await car_branch.owner.update(db=db, data={"id": person_john_main.id, "_relation__source": car_camry_main.id})
        await car_branch.save(db=db, user_id="branch-user-two")

        await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch2)

        merge_at = Timestamp()
        diff_merger = await self._get_diff_merger(db=db, branch=branch2)
        await diff_merger.merge_graph(at=merge_at)

        # validate that the properties were correctly updated
        updated_car = await NodeManager.get_one(db=db, id=car_accord_main.id)
        owner_rel = await updated_car.owner.get(db=db)
        assert owner_rel.peer_id == person_john_main.id
        assert owner_rel.is_protected is True
        owner_rel_source = await owner_rel.get_source(db=db)
        assert owner_rel_source.id == car_camry_main.id

        # validate metadata separately
        updated_car_with_metadata = await NodeManager.get_one(
            db=db, id=car_accord_main.id, include_metadata=MetadataOptions.USER_TIMESTAMPS, prefetch_relationships=True
        )
        owner_rel_with_metadata = await updated_car_with_metadata.owner.get(db=db)
        assert updated_car_with_metadata._get_created_at() < before_test_start
        assert updated_car_with_metadata._get_created_by() == SYSTEM_USER_ID
        assert updated_car_with_metadata._get_updated_at() == merge_at
        assert updated_car_with_metadata._get_updated_by() == "branch-user-two"
        assert owner_rel_with_metadata._get_created_at() < before_test_start
        assert owner_rel_with_metadata._get_created_by() == SYSTEM_USER_ID
        assert owner_rel_with_metadata._get_updated_at() == merge_at
        assert owner_rel_with_metadata._get_updated_by() == "branch-user-two"

        john_car_count = await NodeManager.count_peers(
            db=db,
            ids=[person_john_main.id],
            source_kind="TestPerson",
            filters={},
            schema=cars_rel_schema,
            branch=branch2,
        )
        assert john_car_count == 1

        await diff_merger.rollback(at=merge_at)

        # validate that the properties were correctly rolled back
        rolled_back_car = await NodeManager.get_one(db=db, id=car_accord_main.id)
        owner_rel = await rolled_back_car.owner.get(db=db)
        assert owner_rel.peer_id == person_john_main.id
        assert owner_rel.is_protected is False

        # validate metadata separately
        rolled_back_car_with_metadata = await NodeManager.get_one(
            db=db, id=car_accord_main.id, include_metadata=MetadataOptions.USER_TIMESTAMPS, prefetch_relationships=True
        )
        # Car Node metadata should be restored
        assert rolled_back_car_with_metadata._get_created_at() < before_test_start
        assert rolled_back_car_with_metadata._get_created_by() == SYSTEM_USER_ID
        assert rolled_back_car_with_metadata._get_updated_at() < before_test_start
        assert rolled_back_car_with_metadata._get_updated_by() == SYSTEM_USER_ID
        owner_rel_with_metadata = await rolled_back_car_with_metadata.owner.get(db=db)
        assert owner_rel_with_metadata._get_created_at() < before_test_start
        assert owner_rel_with_metadata._get_created_by() == SYSTEM_USER_ID
        assert owner_rel_with_metadata._get_updated_at() < before_test_start
        assert owner_rel_with_metadata._get_updated_by() == SYSTEM_USER_ID
        await verify_no_duplicate_paths(db=db)

    async def test_branch_delete_with_added_base_relationship(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        diff_repository: DiffRepository,
        person_john_main,
        person_jane_main,
        person_alfred_main,
        car_accord_main,
        car_camry_main,
    ) -> None:
        car_created_at = car_accord_main._get_created_at()

        branch2 = await create_branch(db=db, branch_name="branch2")
        car_main = await NodeManager.get_one(db=db, id=car_accord_main.id)
        await car_main.owner.update(db=db, data={"id": person_alfred_main.id, "_relation__is_protected": True})
        before_alfred_update = Timestamp()
        await car_main.save(db=db, user_id="main-user")
        car_branch = await NodeManager.get_one(db=db, branch=branch2, id=car_accord_main.id)
        await car_branch.delete(db=db, user_id="branch-user")

        diff_coordinator = await self._get_diff_coordinator(db=db, branch=branch2)
        enriched_diff = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch2)
        conflicts_map = enriched_diff.get_all_conflicts()
        # check the conflict
        assert len(conflicts_map) == 1
        conflict_node = get_one_diff_node(diff_root=enriched_diff, node_uuid=car_main.id)
        assert conflict_node.conflict
        assert conflict_node.conflict.base_branch_action is DiffAction.UPDATED
        assert conflict_node.conflict.diff_branch_action is DiffAction.REMOVED

        # manually resolve the conflict
        car_main = await NodeManager.get_one(db=db, id=car_accord_main.id)
        await car_main.owner.update(db=db, data={"id": person_john_main.id, "_relation__is_protected": False})
        before_owner_rel_resolved = Timestamp()
        await car_main.save(db=db, user_id="main-user-2")
        after_owner_rel_resolved = Timestamp()

        # check that the conflict is removed
        enriched_diff_metadata = await diff_coordinator.update_branch_diff(
            base_branch=default_branch, diff_branch=branch2
        )
        enriched_diff = await diff_repository.get_one(
            diff_branch_name=enriched_diff_metadata.diff_branch_name, diff_id=enriched_diff_metadata.uuid
        )
        conflicts_map = enriched_diff.get_all_conflicts()
        assert len(conflicts_map) == 0

        merge_at = Timestamp()
        diff_merger = await self._get_diff_merger(db=db, branch=branch2)
        await diff_merger.merge_graph(at=merge_at)

        # validate that the car was deleted
        updated_car = await NodeManager.get_one(db=db, id=car_accord_main.id)
        assert updated_car is None
        # validate that the relationships were deleted
        alfred_main = await NodeManager.get_one(db=db, id=person_alfred_main.id)
        cars_rels = await alfred_main.cars.get(db=db)
        assert len(cars_rels) == 0
        john_main = await NodeManager.get_one(db=db, id=person_john_main.id)
        cars_rels = await john_main.cars.get(db=db)
        assert len(cars_rels) == 0

        # Validate metadata using NodeMetadataDefaultBranchQuery
        node_metadata_query = await NodeMetadataDefaultBranchQuery.init(
            db=db,
            branch=default_branch,
            node_uuids=[car_accord_main.id, person_john_main.id, person_alfred_main.id],
        )
        await node_metadata_query.execute(db=db)
        node_metadatas = node_metadata_query.get_metadatas()
        assert len(node_metadatas) == 3

        metadata_by_uuid = {m.uuid: m for m in node_metadatas}

        # Validate car_accord_main (deleted)
        car_meta = metadata_by_uuid[car_accord_main.id]
        assert car_meta.is_deleted is True
        assert car_meta.created_at == car_created_at
        assert car_meta.created_by == SYSTEM_USER_ID
        assert car_meta.updated_at == merge_at
        assert car_meta.updated_by == "branch-user"

        # Validate car's attributes (all deleted)
        for attr in car_meta.attributes:
            assert attr.is_deleted is True
            assert attr.created_at == car_created_at
            assert attr.created_by == SYSTEM_USER_ID
            assert attr.updated_at == merge_at
            assert attr.updated_by == "branch-user"

        # Validate car's relationship to john (deleted)
        # two relationships, both deleted
        car_rels_to_john = sorted(
            [r for r in car_meta.relationships if r.peer_uuid == person_john_main.id], key=lambda r: r.updated_at
        )
        assert len(car_rels_to_john) == 2
        resolved_conflict_rel_to_john = car_rels_to_john[0]
        assert resolved_conflict_rel_to_john.is_deleted is True
        assert resolved_conflict_rel_to_john.created_by == "main-user-2"
        assert before_owner_rel_resolved < resolved_conflict_rel_to_john.created_at < after_owner_rel_resolved
        assert resolved_conflict_rel_to_john.updated_by == "main-user-2"
        assert before_owner_rel_resolved < resolved_conflict_rel_to_john.updated_at < after_owner_rel_resolved
        # original is actually updated later b/c it happens during the merge
        original_rel_to_john = car_rels_to_john[1]
        assert original_rel_to_john.is_deleted is True
        assert original_rel_to_john.created_by == SYSTEM_USER_ID
        assert original_rel_to_john.created_at == car_created_at
        assert original_rel_to_john.updated_by == "branch-user"
        assert original_rel_to_john.updated_at == merge_at

        # Validate person_john_main (has deleted relationship to car)
        john_meta = metadata_by_uuid[person_john_main.id]
        assert john_meta.is_deleted is False
        # John's relationship to car should be deleted (via cascade from car deletion)
        john_rels_to_car = sorted(
            [r for r in john_meta.relationships if r.peer_uuid == car_accord_main.id], key=lambda r: r.updated_at
        )
        assert len(john_rels_to_car) == 2
        resolved_conflict_rel_to_car = john_rels_to_car[0]
        assert resolved_conflict_rel_to_car.is_deleted is True
        assert resolved_conflict_rel_to_car.created_by == "main-user-2"
        assert before_owner_rel_resolved < resolved_conflict_rel_to_car.created_at < after_owner_rel_resolved
        assert resolved_conflict_rel_to_car.updated_by == "main-user-2"
        assert before_owner_rel_resolved < resolved_conflict_rel_to_car.updated_at < after_owner_rel_resolved
        # original is actually updated later b/c it happens during the merge
        original_rel_to_car = john_rels_to_car[1]
        assert original_rel_to_car.is_deleted is True
        assert original_rel_to_car.created_by == SYSTEM_USER_ID
        assert original_rel_to_car.created_at == car_created_at
        assert original_rel_to_car.updated_by == "branch-user"
        assert original_rel_to_car.updated_at == merge_at

        # Validate person_alfred_main (should have no relationship to car since it was
        # added after branch creation and then reverted before merge)
        alfred_meta = metadata_by_uuid[person_alfred_main.id]
        assert alfred_meta.is_deleted is False
        assert alfred_meta.created_by == SYSTEM_USER_ID
        assert alfred_meta.created_at < before_alfred_update
        # the car-alfred relationship is deleted by main-user-2
        assert alfred_meta.updated_by == "main-user-2"
        assert before_owner_rel_resolved < alfred_meta.updated_at < after_owner_rel_resolved

        await diff_merger.rollback(at=merge_at)

        rolled_back_car = await NodeManager.get_one(
            db=db, id=car_accord_main.id, include_metadata=MetadataOptions.OWNER
        )
        owner_rel = await rolled_back_car.owner.get(db=db)
        assert owner_rel.peer_id == person_john_main.id
        assert owner_rel.is_protected is False

        # Validate metadata after rollback - car should have metadata from before merge
        # The car was modified on main (twice: first to alfred, then back to john)
        # After rollback, the metadata should reflect the main-user-2 changes (the last main branch change)
        rolled_back_car_with_metadata = await NodeManager.get_one(
            db=db, id=car_accord_main.id, include_metadata=MetadataOptions.USER_TIMESTAMPS, prefetch_relationships=True
        )
        # The car Node metadata should reflect the main-user-2 changes since that was the last change on main
        assert rolled_back_car_with_metadata._get_created_by() == SYSTEM_USER_ID
        assert rolled_back_car_with_metadata._get_created_at() == car_created_at
        assert rolled_back_car_with_metadata._get_updated_by() == "main-user-2"
        assert before_owner_rel_resolved < rolled_back_car_with_metadata._get_updated_at() < after_owner_rel_resolved
        await verify_no_duplicate_paths(db=db)

    async def test_base_delete_with_added_branch_relationship(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        diff_repository: DiffRepository,
        person_john_main,
        person_jane_main,
        person_alfred_main,
        car_accord_main,
        car_camry_main,
    ) -> None:
        car_created_at = car_accord_main._get_created_at()

        branch2 = await create_branch(db=db, branch_name="branch2")
        car_branch = await NodeManager.get_one(db=db, branch=branch2, id=car_accord_main.id)
        await car_branch.owner.update(db=db, data={"id": person_alfred_main.id, "_relation__is_protected": True})
        before_branch_update = Timestamp()
        await car_branch.save(db=db, user_id="branch-user")
        car_main = await NodeManager.get_one(db=db, id=car_accord_main.id)
        before_main_delete = Timestamp()
        await car_main.delete(db=db, user_id="main-user")
        after_main_delete = Timestamp()

        diff_coordinator = await self._get_diff_coordinator(db=db, branch=branch2)
        enriched_diff = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch2)
        conflicts_map = enriched_diff.get_all_conflicts()
        # check the conflict
        assert len(conflicts_map) == 1
        conflict_node = get_one_diff_node(diff_root=enriched_diff, node_uuid=car_branch.id)
        assert conflict_node.conflict
        assert conflict_node.conflict.base_branch_action is DiffAction.REMOVED
        assert conflict_node.conflict.diff_branch_action is DiffAction.UPDATED

        # manually resolve the conflict
        car_branch = await NodeManager.get_one(db=db, branch=branch2, id=car_accord_main.id)
        await car_branch.owner.update(db=db, data={"id": person_john_main.id, "_relation__is_protected": False})
        await car_branch.save(db=db, user_id="branch-user-2")

        # check that the conflict is removed
        enriched_diff_metadata = await diff_coordinator.update_branch_diff(
            base_branch=default_branch, diff_branch=branch2
        )
        enriched_diff = await diff_repository.get_one(
            diff_branch_name=enriched_diff_metadata.diff_branch_name, diff_id=enriched_diff_metadata.uuid
        )
        conflicts_map = enriched_diff.get_all_conflicts()
        assert len(conflicts_map) == 0

        merge_at = Timestamp()
        diff_merger = await self._get_diff_merger(db=db, branch=branch2)
        await diff_merger.merge_graph(at=merge_at)

        # validate that the car remains deleted
        updated_car = await NodeManager.get_one(db=db, id=car_accord_main.id)
        assert updated_car is None
        # validate that the relationships do not exist
        alfred_main = await NodeManager.get_one(db=db, id=person_alfred_main.id)
        cars_rels = await alfred_main.cars.get(db=db)
        assert len(cars_rels) == 0
        john_main = await NodeManager.get_one(db=db, id=person_john_main.id)
        cars_rels = await john_main.cars.get(db=db)
        assert len(cars_rels) == 0

        # Validate metadata using NodeMetadataDefaultBranchQuery
        node_metadata_query = await NodeMetadataDefaultBranchQuery.init(
            db=db,
            branch=default_branch,
            node_uuids=[car_accord_main.id, person_john_main.id, person_alfred_main.id],
        )
        await node_metadata_query.execute(db=db)
        node_metadatas = node_metadata_query.get_metadatas()
        assert len(node_metadatas) == 3

        metadata_by_uuid = {m.uuid: m for m in node_metadatas}

        # Validate car_accord_main (deleted on main, remains deleted after merge)
        car_meta = metadata_by_uuid[car_accord_main.id]
        assert car_meta.is_deleted is True
        assert car_meta.created_at == car_created_at
        assert car_meta.created_by == SYSTEM_USER_ID
        # Car was deleted on main, so updated_at/by should reflect main-user's delete
        assert before_main_delete < car_meta.updated_at < after_main_delete
        assert car_meta.updated_by == "main-user"

        # Validate car's attributes (all deleted)
        for attr in car_meta.attributes:
            assert attr.is_deleted is True
            assert attr.created_at == car_created_at
            assert attr.created_by == SYSTEM_USER_ID
            assert before_main_delete < attr.updated_at < after_main_delete
            assert attr.updated_by == "main-user"

        # Validate car's relationship to john (deleted)
        # The original relationship to john was deleted when car was deleted on main
        car_rels_to_john = [r for r in car_meta.relationships if r.peer_uuid == person_john_main.id]
        assert len(car_rels_to_john) == 1
        original_rel_to_john = car_rels_to_john[0]
        assert original_rel_to_john.is_deleted is True
        assert original_rel_to_john.created_by == SYSTEM_USER_ID
        assert original_rel_to_john.created_at == car_created_at
        assert original_rel_to_john.updated_by == "main-user"
        assert before_main_delete < original_rel_to_john.updated_at < after_main_delete

        # Validate person_john_main (has deleted relationship to car)
        john_meta = metadata_by_uuid[person_john_main.id]
        assert john_meta.is_deleted is False
        # John's relationship to car should be deleted (car was deleted on main)
        john_rels_to_car = [r for r in john_meta.relationships if r.peer_uuid == car_accord_main.id]
        assert len(john_rels_to_car) == 1
        john_rel_to_car = john_rels_to_car[0]
        assert john_rel_to_car.is_deleted is True
        assert john_rel_to_car.created_by == SYSTEM_USER_ID
        assert john_rel_to_car.created_at == car_created_at
        assert john_rel_to_car.updated_by == "main-user"
        assert before_main_delete < john_rel_to_car.updated_at < after_main_delete

        # Validate person_alfred_main (should have no relationship to car since the branch
        # changes are discarded when the car remains deleted)
        alfred_meta = metadata_by_uuid[person_alfred_main.id]
        assert alfred_meta.is_deleted is False
        assert alfred_meta.created_by == SYSTEM_USER_ID
        assert alfred_meta.created_at < before_branch_update
        #  Alfred remains unchanged on main
        assert alfred_meta.updated_by == SYSTEM_USER_ID
        assert alfred_meta.updated_at < before_branch_update
        # Alfred should not have been updated by this merge since branch changes were discarded
        alfred_rels_to_car = [r for r in alfred_meta.relationships if r.peer_uuid == car_accord_main.id]
        assert len(alfred_rels_to_car) == 0

        await diff_merger.rollback(at=merge_at)

        # validate that car remains deleted after rollback (no change expected)
        rolled_back_car = await NodeManager.get_one(db=db, id=car_accord_main.id)
        assert rolled_back_car is None

        # Validate metadata after rollback - car should still be deleted with same metadata
        node_metadata_query_after_rollback = await NodeMetadataDefaultBranchQuery.init(
            db=db,
            branch=default_branch,
            node_uuids=[car_accord_main.id, person_john_main.id, person_alfred_main.id],
        )
        await node_metadata_query_after_rollback.execute(db=db)
        node_metadatas_after_rollback = node_metadata_query_after_rollback.get_metadatas()
        assert len(node_metadatas_after_rollback) == 3

        metadata_by_uuid_after_rollback = {m.uuid: m for m in node_metadatas_after_rollback}

        # Validate car metadata after rollback - should be same as after merge
        car_meta_after_rollback = metadata_by_uuid_after_rollback[car_accord_main.id]
        assert car_meta_after_rollback.is_deleted is True
        assert car_meta_after_rollback.created_at == car_created_at
        assert car_meta_after_rollback.created_by == SYSTEM_USER_ID
        assert before_main_delete < car_meta_after_rollback.updated_at < after_main_delete
        assert car_meta_after_rollback.updated_by == "main-user"

        # Validate john metadata after rollback
        john_meta_after_rollback = metadata_by_uuid_after_rollback[person_john_main.id]
        assert john_meta_after_rollback.is_deleted is False
        john_rels_to_car_after_rollback = [
            r for r in john_meta_after_rollback.relationships if r.peer_uuid == car_accord_main.id
        ]
        assert len(john_rels_to_car_after_rollback) == 1
        john_rel_to_car_after_rollback = john_rels_to_car_after_rollback[0]
        assert john_rel_to_car_after_rollback.is_deleted is True
        assert john_rel_to_car_after_rollback.updated_by == "main-user"
        assert before_main_delete < john_rel_to_car_after_rollback.updated_at < after_main_delete

        await verify_no_duplicate_paths(db=db)

    async def test_delete_with_many_relationship_added(
        self, db: InfrahubDatabase, default_branch: Branch, car_person_schema_unregistered: SchemaRoot
    ) -> None:
        # remove TestCar relationship to TestPerson
        car_schema = car_person_schema_unregistered.get(name="TestCar")
        car_schema.relationships = []
        registry.schema.register_schema(schema=car_person_schema_unregistered, branch=default_branch.name)

        # initial data - track creation timestamps
        before_person_1_create = Timestamp()
        person_1 = await Node.init(db=db, schema="TestPerson", branch=default_branch)
        await person_1.new(db=db, name="Alice", height=160)
        await person_1.save(db=db, user_id="setup-user")
        after_person_1_create = Timestamp()

        before_person_2_create = Timestamp()
        person_2 = await Node.init(db=db, schema="TestPerson", branch=default_branch)
        await person_2.new(db=db, name="Bob", height=161)
        await person_2.save(db=db, user_id="setup-user")
        after_person_2_create = Timestamp()

        before_car_1_create = Timestamp()
        car_1 = await Node.init(db=db, schema="TestCar", branch=default_branch)
        await car_1.new(db=db, name="smart", nbr_seats=2, is_electric=True)
        await car_1.save(db=db, user_id="setup-user")
        after_car_1_create = Timestamp()

        before_car_2_create = Timestamp()
        car_2 = await Node.init(db=db, schema="TestCar", branch=default_branch)
        await car_2.new(db=db, name="big", nbr_seats=12, is_electric=False)
        await car_2.save(db=db, user_id="setup-user")
        after_car_2_create = Timestamp()

        # make the branch
        branch2 = await create_branch(db=db, branch_name="branch2")

        # add relationship on main
        before_rel_create = Timestamp()
        person_1_main = await NodeManager.get_one(db=db, id=person_1.id)
        await person_1_main.cars.update(db=db, data=[car_1, car_2])
        await person_1_main.save(db=db, user_id="main-user")
        after_rel_create = Timestamp()
        # delete node on branch
        person_1_branch = await NodeManager.get_one(db=db, branch=branch2, id=person_1.id)
        await person_1_branch.delete(db=db, user_id="branch-user")

        # check that there are no conflicts
        diff_coordinator = await self._get_diff_coordinator(db=db, branch=branch2)
        enriched_diff = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch2)
        conflicts_map = enriched_diff.get_all_conflicts()
        assert len(conflicts_map) == 0

        # merge the branch
        merge_at = Timestamp()
        diff_merger = await self._get_diff_merger(db=db, branch=branch2)
        await diff_merger.merge_graph(at=merge_at)

        # validate that person_1 is deleted
        deleted_person = await NodeManager.get_one(db=db, id=person_1.id)
        assert deleted_person is None
        # validate that all attributes and relationships connected to person_1,
        # including the relationship connecting car_1 and person_1 is deleted,
        # requires a special query b/c TestCar has no relationship to TestPerson in the schema
        await verify_all_linked_edges_deleted(db=db, node_uuid=person_1.id, branch_name=default_branch.name)
        await verify_no_duplicate_paths(db=db)

        node_metadata_query = await NodeMetadataDefaultBranchQuery.init(
            db=db,
            branch=default_branch,
            node_uuids=[person_1.get_id(), person_2.get_id(), car_1.get_id(), car_2.get_id()],
        )
        await node_metadata_query.execute(db=db)
        node_metadatas = node_metadata_query.get_metadatas()
        assert len(node_metadatas) == 4

        # Get metadata by node UUID for easier assertions
        metadata_by_uuid = {m.uuid: m for m in node_metadatas}

        # Validate person_1 (deleted)
        person_1_meta = metadata_by_uuid[person_1.id]
        assert person_1_meta.is_deleted is True
        assert person_1_meta.created_by == "setup-user"
        assert before_person_1_create < person_1_meta.created_at < after_person_1_create
        assert person_1_meta.updated_by == "branch-user"
        assert person_1_meta.updated_at == merge_at

        # Validate person_1's attributes (all deleted)
        for attr in person_1_meta.attributes:
            assert attr.is_deleted is True
            assert attr.created_by == "setup-user"
            assert before_person_1_create < attr.created_at < after_person_1_create
            assert attr.updated_by == "branch-user"
            assert attr.updated_at == merge_at

        # Validate person_1's relationships to car_1 and car_2 (all deleted)
        # NOTE: metadata is not set to "branch-user" because the relationships were
        # added on the default branch after branch2 was created. The car node's metadata
        # remains unchanged as "main-user".
        person_1_rel_to_car_1 = next((r for r in person_1_meta.relationships if r.peer_uuid == car_1.id), None)
        assert person_1_rel_to_car_1 is not None
        assert person_1_rel_to_car_1.is_deleted is True
        assert person_1_rel_to_car_1.created_by == "main-user"
        assert before_rel_create < person_1_rel_to_car_1.created_at < after_rel_create
        assert person_1_rel_to_car_1.updated_by == "main-user"
        assert person_1_rel_to_car_1.updated_at == person_1_rel_to_car_1.created_at

        person_1_rel_to_car_2 = next((r for r in person_1_meta.relationships if r.peer_uuid == car_2.id), None)
        assert person_1_rel_to_car_2 is not None
        assert person_1_rel_to_car_2.is_deleted is True
        assert person_1_rel_to_car_2.created_by == "main-user"
        assert before_rel_create < person_1_rel_to_car_2.created_at < after_rel_create
        assert person_1_rel_to_car_2.updated_by == "main-user"
        assert person_1_rel_to_car_2.updated_at == person_1_rel_to_car_2.created_at

        # Validate person_2 (unaffected)
        person_2_meta = metadata_by_uuid[person_2.id]
        assert person_2_meta.is_deleted is False
        assert person_2_meta.created_by == "setup-user"
        assert before_person_2_create < person_2_meta.created_at < after_person_2_create
        assert person_2_meta.updated_by == "setup-user"
        assert person_2_meta.updated_at == person_2_meta.created_at
        for attr in person_2_meta.attributes:
            assert attr.is_deleted is False
            assert before_person_2_create < attr.created_at < after_person_2_create

        # Validate car_1 (relationship deleted)
        # NOTE: Same edge case as person_1's relationships - updated_by remains "main-user"
        car_1_meta = metadata_by_uuid[car_1.id]
        assert car_1_meta.is_deleted is False
        assert car_1_meta.created_by == "setup-user"
        assert before_car_1_create < car_1_meta.created_at < after_car_1_create
        assert car_1_meta.updated_by == "main-user"
        assert before_rel_create < car_1_meta.updated_at < after_rel_create

        # Validate car_1's relationship to person_1 (deleted)
        # NOTE: Same edge case as person_1's relationships - updated_by remains "main-user"
        car_1_rel_to_person_1 = next((r for r in car_1_meta.relationships if r.peer_uuid == person_1.id), None)
        assert car_1_rel_to_person_1 is not None
        assert car_1_rel_to_person_1.is_deleted is True
        assert car_1_rel_to_person_1.created_by == "main-user"
        assert before_rel_create < car_1_rel_to_person_1.created_at < after_rel_create
        assert car_1_rel_to_person_1.updated_by == "main-user"
        assert car_1_rel_to_person_1.updated_at == car_1_rel_to_person_1.created_at

        # Validate car_2 (relationship deleted)
        # NOTE: Same edge case as car_1 - car_2's metadata is not updated
        car_2_meta = metadata_by_uuid[car_2.id]
        assert car_2_meta.is_deleted is False
        assert car_2_meta.created_by == "setup-user"
        assert before_car_2_create < car_2_meta.created_at < after_car_2_create
        assert car_2_meta.updated_by == "main-user"
        assert before_rel_create < car_2_meta.updated_at < after_rel_create

        # Validate car_2's relationship to person_1 (deleted)
        # NOTE: Same edge case as person_1's relationships - updated_by remains "main-user"
        car_2_rel_to_person_1 = next((r for r in car_2_meta.relationships if r.peer_uuid == person_1.id), None)
        assert car_2_rel_to_person_1 is not None
        assert car_2_rel_to_person_1.is_deleted is True
        assert car_2_rel_to_person_1.created_by == "main-user"
        assert before_rel_create < car_2_rel_to_person_1.created_at < after_rel_create
        assert car_2_rel_to_person_1.updated_by == "main-user"

    @pytest.mark.parametrize("selection", [ConflictSelection.BASE_BRANCH, ConflictSelection.DIFF_BRANCH])
    async def test_attribute_update_with_conflict(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        diff_repository: DiffRepository,
        person_john_main: Node,
        selection: ConflictSelection,
    ) -> None:
        person_created_at = person_john_main._get_created_at()

        main_value = 200
        branch_value = 150
        branch2 = await create_branch(db=db, branch_name="branch2")
        person_main = await NodeManager.get_one(db=db, branch=default_branch, id=person_john_main.id)
        person_main.height.value = main_value
        before_main_update = Timestamp()
        await person_main.save(db=db, user_id="main-user")
        after_main_update = Timestamp()
        person_branch = await NodeManager.get_one(db=db, branch=branch2, id=person_john_main.id)
        person_branch.height.value = branch_value
        await person_branch.save(db=db, user_id="branch-user")

        # set the conflict resolution
        diff_coordinator = await self._get_diff_coordinator(db=db, branch=branch2)
        enriched_diff = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch2)
        conflicts_map = enriched_diff.get_all_conflicts()
        assert len(conflicts_map) == 1
        expected_path = f"data/{person_john_main.id}/height/value"
        assert expected_path in conflicts_map
        conflict = conflicts_map[expected_path]
        await diff_repository.update_conflict_by_id(conflict_id=conflict.uuid, selection=selection)

        # merge the branch
        merge_at = Timestamp()
        diff_merger = await self._get_diff_merger(db=db, branch=branch2)
        await diff_merger.merge_graph(at=merge_at)

        # validate that person has correct age
        updated_person = await NodeManager.get_one(db=db, branch=default_branch, id=person_john_main.id)
        if selection is ConflictSelection.DIFF_BRANCH:
            assert updated_person.height.value == branch_value
        else:
            assert updated_person.height.value == main_value

        # Validate metadata - when DIFF_BRANCH is selected, merge should update metadata
        # When BASE_BRANCH is selected, main's value is kept so merge may still update metadata
        updated_person_with_metadata = await NodeManager.get_one(
            db=db, branch=default_branch, id=person_john_main.id, include_metadata=MetadataOptions.USER_TIMESTAMPS
        )
        assert updated_person_with_metadata._get_created_at() == person_created_at
        assert updated_person_with_metadata._get_created_by() == SYSTEM_USER_ID
        if selection is ConflictSelection.DIFF_BRANCH:
            # Branch value was merged, so metadata should be updated to merge time with branch-user
            assert updated_person_with_metadata._get_updated_at() == merge_at
            assert updated_person_with_metadata._get_updated_by() == "branch-user"
            # Check height attribute metadata
            assert updated_person_with_metadata.height._get_updated_at() == merge_at
            assert updated_person_with_metadata.height._get_updated_by() == "branch-user"
        else:
            # Branch value was merged, so metadata should be updated to merge time with branch-user
            assert before_main_update < updated_person_with_metadata._get_updated_at() < after_main_update
            assert updated_person_with_metadata._get_updated_by() == "main-user"
            # Check height attribute metadata
            assert before_main_update < updated_person_with_metadata.height._get_updated_at() < after_main_update
            assert updated_person_with_metadata.height._get_updated_by() == "main-user"

        await verify_no_duplicate_paths(db=db)

    async def test_hierarchy_preserved(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        diff_repository: DiffRepository,
        hierarchical_location_schema_simple: SchemaRoot,
    ) -> None:
        branch_name = "branch_hierarch"
        branch = await create_branch(db=db, branch_name=branch_name)
        hierarchy_data = await _build_hierarchical_location_data(db=db, branch=branch)

        diff_coordinator = await self._get_diff_coordinator(db=db, branch=branch)
        await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
        at = Timestamp()
        diff_merger = await self._get_diff_merger(db=db, branch=branch)
        await diff_merger.merge_graph(at=at)

        region_schema = registry.schema.get(name="LocationRegion", duplicate=False)
        region = hierarchy_data["europe"]
        region_descendants = [
            hierarchy_data["paris"],
            hierarchy_data["paris-r1"],
            hierarchy_data["paris-r2"],
            hierarchy_data["london"],
            hierarchy_data["london-r1"],
            hierarchy_data["london-r2"],
        ]
        site_schema = registry.schema.get(name="LocationSite", duplicate=False)
        site = hierarchy_data["paris-r2"]
        site_ancestors = [
            hierarchy_data["paris"],
            hierarchy_data["europe"],
        ]

        retrieved_descendants_map = await NodeManager.query_hierarchy(
            db=db,
            branch=default_branch,
            id=region.id,
            node_schema=region_schema,
            direction=RelationshipHierarchyDirection.DESCENDANTS,
            filters={},
        )
        assert set(retrieved_descendants_map.keys()) == {d.id for d in region_descendants}
        retrieved_ancestors_map = await NodeManager.query_hierarchy(
            db=db,
            branch=default_branch,
            id=site.id,
            node_schema=site_schema,
            direction=RelationshipHierarchyDirection.ANCESTORS,
            filters={},
        )
        assert set(retrieved_ancestors_map.keys()) == {d.id for d in site_ancestors}

        # Validate metadata on merged nodes - europe region was created on branch and merged
        europe_with_metadata = await NodeManager.get_one(
            db=db, id=region.id, include_metadata=MetadataOptions.USER_TIMESTAMPS
        )
        # Merged nodes should have updated_at set to merge time
        assert europe_with_metadata._get_updated_at() == at

        await verify_no_duplicate_paths(db=db)

    async def test_diff_and_merge_with_migrated_node_kind(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_internal_models_schema: SchemaBranch,
        register_core_models_schema: SchemaBranch,
        car_person_schema: SchemaBranch,
        car_accord_main: Node,
        car_camry_main: Node,
        car_yaris_main: Node,
        person_jane_main: Node,
        person_john_main: Node,
    ) -> None:
        car_accord_created_at = car_accord_main._get_created_at()
        car_camry_created_at = car_camry_main._get_created_at()
        car_yaris_created_at = car_yaris_main._get_created_at()

        schema_main = registry.schema.get_schema_branch(name=default_branch.name)
        await registry.schema.update_schema_branch(db=db, branch=default_branch, schema=schema_main, update_db=True)
        original_car_owner = person_john_main

        branch2 = await create_branch(db=db, branch_name="branch2")
        schema_branch = registry.schema.get_schema_branch(name=branch2.name)
        original_car_schema = schema_branch.get(name="TestCar", duplicate=True)
        car_schema_branch = schema_branch.get(name="TestCar", duplicate=True)
        car_schema_branch.name = "NewCar"
        car_schema_branch.namespace = "Test2"
        assert car_schema_branch.kind == "Test2NewCar"
        schema_branch.set(name="Test2NewCar", schema=car_schema_branch)
        person_schema_branch = schema_branch.get(name="TestPerson", duplicate=True)
        cars_rel = person_schema_branch.get_relationship("cars")
        cars_rel.peer = "Test2NewCar"
        cars_driven_rel = person_schema_branch.get_relationship("cars_driven")
        cars_driven_rel.peer = "Test2NewCar"
        schema_branch.set(name="TestPerson", schema=person_schema_branch)
        schema_branch.process()
        await registry.schema.update_schema_branch(
            db=db, branch=branch2, schema=schema_branch, limit=["TestCar", "Test2NewCar", "TestPerson"], update_db=True
        )
        migration = NodeKindUpdateMigration(
            previous_node_schema=schema_branch.get(name="TestCar"),
            new_node_schema=car_schema_branch,
            schema_path=SchemaPath(
                path_type=SchemaPathType.ATTRIBUTE, schema_kind="Test2NewCar", field_name="namespace"
            ),
        )
        migration_at = Timestamp()
        execution_result = await migration.execute(
            migration_input=MigrationInput(db=db, at=migration_at, user_id="migration-user"), branch=branch2
        )
        assert not execution_result.errors

        # update car owner and color
        migrated_car = await NodeManager.get_one(db=db, branch=branch2, id=car_accord_main.id)
        await migrated_car.owner.update(db=db, data=person_jane_main.id)
        new_color = "#654321"
        migrated_car.color.value = new_color
        await migrated_car.save(db=db, user_id="branch-user-update")

        # delete a car
        migrated_car_to_delete = await NodeManager.get_one(db=db, branch=branch2, id=car_camry_main.id)
        await migrated_car_to_delete.delete(db=db, user_id="branch-user-delete")

        merge_at = Timestamp()
        diff_coordinator = await self._get_diff_coordinator(db=db, branch=branch2)
        await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch2)
        diff_merger = await self._get_diff_merger(db=db, branch=branch2)
        await diff_merger.merge_graph(at=merge_at)

        updated_schema_branch = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
        registry.schema.set_schema_branch(name=default_branch.name, schema=updated_schema_branch)
        car_schema_main = updated_schema_branch.get(name="Test2NewCar", duplicate=False)
        assert car_schema_main.id == original_car_schema.id
        person_schema_branch = updated_schema_branch.get(name="TestPerson", duplicate=True)
        cars_rel = person_schema_branch.get_relationship("cars")
        cars_rel.peer = "Test2NewCar"
        cars_driven_rel = person_schema_branch.get_relationship("cars_driven")
        cars_driven_rel.peer = "Test2NewCar"
        with pytest.raises(SchemaNotFoundError):
            updated_schema_branch.get(name="TestCar", duplicate=False)

        retrieved_migrated_car = await NodeManager.get_one(db=db, branch=default_branch, id=car_accord_main.id)
        assert retrieved_migrated_car.get_kind() == "Test2NewCar"
        for attr_name in car_schema_main.attribute_names:
            if attr_name == "color":
                assert retrieved_migrated_car.color.value == new_color
            else:
                assert getattr(retrieved_migrated_car, attr_name).value == getattr(car_accord_main, attr_name).value
        retrieved_owner_rels = await retrieved_migrated_car.owner.get_relationships(db=db)
        assert {r.get_peer_id() for r in retrieved_owner_rels} == {person_jane_main.id}
        retrieved_driver_rels = await retrieved_migrated_car.driver.get_relationships(db=db)
        assert not {r.get_peer_id() for r in retrieved_driver_rels}
        with pytest.raises(SchemaNotFoundError):
            await NodeManager.query(db=db, branch=default_branch, schema="TestCar")
        # try to get deleted node
        with pytest.raises(NodeNotFoundError):
            await NodeManager.get_one(db=db, branch=branch2, id=car_camry_main.id, raise_on_error=True)

        # Validate node-level metadata on migrated car after merge
        migrated_car_with_metadata = await NodeManager.get_one(
            db=db,
            branch=default_branch,
            id=car_accord_main.id,
            include_metadata=MetadataOptions.USER_TIMESTAMPS,
            prefetch_relationships=True,
        )
        # Node created_at is from migration time (when the new kind was created on branch)
        assert migrated_car_with_metadata._get_created_at() == car_accord_created_at
        assert migrated_car_with_metadata._get_created_by() == SYSTEM_USER_ID
        # Node was updated by branch-user-update at the branch update time
        assert migrated_car_with_metadata._get_updated_at() == merge_at
        assert migrated_car_with_metadata._get_updated_by() == "branch-user-update"

        # Validate attribute-level metadata on migrated car after merge
        # Color attribute was updated by branch-user-update
        assert migrated_car_with_metadata.color._get_created_at() == car_accord_created_at
        assert migrated_car_with_metadata.color._get_created_by() == SYSTEM_USER_ID
        assert migrated_car_with_metadata.color._get_updated_at() == merge_at
        assert migrated_car_with_metadata.color._get_updated_by() == "branch-user-update"

        # Other attributes should have migration created_at, updated_at from migration
        for attr_name in ("name", "nbr_seats"):
            attr = migrated_car_with_metadata.get_attribute(name=attr_name)
            assert attr._get_created_at() == car_accord_created_at
            assert attr._get_created_by() == SYSTEM_USER_ID
            assert attr._get_updated_at() == car_accord_created_at
            assert attr._get_updated_by() == SYSTEM_USER_ID

        owner_rel = await migrated_car_with_metadata.owner.get(db=db)
        assert owner_rel._get_created_at() == merge_at
        assert owner_rel._get_created_by() == "branch-user-update"
        assert owner_rel._get_updated_at() == merge_at
        assert owner_rel._get_updated_by() == "branch-user-update"

        # Validate metadata on migrated car with no updates
        unchanged_car_with_metadata = await NodeManager.get_one(
            db=db,
            branch=default_branch,
            id=car_yaris_main.id,
            include_metadata=MetadataQueryOptions(
                node_level=MetadataOptions.USER_TIMESTAMPS,
                attribute_level=MetadataOptions.USER_TIMESTAMPS,
                relationship_level=MetadataOptions.USER_TIMESTAMPS,
            ),
            prefetch_relationships=True,
        )
        assert unchanged_car_with_metadata._get_created_at() == car_yaris_created_at
        assert unchanged_car_with_metadata._get_created_by() == SYSTEM_USER_ID
        assert unchanged_car_with_metadata._get_updated_at() == merge_at
        assert unchanged_car_with_metadata._get_updated_by() == "migration-user"

        for attr_name in ("name", "nbr_seats"):
            attr = unchanged_car_with_metadata.get_attribute(name=attr_name)
            assert attr._get_created_at() == car_yaris_created_at
            assert attr._get_created_by() == SYSTEM_USER_ID
            assert attr._get_updated_at() == car_yaris_created_at
            assert attr._get_updated_by() == SYSTEM_USER_ID

        owner_rel_manager = unchanged_car_with_metadata.get_relationship(name="owner")
        owner_rel = await owner_rel_manager.get(db=db)
        assert owner_rel._get_created_at() == car_yaris_created_at
        assert owner_rel._get_created_by() == SYSTEM_USER_ID
        assert owner_rel._get_updated_at() == car_yaris_created_at
        assert owner_rel._get_updated_by() == SYSTEM_USER_ID

        # Validate metadata on deleted car using NodeMetadataDefaultBranchQuery
        node_metadata_query = await NodeMetadataDefaultBranchQuery.init(
            db=db,
            branch=default_branch,
            node_uuids=[car_camry_main.id],
        )
        await node_metadata_query.execute(db=db)
        node_metadatas = node_metadata_query.get_metadatas()
        assert len(node_metadatas) == 1

        deleted_car_meta = node_metadatas[0]
        assert deleted_car_meta.uuid == car_camry_main.id
        assert deleted_car_meta.is_deleted is True
        # Deleted car should have migration created_at, updated_at from branch user delete
        assert deleted_car_meta.created_at == car_camry_created_at
        assert deleted_car_meta.created_by == SYSTEM_USER_ID
        assert deleted_car_meta.updated_at == merge_at
        assert deleted_car_meta.updated_by == "branch-user-delete"

        # Validate deleted car's attributes metadata
        for attr in deleted_car_meta.attributes:
            assert attr.is_deleted is True
            assert attr.created_at == car_camry_created_at
            assert attr.created_by == SYSTEM_USER_ID
            assert attr.updated_at == merge_at
            assert attr.updated_by == "branch-user-delete"

        for rel in deleted_car_meta.relationships:
            assert rel.is_deleted is True
            assert rel.created_at == car_camry_created_at
            assert rel.created_by == SYSTEM_USER_ID
            assert rel.updated_at == merge_at
            assert rel.updated_by == "branch-user-delete"

        await verify_no_duplicate_paths(db=db)

        await diff_merger.rollback(at=merge_at)

        rolled_back_schema_branch = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
        registry.schema.set_schema_branch(name=default_branch.name, schema=rolled_back_schema_branch)
        car_schema_main = rolled_back_schema_branch.get(name="TestCar", duplicate=False)
        with pytest.raises(SchemaNotFoundError):
            rolled_back_schema_branch.get(name="Test2NewCar", duplicate=False)
        person_schema_main = rolled_back_schema_branch.get(name="TestPerson", duplicate=False)
        cars_rel = person_schema_main.get_relationship("cars")
        cars_rel.peer = "TestCar"
        cars_driven_rel = person_schema_main.get_relationship("cars_driven")
        cars_driven_rel.peer = "TestCar"
        retrieved_unmigrated_car = await NodeManager.get_one(db=db, branch=default_branch, id=car_accord_main.id)
        assert retrieved_unmigrated_car.get_kind() == "TestCar"
        assert retrieved_unmigrated_car.color.value == car_accord_main.color.value
        retrieved_owner_rels = await retrieved_unmigrated_car.owner.get_relationships(db=db)
        assert {r.get_peer_id() for r in retrieved_owner_rels} == {original_car_owner.id}
        with pytest.raises(SchemaNotFoundError):
            await NodeManager.query(db=db, branch=default_branch, schema="Test2NewCar")
        # get undeleted node
        undeleted_car = await NodeManager.get_one(db=db, branch=default_branch, id=car_camry_main.id)
        assert undeleted_car.get_kind() == "TestCar"

        # Validate node-level metadata after rollback for car_accord
        rolled_back_car_with_metadata = await NodeManager.get_one(
            db=db, branch=default_branch, id=car_accord_main.id, include_metadata=MetadataOptions.USER_TIMESTAMPS
        )
        # After rollback, should have original created_at and no user updates
        assert rolled_back_car_with_metadata._get_created_at() == car_accord_created_at
        assert rolled_back_car_with_metadata._get_created_by() == SYSTEM_USER_ID
        assert rolled_back_car_with_metadata._get_updated_at() == car_accord_created_at
        assert rolled_back_car_with_metadata._get_updated_by() == SYSTEM_USER_ID

        # Validate attribute-level metadata after rollback
        assert rolled_back_car_with_metadata.color._get_created_at() == car_accord_created_at
        assert rolled_back_car_with_metadata.color._get_created_by() == SYSTEM_USER_ID
        assert rolled_back_car_with_metadata.color._get_updated_at() == car_accord_created_at
        assert rolled_back_car_with_metadata.color._get_updated_by() == SYSTEM_USER_ID

        assert rolled_back_car_with_metadata.name._get_created_at() == car_accord_created_at
        assert rolled_back_car_with_metadata.name._get_created_by() == SYSTEM_USER_ID
        assert rolled_back_car_with_metadata.name._get_updated_at() == car_accord_created_at
        assert rolled_back_car_with_metadata.name._get_updated_by() == SYSTEM_USER_ID

        # Validate undeleted car (car_camry) metadata after rollback
        undeleted_car_with_metadata = await NodeManager.get_one(
            db=db, branch=default_branch, id=car_camry_main.id, include_metadata=MetadataOptions.USER_TIMESTAMPS
        )
        # Should have original timestamps restored
        assert undeleted_car_with_metadata._get_created_at() == car_camry_created_at
        assert undeleted_car_with_metadata._get_created_by() == SYSTEM_USER_ID
        assert undeleted_car_with_metadata._get_updated_at() == car_camry_created_at
        assert undeleted_car_with_metadata._get_updated_by() == SYSTEM_USER_ID

        # Validate attribute metadata on undeleted car
        assert undeleted_car_with_metadata.color._get_created_at() == car_camry_created_at
        assert undeleted_car_with_metadata.color._get_created_by() == SYSTEM_USER_ID
        assert undeleted_car_with_metadata.color._get_updated_at() == car_camry_created_at
        assert undeleted_car_with_metadata.color._get_updated_by() == SYSTEM_USER_ID

    async def test_diff_and_merge_with_migrated_node_kind_and_migrated_inheritance(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_internal_models_schema: SchemaBranch,
        register_core_models_schema: SchemaBranch,
        car_person_schema_generics: SchemaBranch,
    ) -> None:
        # schema with multiple generics
        root_with_another_generic = SchemaRoot(
            generics=[
                GenericSchema(
                    name="Vehicle",
                    namespace="Test",
                    attributes=[AttributeSchema(name="speed", kind="Text", optional=True)],
                )
            ]
        )
        registry.schema.register_schema(schema=root_with_another_generic, branch=default_branch.name)
        schema_main = registry.schema.get_schema_branch(name=default_branch.name)
        await registry.schema.update_schema_branch(db=db, branch=default_branch, schema=schema_main, update_db=True)

        # initial data
        person_1 = await create_and_save(db=db, branch=default_branch, schema="TestPerson", name="One", height=171)
        person_2 = await create_and_save(db=db, branch=default_branch, schema="TestPerson", name="Two", height=172)
        person_3 = await create_and_save(db=db, branch=default_branch, schema="TestPerson", name="Three", height=173)
        await create_and_save(
            db=db, branch=default_branch, schema="TestGazCar", name="Gaz", nbr_seats=3, mpg=32, owner=person_1
        )
        e_car_1 = await create_and_save(
            db=db,
            branch=default_branch,
            schema="TestElectricCar",
            name="Eee",
            nbr_seats=4,
            nbr_engine=1,
            owner=person_2,
        )
        e_car_1_created_at = e_car_1._get_created_at()
        e_car_2 = await create_and_save(
            db=db,
            branch=default_branch,
            schema="TestElectricCar",
            name="Eee2",
            nbr_seats=5,
            nbr_engine=2,
            owner=person_3,
        )
        e_car_2_created_at = e_car_2._get_created_at()
        original_e_car_1_owner = person_2

        # new branch
        branch2 = await create_branch(db=db, branch_name="branch2")

        # migrate TestElectricCar to be Test2NewElectricCar
        schema_branch = registry.schema.get_schema_branch(name=branch2.name)
        original_car_schema = schema_branch.get(name="TestElectricCar", duplicate=True)
        car_schema_branch = schema_branch.get(name="TestElectricCar", duplicate=True)
        car_schema_branch.name = "NewElectricCar"
        car_schema_branch.namespace = "Test2"
        assert car_schema_branch.kind == "Test2NewElectricCar"
        schema_branch.set(name="Test2NewElectricCar", schema=car_schema_branch)
        schema_branch.process()
        await registry.schema.update_schema_branch(
            db=db,
            branch=branch2,
            schema=schema_branch,
            limit=["TestElectricCar", "Test2NewElectricCar"],
            update_db=True,
        )
        migration = NodeKindUpdateMigration(
            previous_node_schema=schema_branch.get(name="TestElectricCar"),
            new_node_schema=car_schema_branch,
            schema_path=SchemaPath(
                path_type=SchemaPathType.ATTRIBUTE, schema_kind="Test2NewElectricCar", field_name="namespace"
            ),
        )
        migration1_at = Timestamp()
        execution_result = await migration.execute(
            migration_input=MigrationInput(db=db, at=migration1_at, user_id="migration-user-one"), branch=branch2
        )
        assert not execution_result.errors

        # update car owner
        migrated_car = await NodeManager.get_one(db=db, branch=branch2, id=e_car_1.id)
        await migrated_car.owner.update(db=db, data=person_1.id)
        new_color = "#654321"
        migrated_car.color.value = new_color
        await migrated_car.save(db=db, user_id="branch-user")

        # migrate Test2NewElectricCar to inherit from TestVehicle
        schema_branch = registry.schema.get_schema_branch(name=branch2.name)
        car_schema_branch = schema_branch.get(name="Test2NewElectricCar", duplicate=True)
        car_schema_branch.inherit_from += ["TestVehicle"]
        schema_branch.set(name="Test2ElectricNewCar", schema=car_schema_branch)
        schema_branch.process()
        await registry.schema.update_schema_branch(
            db=db, branch=branch2, schema=schema_branch, limit=["Test2NewElectricCar"], update_db=True
        )
        migration = NodeKindUpdateMigration(
            previous_node_schema=schema_branch.get(name="Test2NewElectricCar"),
            new_node_schema=car_schema_branch,
            schema_path=SchemaPath(
                path_type=SchemaPathType.ATTRIBUTE, schema_kind="Test2NewElectricCar", field_name="inherit_from"
            ),
        )
        migration2_at = Timestamp()
        execution_result = await migration.execute(
            migration_input=MigrationInput(db=db, at=migration2_at, user_id="migration-user-two"), branch=branch2
        )
        assert not execution_result.errors

        # delete a car
        migrated_car_to_delete = await NodeManager.get_one(db=db, branch=branch2, id=e_car_2.id)
        await migrated_car_to_delete.delete(db=db, user_id="branch-user-delete")

        merge_at = Timestamp()
        diff_coordinator = await self._get_diff_coordinator(db=db, branch=branch2)
        await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch2)
        diff_merger = await self._get_diff_merger(db=db, branch=branch2)
        await diff_merger.merge_graph(at=merge_at)

        updated_schema_branch = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
        registry.schema.set_schema_branch(name=default_branch.name, schema=updated_schema_branch)
        car_schema_main = updated_schema_branch.get(name="Test2NewElectricCar", duplicate=False)
        assert "TestVehicle" in car_schema_main.inherit_from
        assert car_schema_main.id == original_car_schema.id
        with pytest.raises(SchemaNotFoundError):
            updated_schema_branch.get(name="TestElectricCar", duplicate=False)

        retrieved_migrated_car = await NodeManager.get_one(db=db, branch=default_branch, id=e_car_1.id)
        assert retrieved_migrated_car.get_kind() == "Test2NewElectricCar"
        for attr_name in car_schema_main.attribute_names:
            if attr_name == "color":
                assert retrieved_migrated_car.color.value == new_color
            elif attr_name == "speed":
                assert retrieved_migrated_car.speed is not None
                assert not hasattr(e_car_1, "speed")
            else:
                assert getattr(retrieved_migrated_car, attr_name).value == getattr(e_car_1, attr_name).value
        retrieved_owner_rels = await retrieved_migrated_car.owner.get_relationships(db=db)
        assert {r.get_peer_id() for r in retrieved_owner_rels} == {person_1.id}
        with pytest.raises(SchemaNotFoundError):
            await NodeManager.query(db=db, branch=default_branch, schema="TestElectricCar")
        # try to get deleted node
        with pytest.raises(NodeNotFoundError):
            await NodeManager.get_one(db=db, branch=branch2, id=e_car_2.id, raise_on_error=True)

        # Validate node-level metadata on migrated car after merge
        migrated_car_with_metadata = await NodeManager.get_one(
            db=db,
            branch=default_branch,
            id=e_car_1.id,
            include_metadata=MetadataQueryOptions(
                node_level=MetadataOptions.USER_TIMESTAMPS,
                attribute_level=MetadataOptions.USER_TIMESTAMPS,
                relationship_level=MetadataOptions.USER_TIMESTAMPS,
            ),
            prefetch_relationships=True,
        )
        # Node created_at is from first migration time (when the new kind was created on branch)
        assert migrated_car_with_metadata._get_created_at() == e_car_1_created_at
        assert migrated_car_with_metadata._get_created_by() == SYSTEM_USER_ID
        # Node was updated by branch-user at branch update time
        assert migrated_car_with_metadata._get_updated_at() == merge_at
        assert migrated_car_with_metadata._get_updated_by() == "branch-user"

        # Validate attribute-level metadata on migrated car after merge
        # Color attribute was updated by branch-user
        assert migrated_car_with_metadata.color._get_created_at() == e_car_1_created_at
        assert migrated_car_with_metadata.color._get_created_by() == SYSTEM_USER_ID
        assert migrated_car_with_metadata.color._get_updated_at() == merge_at
        assert migrated_car_with_metadata.color._get_updated_by() == "branch-user"

        # Other attributes should have migration1 created_at, updated_at from last migration
        assert migrated_car_with_metadata.name._get_created_at() == e_car_1_created_at
        assert migrated_car_with_metadata.name._get_created_by() == SYSTEM_USER_ID
        assert migrated_car_with_metadata.name._get_updated_at() == e_car_1_created_at
        assert migrated_car_with_metadata.name._get_updated_by() == SYSTEM_USER_ID

        # Validate relationship-level metadata on migrated car after merge
        # Owner relationship was updated by branch-user
        owner_rel = await migrated_car_with_metadata.owner.get(db=db)
        assert owner_rel._get_created_at() == merge_at
        assert owner_rel._get_created_by() == "branch-user"
        assert owner_rel._get_updated_at() == merge_at
        assert owner_rel._get_updated_by() == "branch-user"

        # Validate metadata on deleted car using NodeMetadataDefaultBranchQuery
        node_metadata_query = await NodeMetadataDefaultBranchQuery.init(
            db=db,
            branch=default_branch,
            node_uuids=[e_car_2.id],
        )
        await node_metadata_query.execute(db=db)
        node_metadatas = node_metadata_query.get_metadatas()
        assert len(node_metadatas) == 1

        deleted_car_meta = node_metadatas[0]
        assert deleted_car_meta.uuid == e_car_2.id
        assert deleted_car_meta.is_deleted is True
        # Deleted car should have migration1 created_at, updated_at from branch user delete
        assert deleted_car_meta.created_at == e_car_2_created_at
        assert deleted_car_meta.created_by == SYSTEM_USER_ID
        assert deleted_car_meta.updated_at == merge_at
        assert deleted_car_meta.updated_by == "branch-user-delete"

        # Validate deleted car's attributes metadata
        for attr in deleted_car_meta.attributes:
            assert attr.is_deleted is True
            assert attr.created_at == e_car_2_created_at
            assert attr.created_by == SYSTEM_USER_ID
            assert attr.updated_at == merge_at
            assert attr.updated_by == "branch-user-delete"

        # Validate deleted car's relationships metadata
        for rel in deleted_car_meta.relationships:
            assert rel.is_deleted is True
            assert rel.created_at == e_car_2_created_at
            assert rel.created_by == SYSTEM_USER_ID
            assert rel.updated_at == merge_at
            assert rel.updated_by == "branch-user-delete"

        await verify_no_duplicate_paths(db=db)

        await diff_merger.rollback(at=merge_at)

        rolled_back_schema_branch = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
        registry.schema.set_schema_branch(name=default_branch.name, schema=rolled_back_schema_branch)
        car_schema_main = rolled_back_schema_branch.get(name="TestElectricCar", duplicate=False)
        assert "TestVehicle" not in car_schema_main.inherit_from
        with pytest.raises(SchemaNotFoundError):
            rolled_back_schema_branch.get(name="Test2NewElectricCar", duplicate=False)
        retrieved_unmigrated_car = await NodeManager.get_one(db=db, branch=default_branch, id=e_car_1.id)
        assert retrieved_unmigrated_car.get_kind() == "TestElectricCar"
        assert retrieved_unmigrated_car.color.value == e_car_1.color.value
        retrieved_owner_rels = await retrieved_unmigrated_car.owner.get_relationships(db=db)
        assert {r.get_peer_id() for r in retrieved_owner_rels} == {original_e_car_1_owner.id}
        with pytest.raises(SchemaNotFoundError):
            await NodeManager.query(db=db, branch=default_branch, schema="Test2NewElectricCar")
        # get undeleted node
        undeleted_car = await NodeManager.get_one(db=db, branch=default_branch, id=e_car_2.id)
        assert undeleted_car.get_kind() == "TestElectricCar"

        # Validate node-level metadata after rollback for e_car_1
        rolled_back_car_with_metadata = await NodeManager.get_one(
            db=db,
            branch=default_branch,
            id=e_car_1.id,
            include_metadata=MetadataQueryOptions(
                node_level=MetadataOptions.USER_TIMESTAMPS,
                attribute_level=MetadataOptions.USER_TIMESTAMPS,
                relationship_level=MetadataOptions.USER_TIMESTAMPS,
            ),
            prefetch_relationships=True,
        )
        # After rollback, should have original created_at and no user updates
        assert rolled_back_car_with_metadata._get_created_at() == e_car_1_created_at
        assert rolled_back_car_with_metadata._get_created_by() == SYSTEM_USER_ID
        assert rolled_back_car_with_metadata._get_updated_at() == e_car_1_created_at
        assert rolled_back_car_with_metadata._get_updated_by() == SYSTEM_USER_ID

        # Validate attribute-level metadata after rollback
        assert rolled_back_car_with_metadata.color._get_created_at() == e_car_1_created_at
        assert rolled_back_car_with_metadata.color._get_created_by() == SYSTEM_USER_ID
        assert rolled_back_car_with_metadata.color._get_updated_at() == e_car_1_created_at
        assert rolled_back_car_with_metadata.color._get_updated_by() == SYSTEM_USER_ID

        assert rolled_back_car_with_metadata.name._get_created_at() == e_car_1_created_at
        assert rolled_back_car_with_metadata.name._get_created_by() == SYSTEM_USER_ID
        assert rolled_back_car_with_metadata.name._get_updated_at() == e_car_1_created_at
        assert rolled_back_car_with_metadata.name._get_updated_by() == SYSTEM_USER_ID

        # Validate relationship-level metadata after rollback for e_car_1
        # After rollback, owner relationship should have original timestamps restored
        owner_rel_manager = rolled_back_car_with_metadata.get_relationship(name="owner")
        owner_rel = await owner_rel_manager.get(db=db)
        assert owner_rel._get_created_at() == e_car_1_created_at
        assert owner_rel._get_created_by() == SYSTEM_USER_ID
        assert owner_rel._get_updated_at() == e_car_1_created_at
        assert owner_rel._get_updated_by() == SYSTEM_USER_ID

        # Validate undeleted car (e_car_2) metadata after rollback
        undeleted_car_with_metadata = await NodeManager.get_one(
            db=db,
            branch=default_branch,
            id=e_car_2.id,
            include_metadata=MetadataQueryOptions(
                node_level=MetadataOptions.USER_TIMESTAMPS,
                attribute_level=MetadataOptions.USER_TIMESTAMPS,
                relationship_level=MetadataOptions.USER_TIMESTAMPS,
            ),
            prefetch_relationships=True,
        )
        # Should have original timestamps restored
        assert undeleted_car_with_metadata._get_created_at() == e_car_2_created_at
        assert undeleted_car_with_metadata._get_created_by() == SYSTEM_USER_ID
        assert undeleted_car_with_metadata._get_updated_at() == e_car_2_created_at
        assert undeleted_car_with_metadata._get_updated_by() == SYSTEM_USER_ID

        # Validate attribute metadata on undeleted car
        assert undeleted_car_with_metadata.color._get_created_at() == e_car_2_created_at
        assert undeleted_car_with_metadata.color._get_created_by() == SYSTEM_USER_ID
        assert undeleted_car_with_metadata.color._get_updated_at() == e_car_2_created_at
        assert undeleted_car_with_metadata.color._get_updated_by() == SYSTEM_USER_ID

        # Validate relationship metadata on undeleted car after rollback
        owner_rel_manager = undeleted_car_with_metadata.get_relationship(name="owner")
        owner_rel = await owner_rel_manager.get(db=db)
        assert owner_rel._get_created_at() == e_car_2_created_at
        assert owner_rel._get_created_by() == SYSTEM_USER_ID
        assert owner_rel._get_updated_at() == e_car_2_created_at
        assert owner_rel._get_updated_by() == SYSTEM_USER_ID

    async def test_diff_and_merge_with_migrated_node_kind_peer(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_internal_models_schema: SchemaBranch,
        register_core_models_schema: SchemaBranch,
        car_person_schema: SchemaBranch,
        car_accord_main: Node,
        car_camry_main: Node,
        person_jane_main: Node,
        person_john_main: Node,
    ):
        car_accord_created_at = car_accord_main._get_created_at()
        car_camry_created_at = car_camry_main._get_created_at()
        original_car_owner = person_john_main
        main_schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        await registry.schema.update_schema_branch(
            db=db,
            branch=default_branch,
            schema=main_schema_branch,
            limit=["TestCar", "Test2NewCar", "TestPerson"],
            update_db=True,
        )
        main_schema_branch = registry.schema.get_schema_branch(name=default_branch.name)

        # migrate TestCar to Test2NewCar on default branch
        original_car_schema = main_schema_branch.get(name="TestCar", duplicate=True)
        new_car_schema = main_schema_branch.get(name="TestCar", duplicate=True)
        new_car_schema.name = "NewCar"
        new_car_schema.namespace = "Test2"
        assert new_car_schema.kind == "Test2NewCar"
        main_schema_branch.set(name="Test2NewCar", schema=new_car_schema)
        person_schema_branch = main_schema_branch.get(name="TestPerson", duplicate=True)
        cars_rel = person_schema_branch.get_relationship("cars")
        cars_rel.peer = "Test2NewCar"
        cars_driven_rel = person_schema_branch.get_relationship("cars_driven")
        cars_driven_rel.peer = "Test2NewCar"
        main_schema_branch.set(name="TestPerson", schema=person_schema_branch)
        main_schema_branch.delete(name="TestCar")
        main_schema_branch.process()
        await registry.schema.update_schema_branch(
            db=db,
            branch=default_branch,
            schema=main_schema_branch,
            limit=["TestCar", "Test2NewCar", "TestPerson"],
            update_db=True,
        )
        migration = NodeKindUpdateMigration(
            previous_node_schema=original_car_schema,
            new_node_schema=new_car_schema,
            schema_path=SchemaPath(
                path_type=SchemaPathType.ATTRIBUTE, schema_kind="Test2NewCar", field_name="namespace"
            ),
        )
        migration_at = Timestamp()
        execution_result = await migration.execute(
            migration_input=MigrationInput(db=db, at=migration_at, user_id="migration-user"), branch=default_branch
        )
        assert not execution_result.errors

        # create new branch
        branch2 = await create_branch(db=db, branch_name="branch2")

        # update car owner
        migrated_car = await NodeManager.get_one(db=db, branch=branch2, id=car_accord_main.id)
        await migrated_car.owner.update(db=db, data=person_jane_main.id)
        new_color = "#654321"
        migrated_car.color.value = new_color
        await migrated_car.save(db=db, user_id="branch-user")

        # delete a car
        migrated_car_to_delete = await NodeManager.get_one(db=db, branch=branch2, id=car_camry_main.id)
        await migrated_car_to_delete.delete(db=db, user_id="branch-user-delete")

        merge_at = Timestamp()
        diff_coordinator = await self._get_diff_coordinator(db=db, branch=branch2)
        await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch2)
        diff_merger = await self._get_diff_merger(db=db, branch=branch2)
        await diff_merger.merge_graph(at=merge_at)

        updated_schema_branch = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
        registry.schema.set_schema_branch(name=default_branch.name, schema=updated_schema_branch)
        car_schema_main = updated_schema_branch.get(name="Test2NewCar", duplicate=False)

        retrieved_migrated_car = await NodeManager.get_one(db=db, branch=default_branch, id=car_accord_main.id)
        assert retrieved_migrated_car.get_kind() == "Test2NewCar"
        for attr_name in car_schema_main.attribute_names:
            if attr_name == "color":
                assert retrieved_migrated_car.color.value == new_color
            else:
                assert getattr(retrieved_migrated_car, attr_name).value == getattr(car_accord_main, attr_name).value
        retrieved_owner_rels = await retrieved_migrated_car.owner.get_relationships(db=db)
        assert {r.get_peer_id() for r in retrieved_owner_rels} == {person_jane_main.id}
        retrieved_driver_rels = await retrieved_migrated_car.driver.get_relationships(db=db)
        assert not {r.get_peer_id() for r in retrieved_driver_rels}
        with pytest.raises(SchemaNotFoundError):
            await NodeManager.query(db=db, branch=default_branch, schema="TestCar")
        # try to get deleted node
        with pytest.raises(NodeNotFoundError):
            await NodeManager.get_one(db=db, branch=branch2, id=car_camry_main.id, raise_on_error=True)

        # Validate metadata on merged car - should have updated_at from merge
        merged_car_with_metadata = await NodeManager.get_one(
            db=db,
            branch=default_branch,
            id=car_accord_main.id,
            include_metadata=MetadataQueryOptions(
                node_level=MetadataOptions.USER_TIMESTAMPS,
                attribute_level=MetadataOptions.USER_TIMESTAMPS,
                relationship_level=MetadataOptions.USER_TIMESTAMPS,
            ),
            prefetch_relationships=True,
        )
        assert merged_car_with_metadata._get_created_at() == car_accord_created_at
        assert merged_car_with_metadata._get_created_by() == SYSTEM_USER_ID
        assert merged_car_with_metadata._get_updated_at() == merge_at
        assert merged_car_with_metadata._get_updated_by() == "branch-user"

        # Validate attribute-level metadata on merged car
        assert merged_car_with_metadata.color._get_created_at() == car_accord_created_at
        assert merged_car_with_metadata.color._get_created_by() == SYSTEM_USER_ID
        assert merged_car_with_metadata.color._get_updated_at() == merge_at
        assert merged_car_with_metadata.color._get_updated_by() == "branch-user"

        # Other attributes should retain migration timestamps
        assert merged_car_with_metadata.name._get_created_at() == car_accord_created_at
        assert merged_car_with_metadata.name._get_created_by() == SYSTEM_USER_ID
        assert merged_car_with_metadata.name._get_updated_at() == car_accord_created_at
        assert merged_car_with_metadata.name._get_updated_by() == SYSTEM_USER_ID

        assert merged_car_with_metadata.nbr_seats._get_created_at() == car_accord_created_at
        assert merged_car_with_metadata.nbr_seats._get_created_by() == SYSTEM_USER_ID
        assert merged_car_with_metadata.nbr_seats._get_updated_at() == car_accord_created_at
        assert merged_car_with_metadata.nbr_seats._get_updated_by() == SYSTEM_USER_ID

        # Validate relationship-level metadata on merged car
        # Owner relationship was updated by branch-user
        owner_rel = await merged_car_with_metadata.owner.get(db=db)
        assert owner_rel._get_created_at() == merge_at
        assert owner_rel._get_created_by() == "branch-user"
        assert owner_rel._get_updated_at() == merge_at
        assert owner_rel._get_updated_by() == "branch-user"

        # Validate metadata on deleted car using NodeMetadataDefaultBranchQuery
        node_metadata_query = await NodeMetadataDefaultBranchQuery.init(
            db=db,
            branch=default_branch,
            node_uuids=[car_camry_main.id],
        )
        await node_metadata_query.execute(db=db)
        node_metadatas = node_metadata_query.get_metadatas()
        assert len(node_metadatas) == 1

        deleted_car_meta = node_metadatas[0]
        assert deleted_car_meta.uuid == car_camry_main.id
        assert deleted_car_meta.is_deleted is True
        # Deleted car should have branch user delete timestamp
        assert deleted_car_meta.created_at == car_camry_created_at
        assert deleted_car_meta.created_by == SYSTEM_USER_ID
        assert deleted_car_meta.updated_at == merge_at
        assert deleted_car_meta.updated_by == "branch-user-delete"

        # Validate deleted car's attributes metadata
        for attr in deleted_car_meta.attributes:
            assert attr.is_deleted is True
            assert attr.created_at == car_camry_created_at
            assert attr.created_by == SYSTEM_USER_ID
            assert attr.updated_at == merge_at
            assert attr.updated_by == "branch-user-delete"

        # Validate deleted car's relationships metadata
        for rel in deleted_car_meta.relationships:
            assert rel.is_deleted is True
            assert rel.created_at == car_camry_created_at
            assert rel.created_by == SYSTEM_USER_ID
            assert rel.updated_at == merge_at
            assert rel.updated_by == "branch-user-delete"

        await verify_no_duplicate_paths(db=db)

        await diff_merger.rollback(at=merge_at)

        retrieved_still_migrated_car = await NodeManager.get_one(db=db, branch=default_branch, id=car_accord_main.id)
        assert retrieved_still_migrated_car.get_kind() == "Test2NewCar"
        assert retrieved_still_migrated_car.color.value == car_accord_main.color.value
        retrieved_owner_rels = await retrieved_still_migrated_car.owner.get_relationships(db=db)
        assert {r.get_peer_id() for r in retrieved_owner_rels} == {original_car_owner.id}
        # get undeleted node
        undeleted_car = await NodeManager.get_one(db=db, branch=default_branch, id=car_camry_main.id)
        assert undeleted_car.get_kind() == "Test2NewCar"

        # Validate node-level metadata after rollback for car_accord
        # Rollback only reverts data changes, not the schema migration
        rolled_back_car_with_metadata = await NodeManager.get_one(
            db=db,
            branch=default_branch,
            id=car_accord_main.id,
            include_metadata=MetadataQueryOptions(
                node_level=MetadataOptions.USER_TIMESTAMPS,
                attribute_level=MetadataOptions.USER_TIMESTAMPS,
                relationship_level=MetadataOptions.USER_TIMESTAMPS,
            ),
            prefetch_relationships=True,
        )
        # After rollback, should have post-migration timestamps (migration wasn't rolled back)
        assert rolled_back_car_with_metadata._get_created_at() == car_accord_created_at
        assert rolled_back_car_with_metadata._get_created_by() == SYSTEM_USER_ID
        assert rolled_back_car_with_metadata._get_updated_at() == migration_at
        assert rolled_back_car_with_metadata._get_updated_by() == "migration-user"

        # Validate attribute-level metadata after rollback
        assert rolled_back_car_with_metadata.color._get_created_at() == car_accord_created_at
        assert rolled_back_car_with_metadata.color._get_created_by() == SYSTEM_USER_ID
        assert rolled_back_car_with_metadata.color._get_updated_at() == car_accord_created_at
        assert rolled_back_car_with_metadata.color._get_updated_by() == SYSTEM_USER_ID

        assert rolled_back_car_with_metadata.name._get_created_at() == car_accord_created_at
        assert rolled_back_car_with_metadata.name._get_created_by() == SYSTEM_USER_ID
        assert rolled_back_car_with_metadata.name._get_updated_at() == car_accord_created_at
        assert rolled_back_car_with_metadata.name._get_updated_by() == SYSTEM_USER_ID

        # Validate relationship-level metadata after rollback for car_accord
        # After rollback, owner relationship should have post-migration timestamps restored
        owner_rel_manager = rolled_back_car_with_metadata.get_relationship(name="owner")
        owner_rel = await owner_rel_manager.get(db=db)
        assert owner_rel._get_created_at() == car_accord_created_at
        assert owner_rel._get_created_by() == SYSTEM_USER_ID
        assert owner_rel._get_updated_at() == car_accord_created_at
        assert owner_rel._get_updated_by() == SYSTEM_USER_ID

        # Validate undeleted car (car_camry) metadata after rollback
        undeleted_car_with_metadata = await NodeManager.get_one(
            db=db,
            branch=default_branch,
            id=car_camry_main.id,
            include_metadata=MetadataQueryOptions(
                node_level=MetadataOptions.USER_TIMESTAMPS,
                attribute_level=MetadataOptions.USER_TIMESTAMPS,
                relationship_level=MetadataOptions.USER_TIMESTAMPS,
            ),
            prefetch_relationships=True,
        )
        # Should have post-migration timestamps restored
        assert undeleted_car_with_metadata._get_created_at() == car_camry_created_at
        assert undeleted_car_with_metadata._get_created_by() == SYSTEM_USER_ID
        assert undeleted_car_with_metadata._get_updated_at() == migration_at
        assert undeleted_car_with_metadata._get_updated_by() == "migration-user"

        # Validate attribute metadata on undeleted car
        assert undeleted_car_with_metadata.color._get_created_at() == car_camry_created_at
        assert undeleted_car_with_metadata.color._get_created_by() == SYSTEM_USER_ID
        assert undeleted_car_with_metadata.color._get_updated_at() == car_camry_created_at
        assert undeleted_car_with_metadata.color._get_updated_by() == SYSTEM_USER_ID

        # Validate relationship metadata on undeleted car after rollback
        owner_rel_manager = undeleted_car_with_metadata.get_relationship(name="owner")
        owner_rel = await owner_rel_manager.get(db=db)
        assert owner_rel._get_created_at() == car_camry_created_at
        assert owner_rel._get_created_by() == SYSTEM_USER_ID
        assert owner_rel._get_updated_at() == car_camry_created_at
        assert owner_rel._get_updated_by() == SYSTEM_USER_ID
