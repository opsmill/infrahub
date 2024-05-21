from infrahub.core.branch import Branch
from infrahub.core.constants import PathType, SchemaPathType
from infrahub.core.node import Node
from infrahub.core.path import DataPath, SchemaPath
from infrahub.core.validators.attribute.unique import (
    AttributeUniquenessChecker,
    AttributeUniqueUpdateValidatorQuery,
)
from infrahub.core.validators.model import SchemaConstraintValidatorRequest
from infrahub.database import InfrahubDatabase


async def test_query_no_violations(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_accord_main: Node,
    car_prius_main: Node,
    car_yaris_main: Node,
    car_volt_main: Node,
):
    car_schema = db.schema.get(name="TestCar")
    seats_attr = car_schema.get_attribute(name="nbr_seats")
    seats_attr.unique = True

    node_schema = car_schema
    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="name")
    query = await AttributeUniqueUpdateValidatorQuery.init(
        db=db, branch=default_branch, node_schema=node_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    assert len(grouped_paths.get_all_data_paths()) == 0


async def test_query_with_violations(
    db: InfrahubDatabase,
    branch: Branch,
    default_branch: Branch,
    car_accord_main: Node,
    car_prius_main: Node,
    car_yaris_main: Node,
    car_volt_main: Node,
    person_john_main,
):
    await branch.rebase(db=db)
    car = await Node.init(db=db, schema="TestCar", branch=branch)
    await car.new(db=db, name="New Accord", nbr_seats=5, is_electric=False, owner=person_john_main.id)
    await car.save(db=db)

    car_schema = db.schema.get(name="TestCar")
    seats_attr = car_schema.get_attribute(name="nbr_seats")
    seats_attr.unique = True

    node_schema = car_schema
    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="nbr_seats")
    query = await AttributeUniqueUpdateValidatorQuery.init(
        db=db, branch=branch, node_schema=node_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    assert len(grouped_paths.get_data_paths("5")) == 3

    assert DataPath(
        branch=branch.name,
        path_type=PathType.ATTRIBUTE,
        node_id=car.id,
        kind="TestCar",
        field_name="nbr_seats",
        value="5",
    ) in grouped_paths.get_data_paths("5")
    assert DataPath(
        branch=default_branch.name,
        path_type=PathType.ATTRIBUTE,
        node_id=car_accord_main.id,
        kind="TestCar",
        field_name="nbr_seats",
        value="5",
    ) in grouped_paths.get_data_paths("5")
    assert DataPath(
        branch=default_branch.name,
        path_type=PathType.ATTRIBUTE,
        node_id=car_prius_main.id,
        kind="TestCar",
        field_name="nbr_seats",
        value="5",
    ) in grouped_paths.get_data_paths("5")
    assert len(grouped_paths.get_data_paths("4")) == 2
    assert {dp.node_id for dp in grouped_paths.get_data_paths("4")} == {car_yaris_main.id, car_volt_main.id}


async def test_query_no_violations_update_in_branch(
    db: InfrahubDatabase,
    branch: Branch,
    default_branch: Branch,
    car_accord_main: Node,
    car_prius_main: Node,
    car_yaris_main: Node,
    car_volt_main: Node,
    person_john_main,
):
    car_accord_main.name.value = "New Accord"
    await car_accord_main.save(db=db)

    await branch.rebase(db=db)
    car = await Node.init(db=db, schema="TestCar", branch=branch)
    await car.new(db=db, name="New Accord", nbr_seats=5, is_electric=False, owner=person_john_main.id)
    await car.save(db=db)
    car.name.value = "Newest Accord"
    await car.save(db=db)

    car_schema = db.schema.get(name="TestCar")

    node_schema = car_schema
    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="name")
    query = await AttributeUniqueUpdateValidatorQuery.init(
        db=db, branch=branch, node_schema=node_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    assert len(grouped_paths.get_all_data_paths()) == 0


async def test_query_no_violations_deleted_node(
    db: InfrahubDatabase,
    branch: Branch,
    default_branch: Branch,
    car_accord_main: Node,
    car_prius_main: Node,
    car_yaris_main: Node,
    car_volt_main: Node,
    person_john_main,
):
    car_accord_main.name.value = "New Accord"
    await car_accord_main.save(db=db)

    await branch.rebase(db=db)
    car = await Node.init(db=db, schema="TestCar", branch=branch)
    await car.new(db=db, name="New Accord", nbr_seats=5, is_electric=False, owner=person_john_main.id)
    await car.save(db=db)
    await car.delete(db=db)

    car_schema = db.schema.get(name="TestCar")

    node_schema = car_schema
    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="name")
    query = await AttributeUniqueUpdateValidatorQuery.init(
        db=db, branch=branch, node_schema=node_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    assert len(grouped_paths.get_all_data_paths()) == 0


async def test_validator(
    db: InfrahubDatabase,
    branch: Branch,
    car_accord_main: Node,
    car_prius_main: Node,
    car_yaris_main: Node,
    car_volt_main: Node,
    person_john_main,
):
    await branch.rebase(db=db)
    car = await Node.init(db=db, schema="TestCar", branch=branch)
    await car.new(db=db, name="New Accord", nbr_seats=5, is_electric=False, owner=person_john_main.id)
    await car.save(db=db)

    car_schema = db.schema.get(name="TestCar")
    seats_attr = car_schema.get_attribute(name="nbr_seats")
    seats_attr.unique = True

    request = SchemaConstraintValidatorRequest(
        branch=branch,
        constraint_name="attribute.regex.update",
        node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="nbr_seats"),
    )

    constraint_checker = AttributeUniquenessChecker(db=db, branch=branch)
    grouped_data_paths = await constraint_checker.check(request)

    assert len(grouped_data_paths) == 1
    data_paths = grouped_data_paths[0].get_all_data_paths()
    assert len(data_paths) == 5
    assert {dp.node_id for dp in data_paths} == {
        car.id,
        car_accord_main.id,
        car_prius_main.id,
        car_yaris_main.id,
        car_volt_main.id,
    }
