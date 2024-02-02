from infrahub.core import registry
from infrahub.core.branch import Branch, ObjectConflict
from infrahub.core.constants import PathType
from infrahub.core.manager import NodeManager
from infrahub.core.validators.uniqueness.checker import UniquenessChecker
from infrahub.database import InfrahubDatabase


class TestUniquenessChecker:
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
        schema = registry.get_schema("TestCar", branch=branch)
        checker = UniquenessChecker(db)

        conflicts = await checker.get_conflicts(schemas=[schema], source_branch=branch)

        assert not conflicts

    async def test_one_violation(
        self,
        db: InfrahubDatabase,
        car_accord_main,
        car_prius_main,
        branch: Branch,
    ):
        schema = registry.get_schema("TestCar", branch=branch)
        schema.get_attribute("nbr_seats").unique = True
        checker = UniquenessChecker(db)

        conflicts = await checker.get_conflicts(schemas=[schema], source_branch=branch)

        assert len(conflicts) == 2
        assert (
            ObjectConflict(
                name="TestCar/nbr_seats",
                type="uniqueness-violation",
                kind="TestCar",
                id=car_accord_main.id,
                conflict_path="TestCar/nbr_seats",
                path="TestCar/nbr_seats",
                path_type=PathType.ATTRIBUTE,
                change_type="attribute_value",
                value=5,
            )
            in conflicts
        )
        assert (
            ObjectConflict(
                name="TestCar/nbr_seats",
                type="uniqueness-violation",
                kind="TestCar",
                id=car_prius_main.id,
                conflict_path="TestCar/nbr_seats",
                path="TestCar/nbr_seats",
                path_type=PathType.ATTRIBUTE,
                change_type="attribute_value",
                value=5,
            )
            in conflicts
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
        schema = registry.get_schema("TestCar", branch=branch)
        schema.get_attribute("nbr_seats").unique = True
        checker = UniquenessChecker(db)

        conflicts = await checker.get_conflicts(schemas=[schema], source_branch=branch)

        assert not conflicts

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
        schema = registry.get_schema("TestCar", branch=branch)
        checker = UniquenessChecker(db)

        conflicts = await checker.get_conflicts(schemas=[schema], source_branch=branch)

        assert not conflicts

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
            db=db, ids=[car_accord_main.id, car_prius_main.id, car_volt_main.id, car_yaris_main.id]
        )
        color = 111111
        for car in cars_to_update.values():
            color += 1
            car.color.value = f"#{color}"
            await car.save(db=db)
        schema = registry.get_schema("TestCar", branch=branch)
        schema.uniqueness_constraints = [["color", "owner__name"]]
        checker = UniquenessChecker(db)

        conflicts = await checker.get_conflicts(schemas=[schema], source_branch=branch)

        assert not conflicts

    async def test_combined_uniqueness_constraints_with_violations(
        self,
        db: InfrahubDatabase,
        car_accord_main,
        car_prius_main,
        car_volt_main,
        car_yaris_main,
        person_jane_main,
        person_john_main,
        branch: Branch,
    ):
        cars_to_update = await NodeManager.get_many(db=db, ids=[car_volt_main.id, car_yaris_main.id])
        color = 111111
        for car in cars_to_update.values():
            color += 1
            car.color.value = f"#{color}"
            await car.save(db=db)
        car_to_update = await NodeManager.get_one(db=db, id=car_accord_main.id)
        car_to_update.color.value = "#444444"
        await car_to_update.owner.update(data=person_jane_main, db=db)
        await car_to_update.save(db=db)
        car_to_update = await NodeManager.get_one(db=db, id=car_prius_main.id)
        car_to_update.color.value = "#444444"
        await car_to_update.owner.update(data=person_john_main, db=db)
        await car_to_update.save(db=db)

        schema = registry.get_schema("TestCar", branch=branch)
        schema.uniqueness_constraints = [["color", "owner__height"]]
        checker = UniquenessChecker(db)

        conflicts = await checker.get_conflicts(schemas=[schema], source_branch=branch)

        assert len(conflicts) == 4
        assert (
            ObjectConflict(
                name="TestCar/color",
                type="uniqueness-violation",
                kind="TestCar",
                id=car_accord_main.id,
                conflict_path="TestCar/color",
                path="TestCar/color",
                path_type=PathType.ATTRIBUTE,
                change_type="attribute_value",
                value="#444444",
            )
            in conflicts
        )
        assert (
            ObjectConflict(
                name="TestCar/color",
                type="uniqueness-violation",
                kind="TestCar",
                id=car_prius_main.id,
                conflict_path="TestCar/color",
                path="TestCar/color",
                path_type=PathType.ATTRIBUTE,
                change_type="attribute_value",
                value="#444444",
            )
            in conflicts
        )
        assert (
            ObjectConflict(
                name="TestCar/owner/height",
                type="uniqueness-violation",
                kind="TestCar",
                id=car_accord_main.id,
                conflict_path="TestCar/owner/height",
                path="TestCar/owner/height",
                path_type=PathType.ATTRIBUTE,
                change_type="attribute_value",
                value="180",
            )
            in conflicts
        )
        assert (
            ObjectConflict(
                name="TestCar/owner/height",
                type="uniqueness-violation",
                kind="TestCar",
                id=car_prius_main.id,
                conflict_path="TestCar/owner/height",
                path="TestCar/owner/height",
                path_type=PathType.ATTRIBUTE,
                change_type="attribute_value",
                value="180",
            )
            in conflicts
        )

    async def test_generic_unique_attribute_violations(
        self,
        db: InfrahubDatabase,
        car_person_generics_data,
        branch: Branch,
    ):
        nolt_car = await NodeManager.get_one_by_id_or_default_filter(
            db=db, schema_name="TestGazCar", id="nolt", branch=branch
        )
        volt_car = await NodeManager.get_one_by_id_or_default_filter(
            db=db, schema_name="TestElectricCar", id="volt", branch=branch
        )
        volt_car.name.value = "nolt"
        await volt_car.save(db=db)

        schema = registry.get_schema("TestCar", branch=branch)
        checker = UniquenessChecker(db)

        conflicts = await checker.get_conflicts(schemas=[schema], source_branch=branch)

        assert len(conflicts) == 2
        assert (
            ObjectConflict(
                name="TestCar/name",
                type="uniqueness-violation",
                kind="TestCar",
                id=volt_car.id,
                conflict_path="TestCar/name",
                path="TestCar/name",
                path_type=PathType.ATTRIBUTE,
                change_type="attribute_value",
                value="nolt",
            )
            in conflicts
        )
        assert (
            ObjectConflict(
                name="TestCar/name",
                type="uniqueness-violation",
                kind="TestCar",
                id=nolt_car.id,
                conflict_path="TestCar/name",
                path="TestCar/name",
                path_type=PathType.ATTRIBUTE,
                change_type="attribute_value",
                value="nolt",
            )
            in conflicts
        )
