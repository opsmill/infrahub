from typing import Any

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import BranchSupportType, PathType, SchemaPathType
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.path import DataPath, SchemaPath
from infrahub.core.schema import SchemaRoot
from infrahub.core.validators.model import SchemaConstraintValidatorRequest
from infrahub.core.validators.relationship.peer import RelationshipPeerChecker, RelationshipPeerUpdateValidatorQuery
from infrahub.database import InfrahubDatabase


@pytest.fixture
async def car_person_schema_generics_simple(db: InfrahubDatabase, default_branch: Branch) -> SchemaRoot:
    SCHEMA: dict[str, Any] = {
        "generics": [
            {
                "name": "Car",
                "namespace": "Test",
                "default_filter": "name__value",
                "display_labels": ["name__value", "color__value"],
                "order_by": ["name__value"],
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "nbr_seats", "kind": "Number"},
                    {"name": "color", "kind": "Text", "default_value": "#444444", "max_length": 7},
                ],
                "relationships": [
                    {
                        "name": "owner",
                        "peer": "TestPerson",
                        "identifier": "person__car",
                        "optional": False,
                        "cardinality": "one",
                    },
                ],
            },
        ],
        "nodes": [
            {
                "name": "ElectricCar",
                "namespace": "Test",
                "display_labels": ["name__value", "color__value"],
                "inherit_from": ["TestCar"],
                "default_filter": "name__value",
                "attributes": [
                    {"name": "nbr_engine", "kind": "Number"},
                ],
            },
            {
                "name": "GazCar",
                "namespace": "Test",
                "display_labels": ["name__value", "color__value"],
                "inherit_from": ["TestCar"],
                "default_filter": "name__value",
                "attributes": [
                    {"name": "mpg", "kind": "Number"},
                ],
            },
            {
                "name": "Person",
                "namespace": "Test",
                "default_filter": "name__value",
                "display_labels": ["name__value"],
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "height", "kind": "Number", "optional": True},
                ],
                "relationships": [
                    {"name": "cars", "peer": "TestCar", "identifier": "person__car", "cardinality": "many"},
                    {
                        "name": "electric_cars",
                        "peer": "TestElectricCar",
                        "identifier": "person__electriccar",
                        "cardinality": "many",
                    },
                ],
            },
        ],
    }

    schema = SchemaRoot(**SCHEMA)
    registry.schema.register_schema(schema=schema, branch=default_branch.name)
    return schema


@pytest.fixture
async def car_person_generic_data(db: InfrahubDatabase, car_person_schema_generics_simple, default_branch: Branch):
    p_1 = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await p_1.new(db=db, name="P1")
    await p_1.save(db=db)
    p_2 = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await p_2.new(db=db, name="P2")
    await p_2.save(db=db)
    e_car = await Node.init(db=db, schema="TestElectricCar", branch=default_branch)
    await e_car.new(db=db, name="ECar", nbr_seats=3, nbr_engine=2, owner=p_1)
    await e_car.save(db=db)
    e_car_2 = await Node.init(db=db, schema="TestElectricCar", branch=default_branch)
    await e_car_2.new(db=db, name="ECar2", nbr_seats=4, nbr_engine=3, owner=p_2)
    await e_car_2.save(db=db)

    return {
        "p_1": p_1,
        "p_2": p_2,
        "e_car": e_car,
        "e_car_2": e_car_2,
    }


async def test_query(
    db: InfrahubDatabase,
    branch: Branch,
    default_branch: Branch,
    car_accord_main: Node,
    car_volt_main: Node,
    person_john_main,
):
    car_schema = registry.schema.get(name="TestCar")
    owner_rel = car_schema.get_relationship(name="owner")
    owner_rel.peer = "TestCar"

    schema_path = SchemaPath(path_type=SchemaPathType.RELATIONSHIP, schema_kind="TestCar", field_name="owner")
    query = await RelationshipPeerUpdateValidatorQuery.init(
        db=db, branch=branch, node_schema=car_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_paths = grouped_paths.get_all_data_paths()
    assert len(all_paths) == 2
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.NODE,
            node_id=car_accord_main.id,
            kind="TestCar",
            field_name="owner",
            peer_id=person_john_main.id,
        )
        in all_paths
    )
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.NODE,
            node_id=car_volt_main.id,
            kind="TestCar",
            field_name="owner",
            peer_id=person_john_main.id,
        )
        in all_paths
    )


async def test_query_no_relationships(
    db: InfrahubDatabase, branch: Branch, car_accord_main: Node, car_volt_main: Node, person_john_main
):
    await branch.rebase(db=db)
    for car in (car_accord_main, car_volt_main):
        fresh_car = await NodeManager.get_one(db=db, id=car.id, branch=branch)
        await fresh_car.owner.update(db=db, data=None)
        await fresh_car.save(db=db)

    car_schema = registry.schema.get(name="TestCar")
    owner_rel = car_schema.get_relationship(name="owner")
    owner_rel.peer = "TestCar"

    schema_path = SchemaPath(path_type=SchemaPathType.RELATIONSHIP, schema_kind="TestCar", field_name="owner")
    query = await RelationshipPeerUpdateValidatorQuery.init(
        db=db, branch=branch, node_schema=car_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_paths = grouped_paths.get_all_data_paths()
    assert len(all_paths) == 0


async def test_query_switch_from_generic_to_node_success(db: InfrahubDatabase, branch: Branch, car_person_generic_data):
    person_schema = registry.schema.get(name="TestPerson")
    cars_rel = person_schema.get_relationship(name="cars")
    cars_rel.peer = "TestElectricCar"

    schema_path = SchemaPath(path_type=SchemaPathType.RELATIONSHIP, schema_kind="TestPerson", field_name="cars")
    query = await RelationshipPeerUpdateValidatorQuery.init(
        db=db, branch=branch, node_schema=person_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_paths = grouped_paths.get_all_data_paths()
    assert len(all_paths) == 0


async def test_query_switch_from_generic_to_node_failure(db: InfrahubDatabase, branch: Branch, car_person_generic_data):
    p_1 = car_person_generic_data["p_1"]
    g_car = await Node.init(db=db, schema="TestGazCar", branch=branch)
    await g_car.new(db=db, name="GCar", nbr_seats=3, mpg=23, owner=p_1)
    await g_car.save(db=db)

    person_schema = registry.schema.get(name="TestPerson")
    cars_rel = person_schema.get_relationship(name="cars")
    cars_rel.peer = "TestElectricCar"

    schema_path = SchemaPath(path_type=SchemaPathType.RELATIONSHIP, schema_kind="TestPerson", field_name="cars")
    query = await RelationshipPeerUpdateValidatorQuery.init(
        db=db, branch=branch, node_schema=person_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_paths = grouped_paths.get_all_data_paths()
    assert all_paths == [
        DataPath(
            branch=branch.name,
            path_type=PathType.NODE,
            node_id=p_1.id,
            kind="TestPerson",
            field_name="cars",
            peer_id=g_car.id,
        )
    ]


async def test_query_switch_from_node_to_generic_success(db: InfrahubDatabase, branch: Branch, car_person_generic_data):
    p_1 = car_person_generic_data["p_1"]
    e_car = car_person_generic_data["e_car"]
    g_car = await Node.init(db=db, schema="TestGazCar", branch=branch)
    await g_car.new(db=db, name="GCar", nbr_seats=3, mpg=29, owner=p_1)
    await g_car.save(db=db)
    await p_1.electric_cars.update(db=db, data=[g_car, e_car])
    await p_1.save(db=db)

    person_schema = registry.schema.get(name="TestPerson")
    ecars_rel = person_schema.get_relationship(name="electric_cars")
    ecars_rel.peer = "TestCar"

    schema_path = SchemaPath(
        path_type=SchemaPathType.RELATIONSHIP, schema_kind="TestPerson", field_name="electric_cars"
    )
    query = await RelationshipPeerUpdateValidatorQuery.init(
        db=db, branch=branch, node_schema=person_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_paths = grouped_paths.get_all_data_paths()
    assert len(all_paths) == 0


async def test_query_switch_from_node_to_generic_failure(db: InfrahubDatabase, branch: Branch, car_person_generic_data):
    await branch.rebase(db=db)
    p_1 = await NodeManager.get_one(db=db, id=car_person_generic_data["p_1"].id, branch=branch)
    e_car = await NodeManager.get_one(db=db, id=car_person_generic_data["e_car"].id, branch=branch)
    g_car = await Node.init(db=db, schema="TestGazCar", branch=branch)
    await g_car.new(db=db, name="GCar", nbr_seats=3, mpg=29, owner=p_1)
    await g_car.save(db=db)
    await p_1.electric_cars.update(db=db, data=[g_car, e_car])
    await p_1.save(db=db)

    person_schema = registry.schema.get(name="TestPerson")
    ecars_rel = person_schema.get_relationship(name="electric_cars")
    ecars_rel.peer = "TestPerson"

    schema_path = SchemaPath(
        path_type=SchemaPathType.RELATIONSHIP, schema_kind="TestPerson", field_name="electric_cars"
    )
    query = await RelationshipPeerUpdateValidatorQuery.init(
        db=db, branch=branch, node_schema=person_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_paths = grouped_paths.get_all_data_paths()
    assert len(all_paths) == 2
    assert (
        DataPath(
            branch=branch.name,
            path_type=PathType.NODE,
            node_id=p_1.id,
            kind="TestPerson",
            field_name="electric_cars",
            peer_id=g_car.id,
        )
        in all_paths
    )
    assert (
        DataPath(
            branch=branch.name,
            path_type=PathType.NODE,
            node_id=p_1.id,
            kind="TestPerson",
            field_name="electric_cars",
            peer_id=e_car.id,
        )
        in all_paths
    )


async def test_query_update_on_branch_success(
    db: InfrahubDatabase, branch: Branch, default_branch: Branch, car_person_generic_data
):
    p_1 = car_person_generic_data["p_1"]
    g_car = await Node.init(db=db, schema="TestGazCar", branch=default_branch)
    await g_car.new(db=db, name="GCar", nbr_seats=3, mpg=29, owner=p_1)
    await g_car.save(db=db)
    await p_1.cars.get_relationships(db=db)
    await p_1.cars.update(db=db, data=[*p_1.cars, g_car])
    await p_1.save(db=db)

    await branch.rebase(db=db)
    p_1 = await NodeManager.get_one(db=db, id=p_1.id, branch=branch)
    e_car = await NodeManager.get_one(db=db, id=car_person_generic_data["e_car"].id, branch=branch)
    await p_1.cars.update(db=db, data=[e_car])
    await p_1.save(db=db)

    person_schema = registry.schema.get(name="TestPerson")
    cars_rel = person_schema.get_relationship(name="cars")
    cars_rel.peer = "TestElectricCar"

    schema_path = SchemaPath(path_type=SchemaPathType.RELATIONSHIP, schema_kind="TestPerson", field_name="cars")
    query = await RelationshipPeerUpdateValidatorQuery.init(
        db=db, branch=branch, node_schema=person_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_paths = grouped_paths.get_all_data_paths()
    assert len(all_paths) == 0


async def test_query_update_on_branch_failure(
    db: InfrahubDatabase, branch: Branch, default_branch: Branch, car_person_generic_data
):
    p_2 = car_person_generic_data["p_2"]
    g_car = await Node.init(db=db, schema="TestGazCar", branch=default_branch)
    await g_car.new(db=db, name="GCar", nbr_seats=3, mpg=29, owner=p_2)
    await g_car.save(db=db)

    await branch.rebase(db=db)
    p_1 = await NodeManager.get_one(db=db, id=car_person_generic_data["p_1"].id, branch=branch)
    e_car = await NodeManager.get_one(db=db, id=car_person_generic_data["e_car"].id, branch=branch)
    await p_1.cars.update(db=db, data=[e_car, g_car])
    await p_1.save(db=db)

    person_schema = registry.schema.get(name="TestPerson")
    cars_rel = person_schema.get_relationship(name="cars")
    cars_rel.peer = "TestElectricCar"

    schema_path = SchemaPath(path_type=SchemaPathType.RELATIONSHIP, schema_kind="TestPerson", field_name="cars")
    query = await RelationshipPeerUpdateValidatorQuery.init(
        db=db, branch=branch, node_schema=person_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_paths = grouped_paths.get_all_data_paths()
    assert len(all_paths) == 2
    assert (
        DataPath(
            branch=branch.name,
            path_type=PathType.NODE,
            node_id=p_1.id,
            kind="TestPerson",
            field_name="cars",
            peer_id=g_car.id,
        )
        in all_paths
    )
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.NODE,
            node_id=p_2.id,
            kind="TestPerson",
            field_name="cars",
            peer_id=g_car.id,
        )
        in all_paths
    )


async def test_query_delete_on_branch(
    db: InfrahubDatabase, branch: Branch, default_branch: Branch, car_person_generic_data
):
    p_1 = car_person_generic_data["p_1"]
    g_car = await Node.init(db=db, schema="TestGazCar", branch=default_branch)
    await g_car.new(db=db, name="GCar", nbr_seats=3, mpg=29, owner=p_1)
    await g_car.save(db=db)
    await p_1.cars.get_relationships(db=db)
    await p_1.cars.update(db=db, data=[*p_1.cars, g_car])
    await p_1.save(db=db)

    await branch.rebase(db=db)
    p_1 = await NodeManager.get_one(db=db, id=p_1.id, branch=branch)
    await p_1.delete(db=db)

    person_schema = registry.schema.get(name="TestPerson")
    cars_rel = person_schema.get_relationship(name="cars")
    cars_rel.peer = "TestElectricCar"

    schema_path = SchemaPath(path_type=SchemaPathType.RELATIONSHIP, schema_kind="TestPerson", field_name="cars")
    query = await RelationshipPeerUpdateValidatorQuery.init(
        db=db, branch=branch, node_schema=person_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_paths = grouped_paths.get_all_data_paths()
    assert len(all_paths) == 0


async def test_validator(
    db: InfrahubDatabase,
    branch: Branch,
    default_branch: Branch,
    car_accord_main: Node,
    car_volt_main: Node,
    person_john_main,
):
    car_schema = registry.schema.get(name="TestCar")
    owner_rel = car_schema.get_relationship(name="owner")
    owner_rel.peer = "TestCar"

    request = SchemaConstraintValidatorRequest(
        branch=default_branch,
        constraint_name="relationship.peer.update",
        node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.RELATIONSHIP, schema_kind="TestCar", field_name="owner"),
    )

    constraint_checker = RelationshipPeerChecker(db=db, branch=default_branch)
    grouped_data_paths = await constraint_checker.check(request)

    assert len(grouped_data_paths) == 1
    all_paths = grouped_data_paths[0].get_all_data_paths()
    assert len(all_paths) == 2
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.NODE,
            node_id=car_accord_main.id,
            kind="TestCar",
            field_name="owner",
            peer_id=person_john_main.id,
        )
        in all_paths
    )
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.NODE,
            node_id=car_volt_main.id,
            kind="TestCar",
            field_name="owner",
            peer_id=person_john_main.id,
        )
        in all_paths
    )
