from typing import Literal
from unittest.mock import AsyncMock

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import DiffAction, MetadataOptions, RelationshipHierarchyDirection, SchemaPathType
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.data_check_synchronizer import DiffDataCheckSynchronizer
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.diff.model.path import ConflictSelection
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.schema.node_kind_update import NodeKindUpdateMigration
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
        await new_node.save(db=db)
        branch2 = await create_branch(db=db, branch_name="branch2")
        branch_node = await NodeManager.get_one(db=db, branch=branch2, id=new_node.id)
        branch_node.mylist.value = ["c", "d", 3, 4]
        await branch_node.save(db=db)
        diff_coordinator = await self._get_diff_coordinator(db=db, branch=branch2)
        await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch2)
        diff_merger = await self._get_diff_merger(db=db, branch=branch2)
        await diff_merger.merge_graph(at=Timestamp())

        updated_node = await NodeManager.get_one(db=db, branch=default_branch, id=new_node.id)
        assert updated_node.mylist.value == ["c", "d", 3, 4]
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
        await john_main.save(db=db)
        john_branch = await NodeManager.get_one(db=db, branch=branch2, id=person_john_main.id)
        john_branch.name.value = "John-branch"
        await john_branch.save(db=db)

        at = Timestamp()
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
        await diff_merger.merge_graph(at=at)

        updated_john = await NodeManager.get_one(db=db, id=person_john_main.id)
        assert updated_john.name.value == expected_value["name"]
        assert await updated_john.get_hfid(db=db) == expected_value["hfid"]

        await diff_merger.rollback(at=at)

        rolled_back_john = await NodeManager.get_one(db=db, id=person_john_main.id)
        assert rolled_back_john.name.value == "John-main"
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
        await car_main.save(db=db)
        car_branch = await NodeManager.get_one(db=db, branch=branch2, id=car_accord_main.id)
        await car_branch.owner.update(db=db, data=person_jane_main)
        await car_branch.save(db=db)

        at = Timestamp()
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
        await diff_merger.merge_graph(at=at)

        updated_car = await NodeManager.get_one(db=db, id=car_accord_main.id)
        owner_rel = await updated_car.owner.get(db=db)
        if conflict_selection is ConflictSelection.BASE_BRANCH:
            assert owner_rel.peer_id == person_alfred_main.id
        if conflict_selection is ConflictSelection.DIFF_BRANCH:
            assert owner_rel.peer_id == person_jane_main.id

        await diff_merger.rollback(at=at)

        rolled_back_car = await NodeManager.get_one(db=db, id=car_accord_main.id)
        owner_rel = await rolled_back_car.owner.get(db=db)
        assert owner_rel.peer_id == person_alfred_main.id
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
        await john_main.save(db=db)
        john_branch = await NodeManager.get_one(db=db, branch=branch2, id=person_john_main.id)
        john_branch.name.source = person_jane_main
        await john_branch.save(db=db)

        at = Timestamp()
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
        await diff_merger.merge_graph(at=at)

        updated_john = await NodeManager.get_one(db=db, id=person_john_main.id, include_metadata=MetadataOptions.SOURCE)

        attr_source = await updated_john.name.get_source(db=db)
        if conflict_selection is ConflictSelection.BASE_BRANCH:
            assert attr_source.id == person_alfred_main.id
        if conflict_selection is ConflictSelection.DIFF_BRANCH:
            assert attr_source.id == person_jane_main.id

        await diff_merger.rollback(at=at)

        rolled_back_john = await NodeManager.get_one(
            db=db, id=person_john_main.id, include_metadata=MetadataOptions.SOURCE
        )
        attr_source = await rolled_back_john.name.get_source(db=db)
        assert attr_source.id == person_alfred_main.id
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
        await car_main.save(db=db)
        car_branch = await NodeManager.get_one(db=db, branch=branch2, id=car_accord_main.id)
        await car_branch.owner.update(db=db, data={"id": person_john_main.id, "_relation__owner": person_jane_main.id})
        await car_branch.save(db=db)

        at = Timestamp()
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
        await diff_merger.merge_graph(at=at)

        updated_car = await NodeManager.get_one(db=db, id=car_accord_main.id, include_metadata=MetadataOptions.OWNER)
        owner_rel = await updated_car.owner.get(db=db)
        owner_prop = await owner_rel.get_owner(db=db)
        if conflict_selection is ConflictSelection.BASE_BRANCH:
            assert owner_prop.id == person_alfred_main.id
        if conflict_selection is ConflictSelection.DIFF_BRANCH:
            assert owner_prop.id == person_jane_main.id

        john_car_count = await NodeManager.count_peers(
            db=db,
            ids=[person_john_main.id],
            source_kind="TestPerson",
            filters={},
            schema=cars_rel_schema,
            branch=branch2,
        )
        assert john_car_count == 1

        await diff_merger.rollback(at=at)

        rolled_back_car = await NodeManager.get_one(
            db=db, id=car_accord_main.id, include_metadata=MetadataOptions.OWNER
        )
        owner_rel = await rolled_back_car.owner.get(db=db)
        owner_prop = await owner_rel.get_owner(db=db)
        assert owner_prop.id == person_alfred_main.id
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
        branch2 = await create_branch(db=db, branch_name="branch2")
        person_branch = await NodeManager.get_one(db=db, branch=branch2, id=person_jane_main.id)
        person_branch.height.value = new_height
        await person_branch.save(db=db)

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
        await diff_merger.merge_graph(at=Timestamp())

        updated_person = await NodeManager.get_one(db=db, id=person_jane_main.id)
        assert updated_person.height.value == new_height
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
        branch2 = await create_branch(db=db, branch_name="branch2")
        branch_car = await Node.init(db=db, schema="TestCar", branch=branch2)
        await branch_car.new(db=db, name="new camry", nbr_seats=5, is_electric=False, owner=person_jane_main.id)
        await branch_car.save(db=db)

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
        await diff_merger.merge_graph(at=Timestamp())

        updated_car = await NodeManager.get_one(db=db, id=branch_car.id)
        assert updated_car.name.value == "new camry"
        assert updated_car.nbr_seats.value == 5
        assert updated_car.is_electric.value is False
        owner_rel = await updated_car.owner.get(db=db)
        assert owner_rel.peer_id == person_jane_main.id
        await verify_no_duplicate_paths(db=db)

    async def test_relationship_set_to_null(
        self, db: InfrahubDatabase, default_branch: Branch, diff_repository: DiffRepository, animal_person_schema
    ) -> None:
        person_main = await Node.init(db=db, schema="TestPerson")
        await person_main.new(db=db, name="Dude")
        await person_main.save(db=db)
        friend_main = await Node.init(db=db, schema="TestPerson")
        await friend_main.new(db=db, name="Friend")
        await friend_main.save(db=db)
        dog_main = await Node.init(db=db, schema="TestDog")
        await dog_main.new(db=db, name="good dog", breed="mixed", owner=person_main, best_friend=friend_main)
        await dog_main.save(db=db)

        branch2 = await create_branch(db=db, branch_name="branch2")
        dog_branch = await NodeManager.get_one(db=db, branch=branch2, id=dog_main.id)
        await dog_branch.best_friend.update(db=db, data=None)
        await dog_branch.save(db=db)

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
        await diff_merger.merge_graph(at=Timestamp())

        updated_dog = await NodeManager.get_one(db=db, id=dog_main.id)
        best_friend_rels = await updated_dog.best_friend.get_relationships(db=db)
        assert len(best_friend_rels) == 0
        updated_friend = await NodeManager.get_one(db=db, id=friend_main.id)
        best_friend_rels = await updated_friend.best_friends.get_relationships(db=db)
        assert len(best_friend_rels) == 0
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
        await person.save(db=db)
        car = await Node.init(db=db, schema="TestCar", branch=branch2)
        await car.new(db=db, name="camry", owner=person.id)
        await car.save(db=db)

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
        await diff_merger.merge_graph(at=Timestamp())

        # validate person update on main
        updated_person = await NodeManager.get_one(db=db, id=person.id)
        assert updated_person.height.value == 180
        assert updated_person.name.value == "Guy"
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
        )
        assert len(owner_rels) == 1
        assert owner_rels[0].peer_id == person.id
        await verify_no_duplicate_paths(db=db)

    async def test_agnostic_and_aware_nodes_added_on_branch(
        self, db: InfrahubDatabase, default_branch: Branch, diff_repository: DiffRepository, car_person_schema_global
    ) -> None:
        branch2 = await create_branch(db=db, branch_name="branch2")
        person = await Node.init(db=db, schema="TestPerson", branch=branch2)
        await person.new(db=db, name="Guy", height=180)
        await person.save(db=db)
        car = await Node.init(db=db, schema="TestCar", branch=branch2)
        await car.new(db=db, name="camry", nbr_seats=3, is_electric=False, owner=person.id)
        await car.save(db=db)

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
        await diff_merger.merge_graph(at=Timestamp())

        # validate person (agnostic) exists on main
        updated_person = await NodeManager.get_one(db=db, id=person.id)
        assert updated_person.height.value == 180
        assert updated_person.name.value == "Guy"
        cars_rels = await updated_person.cars.get(db=db)
        assert len(cars_rels) == 1
        assert cars_rels[0].peer_id == car.id
        # validate car merged to main
        updated_car = await NodeManager.get_one(db=db, id=car.id)
        assert updated_car.name.value == "camry"
        assert updated_car.nbr_seats.value == 3
        assert updated_car.is_electric.value is False
        owner_rel = await updated_car.owner.get(db=db)
        assert owner_rel.peer_id == person.id

        person_schema = registry.schema.get(name="TestPerson", duplicate=False)
        cars_rel_schema = person_schema.get_relationship(name="cars")
        cars_rels = await NodeManager.query_peers(
            db=db, ids=[person.id], source_kind="TestPerson", schema=cars_rel_schema, filters={}, fetch_peers=True
        )
        assert len(cars_rels) == 1
        assert cars_rels[0].peer_id == car.id
        car_schema = registry.schema.get(name="TestCar", duplicate=False)
        owner_rel_schema = car_schema.get_relationship(name="owner")
        owner_rels = await NodeManager.query_peers(
            db=db, ids=[car.id], source_kind="TestCar", schema=owner_rel_schema, filters={}, fetch_peers=True
        )
        assert len(owner_rels) == 1
        assert owner_rels[0].peer_id == person.id
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
        )
        assert len(owner_rels) == 1
        assert owner_rels[0].peer_id == person.id
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
        person_schema = db.schema.get(name="TestPerson", duplicate=False)
        cars_rel_schema = person_schema.get_relationship(name="cars")
        branch2 = await create_branch(db=db, branch_name="branch2")
        car_branch = await NodeManager.get_one(db=db, branch=branch2, id=car_accord_main.id)
        await car_branch.owner.update(db=db, data={"id": person_john_main.id, "_relation__is_protected": True})
        await car_branch.save(db=db)

        diff_coordinator = await self._get_diff_coordinator(db=db, branch=branch2)
        await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch2)

        car_branch = await NodeManager.get_one(db=db, branch=branch2, id=car_accord_main.id)
        await car_branch.owner.update(db=db, data={"id": person_john_main.id, "_relation__is_visible": False})
        await car_branch.save(db=db)

        await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch2)

        at = Timestamp()
        diff_merger = await self._get_diff_merger(db=db, branch=branch2)
        await diff_merger.merge_graph(at=at)

        # validate that the properties were correctly updated
        updated_car = await NodeManager.get_one(db=db, id=car_accord_main.id)
        owner_rel = await updated_car.owner.get(db=db)
        assert owner_rel.peer_id == person_john_main.id
        assert owner_rel.is_protected is True
        assert owner_rel.is_visible is False

        john_car_count = await NodeManager.count_peers(
            db=db,
            ids=[person_john_main.id],
            source_kind="TestPerson",
            filters={},
            schema=cars_rel_schema,
            branch=branch2,
        )
        assert john_car_count == 1

        await diff_merger.rollback(at=at)

        # validate that the properties were correctly rolled back
        updated_car = await NodeManager.get_one(db=db, id=car_accord_main.id)
        owner_rel = await updated_car.owner.get(db=db)
        assert owner_rel.peer_id == person_john_main.id
        assert owner_rel.is_protected is False
        assert owner_rel.is_visible is True
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
        branch2 = await create_branch(db=db, branch_name="branch2")
        car_main = await NodeManager.get_one(db=db, id=car_accord_main.id)
        await car_main.owner.update(db=db, data={"id": person_alfred_main.id, "_relation__is_protected": True})
        await car_main.save(db=db)
        car_branch = await NodeManager.get_one(db=db, branch=branch2, id=car_accord_main.id)
        await car_branch.delete(db=db)

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
        await car_main.save(db=db)

        # check that the conflict is removed
        enriched_diff_metadata = await diff_coordinator.update_branch_diff(
            base_branch=default_branch, diff_branch=branch2
        )
        enriched_diff = await diff_repository.get_one(
            diff_branch_name=enriched_diff_metadata.diff_branch_name, diff_id=enriched_diff_metadata.uuid
        )
        conflicts_map = enriched_diff.get_all_conflicts()
        assert len(conflicts_map) == 0

        at = Timestamp()
        diff_merger = await self._get_diff_merger(db=db, branch=branch2)
        await diff_merger.merge_graph(at=at)

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

        await diff_merger.rollback(at=at)

        rolled_back_car = await NodeManager.get_one(
            db=db, id=car_accord_main.id, include_metadata=MetadataOptions.OWNER
        )
        owner_rel = await rolled_back_car.owner.get(db=db)
        assert owner_rel.peer_id == person_john_main.id
        assert owner_rel.is_protected is False
        assert owner_rel.is_visible is True
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
        branch2 = await create_branch(db=db, branch_name="branch2")
        car_branch = await NodeManager.get_one(db=db, branch=branch2, id=car_accord_main.id)
        await car_branch.owner.update(db=db, data={"id": person_alfred_main.id, "_relation__is_protected": True})
        await car_branch.save(db=db)
        car_main = await NodeManager.get_one(db=db, id=car_accord_main.id)
        await car_main.delete(db=db)

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
        await car_branch.save(db=db)

        # check that the conflict is removed
        enriched_diff = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch2)
        conflicts_map = enriched_diff.get_all_conflicts()
        assert len(conflicts_map) == 0

        at = Timestamp()
        diff_merger = await self._get_diff_merger(db=db, branch=branch2)
        await diff_merger.merge_graph(at=at)

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

        await diff_merger.rollback(at=at)

        # validate that car remains deleted after rollback
        rolled_back_car = await NodeManager.get_one(db=db, id=car_accord_main.id)
        assert rolled_back_car is None
        await verify_no_duplicate_paths(db=db)

    async def test_delete_with_many_relationship_added(
        self, db: InfrahubDatabase, default_branch: Branch, car_person_schema_unregistered: SchemaRoot
    ) -> None:
        # remove TestCar relationship to TestPerson
        car_schema = car_person_schema_unregistered.get(name="TestCar")
        car_schema.relationships = []
        registry.schema.register_schema(schema=car_person_schema_unregistered, branch=default_branch.name)
        # initial data
        person_1 = await Node.init(db=db, schema="TestPerson", branch=default_branch)
        await person_1.new(db=db, name="Alice", height=160)
        await person_1.save(db=db)
        person_2 = await Node.init(db=db, schema="TestPerson", branch=default_branch)
        await person_2.new(db=db, name="Bob", height=161)
        await person_2.save(db=db)
        car_1 = await Node.init(db=db, schema="TestCar", branch=default_branch)
        await car_1.new(db=db, name="smart", nbr_seats=2, is_electric=True)
        await car_1.save(db=db)
        car_2 = await Node.init(db=db, schema="TestCar", branch=default_branch)
        await car_2.new(db=db, name="big", nbr_seats=12, is_electric=False)
        await car_2.save(db=db)
        # make the branch
        branch2 = await create_branch(db=db, branch_name="branch2")

        # add relationship on main
        person_1_main = await NodeManager.get_one(db=db, id=person_1.id)
        await person_1_main.cars.update(db=db, data=[car_1, car_2])
        await person_1_main.save(db=db)
        # delete node on branch
        person_1_branch = await NodeManager.get_one(db=db, branch=branch2, id=person_1.id)
        await person_1_branch.delete(db=db)

        # check that there are no conflicts
        diff_coordinator = await self._get_diff_coordinator(db=db, branch=branch2)
        enriched_diff = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch2)
        conflicts_map = enriched_diff.get_all_conflicts()
        assert len(conflicts_map) == 0

        # merge the branch
        at = Timestamp()
        diff_merger = await self._get_diff_merger(db=db, branch=branch2)
        await diff_merger.merge_graph(at=at)

        # validate that person_1 is deleted
        deleted_person = await NodeManager.get_one(db=db, id=person_1.id)
        assert deleted_person is None
        # validate that all attributes and relationships connected to person_1,
        # including the relationship connecting car_1 and person_1 is deleted,
        # requires a special query b/c TestCar has no relationship to TestPerson in the schema
        await verify_all_linked_edges_deleted(db=db, node_uuid=person_1.id, branch_name=default_branch.name)
        await verify_no_duplicate_paths(db=db)

    @pytest.mark.parametrize("selection", [ConflictSelection.BASE_BRANCH, ConflictSelection.DIFF_BRANCH])
    async def test_attribute_update_with_conflict(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        diff_repository: DiffRepository,
        person_john_main: Node,
        selection: ConflictSelection,
    ) -> None:
        main_value = 200
        branch_value = 150
        branch2 = await create_branch(db=db, branch_name="branch2")
        person_main = await NodeManager.get_one(db=db, branch=default_branch, id=person_john_main.id)
        person_main.height.value = main_value
        await person_main.save(db=db)
        person_branch = await NodeManager.get_one(db=db, branch=branch2, id=person_john_main.id)
        person_branch.height.value = branch_value
        await person_branch.save(db=db)

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
        at = Timestamp()
        diff_merger = await self._get_diff_merger(db=db, branch=branch2)
        await diff_merger.merge_graph(at=at)

        # validate that person has correct age
        updated_person = await NodeManager.get_one(db=db, branch=default_branch, id=person_john_main.id)
        if selection is ConflictSelection.DIFF_BRANCH:
            assert updated_person.height.value == branch_value
        else:
            assert updated_person.height.value == main_value
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
        person_jane_main: Node,
        person_john_main: Node,
    ) -> None:
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
        execution_result = await migration.execute(db=db, branch=branch2)
        assert not execution_result.errors

        # update car owner
        migrated_car = await NodeManager.get_one(db=db, branch=branch2, id=car_accord_main.id)
        await migrated_car.owner.update(db=db, data=person_jane_main.id)
        new_color = "#654321"
        migrated_car.color.value = new_color
        await migrated_car.save(db=db)

        # delete a car
        migrated_car_to_delete = await NodeManager.get_one(db=db, branch=branch2, id=car_camry_main.id)
        await migrated_car_to_delete.delete(db=db)

        at = Timestamp()
        diff_coordinator = await self._get_diff_coordinator(db=db, branch=branch2)
        await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch2)
        diff_merger = await self._get_diff_merger(db=db, branch=branch2)
        await diff_merger.merge_graph(at=at)

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
        await verify_no_duplicate_paths(db=db)

        await diff_merger.rollback(at=at)

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
        e_car_2 = await create_and_save(
            db=db,
            branch=default_branch,
            schema="TestElectricCar",
            name="Eee2",
            nbr_seats=5,
            nbr_engine=2,
            owner=person_3,
        )
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
        execution_result = await migration.execute(db=db, branch=branch2)
        assert not execution_result.errors

        # update car owner
        migrated_car = await NodeManager.get_one(db=db, branch=branch2, id=e_car_1.id)
        await migrated_car.owner.update(db=db, data=person_1.id)
        new_color = "#654321"
        migrated_car.color.value = new_color
        await migrated_car.save(db=db)

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
        execution_result = await migration.execute(db=db, branch=branch2)
        assert not execution_result.errors

        # delete a car
        migrated_car_to_delete = await NodeManager.get_one(db=db, branch=branch2, id=e_car_2.id)
        await migrated_car_to_delete.delete(db=db)

        at = Timestamp()
        diff_coordinator = await self._get_diff_coordinator(db=db, branch=branch2)
        await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch2)
        diff_merger = await self._get_diff_merger(db=db, branch=branch2)
        await diff_merger.merge_graph(at=at)

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
        await verify_no_duplicate_paths(db=db)

        await diff_merger.rollback(at=at)

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
        execution_result = await migration.execute(db=db, branch=default_branch)
        assert not execution_result.errors

        # create new branch
        branch2 = await create_branch(db=db, branch_name="branch2")

        # update car owner
        migrated_car = await NodeManager.get_one(db=db, branch=branch2, id=car_accord_main.id)
        await migrated_car.owner.update(db=db, data=person_jane_main.id)
        new_color = "#654321"
        migrated_car.color.value = new_color
        await migrated_car.save(db=db)

        # delete a car
        migrated_car_to_delete = await NodeManager.get_one(db=db, branch=branch2, id=car_camry_main.id)
        await migrated_car_to_delete.delete(db=db)

        at = Timestamp()
        diff_coordinator = await self._get_diff_coordinator(db=db, branch=branch2)
        await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch2)
        diff_merger = await self._get_diff_merger(db=db, branch=branch2)
        await diff_merger.merge_graph(at=at)

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
        await verify_no_duplicate_paths(db=db)

        await diff_merger.rollback(at=at)

        retrieved_still_migrated_car = await NodeManager.get_one(db=db, branch=default_branch, id=car_accord_main.id)
        assert retrieved_still_migrated_car.get_kind() == "Test2NewCar"
        assert retrieved_still_migrated_car.color.value == car_accord_main.color.value
        retrieved_owner_rels = await retrieved_still_migrated_car.owner.get_relationships(db=db)
        assert {r.get_peer_id() for r in retrieved_owner_rels} == {original_car_owner.id}
        # get undeleted node
        undeleted_car = await NodeManager.get_one(db=db, branch=default_branch, id=car_camry_main.id)
        assert undeleted_car.get_kind() == "Test2NewCar"
