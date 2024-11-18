from random import randint

import pytest

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
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.relationship_schema import RelationshipSchema
from infrahub.database import InfrahubDatabase
from tests.helpers.schema import WIDGET


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


async def test_query_NodeGetListQuery_filter_attribute_isnull(
    db: InfrahubDatabase, person_albert_main, person_alfred_main, person_jane_main, branch: Branch
):
    person_schema = registry.schema.get(name="TestPerson", branch=branch, duplicate=False)
    person_branch = await NodeManager.get_one(db=db, branch=branch, id=person_albert_main.id)
    person_branch.height.value = None
    await person_branch.save(db=db)

    query = await NodeGetListQuery.init(
        db=db,
        branch=branch,
        schema=person_schema,
        filters={"height__isnull": True},
    )
    await query.execute(db=db)
    assert query.get_node_ids() == [person_albert_main.id]

    query = await NodeGetListQuery.init(
        db=db,
        branch=branch,
        schema=person_schema,
        filters={"height__isnull": False},
    )
    await query.execute(db=db)
    assert set(query.get_node_ids()) == {person_alfred_main.id, person_jane_main.id}

    person_branch = await NodeManager.get_one(db=db, branch=branch, id=person_albert_main.id)
    person_branch.height.value = 155
    await person_branch.save(db=db)

    query = await NodeGetListQuery.init(
        db=db,
        branch=branch,
        schema=person_schema,
        filters={"height__isnull": True},
    )
    await query.execute(db=db)
    assert query.get_node_ids() == []

    query = await NodeGetListQuery.init(
        db=db,
        branch=branch,
        schema=person_schema,
        filters={"height__isnull": False},
    )
    await query.execute(db=db)
    assert set(query.get_node_ids()) == {person_albert_main.id, person_alfred_main.id, person_jane_main.id}


async def test_query_NodeGetListQuery_filter_relationship_isnull_one(
    db: InfrahubDatabase, car_accord_main, car_camry_main, car_volt_main, person_jane_main, branch: Branch
):
    car_schema = registry.schema.get(name="TestCar", branch=branch, duplicate=False)
    owner_rel = car_schema.get_relationship(name="owner")
    owner_rel.optional = True
    car_branch = await NodeManager.get_one(db=db, branch=branch, id=car_camry_main.id)
    await car_branch.owner.update(db=db, data=[None])
    await car_branch.save(db=db)

    query = await NodeGetListQuery.init(
        db=db,
        branch=branch,
        schema=car_schema,
        filters={"owner__isnull": True},
    )
    await query.execute(db=db)
    assert query.get_node_ids() == [car_camry_main.id]

    query = await NodeGetListQuery.init(
        db=db,
        branch=branch,
        schema=car_schema,
        filters={"owner__isnull": False},
    )
    await query.execute(db=db)
    assert set(query.get_node_ids()) == {car_accord_main.id, car_volt_main.id}

    car_branch = await NodeManager.get_one(db=db, branch=branch, id=car_camry_main.id)
    await car_branch.owner.update(db=db, data=person_jane_main)
    await car_branch.save(db=db)

    query = await NodeGetListQuery.init(
        db=db,
        branch=branch,
        schema=car_schema,
        filters={"owner__isnull": True},
    )
    await query.execute(db=db)
    assert query.get_node_ids() == []

    query = await NodeGetListQuery.init(
        db=db,
        branch=branch,
        schema=car_schema,
        filters={"owner__isnull": False},
    )
    await query.execute(db=db)
    assert set(query.get_node_ids()) == {car_camry_main.id, car_accord_main.id, car_volt_main.id}


async def test_query_NodeGetListQuery_filter_relationship_isnull_many(
    db: InfrahubDatabase,
    car_accord_main,
    car_camry_main,
    person_albert_main,
    person_alfred_main,
    person_jane_main,
    person_john_main,
    branch: Branch,
):
    person_schema = registry.schema.get(name="TestPerson", branch=branch)
    person_schema.order_by = ["name__value"]
    car_branch = await NodeManager.get_one(db=db, branch=branch, id=car_camry_main.id)
    await car_branch.owner.update(db=db, data=person_albert_main)
    await car_branch.save(db=db)

    query = await NodeGetListQuery.init(
        db=db,
        branch=branch,
        schema=person_schema,
        filters={"cars__isnull": True},
    )
    await query.execute(db=db)
    assert query.get_node_ids() == [person_alfred_main.id, person_jane_main.id]

    query = await NodeGetListQuery.init(
        db=db,
        branch=branch,
        schema=person_schema,
        filters={"cars__isnull": False},
    )
    await query.execute(db=db)
    assert query.get_node_ids() == [person_albert_main.id, person_john_main.id]


async def test_query_NodeGetListQuery_filter_relationship_attribute_isnull_not_allowed(
    db: InfrahubDatabase, car_person_schema, default_branch
):
    car_schema = registry.schema.get(name="TestCar", branch=default_branch, duplicate=False)

    with pytest.raises(RuntimeError, match=r"owner__height__isnull is not allowed"):
        await NodeGetListQuery.init(
            db=db,
            branch=default_branch,
            schema=car_schema,
            filters={"owner__height__isnull": True},
        )


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
    car_accord = await NodeManager.get_one(db=db, branch=branch, id=car_accord_main.id)
    await car_accord.owner.update(db=db, data=person_jane_main)
    await car_accord.save(db=db)

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
    db: InfrahubDatabase, car_accord_main, car_camry_main, car_volt_main, car_yaris_main, branch: Branch
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


async def test_query_NodeGetListQuery_order_by_relationship_value_with_update(
    db: InfrahubDatabase,
    person_john_main,
    person_jane_main,
    car_accord_main,
    car_camry_main,
    car_volt_main,
    car_yaris_main,
    branch: Branch,
):
    schema = registry.schema.get(name="TestCar", branch=branch, duplicate=False)
    schema.relationships.append(
        RelationshipSchema(
            name="other_car",
            peer="TestCar",
            cardinality=RelationshipCardinality.ONE,
            identifier="testcar__other_car",
            branch=BranchSupportType.AWARE,
        )
    )
    schema.order_by = ["other_car__name__value"]

    accord = await NodeManager.get_one(db=db, branch=branch, id=car_accord_main.id)
    await accord.other_car.update(db=db, data=car_camry_main)
    await accord.save(db=db)
    # update related value to ZZZ
    camry = await NodeManager.get_one(db=db, branch=branch, id=car_camry_main.id)
    camry.name.value = "zzz"
    await camry.save(db=db)
    volt = await NodeManager.get_one(db=db, branch=branch, id=car_volt_main.id)
    await volt.other_car.update(db=db, data=car_yaris_main)
    await volt.save(db=db)
    # update related value to AAA
    yaris = await NodeManager.get_one(db=db, branch=branch, id=car_yaris_main.id)
    yaris.name.value = "aaa"
    await yaris.save(db=db)
    # delete relationship, so related value is effectively null
    volt = await NodeManager.get_one(db=db, branch=branch, id=car_volt_main.id)
    await volt.other_car.update(db=db, data=None)
    await volt.save(db=db)

    query = await NodeGetListQuery.init(
        db=db,
        branch=branch,
        schema=schema,
    )
    await query.execute(db=db)

    retrieved_node_ids = query.get_node_ids()
    assert len(retrieved_node_ids) == 4
    assert retrieved_node_ids[0] == car_camry_main.id  # accord
    assert retrieved_node_ids[1] == car_accord_main.id  # zzz
    # null ones can be any order
    assert set(retrieved_node_ids[2:]) == {car_yaris_main.id, car_volt_main.id}


async def test_query_NodeGetListQuery_filter_with_profiles(
    db: InfrahubDatabase, person_john_main, person_jim_main, person_albert_main, person_alfred_main, branch: Branch
):
    profile_schema = registry.schema.get("ProfileTestPerson", branch=branch, duplicate=False)
    person_profile = await Node.init(db=db, schema=profile_schema, branch=branch)
    await person_profile.new(db=db, profile_name="person_profile_1", height=172, profile_priority=1001)
    await person_profile.save(db=db)
    person_profile_2 = await Node.init(db=db, schema=profile_schema, branch=branch)
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


async def test_query_NodeGetListQuery_filter_with_generic_profiles(
    db: InfrahubDatabase, animal_person_schema, default_branch: Branch
):
    animal_profile_schema = registry.schema.get("ProfileTestAnimal", duplicate=False)
    animal_profile = await Node.init(db=db, schema=animal_profile_schema)
    await animal_profile.new(db=db, profile_name="animal_profile", profile_priority=1000, weight=100)
    await animal_profile.save(db=db)
    cat_profile_schema = registry.schema.get("ProfileTestCat", duplicate=False)
    cat_profile = await Node.init(db=db, schema=cat_profile_schema)
    await cat_profile.new(db=db, profile_name="cat_profile", profile_priority=1001, weight=10)
    await cat_profile.save(db=db)
    dog_profile_schema = registry.schema.get("ProfileTestDog", duplicate=False)
    dog_profile = await Node.init(db=db, schema=dog_profile_schema)
    await dog_profile.new(db=db, profile_name="dog_profile", profile_priority=1002, weight=50)
    await dog_profile.save(db=db)
    person_schema = registry.schema.get("TestPerson", duplicate=False)
    person = await Node.init(db=db, schema=person_schema)
    await person.new(db=db, name="Ernest")
    await person.save(db=db)
    dog_schema = registry.schema.get("TestDog", duplicate=False)
    big_dog = await Node.init(db=db, schema=dog_schema)
    await big_dog.new(db=db, name="bigdog", breed="mixed", owner=person, profiles=[animal_profile, dog_profile])
    await big_dog.save(db=db)
    medium_dog = await Node.init(db=db, schema=dog_schema)
    await medium_dog.new(db=db, name="mediumdog", breed="mixed", owner=person, profiles=[dog_profile])
    await medium_dog.save(db=db)
    cat_schema = registry.schema.get("TestCat", duplicate=False)
    gigantic_cat = await Node.init(db=db, schema=cat_schema)
    await gigantic_cat.new(
        db=db, name="giganticcat", breed="orange", owner=person, profiles=[cat_profile, animal_profile]
    )
    await gigantic_cat.save(db=db)
    small_cat = await Node.init(db=db, schema=cat_schema)
    await small_cat.new(db=db, name="smallcat", breed="orange", owner=person, weight=7)
    await small_cat.save(db=db)
    animal_schema = registry.schema.get("TestAnimal", duplicate=False)

    animal_profile_query = await NodeGetListQuery.init(
        db=db, schema=animal_schema, branch=default_branch, filters={"weight__value": 100}
    )
    await animal_profile_query.execute(db=db)
    assert set(animal_profile_query.get_node_ids()) == {big_dog.id, gigantic_cat.id}
    medium_dog_query = await NodeGetListQuery.init(
        db=db, schema=animal_schema, branch=default_branch, filters={"weight__value": 50}
    )
    await medium_dog_query.execute(db=db)
    assert medium_dog_query.get_node_ids() == [medium_dog.id]
    small_cat_query = await NodeGetListQuery.init(
        db=db, schema=animal_schema, branch=default_branch, filters={"weight__value": 7}
    )
    await small_cat_query.execute(db=db)
    assert small_cat_query.get_node_ids() == [small_cat.id]


async def test_query_NodeGetListQuery_order_with_profiles(
    db: InfrahubDatabase, car_camry_main, car_accord_main, car_volt_main, branch: Branch
):
    profile_schema = registry.schema.get("ProfileTestCar", branch=branch, duplicate=False)
    car_profile_black = await Node.init(db=db, schema=profile_schema, branch=branch)
    await car_profile_black.new(db=db, profile_name="car_profile_black", color="#000000", profile_priority=1001)
    await car_profile_black.save(db=db)
    car_profile_white = await Node.init(db=db, schema=profile_schema, branch=branch)
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
    default_branch: Branch,
    car_camry_main,
    car_accord_main,
    car_volt_main,
    branch: Branch,
):
    profile_schema = registry.schema.get("ProfileTestCar", branch=branch, duplicate=False)
    car_profile_black = await Node.init(db=db, schema=profile_schema, branch=branch)
    await car_profile_black.new(db=db, profile_name="car_profile_black", color="#000000", profile_priority=1001)
    await car_profile_black.save(db=db)
    car_profile_white = await Node.init(db=db, schema=profile_schema, branch=branch)
    await car_profile_white.new(db=db, profile_name="car_profile_white", color="#ffffff", profile_priority=1002)
    await car_profile_white.save(db=db)
    await branch.rebase(db=db)

    car_schema = registry.schema.get("TestCar", branch=branch, duplicate=False)
    car = await NodeManager.get_one(db=db, id=car_camry_main.id, branch=branch)
    await car.profiles.update(data=[car_profile_white], db=db)
    await car.save(db=db)
    car = await NodeManager.get_one(db=db, id=car_accord_main.id, branch=branch)
    await car.profiles.update(data=[car_profile_black], db=db)
    await car.save(db=db)
    car = await NodeManager.get_one(db=db, id=car_volt_main.id, branch=branch)
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
):
    profile_schema = registry.schema.get("ProfileTestCar", branch=branch, duplicate=False)
    car_profile_black = await Node.init(db=db, schema=profile_schema, branch=branch)
    await car_profile_black.new(db=db, profile_name="car_profile_black", color="#000000", profile_priority=1001)
    await car_profile_black.save(db=db)
    car_profile_white = await Node.init(db=db, schema=profile_schema, branch=branch)
    await car_profile_white.new(db=db, profile_name="car_profile_white", color="#ffffff", profile_priority=1002)
    await car_profile_white.save(db=db)
    car_schema = registry.schema.get("TestCar", branch=branch, duplicate=False)
    car = await NodeManager.get_one(db=db, id=car_camry_main.id, branch=branch)
    await car.profiles.update(data=[car_profile_white], db=db)
    await car.save(db=db)
    car = await NodeManager.get_one(db=db, id=car_accord_main.id, branch=branch)
    await car.profiles.update(data=[car_profile_black], db=db)
    await car.save(db=db)
    car = await NodeManager.get_one(db=db, id=car_volt_main.id, branch=branch)
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


async def test_query_NodeGetListQuery_multiple_profiles_same_priority_filter_and_order(
    db: InfrahubDatabase,
    car_camry_main,
    car_accord_main,
    branch: Branch,
):
    profile_schema = registry.schema.get("ProfileTestCar", branch=branch, duplicate=False)
    profiles_group_1 = []
    expected_profile_1 = None
    for i in range(10):
        car_profile = await Node.init(db=db, schema=profile_schema, branch=branch)
        await car_profile.new(
            db=db, profile_name=f"car_profile_{i}", color=f"#{randint(100000, 499999)}", profile_priority=1000
        )
        await car_profile.save(db=db)
        if not expected_profile_1 or car_profile.id < expected_profile_1.id:
            expected_profile_1 = car_profile
            profiles_group_1.append(car_profile)
    profiles_group_2 = []
    expected_profile_2 = None
    for i in range(10, 20):
        car_profile = await Node.init(db=db, schema=profile_schema, branch=branch)
        await car_profile.new(
            db=db, profile_name=f"car_profile_{i}", color=f"#{randint(500000, 999999)}", profile_priority=1000
        )
        await car_profile.save(db=db)
        if not expected_profile_2 or car_profile.id < expected_profile_2.id:
            expected_profile_2 = car_profile
            profiles_group_2.append(car_profile)
    car_schema = registry.schema.get("TestCar", branch=branch, duplicate=False)
    car_schema.order_by = ["color__value"]
    car = await NodeManager.get_one(db=db, id=car_camry_main.id, branch=branch)
    await car.profiles.update(data=profiles_group_1, db=db)
    await car.save(db=db)
    car = await NodeManager.get_one(db=db, id=car_accord_main.id, branch=branch)
    await car.profiles.update(data=profiles_group_2, db=db)
    await car.save(db=db)

    query = await NodeGetListQuery.init(
        db=db, branch=branch, schema=car_schema, filters={"color__value": expected_profile_1.color.value}
    )
    await query.execute(db=db)
    assert query.get_node_ids() == [car_camry_main.id]
    query = await NodeGetListQuery.init(
        db=db, branch=branch, schema=car_schema, filters={"color__value": expected_profile_2.color.value}
    )
    await query.execute(db=db)
    assert query.get_node_ids() == [car_accord_main.id]
    query = await NodeGetListQuery.init(db=db, branch=branch, schema=car_schema)
    await query.execute(db=db)
    assert query.get_node_ids() == [car_camry_main.id, car_accord_main.id]


async def test_query_NodeGetListQuery_pagination_order_by(
    db: InfrahubDatabase, default_branch: Branch, node_group_schema
):
    """Validate that pagination works for nodes which have an order_by clause on non unique attributes."""
    schema_root = SchemaRoot(nodes=[WIDGET])

    registry.schema.register_schema(schema=schema_root, branch=default_branch.name)

    widget_schema = registry.schema.get_node_schema("TestingWidget", branch=default_branch, duplicate=False)

    for i in range(20):
        car_profile = await Node.init(db=db, schema=widget_schema, branch=default_branch)
        await car_profile.new(db=db, name="top-widget", description=f"widget index {i}")
        await car_profile.save(db=db)

    node_ids = set()
    for offset in range(0, 19, 2):
        query = await NodeGetListQuery.init(db=db, branch=default_branch, schema=widget_schema, limit=2, offset=offset)
        await query.execute(db=db)

        result_ids = query.get_node_ids()
        node_ids.update(result_ids)

    # If we don't get 20 results it means that the pagination is returning the same node multiple times
    assert len(node_ids) == 20
    # Validate that the order_by clause hasn't changed on the test schema which would defeat the purpose of this test
    assert widget_schema.order_by == ["name__value"]
