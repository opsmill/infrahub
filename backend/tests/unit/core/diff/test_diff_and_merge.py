from unittest.mock import AsyncMock

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.data_check_synchronizer import DiffDataCheckSynchronizer
from infrahub.core.diff.merger.merger import DiffMerger
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
    # @pytest.fixture
    # def diff_merger(
    #     self,
    #     db: InfrahubDatabase,
    #     default_branch: Branch,
    #     source_branch: Branch,
    #     car_person_schema: SchemaBranch,
    # ) -> DiffMerger:
    #     db.add_schema(car_person_schema)
    #     db.add_schema(car_person_schema, name=source_branch.name)
    #     return DiffMerger(
    #         db=db,
    #         source_branch=source_branch,
    #         destination_branch=default_branch,
    #         diff_repository=mock_diff_repository,
    #         serializer=DiffMergeSerializer(db=db, max_batch_size=50),
    #     )

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

        diff_coordinator = await self._get_diff_coordinator(db=db, branch=branch2)
        await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch2)
        diff_merger = await self._get_diff_merger(db=db, branch=branch2)
        await diff_merger.merge_graph(at=Timestamp())

        updated_schema = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
        car_schema_main = updated_schema.get(name="TestCar", duplicate=False)
        new_int_attr = car_schema_main.get_attribute(name="num_cupholders")
        assert new_int_attr.default_value == 15
        new_bool_attr = car_schema_main.get_attribute(name="is_cool")
        assert new_bool_attr.default_value is False
        new_str_attr = car_schema_main.get_attribute(name="nickname")
        assert new_str_attr.default_value == "car"
