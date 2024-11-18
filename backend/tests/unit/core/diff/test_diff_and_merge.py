from unittest.mock import AsyncMock

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.data_check_synchronizer import DiffDataCheckSynchronizer
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.diff.model.path import ConflictSelection
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.dependencies.registry import get_component_registry


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
    ):
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

    async def test_diff_and_merge_schema_with_default_values(
        self, db: InfrahubDatabase, default_branch: Branch, register_core_models_schema, car_person_schema: SchemaBranch
    ):
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

    @pytest.mark.parametrize(
        "conflict_selection,expected_value",
        [(ConflictSelection.BASE_BRANCH, "John-main"), (ConflictSelection.DIFF_BRANCH, "John-branch")],
    )
    async def test_diff_and_merge_with_attribute_value_conflict(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        diff_repository: DiffRepository,
        person_john_main,
        person_jane_main,
        person_alfred_main,
        car_accord_main,
        conflict_selection,
        expected_value,
    ):
        branch2 = await create_branch(db=db, branch_name="branch2")
        john_main = await NodeManager.get_one(db=db, id=person_john_main.id)
        john_main.name.value = "John-main"
        await john_main.save(db=db)
        john_branch = await NodeManager.get_one(db=db, branch=branch2, id=person_john_main.id)
        john_branch.name.value = "John-branch"
        await john_branch.save(db=db)

        at = Timestamp()
        diff_coordinator = await self._get_diff_coordinator(db=db, branch=branch2)
        enriched_diff = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch2)
        conflicts_map = enriched_diff.get_all_conflicts()
        assert len(conflicts_map) == 1
        conflict = next(iter(conflicts_map.values()))
        await diff_repository.update_conflict_by_id(conflict_id=conflict.uuid, selection=conflict_selection)
        diff_merger = await self._get_diff_merger(db=db, branch=branch2)
        await diff_merger.merge_graph(at=at)

        updated_john = await NodeManager.get_one(db=db, id=person_john_main.id)
        assert updated_john.name.value == expected_value

        await diff_merger.rollback(at=at)

        rolled_back_john = await NodeManager.get_one(db=db, id=person_john_main.id)
        assert rolled_back_john.name.value == "John-main"

    @pytest.mark.parametrize(
        "conflict_selection",
        [ConflictSelection.BASE_BRANCH, ConflictSelection.DIFF_BRANCH],
    )
    async def test_diff_and_merge_with_relationship_conflict(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        diff_repository: DiffRepository,
        person_john_main,
        person_jane_main,
        person_alfred_main,
        car_accord_main,
        car_camry_main,
        conflict_selection,
    ):
        branch2 = await create_branch(db=db, branch_name="branch2")
        car_main = await NodeManager.get_one(db=db, id=car_accord_main.id)
        await car_main.owner.update(db=db, data=person_alfred_main)
        await car_main.save(db=db)
        car_branch = await NodeManager.get_one(db=db, branch=branch2, id=car_accord_main.id)
        await car_branch.owner.update(db=db, data=person_jane_main)
        await car_branch.save(db=db)

        at = Timestamp()
        diff_coordinator = await self._get_diff_coordinator(db=db, branch=branch2)
        enriched_diff = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch2)
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

    @pytest.mark.parametrize(
        "conflict_selection",
        [ConflictSelection.BASE_BRANCH, ConflictSelection.DIFF_BRANCH],
    )
    async def test_diff_and_merge_with_attribute_property_conflict(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        diff_repository: DiffRepository,
        person_john_main,
        person_jane_main,
        person_alfred_main,
        car_accord_main,
        conflict_selection,
    ):
        branch2 = await create_branch(db=db, branch_name="branch2")
        john_main = await NodeManager.get_one(db=db, id=person_john_main.id)
        john_main.name.source = person_alfred_main
        await john_main.save(db=db)
        john_branch = await NodeManager.get_one(db=db, branch=branch2, id=person_john_main.id)
        john_branch.name.source = person_jane_main
        await john_branch.save(db=db)

        at = Timestamp()
        diff_coordinator = await self._get_diff_coordinator(db=db, branch=branch2)
        enriched_diff = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch2)
        conflicts_map = enriched_diff.get_all_conflicts()
        assert len(conflicts_map) == 1
        conflict = next(iter(conflicts_map.values()))
        await diff_repository.update_conflict_by_id(conflict_id=conflict.uuid, selection=conflict_selection)
        diff_merger = await self._get_diff_merger(db=db, branch=branch2)
        await diff_merger.merge_graph(at=at)

        updated_john = await NodeManager.get_one(db=db, id=person_john_main.id, include_source=True)

        attr_source = await updated_john.name.get_source(db=db)
        if conflict_selection is ConflictSelection.BASE_BRANCH:
            assert attr_source.id == person_alfred_main.id
        if conflict_selection is ConflictSelection.DIFF_BRANCH:
            assert attr_source.id == person_jane_main.id

        await diff_merger.rollback(at=at)

        rolled_back_john = await NodeManager.get_one(db=db, id=person_john_main.id, include_source=True)
        attr_source = await rolled_back_john.name.get_source(db=db)
        assert attr_source.id == person_alfred_main.id

    @pytest.mark.parametrize(
        "conflict_selection",
        [ConflictSelection.BASE_BRANCH, ConflictSelection.DIFF_BRANCH],
    )
    async def test_diff_and_merge_with_relationship_property_conflict(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        diff_repository: DiffRepository,
        person_john_main,
        person_jane_main,
        person_alfred_main,
        car_accord_main,
        car_camry_main,
        conflict_selection,
    ):
        branch2 = await create_branch(db=db, branch_name="branch2")
        car_main = await NodeManager.get_one(db=db, id=car_accord_main.id)
        await car_main.owner.update(db=db, data={"id": person_john_main.id, "_relation__owner": person_alfred_main.id})
        await car_main.save(db=db)
        car_branch = await NodeManager.get_one(db=db, branch=branch2, id=car_accord_main.id)
        await car_branch.owner.update(db=db, data={"id": person_john_main.id, "_relation__owner": person_jane_main.id})
        await car_branch.save(db=db)

        at = Timestamp()
        diff_coordinator = await self._get_diff_coordinator(db=db, branch=branch2)
        enriched_diff = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch2)
        conflicts_map = enriched_diff.get_all_conflicts()
        # conflict on both sides of the relationship
        assert len(conflicts_map) == 2
        for conflict in conflicts_map.values():
            await diff_repository.update_conflict_by_id(conflict_id=conflict.uuid, selection=conflict_selection)
        diff_merger = await self._get_diff_merger(db=db, branch=branch2)
        await diff_merger.merge_graph(at=at)

        updated_car = await NodeManager.get_one(db=db, id=car_accord_main.id, include_owner=True)
        owner_rel = await updated_car.owner.get(db=db)
        owner_prop = await owner_rel.get_owner(db=db)
        if conflict_selection is ConflictSelection.BASE_BRANCH:
            assert owner_prop.id == person_alfred_main.id
        if conflict_selection is ConflictSelection.DIFF_BRANCH:
            assert owner_prop.id == person_jane_main.id

        await diff_merger.rollback(at=at)

        rolled_back_car = await NodeManager.get_one(db=db, id=car_accord_main.id, include_owner=True)
        owner_rel = await rolled_back_car.owner.get(db=db)
        owner_prop = await owner_rel.get_owner(db=db)
        assert owner_prop.id == person_alfred_main.id
