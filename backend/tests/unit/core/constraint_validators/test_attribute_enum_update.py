from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import PathType, SchemaPathType
from infrahub.core.manager import NodeManager
from infrahub.core.path import DataPath, SchemaPath
from infrahub.core.validators.attribute.enum import AttributeEnumChecker, AttributeEnumUpdateValidatorQuery
from infrahub.core.validators.model import SchemaConstraintValidatorRequest
from infrahub.database import InfrahubDatabase


async def test_query_new_choice_value(db: InfrahubDatabase, default_branch: Branch, car_accord_main, car_camry_main):
    car_schema = registry.schema.get(name="TestCar")
    transmission_attr = car_schema.get_attribute(name="transmission")
    transmission_attr.enum.append("warp-drive")

    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="transmission")

    query = await AttributeEnumUpdateValidatorQuery.init(
        db=db, branch=default_branch, node_schema=car_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert len(all_data_paths) == 0


async def test_query_remove_choice(db: InfrahubDatabase, default_branch: Branch, car_accord_main, car_camry_main):
    car = await NodeManager.get_one(id=car_accord_main.id, db=db, branch=default_branch)
    car.transmission.value = "manual"
    await car.save(db=db)

    car_schema = registry.schema.get(name="TestCar", branch=default_branch)
    transmission_attr = car_schema.get_attribute(name="transmission")
    transmission_attr.enum = ["flintstone-feet"]

    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="transmission")

    query = await AttributeEnumUpdateValidatorQuery.init(
        db=db, branch=default_branch, node_schema=car_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert len(all_data_paths) == 1
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=car_accord_main.id,
            kind="TestCar",
            field_name="transmission",
            value="manual",
        )
        in all_data_paths
    )


async def test_query_convert_to_enum(db: InfrahubDatabase, default_branch: Branch, car_accord_main, car_camry_main):
    car = await NodeManager.get_one(id=car_accord_main.id, db=db, branch=default_branch)
    car.color.value = "#123123"
    await car.save(db=db)

    car_schema = registry.schema.get(name="TestCar", branch=default_branch)
    color_attr = car_schema.get_attribute(name="color")
    color_attr.enum = ["#444444", "#123123"]

    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="color")

    query = await AttributeEnumUpdateValidatorQuery.init(
        db=db, branch=default_branch, node_schema=car_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert len(all_data_paths) == 0


async def test_query_update_on_branch(db: InfrahubDatabase, branch: Branch, car_accord_main, car_camry_main):
    car_accord_main.color.value = "#654654"
    await car_accord_main.save(db=db)
    await branch.rebase(db=db)
    car = await NodeManager.get_one(id=car_accord_main.id, db=db, branch=branch)
    car.color.value = "#123123"
    await car.save(db=db)

    car_schema = registry.schema.get(name="TestCar", branch=branch)
    color_attr = car_schema.get_attribute(name="color")
    color_attr.enum = ["#444444", "#123123"]

    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="color")

    query = await AttributeEnumUpdateValidatorQuery.init(
        db=db, branch=branch, node_schema=car_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert len(all_data_paths) == 0


async def test_query_delete_on_branch(db: InfrahubDatabase, branch: Branch, car_accord_main, car_camry_main):
    car_accord_main.color.value = "#654654"
    await car_accord_main.save(db=db)
    await branch.rebase(db=db)
    car = await NodeManager.get_one(id=car_accord_main.id, db=db, branch=branch)
    await car.delete(db=db)

    car_schema = registry.schema.get(name="TestCar", branch=branch)
    color_attr = car_schema.get_attribute(name="color")
    color_attr.enum = ["#444444", "#123123"]

    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="color")

    query = await AttributeEnumUpdateValidatorQuery.init(
        db=db, branch=branch, node_schema=car_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert len(all_data_paths) == 0


async def test_validator(
    db: InfrahubDatabase, branch: Branch, default_branch: Branch, car_accord_main, car_camry_main, car_prius_main
):
    await branch.rebase(db=db)
    car = await NodeManager.get_one(id=car_accord_main.id, db=db, branch=branch)
    car.color.value = "#123123"
    await car.save(db=db)

    car_schema = registry.schema.get(name="TestCar", branch=branch)
    color_attr = car_schema.get_attribute(name="color")
    color_attr.enum = ["#123123"]

    request = SchemaConstraintValidatorRequest(
        branch=branch,
        constraint_name="attribute.enum.update",
        node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="color"),
    )

    constraint_checker = AttributeEnumChecker(db=db, branch=branch)
    grouped_data_paths = await constraint_checker.check(request)

    assert len(grouped_data_paths) == 1
    data_paths = grouped_data_paths[0].get_all_data_paths()
    assert len(data_paths) == 2
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=car_camry_main.id,
            kind="TestCar",
            field_name="color",
            value="#444444",
        )
        in data_paths
    )
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=car_prius_main.id,
            kind="TestCar",
            field_name="color",
            value="#444444",
        )
        in data_paths
    )
