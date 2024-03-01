import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import PathType, SchemaPathType
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.path import DataPath, SchemaPath
from infrahub.core.validators.model import SchemaConstraintValidatorRequest
from infrahub.core.validators.relationship.count import RelationshipCountChecker, RelationshipCountUpdateValidatorQuery
from infrahub.database import InfrahubDatabase


@pytest.mark.parametrize("min_count,max_count", [(None, None), (None, 10), (1, None), (1, 10)])
async def test_query_success(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_accord_main: Node,
    car_volt_main: Node,
    person_john_main,
    min_count,
    max_count,
):
    car_schema = registry.schema.get(name="TestPerson")
    cars_rel = car_schema.get_relationship(name="cars")
    cars_rel.min_count = min_count
    cars_rel.max_count = max_count

    schema_path = SchemaPath(path_type=SchemaPathType.RELATIONSHIP, schema_kind="TestPerson", field_name="cars")
    query = await RelationshipCountUpdateValidatorQuery.init(
        db=db, branch=default_branch, node_schema=car_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_paths = grouped_paths.get_all_data_paths()
    assert len(all_paths) == 0


@pytest.mark.parametrize(
    "min_count,max_count",
    [
        (None, 2),
        (4, 10),
        (4, None),
    ],
)
async def test_query_failure(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_accord_main: Node,
    car_volt_main: Node,
    car_prius_main: Node,
    person_john_main,
    min_count,
    max_count,
):
    car_schema = registry.schema.get(name="TestPerson")
    cars_rel = car_schema.get_relationship(name="cars")
    cars_rel.min_count = min_count
    cars_rel.max_count = max_count

    schema_path = SchemaPath(path_type=SchemaPathType.RELATIONSHIP, schema_kind="TestPerson", field_name="cars")
    query = await RelationshipCountUpdateValidatorQuery.init(
        db=db, branch=default_branch, node_schema=car_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_paths = grouped_paths.get_all_data_paths()
    assert len(all_paths) == 1
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.NODE,
            node_id=person_john_main.id,
            kind="TestPerson",
            field_name="cars",
            value=3,
        )
        in all_paths
    )


async def test_query_update_on_branch_failure(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_accord_main: Node,
    car_volt_main: Node,
    car_prius_main: Node,
    car_camry_main: Node,
    car_yaris_main: Node,
    person_john_main,
):
    branch = await create_branch(branch_name=str("branch2"), db=db)
    person_john = await NodeManager.get_one(db=db, id=person_john_main.id, branch=default_branch)
    car = await Node.init(db=db, schema="TestCar", branch=branch)
    await car.new(db=db, name="NewCar", nbr_seats=4, is_electric=True, owner=person_john)
    await car.save(db=db)

    car_schema = registry.schema.get(name="TestPerson")
    cars_rel = car_schema.get_relationship(name="cars")
    cars_rel.min_count = None
    cars_rel.max_count = 3

    schema_path = SchemaPath(path_type=SchemaPathType.RELATIONSHIP, schema_kind="TestPerson", field_name="cars")
    query = await RelationshipCountUpdateValidatorQuery.init(
        db=db, branch=branch, node_schema=car_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_paths = grouped_paths.get_all_data_paths()
    assert len(all_paths) == 2
    assert (
        DataPath(
            branch=branch.name,
            path_type=PathType.NODE,
            node_id=person_john_main.id,
            kind="TestPerson",
            field_name="cars",
            value=1,
        )
        in all_paths
    )
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.NODE,
            node_id=person_john_main.id,
            kind="TestPerson",
            field_name="cars",
            value=3,
        )
        in all_paths
    )


async def test_query_update_on_branch_success(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_accord_main: Node,
    car_volt_main: Node,
    car_prius_main: Node,
    car_camry_main: Node,
    car_yaris_main: Node,
    person_john_main,
):
    branch = await create_branch(branch_name=str("branch2"), db=db)
    person_john = await NodeManager.get_one(db=db, id=person_john_main.id, branch=branch)
    await person_john.cars.update(db=db, data=[car_accord_main.id, car_volt_main.id])
    await person_john.save(db=db)

    car_schema = registry.schema.get(name="TestPerson")
    cars_rel = car_schema.get_relationship(name="cars")
    cars_rel.min_count = 1
    cars_rel.max_count = 2

    schema_path = SchemaPath(path_type=SchemaPathType.RELATIONSHIP, schema_kind="TestPerson", field_name="cars")
    query = await RelationshipCountUpdateValidatorQuery.init(
        db=db, branch=branch, node_schema=car_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_paths = grouped_paths.get_all_data_paths()
    assert len(all_paths) == 0


async def test_query_delete_on_branch_failure(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_accord_main: Node,
    car_volt_main: Node,
    car_prius_main: Node,
    car_camry_main: Node,
    car_yaris_main: Node,
    person_john_main,
    person_jane_main,
):
    branch = await create_branch(branch_name=str("branch2"), db=db)
    old_car = await NodeManager.get_one(db=db, id=car_accord_main.id, branch=branch)
    await old_car.delete(db=db)

    car_schema = registry.schema.get(name="TestPerson")
    cars_rel = car_schema.get_relationship(name="cars")
    cars_rel.min_count = 4
    cars_rel.max_count = None

    schema_path = SchemaPath(path_type=SchemaPathType.RELATIONSHIP, schema_kind="TestPerson", field_name="cars")
    query = await RelationshipCountUpdateValidatorQuery.init(
        db=db, branch=branch, node_schema=car_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_paths = grouped_paths.get_all_data_paths()
    assert len(all_paths) == 3
    assert (
        DataPath(
            branch=branch.name,
            path_type=PathType.NODE,
            node_id=person_john_main.id,
            kind="TestPerson",
            field_name="cars",
            value=0,
        )
        in all_paths
    )
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.NODE,
            node_id=person_john_main.id,
            kind="TestPerson",
            field_name="cars",
            value=2,
        )
        in all_paths
    )
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.NODE,
            node_id=person_jane_main.id,
            kind="TestPerson",
            field_name="cars",
            value=2,
        )
        in all_paths
    )


async def test_query_delete_on_branch_success(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_accord_main: Node,
    car_volt_main: Node,
    car_prius_main: Node,
    car_camry_main: Node,
    car_yaris_main: Node,
    person_john_main,
):
    branch = await create_branch(branch_name=str("branch2"), db=db)
    car = await NodeManager.get_one(db=db, id=car_accord_main.id, branch=branch)
    await car.delete(db=db)

    car_schema = registry.schema.get(name="TestPerson")
    cars_rel = car_schema.get_relationship(name="cars")
    cars_rel.min_count = 1
    cars_rel.max_count = 2

    schema_path = SchemaPath(path_type=SchemaPathType.RELATIONSHIP, schema_kind="TestPerson", field_name="cars")
    query = await RelationshipCountUpdateValidatorQuery.init(
        db=db, branch=branch, node_schema=car_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_paths = grouped_paths.get_all_data_paths()
    assert len(all_paths) == 0


async def test_validator(
    db: InfrahubDatabase,
    branch: Branch,
    default_branch: Branch,
    person_john_main,
    person_jane_main,
    car_camry_main,
    car_accord_main,
    car_prius_main,
    car_volt_main,
):
    person_schema = registry.schema.get(name="TestPerson", branch=branch)
    cars_attr = person_schema.get_relationship(name="cars")
    cars_attr.min_count = 1
    cars_attr.max_count = 2
    registry.schema.set(name="TestPerson", schema=person_schema, branch=branch.name)

    request = SchemaConstraintValidatorRequest(
        branch=branch,
        constraint_name="relationship.max_count.update",
        node_schema=person_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPerson", field_name="cars"),
    )

    constraint_checker = RelationshipCountChecker(db=db, branch=branch)
    grouped_data_paths = await constraint_checker.check(request)

    assert len(grouped_data_paths) == 1
    data_paths = grouped_data_paths[0].get_all_data_paths()
    assert len(data_paths) == 1
    assert DataPath(
        branch=default_branch.name,
        path_type=PathType.NODE,
        node_id=person_john_main.id,
        kind="TestPerson",
        field_name="cars",
        value=3,
    )
