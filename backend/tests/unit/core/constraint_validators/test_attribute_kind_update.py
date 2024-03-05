from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import PathType, SchemaPathType
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.path import DataPath, SchemaPath
from infrahub.core.validators.attribute.kind import AttributeKindChecker, AttributeKindUpdateValidatorQuery
from infrahub.core.validators.model import SchemaConstraintValidatorRequest
from infrahub.database import InfrahubDatabase


async def test_query_success(db: InfrahubDatabase, default_branch: Branch, person_john_main):
    car_schema = registry.schema.get(name="TestCar")
    car = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car.new(db=db, name="http://www.accord.com", nbr_seats=5, is_electric=False, owner=person_john_main.id)
    await car.save(db=db)
    name_attr = car_schema.get_attribute(name="name")
    name_attr.kind = "URL"
    registry.schema.set(name="TestCar", schema=car_schema, branch=default_branch.name)

    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="name")

    query = await AttributeKindUpdateValidatorQuery.init(
        db=db, branch=default_branch, node_schema=car_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert len(all_data_paths) == 0


async def test_query_failure(db: InfrahubDatabase, default_branch: Branch, car_accord_main, car_camry_main):
    car_schema = registry.schema.get(name="TestCar")
    name_attr = car_schema.get_attribute(name="name")
    name_attr.kind = "IPNetwork"
    registry.schema.set(name="TestCar", schema=car_schema, branch=default_branch.name)

    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="name")

    query = await AttributeKindUpdateValidatorQuery.init(
        db=db, branch=default_branch, node_schema=car_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert len(all_data_paths) == 2
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=car_camry_main.id,
            kind="TestCar",
            field_name="name",
            value=car_camry_main.name.value,
        )
        in all_data_paths
    )
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=car_accord_main.id,
            kind="TestCar",
            field_name="name",
            value=car_accord_main.name.value,
        )
        in all_data_paths
    )


async def test_query_update_on_branch(
    db: InfrahubDatabase, branch: Branch, default_branch: Branch, car_accord_main, car_camry_main, car_volt_main
):
    await branch.rebase(db=db)
    car_accord = await NodeManager.get_one(db=db, branch=branch, id=car_accord_main.id)
    car_accord.name.value = "http://www.accord.com"
    await car_accord.save(db=db)
    car_volt = await NodeManager.get_one(db=db, branch=branch, id=car_volt_main.id)
    car_volt.name.value = "still-not-a-url.com"
    await car_volt.save(db=db)
    car_schema = registry.schema.get(name="TestCar", branch=branch)
    name_attr = car_schema.get_attribute(name="name")
    name_attr.kind = "URL"
    registry.schema.set(name="TestCar", schema=car_schema, branch=default_branch.name)

    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="name")

    query = await AttributeKindUpdateValidatorQuery.init(
        db=db, branch=branch, node_schema=car_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert len(all_data_paths) == 2
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=car_camry_main.id,
            kind="TestCar",
            field_name="name",
            value=car_camry_main.name.value,
        )
        in all_data_paths
    )
    assert (
        DataPath(
            branch=branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=car_volt_main.id,
            kind="TestCar",
            field_name="name",
            value="still-not-a-url.com",
        )
        in all_data_paths
    )


async def test_query_delete_on_branch(
    db: InfrahubDatabase, branch: Branch, default_branch: Branch, car_accord_main, car_camry_main, car_volt_main
):
    await branch.rebase(db=db)
    car_accord = await NodeManager.get_one(db=db, branch=branch, id=car_accord_main.id)
    car_accord.name.value = "1234"
    await car_accord.save(db=db)
    car_volt = await NodeManager.get_one(db=db, branch=branch, id=car_volt_main.id)
    await car_volt.delete(db=db)
    car_schema = registry.schema.get(name="TestCar", branch=branch)
    name_attr = car_schema.get_attribute(name="name")
    name_attr.kind = "URL"
    registry.schema.set(name="TestCar", schema=car_schema, branch=default_branch.name)

    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="name")

    query = await AttributeKindUpdateValidatorQuery.init(
        db=db, branch=branch, node_schema=car_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert len(all_data_paths) == 2
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=car_camry_main.id,
            kind="TestCar",
            field_name="name",
            value=car_camry_main.name.value,
        )
        in all_data_paths
    )
    assert (
        DataPath(
            branch=branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=car_accord_main.id,
            kind="TestCar",
            field_name="name",
            value="1234",
        )
        in all_data_paths
    )


async def test_validator(
    db: InfrahubDatabase, branch: Branch, default_branch: Branch, car_accord_main, car_camry_main, car_prius_main
):
    await branch.rebase(db=db)
    car = await NodeManager.get_one(id=car_accord_main.id, db=db, branch=branch)
    car.name.value = "http://www.accord.com"
    await car.save(db=db)
    car2 = await NodeManager.get_one(id=car_camry_main.id, db=db, branch=branch)
    car2.name.value = "one-internet-please"
    await car2.save(db=db)

    car_schema = registry.schema.get(name="TestCar", branch=branch)
    name_attr = car_schema.get_attribute(name="name")
    name_attr.kind = "URL"
    registry.schema.set(name="TestCar", schema=car_schema, branch=default_branch.name)

    request = SchemaConstraintValidatorRequest(
        branch=branch,
        constraint_name="attribute.kind.update",
        node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="name"),
    )

    constraint_checker = AttributeKindChecker(db=db, branch=branch)
    grouped_data_paths = await constraint_checker.check(request)

    assert len(grouped_data_paths) == 1
    data_paths = grouped_data_paths[0].get_all_data_paths()
    assert len(data_paths) == 2
    assert (
        DataPath(
            branch=branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=car_camry_main.id,
            kind="TestCar",
            field_name="name",
            value="one-internet-please",
        )
        in data_paths
    )
    assert (
        DataPath(
            branch=default_branch.name,
            node_id=car_prius_main.id,
            path_type=PathType.ATTRIBUTE,
            kind="TestCar",
            field_name="name",
            value=car_prius_main.name.value,
        )
        in data_paths
    )
