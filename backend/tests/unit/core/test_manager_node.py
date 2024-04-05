import pytest
from infrahub_sdk import UUIDT

from infrahub.core.branch import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager, identify_node_class
from infrahub.core.node import Node
from infrahub.core.query.node import NodeToProcess
from infrahub.core.registry import registry
from infrahub.core.schema import NodeSchema
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase


async def test_get_one_attribute(db: InfrahubDatabase, default_branch: Branch, criticality_schema):
    obj1 = await Node.init(db=db, schema=criticality_schema)
    await obj1.new(db=db, name="low", level=4)
    await obj1.save(db=db)
    obj2 = await Node.init(db=db, schema=criticality_schema)
    await obj2.new(db=db, name="medium", level=3, description="My desc", color="#333333")
    await obj2.save(db=db)

    obj = await NodeManager.get_one(db=db, id=obj2.id)

    assert obj.id == obj2.id
    assert obj.db_id == obj2.db_id
    assert obj.name.value == "medium"
    assert obj.name.id
    assert obj.level.value == 3
    assert obj.level.id
    assert obj.description.value == "My desc"
    assert obj.description.id
    assert obj.color.value == "#333333"
    assert obj.color.id

    obj = await NodeManager.get_one(db=db, id=obj1.id)

    assert obj.id == obj1.id
    assert obj.db_id == obj1.db_id
    assert obj.name.value == "low"
    assert obj.name.id
    assert obj.level.value == 4
    assert obj.level.id
    assert obj.description.value is None
    assert obj.description.id
    assert obj.color.value == "#444444"
    assert obj.color.id


async def test_get_one_attribute_with_node_property(
    db: InfrahubDatabase, default_branch, criticality_schema, first_account, second_account
):
    obj1 = await Node.init(db=db, schema=criticality_schema)
    await obj1.new(db=db, name="low", level=4, _source=first_account)
    await obj1.save(db=db)
    obj2 = await Node.init(db=db, schema=criticality_schema)
    await obj2.new(
        db=db,
        name="medium",
        level={"value": 3, "source": second_account.id},
        description="My desc",
        color="#333333",
        _source=first_account,
    )
    await obj2.save(db=db)

    obj = await NodeManager.get_one(db=db, id=obj2.id, include_source=True)

    assert obj.id == obj2.id
    assert obj.db_id == obj2.db_id
    assert obj.name.value == "medium"
    assert obj.name.id
    assert obj.name.source_id == first_account.id
    assert obj.level.value == 3
    assert obj.level.id
    assert obj.level.source_id == second_account.id
    assert obj.description.value == "My desc"
    assert obj.description.id
    assert obj.description.source_id == first_account.id
    assert obj.color.value == "#333333"
    assert obj.color.id
    assert obj.color.source_id == first_account.id


async def test_get_one_attribute_with_flag_property(
    db: InfrahubDatabase, default_branch, criticality_schema, first_account, second_account
):
    obj1 = await Node.init(db=db, schema=criticality_schema)
    await obj1.new(db=db, name={"value": "low", "is_protected": True}, level={"value": 4, "is_visible": False})
    await obj1.save(db=db)

    obj = await NodeManager.get_one(db=db, id=obj1.id, fields={"name": True, "level": True, "color": True})

    assert obj.id == obj1.id
    assert obj.db_id == obj1.db_id
    assert obj.name.value == "low"
    assert obj.name.id
    assert obj.name.is_visible is True
    assert obj.name.is_protected is True

    assert obj.level.value == 4
    assert obj.level.id
    assert obj.level.is_visible is False
    assert obj.level.is_protected is False

    assert obj.color.value == "#444444"
    assert obj.color.id
    assert obj.color.is_visible is True
    assert obj.color.is_protected is False


async def test_get_one_relationship(db: InfrahubDatabase, default_branch: Branch, car_person_schema):
    car = registry.schema.get(name="TestCar")
    person = registry.schema.get(name="TestPerson")

    p1 = await Node.init(db=db, schema=person)
    await p1.new(db=db, name="John", height=180)
    await p1.save(db=db)

    c1 = await Node.init(db=db, schema=car)
    await c1.new(db=db, name="volt", nbr_seats=4, is_electric=True, owner=p1)
    await c1.save(db=db)
    c2 = await Node.init(db=db, schema=car)
    await c2.new(db=db, name="accord", nbr_seats=5, is_electric=False, owner=p1.id)
    await c2.save(db=db)

    c11 = await NodeManager.get_one(db=db, id=c1.id)

    assert c11.name.value == "volt"
    assert c11.nbr_seats.value == 4
    assert c11.is_electric.value is True
    c11_peer = await c11.owner.get_peer(db=db)
    assert c11_peer.id == p1.id

    p11 = await NodeManager.get_one(db=db, id=p1.id)
    assert p11.name.value == "John"
    assert p11.height.value == 180
    assert len(list(await p11.cars.get(db=db))) == 2


async def test_get_one_relationship_with_flag_property(db: InfrahubDatabase, default_branch: Branch, car_person_schema):
    p1 = await Node.init(db=db, schema="TestPerson")
    await p1.new(db=db, name="John", height=180)
    await p1.save(db=db)

    c1 = await Node.init(db=db, schema="TestCar")
    await c1.new(
        db=db,
        name="volt",
        nbr_seats=4,
        is_electric=True,
        owner={"id": p1.id, "_relation__is_protected": True, "_relation__is_visible": False},
    )
    await c1.save(db=db)

    c2 = await Node.init(db=db, schema="TestCar")
    await c2.new(
        db=db,
        name="accord",
        nbr_seats=5,
        is_electric=False,
        owner={"id": p1.id, "_relation__is_visible": False},
    )
    await c2.save(db=db)

    c11 = await NodeManager.get_one(db=db, id=c1.id)

    assert c11.name.value == "volt"
    assert c11.nbr_seats.value == 4
    assert c11.is_electric.value is True
    c11_peer = await c11.owner.get_peer(db=db)
    assert c11_peer.id == p1.id
    rel = await c11.owner.get(db=db)
    assert rel.is_visible is False
    assert rel.is_protected is True

    p11 = await NodeManager.get_one(db=db, id=p1.id)
    assert p11.name.value == "John"
    assert p11.height.value == 180

    rels = await p11.cars.get(db=db)
    assert len(rels) == 2
    assert rels[0].is_visible is False
    assert rels[1].is_visible is False


async def test_get_one_by_id_or_default_filter(
    db: InfrahubDatabase,
    default_branch: Branch,
    criticality_schema: NodeSchema,
    criticality_low: Node,
    criticality_medium: Node,
):
    node1 = await NodeManager.get_one_by_id_or_default_filter(
        db=db, id=criticality_low.id, schema_name=criticality_schema.kind
    )
    assert isinstance(node1, Node)
    assert node1.id == criticality_low.id

    node2 = await NodeManager.get_one_by_id_or_default_filter(
        db=db, id=criticality_low.name.value, schema_name=criticality_schema.kind
    )
    assert isinstance(node2, Node)
    assert node2.id == criticality_low.id


async def test_get_many(db: InfrahubDatabase, default_branch: Branch, criticality_low, criticality_medium):
    nodes = await NodeManager.get_many(db=db, ids=[criticality_low.id, criticality_medium.id])
    assert len(nodes) == 2


async def test_get_many_prefetch(db: InfrahubDatabase, default_branch: Branch, person_jack_tags_main):
    nodes = await NodeManager.get_many(db=db, ids=[person_jack_tags_main.id], prefetch_relationships=True)

    assert len(nodes) == 1
    assert nodes[person_jack_tags_main.id]
    tags = await nodes[person_jack_tags_main.id].tags.get(db=db)
    assert len(tags) == 2
    assert tags[0]._peer
    assert tags[1]._peer


async def test_get_many_with_profile(db: InfrahubDatabase, default_branch: Branch, criticality_low, criticality_medium):
    profile_schema = registry.schema.get("ProfileTestCriticality", branch=default_branch)
    crit_profile_1 = await Node.init(db=db, schema=profile_schema)
    await crit_profile_1.new(db=db, profile_name="crit_profile_1", color="green", profile_priority=1001)
    await crit_profile_1.save(db=db)
    crit_profile_2 = await Node.init(db=db, schema=profile_schema)
    await crit_profile_2.new(db=db, profile_name="crit_profile_2", color="blue", profile_priority=1002)
    await crit_profile_2.save(db=db)
    crit_low = await NodeManager.get_one(db=db, id=criticality_low.id, branch=default_branch)
    await crit_low.profiles.update(db=db, data=[crit_profile_1, crit_profile_2])
    await crit_low.save(db=db)

    node_map = await NodeManager.get_many(db=db, ids=[criticality_low.id, criticality_medium.id])
    assert len(node_map) == 2
    assert node_map[criticality_low.id].color.value == "green"
    owner = await node_map[criticality_low.id].color.get_owner(db=db)
    assert owner.id == crit_profile_1.id


async def test_query_no_filter(
    db: InfrahubDatabase,
    default_branch: Branch,
    criticality_schema: NodeSchema,
    criticality_low: Node,
    criticality_medium: Node,
    criticality_high: Node,
):
    nodes = await NodeManager.query(db=db, schema=criticality_schema)
    assert len(nodes) == 3


async def test_query_with_filter_string_int(
    db: InfrahubDatabase,
    default_branch: Branch,
    criticality_schema,
    criticality_low: Node,
    criticality_medium: Node,
    criticality_high: Node,
):
    nodes = await NodeManager.query(db=db, schema=criticality_schema, filters={"color__value": "#333333"})
    assert len(nodes) == 2

    nodes = await NodeManager.query(db=db, schema=criticality_schema, filters={"description__value": "My other desc"})
    assert len(nodes) == 1

    nodes = await NodeManager.query(
        db=db, schema=criticality_schema, filters={"level__value": 3, "color__value": "#333333"}
    )
    assert len(nodes) == 1


async def test_query_filter_with_multiple_values_string_int(
    db: InfrahubDatabase,
    default_branch: Branch,
    criticality_schema,
    criticality_low: Node,
    criticality_medium: Node,
    criticality_high: Node,
):
    nodes = await NodeManager.query(db=db, schema=criticality_schema, filters={"level__values": [2, 3]})
    assert len(nodes) == 2

    nodes = await NodeManager.query(db=db, schema=criticality_schema, filters={"name__values": ["medium", "low"]})
    assert len(nodes) == 2


async def test_query_with_filter_bool_rel(
    db: InfrahubDatabase,
    person_john_main,
    person_jane_main,
    car_accord_main,
    car_volt_main,
    car_yaris_main,
    car_camry_main,
    branch: Branch,
):
    car = registry.schema.get(name="TestCar")

    # Check filter with a boolean
    nodes = await NodeManager.query(db=db, schema=car, branch=branch, filters={"is_electric__value": False})
    assert len(nodes) == 3

    # Check filter with a relationship
    nodes = await NodeManager.query(db=db, schema=car, branch=branch, filters={"owner__name__value": "John"})
    assert len(nodes) == 2


async def test_query_filter_with_multiple_values_rel(
    db: InfrahubDatabase,
    person_john_main,
    person_jane_main,
    car_accord_main,
    car_volt_main,
    car_yaris_main,
    car_camry_main,
    branch: Branch,
):
    car = registry.schema.get(name="TestCar")

    nodes = await NodeManager.query(db=db, schema=car, branch=branch, filters={"owner__name__values": ["John", "Jane"]})
    assert len(nodes) == 4


async def test_qeury_with_multiple_values_invalid_type(
    db: InfrahubDatabase,
    person_john_main,
    person_jane_main,
    car_accord_main,
    car_volt_main,
    car_yaris_main,
    car_camry_main,
    branch: Branch,
):
    car = registry.schema.get(name="TestCar")

    with pytest.raises(TypeError):
        await NodeManager.query(db=db, schema=car, branch=branch, filters={"owner__name__values": [1.0]})

    with pytest.raises(TypeError):
        await NodeManager.query(db=db, schema=car, branch=branch, filters={"owner__name__values": [None]})


async def test_query_non_default_class(
    db: InfrahubDatabase,
    default_branch: Branch,
    criticality_schema: NodeSchema,
    criticality_low: Node,
    criticality_medium: Node,
):
    class TestCriticality(Node):
        def always_true(self):
            return True

    registry.node["TestCriticality"] = TestCriticality

    nodes = await NodeManager.query(db=db, schema=criticality_schema)
    assert len(nodes) == 2
    assert isinstance(nodes[0], TestCriticality)
    assert nodes[0].always_true()


async def test_query_class_name(
    db: InfrahubDatabase,
    default_branch: Branch,
    criticality_schema: NodeSchema,
    criticality_low: Node,
    criticality_medium: Node,
):
    nodes = await NodeManager.query(db=db, schema="TestCriticality")
    assert len(nodes) == 2


async def test_identify_node_class(db: InfrahubDatabase, car_schema, default_branch):
    node = NodeToProcess(
        schema=car_schema,
        node_id=33,
        node_uuid=str(UUIDT()),
        profile_uuids=[],
        updated_at=Timestamp().to_string(),
        branch=default_branch,
        labels=["Node", "TestCar"],
    )

    class Car(Node):
        pass

    class Vehicule(Node):
        pass

    assert identify_node_class(node=node) == Node

    registry.node["TestVehicule"] = Vehicule
    assert identify_node_class(node=node) == Vehicule

    registry.node["TestCar"] = Car
    assert identify_node_class(node=node) == Car


# ------------------------------------------------------------------------
# WITH BRANCH
# ------------------------------------------------------------------------


async def test_get_one_local_attribute_with_branch(db: InfrahubDatabase, default_branch: Branch, criticality_schema):
    obj1 = await Node.init(db=db, schema=criticality_schema)
    await obj1.new(db=db, name="low", level=4)
    await obj1.save(db=db)

    second_branch = await create_branch(branch_name="branch2", db=db)

    obj2 = await Node.init(db=db, schema=criticality_schema, branch=second_branch)
    await obj2.new(db=db, name="medium", level=3, description="My desc", color="#333333")
    await obj2.save(db=db)

    obj = await NodeManager.get_one(db=db, id=obj2.id, branch=second_branch)

    assert obj.id == obj2.id
    assert obj.db_id == obj2.db_id
    assert obj.name.value == "medium"
    assert obj.name.id
    assert obj.level.value == 3
    assert obj.level.id
    assert obj.description.value == "My desc"
    assert obj.description.id
    assert obj.color.value == "#333333"
    assert obj.color.id

    obj = await NodeManager.get_one(db=db, id=obj1.id, branch=second_branch)

    assert obj.id == obj1.id
    assert obj.db_id == obj1.db_id
    assert obj.name.value == "low"
    assert obj.name.id
    assert obj.level.value == 4
    assert obj.level.id
    assert obj.description.value is None
    assert obj.description.id
    assert obj.color.value == "#444444"
    assert obj.color.id


# ------------------------------------------------------------------------
# WITH BRANCH
# ------------------------------------------------------------------------


async def test_get_one_global(db: InfrahubDatabase, default_branch: Branch, base_dataset_12):
    branch1 = await registry.get_branch(db=db, branch="branch1")

    obj1 = await NodeManager.get_one(db=db, id="p1", branch=branch1)

    assert obj1.id == "p1"
    assert obj1.db_id
    assert obj1.name.value == "John Doe"
    assert obj1.height.value is None

    obj2 = await NodeManager.get_one(db=db, id="c1", branch=branch1)

    assert obj2.id == "c1"
    assert obj2.db_id
    assert obj2.name.value == "volt"
    assert obj2.nbr_seats.value == 4
    assert obj2.color.value == "#444444"
    assert obj2.is_electric.value is True


async def test_get_one_global_isolated(db: InfrahubDatabase, default_branch: Branch, base_dataset_12):
    branch1 = await registry.get_branch(db=db, branch="branch1")
    branch1.is_isolated = True

    obj1 = await NodeManager.get_one(db=db, id="p1", branch=branch1)

    assert obj1.id == "p1"
    assert obj1.db_id
    assert obj1.name.value == "John Doe"
    assert obj1.height.value is None

    obj2 = await NodeManager.get_one(db=db, id="c1", branch=branch1)

    assert obj2.id == "c1"
    assert obj2.db_id
    assert obj2.name.value == "accord"
    assert obj2.nbr_seats.value == 4
    assert obj2.color.value == "#444444"
    assert obj2.is_electric.value is True
