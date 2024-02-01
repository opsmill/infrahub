from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.query.constraints.node_unique_attributes import NodeUniqueAttributeConstraintQuery
from infrahub.database import InfrahubDatabase


async def test_query_uniqueness_no_violations(
    db: InfrahubDatabase,
    car_accord_main,
    car_camry_main,
    car_volt_main,
    car_yaris_main,
    car_prius_main,
    branch: Branch,
):
    schema = registry.schema.get(name="TestCar", branch=branch)

    query = await NodeUniqueAttributeConstraintQuery.init(db=db, branch=branch, schema=schema)
    query_result = await query.execute(db=db)

    assert not query_result.results


async def test_query_uniqueness_one_violation(
    db: InfrahubDatabase,
    car_accord_main,
    car_prius_main,
    branch: Branch,
):
    schema = registry.schema.get(name="TestCar", branch=branch)
    schema.get_attribute("nbr_seats").unique = True

    query = await NodeUniqueAttributeConstraintQuery.init(db=db, branch=branch, schema=schema)
    query_result = await query.execute(db=db)

    assert len(query_result.results) == 1
    assert query_result.results[0].data["kind"] == "TestCar"
    assert set(query_result.results[0].data["node_ids"]) == {car_accord_main.id, car_prius_main.id}
    assert query_result.results[0].data["node_count"] == 2
    assert query_result.results[0].data["attr_name"] == "nbr_seats"
    assert query_result.results[0].data["attr_value"] == 5


async def test_query_uniqueness_deleted_node_ignored(
    db: InfrahubDatabase,
    car_accord_main,
    car_prius_main,
    branch: Branch,
):
    node_to_delete = await NodeManager.get_one(id=car_accord_main.id, db=db, branch=branch)
    await node_to_delete.delete(db=db)
    schema = registry.schema.get(name="TestCar", branch=branch)
    schema.get_attribute("nbr_seats").unique = True

    query = await NodeUniqueAttributeConstraintQuery.init(db=db, branch=branch, schema=schema)
    query_result = await query.execute(db=db)

    assert not query_result.results


async def test_query_uniqueness_get_latest_update(
    db: InfrahubDatabase,
    car_accord_main,
    car_prius_main,
    branch: Branch,
):
    car_to_update = await NodeManager.get_one(id=car_accord_main.id, db=db, branch=branch)
    car_to_update.nbr_seats.value = 3
    await car_to_update.save(db=db)
    schema = registry.schema.get(name="TestCar", branch=branch)
    schema.get_attribute("nbr_seats").unique = True

    query = await NodeUniqueAttributeConstraintQuery.init(db=db, branch=branch, schema=schema)
    query_result = await query.execute(db=db)

    assert not query_result.results


async def test_query_uniqueness_cross_branch_conflict(
    db: InfrahubDatabase,
    car_accord_main,
    car_prius_main,
    person_john_main,
    default_branch: Branch,
):
    branch_2 = await create_branch(branch_name="branch2", db=db)
    new_car_main = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await new_car_main.new(db=db, name="Thunderbolt", nbr_seats=2, is_electric=True, owner=person_john_main)
    await new_car_main.save(db=db)
    new_car_branch = await Node.init(db=db, schema="TestCar", branch=branch_2)
    await new_car_branch.new(db=db, name="Thunderbolt", nbr_seats=4, is_electric=True, owner=person_john_main)
    await new_car_branch.save(db=db)
    schema = registry.schema.get(name="TestCar", branch=default_branch)

    query = await NodeUniqueAttributeConstraintQuery.init(db=db, branch=branch_2, schema=schema)
    query_result = await query.execute(db=db)

    assert len(query_result.results) == 1
    assert query_result.results[0].data["kind"] == "TestCar"
    assert set(query_result.results[0].data["node_ids"]) == {new_car_main.id, new_car_branch.id}
    assert query_result.results[0].data["node_count"] == 2
    assert query_result.results[0].data["attr_name"] == "name"
    assert query_result.results[0].data["attr_value"] == "Thunderbolt"


async def test_query_uniqueness_multiple_attribute_violations(
    db: InfrahubDatabase,
    car_accord_main,
    car_prius_main,
    car_volt_main,
    car_camry_main,
    branch: Branch,
):
    for car_id in (car_volt_main.id, car_camry_main.id):
        car_to_update = await NodeManager.get_one(id=car_id, db=db, branch=branch)
        car_to_update.color.value = "#ffffff"
        await car_to_update.save(db=db)

    schema = registry.schema.get(name="TestCar", branch=branch)
    schema.get_attribute("nbr_seats").unique = True
    schema.get_attribute("color").unique = True
    expected_result_dicts = [
        {
            "kind": "TestCar",
            "attr_name": "nbr_seats",
            "node_ids": {car_accord_main.id, car_prius_main.id, car_camry_main.id},
            "node_count": 3,
            "attr_value": 5,
            "relationship_identifier": None,
        },
        {
            "kind": "TestCar",
            "attr_name": "color",
            "node_ids": {car_volt_main.id, car_camry_main.id},
            "node_count": 2,
            "attr_value": "#ffffff",
            "relationship_identifier": None,
        },
        {
            "kind": "TestCar",
            "attr_name": "color",
            "node_ids": {car_accord_main.id, car_prius_main.id},
            "node_count": 2,
            "attr_value": "#444444",
            "relationship_identifier": None,
        },
    ]

    query = await NodeUniqueAttributeConstraintQuery.init(db=db, branch=branch, schema=schema)
    query_result = await query.execute(db=db)

    assert len(query_result.results) == 3
    for result in query_result.results:
        serial_result = dict(result.data)
        serial_result["node_ids"] = set(serial_result["node_ids"])
        assert serial_result in expected_result_dicts
