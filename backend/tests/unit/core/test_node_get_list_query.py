from infrahub.core.branch import Branch
from infrahub.core.constants import (
    BranchSupportType,
    InfrahubKind,
    RelationshipCardinality,
    RelationshipDirection,
)
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.query.node import NodeGetListQuery
from infrahub.core.registry import registry
from infrahub.core.schema.relationship_schema import RelationshipSchema
from infrahub.database import InfrahubDatabase


async def test_query_NodeGetListQuery(
    db: InfrahubDatabase, person_john_main, person_jim_main, person_albert_main, person_alfred_main, branch: Branch
):
    person_schema = registry.schema.get(name="TestPerson", branch=branch)
    ids = [person_john_main.id, person_jim_main.id, person_albert_main.id, person_alfred_main.id]
    query = await NodeGetListQuery.init(db=db, branch=branch, schema=person_schema)
    await query.execute(db=db)
    assert sorted(query.get_node_ids()) == sorted(ids)


async def test_query_NodeGetListQuery_filter_id(
    db: InfrahubDatabase, person_john_main, person_jim_main, person_albert_main, person_alfred_main, branch: Branch
):
    person_schema = registry.schema.get(name="TestPerson", branch=branch)
    query = await NodeGetListQuery.init(db=db, branch=branch, schema=person_schema, filters={"id": person_john_main.id})
    await query.execute(db=db)
    assert len(query.get_node_ids()) == 1


async def test_query_NodeGetListQuery_filter_ids(
    db: InfrahubDatabase, person_john_main, person_jim_main, person_albert_main, person_alfred_main, branch: Branch
):
    person_schema = registry.schema.get(name="TestPerson", branch=branch)
    person_schema.order_by = ["height__value"]
    query = await NodeGetListQuery.init(
        db=db,
        branch=branch,
        schema=person_schema,
        filters={"ids": [person_jim_main.id, person_john_main.id, person_albert_main.id]},
    )
    await query.execute(db=db)
    assert query.get_node_ids() == [person_albert_main.id, person_jim_main.id, person_john_main.id]


async def test_query_NodeGetListQuery_filter_height(
    db: InfrahubDatabase, person_john_main, person_jim_main, person_albert_main, person_alfred_main, branch: Branch
):
    schema = registry.schema.get(name="TestPerson", branch=branch)
    query = await NodeGetListQuery.init(db=db, branch=branch, schema=schema, filters={"height__value": 160})
    await query.execute(db=db)
    assert len(query.get_node_ids()) == 2


async def test_query_NodeGetListQuery_filter_owner(
    db: InfrahubDatabase, default_branch: Branch, person_john_main: Node, first_account: Node, branch: Branch
):
    person = await Node.init(db=db, schema="TestPerson", branch=branch)
    await person.new(db=db, name={"value": "Diane", "owner": first_account.id}, height=165)
    await person.save(db=db)

    schema = registry.schema.get(name="TestPerson", branch=branch)
    query = await NodeGetListQuery.init(
        db=db, branch=branch, schema=schema, filters={"any__owner__id": first_account.id}
    )
    await query.execute(db=db)
    assert len(query.get_node_ids()) == 1

    schema = registry.schema.get(name="TestPerson", branch=branch)
    query = await NodeGetListQuery.init(
        db=db, branch=branch, schema=schema, filters={"name__owner__id": first_account.id}
    )
    await query.execute(db=db)
    assert len(query.get_node_ids()) == 1

    schema = registry.schema.get(name="TestPerson", branch=branch)
    query = await NodeGetListQuery.init(
        db=db, branch=branch, schema=schema, filters={"height__owner__id": first_account.id}
    )
    await query.execute(db=db)
    assert len(query.get_node_ids()) == 0


async def test_query_NodeGetListQuery_filter_boolean(
    db: InfrahubDatabase, car_accord_main, car_camry_main, car_volt_main, car_yaris_main, branch: Branch
):
    schema = registry.schema.get(name="TestCar", branch=branch)
    query = await NodeGetListQuery.init(db=db, branch=branch, schema=schema, filters={"is_electric__value": False})
    await query.execute(db=db)
    assert len(query.get_node_ids()) == 3


async def test_query_NodeGetListQuery_deleted_node(
    db: InfrahubDatabase, car_accord_main, car_camry_main: Node, car_volt_main, car_yaris_main, branch: Branch
):
    node_to_delete = await NodeManager.get_one(id=car_camry_main.id, db=db, branch=branch)
    await node_to_delete.delete(db=db)

    schema = registry.schema.get(name="TestCar", branch=branch)
    schema.order_by = ["owner__name__value"]

    query = await NodeGetListQuery.init(db=db, branch=branch, schema=schema, filters={"is_electric__value": False})
    await query.execute(db=db)
    assert len(query.get_node_ids()) == 2


async def test_query_NodeGetListQuery_filter_relationship(
    db: InfrahubDatabase, car_accord_main, car_camry_main, car_volt_main, car_yaris_main, branch: Branch
):
    schema = registry.schema.get(name="TestCar", branch=branch)
    query = await NodeGetListQuery.init(db=db, branch=branch, schema=schema, filters={"owner__name__value": "John"})
    await query.execute(db=db)
    assert len(query.get_node_ids()) == 2


async def test_query_NodeGetListQuery_filter_relationship_ids(
    db: InfrahubDatabase,
    person_john_main,
    car_accord_main,
    car_camry_main,
    car_volt_main,
    car_yaris_main,
    branch: Branch,
):
    schema = registry.schema.get(name="TestCar", branch=branch)
    query = await NodeGetListQuery.init(
        db=db, branch=branch, schema=schema, filters={"owner__ids": [person_john_main.id]}
    )
    await query.execute(db=db)
    assert len(query.get_node_ids()) == 2


async def test_query_NodeGetListQuery_filter_relationship_ids_with_update(
    db: InfrahubDatabase,
    person_john_main,
    person_jane_main,
    car_accord_main,
    car_camry_main,
    car_volt_main,
    car_yaris_main,
    branch: Branch,
):
    schema = registry.schema.get(name="TestCar", branch=branch)
    await car_accord_main.owner.update(db=db, data=person_jane_main)
    await car_accord_main.save(db=db)

    query = await NodeGetListQuery.init(
        db=db, branch=branch, schema=schema, filters={"owner__ids": [person_john_main.id]}
    )
    await query.execute(db=db)
    node_ids = query.get_node_ids()
    assert node_ids == [car_volt_main.id]


async def test_query_NodeGetListQuery_filter_and_sort(
    db: InfrahubDatabase, car_accord_main, car_camry_main, car_volt_main, car_yaris_main, branch: Branch
):
    schema = registry.schema.get(name="TestCar", branch=branch)
    schema.order_by = ["owner__name__value", "is_electric__value"]

    query = await NodeGetListQuery.init(
        db=db,
        branch=branch,
        schema=schema,
        filters={"owner__name__value": "John", "is_electric__value": False},
    )
    await query.execute(db=db)
    assert len(query.get_node_ids()) == 1


async def test_query_NodeGetListQuery_filter_and_sort_with_revision(
    db: InfrahubDatabase, car_accord_main, car_camry_main, car_volt_main, car_yaris_main, branch: Branch
):
    node = await NodeManager.get_one(id=car_volt_main.id, db=db, branch=branch)
    node.is_electric.value = False
    await node.save(db=db)

    schema = registry.schema.get(name="TestCar", branch=branch)
    schema.order_by = ["owner__name__value", "is_electric__value"]

    query = await NodeGetListQuery.init(
        db=db,
        branch=branch,
        schema=schema,
        filters={"owner__name__value": "John", "is_electric__value": False},
    )
    await query.execute(db=db)
    assert len(query.get_node_ids()) == 2


async def test_query_NodeGetListQuery_with_generics(db: InfrahubDatabase, group_group1_main, branch: Branch):
    schema = registry.schema.get(name=InfrahubKind.GENERICGROUP, branch=branch)
    query = await NodeGetListQuery.init(
        db=db,
        branch=branch,
        schema=schema,
    )
    await query.execute(db=db)
    assert query.get_node_ids() == [group_group1_main.id]


async def test_query_NodeGetListQuery_order_by(
    db: InfrahubDatabase, car_accord_main, car_camry_main, car_volt_main, car_yaris_main, branch: Branch
):
    schema = registry.schema.get(name="TestCar", branch=branch)
    schema.order_by = ["owner__name__value", "name__value"]

    query = await NodeGetListQuery.init(
        db=db,
        branch=branch,
        schema=schema,
    )
    await query.execute(db=db)
    assert query.get_node_ids() == [car_camry_main.id, car_yaris_main.id, car_accord_main.id, car_volt_main.id]


async def test_query_NodeGetListQuery_order_by_optional_relationship_nulls(
    db: InfrahubDatabase, branch: Branch, car_accord_main, car_camry_main, car_volt_main, car_yaris_main
):
    schema = registry.schema.get(name="TestCar", branch=branch, duplicate=False)
    schema.relationships.append(
        RelationshipSchema(
            name="other_car",
            peer="TestCar",
            cardinality=RelationshipCardinality.ONE,
            identifier="testcar__other_car",
            branch=BranchSupportType.AWARE,
            direction=RelationshipDirection.OUTBOUND,
        )
    )
    schema.order_by = ["other_car__name__value"]

    accord = await NodeManager.get_one(db=db, branch=branch, id=car_accord_main.id)
    await accord.other_car.update(db=db, data=car_camry_main)
    await accord.save(db=db)
    volt = await NodeManager.get_one(db=db, branch=branch, id=car_volt_main.id)
    await volt.other_car.update(db=db, data=car_yaris_main)
    await volt.save(db=db)

    query = await NodeGetListQuery.init(
        db=db,
        branch=branch,
        schema=schema,
    )
    await query.execute(db=db)

    retrieved_node_ids = query.get_node_ids()
    assert len(retrieved_node_ids) == 4
    assert retrieved_node_ids[0] == car_accord_main.id
    assert retrieved_node_ids[1] == car_volt_main.id
    # null ones can be any order
    assert set(retrieved_node_ids[2:]) == {car_camry_main.id, car_yaris_main.id}


async def test_query_NodeGetListQuery_filter_with_profiles(
    db: InfrahubDatabase, person_john_main, person_jim_main, person_albert_main, person_alfred_main, branch: Branch
):
    profile_schema = registry.schema.get("ProfileTestPerson", branch=branch, duplicate=False)
    person_profile = await Node.init(db=db, schema=profile_schema)
    await person_profile.new(db=db, profile_name="person_profile_1", height=172, profile_priority=1001)
    await person_profile.save(db=db)
    person_profile_2 = await Node.init(db=db, schema=profile_schema)
    await person_profile_2.new(db=db, profile_name="person_profile_2", height=177, profile_priority=1002)
    await person_profile_2.save(db=db)

    person_schema = registry.schema.get("TestPerson", branch=branch, duplicate=False)
    person_schema.order_by = ["height__value", "name__value"]
    person = await NodeManager.get_one(db=db, id=person_john_main.id, branch=branch)
    person.height.value = None
    person.height.is_default = True
    await person.profiles.update(data=[person_profile, person_profile_2], db=db)
    await person.save(db=db)
    person = await NodeManager.get_one(db=db, id=person_jim_main.id, branch=branch)
    person.height.value = None
    person.height.is_default = True
    await person.profiles.update(data=[person_profile], db=db)
    await person.save(db=db)
    person = await NodeManager.get_one(db=db, id=person_albert_main.id, branch=branch)
    await person.profiles.update(data=[person_profile_2], db=db)
    await person.save(db=db)
    person = await NodeManager.get_one(db=db, id=person_alfred_main.id, branch=branch)
    person.height.value = 172
    await person.save(db=db)

    person_schema = registry.schema.get(name="TestPerson", branch=branch)
    query = await NodeGetListQuery.init(db=db, branch=branch, schema=person_schema, filters={"height__value": 172})

    await query.execute(db=db)

    assert query.get_node_ids() == [person_alfred_main.id, person_jim_main.id, person_john_main.id]


async def test_query_NodeGetListQuery_order_with_profiles(
    db: InfrahubDatabase, car_camry_main, car_accord_main, car_volt_main, branch: Branch
):
    profile_schema = registry.schema.get("ProfileTestCar", branch=branch, duplicate=False)
    car_profile_black = await Node.init(db=db, schema=profile_schema)
    await car_profile_black.new(db=db, profile_name="car_profile_black", color="#000000", profile_priority=1001)
    await car_profile_black.save(db=db)
    car_profile_white = await Node.init(db=db, schema=profile_schema)
    await car_profile_white.new(db=db, profile_name="car_profile_white", color="#ffffff", profile_priority=1002)
    await car_profile_white.save(db=db)

    car_schema = registry.schema.get("TestCar", branch=branch, duplicate=False)
    car_schema.order_by = ["color__value", "name__value"]
    car = await NodeManager.get_one(db=db, id=car_camry_main.id, branch=branch)
    await car.profiles.update(data=[car_profile_white], db=db)
    await car.save(db=db)
    car = await NodeManager.get_one(db=db, id=car_accord_main.id, branch=branch)
    await car.profiles.update(data=[car_profile_black], db=db)
    await car.save(db=db)
    car = await NodeManager.get_one(db=db, id=car_volt_main.id, branch=branch)
    await car.profiles.update(data=[car_profile_black, car_profile_white], db=db)
    await car.save(db=db)

    query = await NodeGetListQuery.init(db=db, branch=branch, schema=car_schema)

    await query.execute(db=db)

    assert query.get_node_ids() == [car_accord_main.id, car_volt_main.id, car_camry_main.id]


async def test_query_NodeGetListQuery_with_profiles_deleted(
    db: InfrahubDatabase,
    car_camry_main,
    car_accord_main,
    car_volt_main,
    branch: Branch,
    default_branch: Branch,
):
    profile_schema = registry.schema.get("ProfileTestCar", branch=branch, duplicate=False)
    car_profile_black = await Node.init(db=db, schema=profile_schema)
    await car_profile_black.new(db=db, profile_name="car_profile_black", color="#000000", profile_priority=1001)
    await car_profile_black.save(db=db)
    car_profile_white = await Node.init(db=db, schema=profile_schema)
    await car_profile_white.new(db=db, profile_name="car_profile_white", color="#ffffff", profile_priority=1002)
    await car_profile_white.save(db=db)
    await branch.rebase(db=db)

    car_schema = registry.schema.get("TestCar", branch=branch, duplicate=False)
    car = await NodeManager.get_one(db=db, id=car_camry_main.id, branch=default_branch)
    await car.profiles.update(data=[car_profile_white], db=db)
    await car.save(db=db)
    car = await NodeManager.get_one(db=db, id=car_accord_main.id, branch=default_branch)
    await car.profiles.update(data=[car_profile_black], db=db)
    await car.save(db=db)
    car = await NodeManager.get_one(db=db, id=car_volt_main.id, branch=default_branch)
    await car.profiles.update(data=[car_profile_black, car_profile_white], db=db)
    await car.save(db=db)

    car_profile_white_branch = await NodeManager.get_one(db=db, id=car_profile_white.id, branch=branch)
    await car_profile_white_branch.delete(db=db)

    query = await NodeGetListQuery.init(db=db, branch=branch, schema=car_schema, filters={"color__value": "#444444"})
    await query.execute(db=db)
    assert query.get_node_ids() == [car_camry_main.id]
    query = await NodeGetListQuery.init(db=db, branch=branch, schema=car_schema, filters={"color__value": "#000000"})
    await query.execute(db=db)
    assert set(query.get_node_ids()) == {car_accord_main.id, car_volt_main.id}
    query = await NodeGetListQuery.init(db=db, branch=branch, schema=car_schema, filters={"color__value": "#ffffff"})
    await query.execute(db=db)
    assert query.get_node_ids() == []


async def test_query_NodeGetListQuery_updated_profile_priorities_on_branch(
    db: InfrahubDatabase,
    car_camry_main,
    car_accord_main,
    car_volt_main,
    branch: Branch,
    default_branch: Branch,
):
    profile_schema = registry.schema.get("ProfileTestCar", branch=branch, duplicate=False)
    car_profile_black = await Node.init(db=db, schema=profile_schema)
    await car_profile_black.new(db=db, profile_name="car_profile_black", color="#000000", profile_priority=1001)
    await car_profile_black.save(db=db)
    car_profile_white = await Node.init(db=db, schema=profile_schema)
    await car_profile_white.new(db=db, profile_name="car_profile_white", color="#ffffff", profile_priority=1002)
    await car_profile_white.save(db=db)
    car_schema = registry.schema.get("TestCar", branch=branch, duplicate=False)
    car = await NodeManager.get_one(db=db, id=car_camry_main.id, branch=default_branch)
    await car.profiles.update(data=[car_profile_white], db=db)
    await car.save(db=db)
    car = await NodeManager.get_one(db=db, id=car_accord_main.id, branch=default_branch)
    await car.profiles.update(data=[car_profile_black], db=db)
    await car.save(db=db)
    car = await NodeManager.get_one(db=db, id=car_volt_main.id, branch=default_branch)
    await car.profiles.update(data=[car_profile_black, car_profile_white], db=db)
    await car.save(db=db)
    await branch.rebase(db=db)

    car_profile_black_branch = await NodeManager.get_one(db=db, branch=branch, id=car_profile_black.id)
    car_profile_black_branch.profile_priority.value = 3000
    await car_profile_black_branch.save(db=db)
    car_profile_white_branch = await NodeManager.get_one(db=db, branch=branch, id=car_profile_white.id)
    car_profile_white_branch.profile_priority.value = 2000
    await car_profile_white_branch.save(db=db)

    query = await NodeGetListQuery.init(db=db, branch=branch, schema=car_schema, filters={"color__value": "#444444"})
    await query.execute(db=db)
    assert query.get_node_ids() == []
    query = await NodeGetListQuery.init(db=db, branch=branch, schema=car_schema, filters={"color__value": "#000000"})
    await query.execute(db=db)
    assert query.get_node_ids() == [car_accord_main.id]
    query = await NodeGetListQuery.init(db=db, branch=branch, schema=car_schema, filters={"color__value": "#ffffff"})
    await query.execute(db=db)
    assert set(query.get_node_ids()) == {car_camry_main.id, car_volt_main.id}


async def test_query_NodeGetListQuery_updated_profile_attributes_on_branch(
    db: InfrahubDatabase,
    car_camry_main,
    car_accord_main,
    car_volt_main,
    branch: Branch,
    default_branch: Branch,
):
    profile_schema = registry.schema.get("ProfileTestCar", branch=branch, duplicate=False)
    car_profile_black = await Node.init(db=db, schema=profile_schema)
    await car_profile_black.new(db=db, profile_name="car_profile_black", color="#000000", profile_priority=1001)
    await car_profile_black.save(db=db)
    car_profile_white = await Node.init(db=db, schema=profile_schema)
    await car_profile_white.new(db=db, profile_name="car_profile_white", color="#ffffff", profile_priority=1002)
    await car_profile_white.save(db=db)
    car_schema = registry.schema.get("TestCar", branch=branch, duplicate=False)
    car = await NodeManager.get_one(db=db, id=car_camry_main.id, branch=default_branch)
    await car.profiles.update(data=[car_profile_white], db=db)
    await car.save(db=db)
    car = await NodeManager.get_one(db=db, id=car_accord_main.id, branch=default_branch)
    await car.profiles.update(data=[car_profile_black], db=db)
    await car.save(db=db)
    car = await NodeManager.get_one(db=db, id=car_volt_main.id, branch=default_branch)
    await car.profiles.update(data=[car_profile_black, car_profile_white], db=db)
    await car.save(db=db)
    await branch.rebase(db=db)

    car_profile_black_branch = await NodeManager.get_one(db=db, branch=branch, id=car_profile_black.id)
    car_profile_black_branch.color.value = "#000001"
    await car_profile_black_branch.save(db=db)
    car_profile_white_branch = await NodeManager.get_one(db=db, branch=branch, id=car_profile_white.id)
    car_profile_white_branch.color.value = "#fffffe"
    await car_profile_white_branch.save(db=db)

    query = await NodeGetListQuery.init(db=db, branch=branch, schema=car_schema, filters={"color__value": "#444444"})
    await query.execute(db=db)
    assert query.get_node_ids() == []
    query = await NodeGetListQuery.init(db=db, branch=branch, schema=car_schema, filters={"color__value": "#000000"})
    await query.execute(db=db)
    assert query.get_node_ids() == []
    query = await NodeGetListQuery.init(db=db, branch=branch, schema=car_schema, filters={"color__value": "#ffffff"})
    await query.execute(db=db)
    assert query.get_node_ids() == []
    query = await NodeGetListQuery.init(db=db, branch=branch, schema=car_schema, filters={"color__value": "#000001"})
    await query.execute(db=db)
    assert set(query.get_node_ids()) == {car_accord_main.id, car_volt_main.id}
    query = await NodeGetListQuery.init(db=db, branch=branch, schema=car_schema, filters={"color__value": "#fffffe"})
    await query.execute(db=db)
    assert query.get_node_ids() == [car_camry_main.id]


async def test_query_NodeGetListQuery_updated_profile_attributes_nulled_on_branch(
    db: InfrahubDatabase,
    car_camry_main,
    car_accord_main,
    car_volt_main,
    branch: Branch,
    default_branch: Branch,
):
    profile_schema = registry.schema.get("ProfileTestCar", branch=branch, duplicate=False)
    car_profile_black = await Node.init(db=db, schema=profile_schema)
    await car_profile_black.new(db=db, profile_name="car_profile_black", color="#000000", profile_priority=1001)
    await car_profile_black.save(db=db)
    car_profile_white = await Node.init(db=db, schema=profile_schema)
    await car_profile_white.new(db=db, profile_name="car_profile_white", color="#ffffff", profile_priority=1002)
    await car_profile_white.save(db=db)
    car_schema = registry.schema.get("TestCar", branch=branch, duplicate=False)
    car = await NodeManager.get_one(db=db, id=car_camry_main.id, branch=default_branch)
    await car.profiles.update(data=[car_profile_white], db=db)
    await car.save(db=db)
    car = await NodeManager.get_one(db=db, id=car_accord_main.id, branch=default_branch)
    await car.profiles.update(data=[car_profile_black], db=db)
    await car.save(db=db)
    car = await NodeManager.get_one(db=db, id=car_volt_main.id, branch=default_branch)
    await car.profiles.update(data=[car_profile_black, car_profile_white], db=db)
    await car.save(db=db)
    await branch.rebase(db=db)

    car_profile_black_branch = await NodeManager.get_one(db=db, branch=branch, id=car_profile_black.id)
    car_profile_black_branch.color.value = None
    await car_profile_black_branch.save(db=db)

    query = await NodeGetListQuery.init(db=db, branch=branch, schema=car_schema, filters={"color__value": "#444444"})
    await query.execute(db=db)
    assert query.get_node_ids() == [car_accord_main.id]
    query = await NodeGetListQuery.init(db=db, branch=branch, schema=car_schema, filters={"color__value": "#000000"})
    await query.execute(db=db)
    assert query.get_node_ids() == []
    query = await NodeGetListQuery.init(db=db, branch=branch, schema=car_schema, filters={"color__value": "#ffffff"})
    await query.execute(db=db)
    assert set(query.get_node_ids()) == {car_camry_main.id, car_volt_main.id}
