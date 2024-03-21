from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import PathType, SchemaPathType
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.path import DataPath, SchemaPath
from infrahub.core.validators.model import SchemaConstraintValidatorRequest
from infrahub.core.validators.uniqueness.checker import UniquenessChecker
from infrahub.database import InfrahubDatabase


class TestUniquenessChecker:
    async def __call_system_under_test(self, db, branch, schema):
        checker = UniquenessChecker(db, branch)
        schema_path = SchemaPath(path_type=SchemaPathType.NODE, schema_kind=schema.kind)
        request = SchemaConstraintValidatorRequest(
            branch=branch,
            constraint_name="node.uniqueness_constraints.update",
            node_schema=schema,
            schema_path=schema_path,
        )
        return await checker.check(request)

    async def test_no_violations(
        self,
        db: InfrahubDatabase,
        car_accord_main,
        car_camry_main,
        car_volt_main,
        car_yaris_main,
        car_prius_main,
        branch: Branch,
    ):
        schema = registry.schema.get("TestCar", branch=branch)

        grouped_data_paths = await self.__call_system_under_test(db, branch, schema)

        assert len(grouped_data_paths) == 1
        assert not grouped_data_paths[0].get_all_data_paths()

    async def test_one_violation(
        self,
        db: InfrahubDatabase,
        car_accord_main,
        car_prius_main,
        branch: Branch,
        default_branch: Branch,
    ):
        schema = registry.schema.get("TestCar", branch=branch)
        schema.get_attribute("nbr_seats").unique = True

        grouped_data_paths = await self.__call_system_under_test(db, branch, schema)

        assert len(grouped_data_paths) == 1
        all_data_paths = grouped_data_paths[0].get_all_data_paths()
        assert len(all_data_paths) == 2
        assert (
            DataPath(
                branch=default_branch.name,
                path_type=PathType.ATTRIBUTE,
                node_id=car_accord_main.id,
                kind="TestCar",
                field_name="nbr_seats",
                property_name="value",
                value="5",
            )
            in all_data_paths
        )
        assert (
            DataPath(
                branch=default_branch.name,
                path_type=PathType.ATTRIBUTE,
                node_id=car_prius_main.id,
                kind="TestCar",
                field_name="nbr_seats",
                property_name="value",
                value="5",
            )
            in all_data_paths
        )

    async def test_deleted_node_ignored(
        self,
        db: InfrahubDatabase,
        car_accord_main,
        car_prius_main,
        branch: Branch,
    ):
        node_to_delete = await NodeManager.get_one(id=car_accord_main.id, db=db, branch=branch)
        await node_to_delete.delete(db=db)
        schema = registry.schema.get("TestCar", branch=branch)
        schema.get_attribute("nbr_seats").unique = True

        grouped_data_paths = await self.__call_system_under_test(db, branch, schema)

        assert len(grouped_data_paths) == 1
        assert not grouped_data_paths[0].get_all_data_paths()

    async def test_get_latest_update(
        self,
        db: InfrahubDatabase,
        car_accord_main,
        car_prius_main,
        branch: Branch,
    ):
        car_to_update = await NodeManager.get_one(id=car_accord_main.id, db=db, branch=branch)
        car_to_update.nbr_seats.value = 3
        await car_to_update.save(db=db)
        schema = registry.schema.get("TestCar", branch=branch)

        grouped_data_paths = await self.__call_system_under_test(db, branch, schema)

        assert len(grouped_data_paths) == 1
        assert not grouped_data_paths[0].get_all_data_paths()

    async def test_combined_uniqueness_constraint_no_violations(
        self,
        db: InfrahubDatabase,
        car_accord_main,
        car_prius_main,
        car_volt_main,
        car_yaris_main,
        branch: Branch,
    ):
        cars_to_update = await NodeManager.get_many(
            db=db, ids=[car_accord_main.id, car_prius_main.id, car_volt_main.id, car_yaris_main.id], branch=branch
        )
        color = 111111
        for car in cars_to_update.values():
            color += 1
            car.color.value = f"#{color}"
            await car.save(db=db)
        schema = registry.schema.get("TestCar", branch=branch)
        schema.uniqueness_constraints = [["color__value", "owner__name"]]
        grouped_data_paths = await self.__call_system_under_test(db, branch, schema)

        assert len(grouped_data_paths) == 1
        assert not grouped_data_paths[0].get_all_data_paths()

    async def test_combined_uniqueness_constraints_with_violations(
        self,
        db: InfrahubDatabase,
        car_accord_main,
        car_prius_main,
        car_volt_main,
        car_yaris_main,
        person_jane_main,
        branch: Branch,
        default_branch: Branch,
    ):
        cars_to_update = await NodeManager.get_many(db=db, ids=[car_volt_main.id, car_yaris_main.id], branch=branch)
        color = 111111
        for car in cars_to_update.values():
            color += 1
            car.color.value = f"#{color}"
            await car.save(db=db)
        car_to_update = await NodeManager.get_one(db=db, id=car_accord_main.id, branch=branch)
        car_to_update.color.value = "#444445"
        await car_to_update.owner.update(data=person_jane_main, db=db)
        await car_to_update.save(db=db)
        car_to_update = await NodeManager.get_one(db=db, id=car_prius_main.id, branch=branch)
        car_to_update.color.value = "#444445"
        await car_to_update.save(db=db)

        schema = registry.schema.get("TestCar", branch=branch)
        schema.uniqueness_constraints = [["color__value", "owner__height"]]

        grouped_data_paths = await self.__call_system_under_test(db, branch, schema)

        assert len(grouped_data_paths) == 1
        all_data_paths = grouped_data_paths[0].get_all_data_paths()
        assert len(all_data_paths) == 4

        assert (
            DataPath(
                branch=branch.name,
                path_type=PathType.ATTRIBUTE,
                node_id=car_accord_main.id,
                kind="TestCar",
                field_name="color",
                property_name="value",
                value="#444445",
            )
            in all_data_paths
        )
        assert (
            DataPath(
                branch=branch.name,
                path_type=PathType.ATTRIBUTE,
                node_id=car_prius_main.id,
                kind="TestCar",
                field_name="color",
                property_name="value",
                value="#444445",
            )
            in all_data_paths
        )
        assert (
            DataPath(
                branch=branch.name,
                path_type=PathType.RELATIONSHIP_ONE,
                node_id=car_accord_main.id,
                kind="TestCar",
                field_name="owner",
                property_name="height",
                value="180",
            )
            in all_data_paths
        )
        assert (
            DataPath(
                branch=default_branch.name,
                path_type=PathType.RELATIONSHIP_ONE,
                node_id=car_prius_main.id,
                kind="TestCar",
                field_name="owner",
                property_name="height",
                value="180",
            )
            in all_data_paths
        )

    async def test_generic_unique_attribute_violations(
        self,
        db: InfrahubDatabase,
        car_person_generics_data_simple,
        branch: Branch,
        default_branch: Branch,
    ):
        nolt_car = await NodeManager.get_one_by_id_or_default_filter(
            db=db, schema_name="TestGazCar", id="nolt", branch=branch
        )
        volt_car = await NodeManager.get_one_by_id_or_default_filter(
            db=db, schema_name="TestElectricCar", id="volt", branch=branch
        )
        volt_car.name.value = "nolt"
        await volt_car.save(db=db)

        schema = registry.schema.get("TestCar", branch=branch)

        grouped_data_paths = await self.__call_system_under_test(db, branch, schema)

        assert len(grouped_data_paths) == 1
        all_data_paths = grouped_data_paths[0].get_all_data_paths()
        assert len(all_data_paths) == 2
        assert (
            DataPath(
                branch=branch.name,
                path_type=PathType.ATTRIBUTE,
                node_id=volt_car.id,
                kind="TestCar",
                field_name="name",
                property_name="value",
                value="nolt",
            )
            in all_data_paths
        )
        assert (
            DataPath(
                branch=default_branch.name,
                path_type=PathType.ATTRIBUTE,
                node_id=nolt_car.id,
                kind="TestCar",
                field_name="name",
                property_name="value",
                value="nolt",
            )
            in all_data_paths
        )

    async def test_generic_unique_attribute_multiple_relationship_violations_to_same_node(
        self,
        db: InfrahubDatabase,
        car_person_generics_data_simple,
        branch: Branch,
        default_branch: Branch,
    ):
        person = registry.schema.get(name="TestPerson")
        nolt_owner = await Node.init(db=db, schema=person)
        await nolt_owner.new(db=db, name="Rupert", height=180)
        await nolt_owner.save(db=db)

        volt_car = await NodeManager.get_one_by_id_or_default_filter(
            db=db, schema_name="TestElectricCar", id="volt", branch=branch
        )
        await volt_car.owner.get_peer(db=db)
        await volt_car.previous_owner.update(data=nolt_owner, db=db)
        await volt_car.save(db=db)
        nolt_car = await NodeManager.get_one_by_id_or_default_filter(
            db=db, schema_name="TestGazCar", id="nolt", branch=branch
        )
        await nolt_car.owner.update(data=nolt_owner, db=db)
        await nolt_car.previous_owner.update(data=nolt_owner, db=db)
        await nolt_car.save(db=db)

        schema = registry.schema.get("TestCar", branch=branch)
        schema.uniqueness_constraints = [["owner__height", "previous_owner__height"]]

        grouped_data_paths = await self.__call_system_under_test(db, branch, schema)

        assert len(grouped_data_paths) == 1
        all_data_paths = grouped_data_paths[0].get_all_data_paths()
        assert len(all_data_paths) == 4
        assert (
            DataPath(
                branch=default_branch.name,
                path_type=PathType.RELATIONSHIP_ONE,
                node_id=volt_car.id,
                kind="TestCar",
                field_name="owner",
                property_name="height",
                value="180",
            )
            in all_data_paths
        )
        assert (
            DataPath(
                branch=branch.name,
                path_type=PathType.RELATIONSHIP_ONE,
                node_id=nolt_car.id,
                kind="TestCar",
                field_name="owner",
                property_name="height",
                value="180",
            )
            in all_data_paths
        )
        assert (
            DataPath(
                branch=branch.name,
                path_type=PathType.RELATIONSHIP_ONE,
                node_id=volt_car.id,
                kind="TestCar",
                field_name="previous_owner",
                property_name="height",
                value="180",
            )
            in all_data_paths
        )
        assert (
            DataPath(
                branch=branch.name,
                path_type=PathType.RELATIONSHIP_ONE,
                node_id=nolt_car.id,
                kind="TestCar",
                field_name="previous_owner",
                property_name="height",
                value="180",
            )
            in all_data_paths
        )

    async def test_generic_unique_constraint_relationship_with_and_without_attr(
        self,
        db: InfrahubDatabase,
        car_person_generics_data_simple,
        branch: Branch,
        default_branch: Branch,
    ):
        owner = car_person_generics_data_simple["p1"]
        volt_car = await NodeManager.get_one_by_id_or_default_filter(
            db=db, schema_name="TestElectricCar", id="volt", branch=branch
        )
        await volt_car.previous_owner.update(data=owner, db=db)
        await volt_car.save(db=db)
        bolt_car = await NodeManager.get_one_by_id_or_default_filter(
            db=db, schema_name="TestElectricCar", id="bolt", branch=branch
        )
        await bolt_car.previous_owner.update(data=owner, db=db)
        await bolt_car.save(db=db)

        schema = registry.schema.get("TestCar", branch=branch)
        schema.uniqueness_constraints = [["owner", "previous_owner__height"]]
        grouped_data_paths = await self.__call_system_under_test(db, branch, schema)

        assert len(grouped_data_paths) == 1
        all_data_paths = grouped_data_paths[0].get_all_data_paths()
        assert len(all_data_paths) == 4
        assert (
            DataPath(
                branch=default_branch.name,
                path_type=PathType.RELATIONSHIP_ONE,
                node_id=volt_car.id,
                kind="TestCar",
                field_name="owner",
                property_name="id",
                value=owner.id,
            )
            in all_data_paths
        )
        assert (
            DataPath(
                branch=default_branch.name,
                path_type=PathType.RELATIONSHIP_ONE,
                node_id=bolt_car.id,
                kind="TestCar",
                field_name="owner",
                property_name="id",
                value=owner.id,
            )
            in all_data_paths
        )
        assert (
            DataPath(
                branch=branch.name,
                path_type=PathType.RELATIONSHIP_ONE,
                node_id=volt_car.id,
                kind="TestCar",
                field_name="previous_owner",
                property_name="height",
                value="180",
            )
            in all_data_paths
        )
        assert (
            DataPath(
                branch=branch.name,
                path_type=PathType.RELATIONSHIP_ONE,
                node_id=bolt_car.id,
                kind="TestCar",
                field_name="previous_owner",
                property_name="height",
                value="180",
            )
            in all_data_paths
        )

    async def test_relationship_violation_wo_attribute(
        self,
        db: InfrahubDatabase,
        car_accord_main,
        car_prius_main,
        car_camry_main,
        person_john_main,
        branch: Branch,
        default_branch: Branch,
    ):
        car_to_update = await NodeManager.get_one(id=car_camry_main.id, db=db, branch=branch)
        await car_to_update.owner.update(data=person_john_main, db=db)
        await car_to_update.save(db=db)

        schema = registry.schema.get("TestCar", branch=branch)
        schema.uniqueness_constraints = [["owner"]]
        grouped_data_paths = await self.__call_system_under_test(db, branch, schema)

        assert len(grouped_data_paths) == 1
        all_data_paths = grouped_data_paths[0].get_all_data_paths()
        assert len(all_data_paths) == 3
        assert (
            DataPath(
                branch=default_branch.name,
                path_type=PathType.RELATIONSHIP_ONE,
                node_id=car_accord_main.id,
                kind="TestCar",
                field_name="owner",
                property_name="id",
                value=person_john_main.id,
            )
            in all_data_paths
        )
        assert (
            DataPath(
                branch=default_branch.name,
                path_type=PathType.RELATIONSHIP_ONE,
                node_id=car_prius_main.id,
                kind="TestCar",
                field_name="owner",
                property_name="id",
                value=person_john_main.id,
            )
            in all_data_paths
        )
        assert (
            DataPath(
                branch=branch.name,
                path_type=PathType.RELATIONSHIP_ONE,
                node_id=car_camry_main.id,
                kind="TestCar",
                field_name="owner",
                property_name="id",
                value=person_john_main.id,
            )
            in all_data_paths
        )

    async def test_relationship_no_violation_with_overlaps(
        self,
        db: InfrahubDatabase,
        car_accord_main,
        car_prius_main,
        car_camry_main,
        default_branch: Branch,
    ):
        car_accord_main.color.value = "#111111"
        await car_accord_main.save(db=db)
        car_prius_main.color.value = "#222222"
        await car_prius_main.save(db=db)
        car_camry_main.color.value = "#111111"
        await car_camry_main.save(db=db)

        schema = registry.schema.get("TestCar", branch=default_branch)
        schema.uniqueness_constraints = [["owner", "color"]]
        grouped_data_paths = await self.__call_system_under_test(db, default_branch, schema)

        assert len(grouped_data_paths) == 1
        all_data_paths = grouped_data_paths[0].get_all_data_paths()
        assert len(all_data_paths) == 0

    async def test_relationship_violations_with_overlaps(
        self,
        db: InfrahubDatabase,
        car_accord_main,
        car_prius_main,
        car_camry_main,
        person_john_main,
        person_jane_main,
        branch: Branch,
        default_branch: Branch,
    ):
        await branch.rebase(db=db)
        car_accord_main.color.value = "#111111"
        car_accord_main.nbr_seats.value = 3
        await car_accord_main.save(db=db)
        car_prius_main.color.value = "#222222"  # violation
        car_prius_main.nbr_seats.value = 4
        await car_prius_main.save(db=db)
        car_camry_main.color.value = "#111111"
        car_camry_main.nbr_seats.value = 5
        await car_camry_main.save(db=db)

        car_1_branch = await Node.init(db=db, schema="TestCar", branch=branch)
        await car_1_branch.new(
            db=db, name="lightcycle", nbr_seats=1, is_electric=True, owner=person_john_main.id, color="#333333"
        )
        await car_1_branch.save(db=db)
        car_2_branch = await Node.init(db=db, schema="TestCar", branch=branch)
        await car_2_branch.new(
            db=db, name="batcycle", nbr_seats=1, is_electric=False, owner=person_jane_main.id, color="#222222"
        )  # violation
        await car_2_branch.save(db=db)
        car_3_branch = await Node.init(db=db, schema="TestCar", branch=branch)
        await car_3_branch.new(
            db=db, name="robincycle", nbr_seats=1, is_electric=True, owner=person_john_main.id, color="#222222"
        )  # violation
        await car_3_branch.save(db=db)

        schema = registry.schema.get("TestCar", branch=branch)
        schema.uniqueness_constraints = [["owner", "color"], ["color", "nbr_seats"]]
        grouped_data_paths = await self.__call_system_under_test(db, branch, schema)

        assert len(grouped_data_paths) == 1
        all_data_paths = grouped_data_paths[0].get_all_data_paths()
        assert len(all_data_paths) == 8
        assert (
            DataPath(
                branch=default_branch.name,
                path_type=PathType.RELATIONSHIP_ONE,
                node_id=car_prius_main.id,
                kind="TestCar",
                field_name="owner",
                property_name="id",
                value=person_john_main.id,
            )
            in all_data_paths
        )
        assert (
            DataPath(
                branch=default_branch.name,
                path_type=PathType.ATTRIBUTE,
                node_id=car_prius_main.id,
                kind="TestCar",
                field_name="color",
                property_name="value",
                value="#222222",
            )
            in all_data_paths
        )
        assert (
            DataPath(
                branch=branch.name,
                path_type=PathType.RELATIONSHIP_ONE,
                node_id=car_3_branch.id,
                kind="TestCar",
                field_name="owner",
                property_name="id",
                value=person_john_main.id,
            )
            in all_data_paths
        )
        assert (
            DataPath(
                branch=branch.name,
                path_type=PathType.ATTRIBUTE,
                node_id=car_3_branch.id,
                kind="TestCar",
                field_name="color",
                property_name="value",
                value="#222222",
            )
            in all_data_paths
        )
        assert (
            DataPath(
                branch=branch.name,
                path_type=PathType.ATTRIBUTE,
                node_id=car_3_branch.id,
                kind="TestCar",
                field_name="nbr_seats",
                property_name="value",
                value="1",
            )
            in all_data_paths
        )
        assert (
            DataPath(
                branch=branch.name,
                path_type=PathType.ATTRIBUTE,
                node_id=car_2_branch.id,
                kind="TestCar",
                field_name="color",
                property_name="value",
                value="#222222",
            )
            in all_data_paths
        )
        assert (
            DataPath(
                branch=branch.name,
                path_type=PathType.ATTRIBUTE,
                node_id=car_2_branch.id,
                kind="TestCar",
                field_name="nbr_seats",
                property_name="value",
                value="1",
            )
            in all_data_paths
        )
        assert (
            DataPath(
                branch=branch.name,
                path_type=PathType.ATTRIBUTE,
                node_id=car_3_branch.id,
                kind="TestCar",
                field_name="color",
                property_name="value",
                value="#222222",
            )
            in all_data_paths
        )
