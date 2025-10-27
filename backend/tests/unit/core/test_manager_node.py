import copy

import pytest
from infrahub_sdk.uuidt import UUIDT

from infrahub import config
from infrahub.constants.database import Neo4jRuntime
from infrahub.core.branch import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager, identify_node_class
from infrahub.core.node import Node
from infrahub.core.query.node import NodeToProcess
from infrahub.core.registry import registry
from infrahub.core.relationship import Relationship
from infrahub.core.schema import NodeSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import NodeNotFoundError
from tests.constants import TestKind
from tests.helpers.schema import DEVICE_SCHEMA


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

    not_exist = await NodeManager.get_one(db=db, id="e57fef37-d9eb-4548-b890-b5e31d76f56b")
    assert not not_exist

    with pytest.raises(NodeNotFoundError, match=r"Unable to find the node"):
        await NodeManager.get_one(db=db, id="e57fef37-d9eb-4548-b890-b5e31d76f56b", raise_on_error=True)


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
    criticality_schema: SchemaBranch,
    criticality_low: Node,
    criticality_medium: Node,
):
    node1 = await NodeManager.get_one_by_id_or_default_filter(
        db=db, id=criticality_low.id, kind=criticality_schema.kind
    )
    assert isinstance(node1, Node)
    assert node1.id == criticality_low.id

    node2 = await NodeManager.get_one_by_id_or_default_filter(
        db=db, id=criticality_low.name.value, kind=criticality_schema.kind
    )
    assert isinstance(node2, Node)
    assert node2.id == criticality_low.id


async def test_get_one_by_hfid(
    db: InfrahubDatabase,
    default_branch: Branch,
    animal_person_schema: SchemaBranch,
):
    person_schema = animal_person_schema.get(name="TestPerson")
    dog_schema = animal_person_schema.get(name="TestDog")

    person1 = await Node.init(db=db, schema=person_schema, branch=default_branch)
    await person1.new(db=db, name="Jack")
    await person1.save(db=db)

    person2 = await Node.init(db=db, schema=person_schema, branch=default_branch)
    await person2.new(db=db, name="Jim")
    await person2.save(db=db)

    dog1 = await Node.init(db=db, schema=dog_schema, branch=default_branch)
    await dog1.new(db=db, name="Rocky", breed="Labrador", owner=person1)
    await dog1.save(db=db)

    dog2 = await Node.init(db=db, schema=dog_schema, branch=default_branch)
    await dog2.new(db=db, name="Bella", breed="French Bulldog", owner=person1)
    await dog2.save(db=db)

    node1 = await NodeManager.get_one_by_hfid(db=db, hfid=["Jack", "Rocky"], kind=dog_schema.kind)
    assert isinstance(node1, Node)
    assert node1.id == dog1.id

    not_a_dog = await NodeManager.get_one_by_hfid(db=db, hfid=["Not", "Dog"], kind=dog_schema.kind)
    assert not not_a_dog

    with pytest.raises(NodeNotFoundError, match=r"Unable to find the node"):
        await NodeManager.get_one_by_hfid(db=db, hfid=["Not", "Dog"], kind=dog_schema.kind, raise_on_error=True)


async def test_get_by_hfid_with_invalid_hfid(db: InfrahubDatabase, branch: Branch):
    schema = copy.deepcopy(DEVICE_SCHEMA)
    # Change device schema to add a HFID
    schema.nodes[0].human_friendly_id = ["name__value"]
    schema.nodes[0].generate_template = False

    registry.schema.register_schema(schema=schema, branch=branch.name)

    device = await Node.init(db=db, schema=TestKind.DEVICE, branch=branch)
    await device.new(db=db, name="device-01", manufacturer="Juniper", height=1, weight=6, airflow="Front to rear")
    await device.save(db=db)
    device_hfid = await device.get_hfid(db=db)

    with pytest.raises(NodeNotFoundError, match=r"does not have a HFID defined"):
        await NodeManager.get_one_by_hfid(db=db, branch=branch, kind=TestKind.INTERFACE_HOLDER, hfid=device_hfid)

    with pytest.raises(NodeNotFoundError, match=r"HFID does not contain the same number of elements"):
        await NodeManager.get_one_by_hfid(db=db, branch=branch, kind=TestKind.DEVICE, hfid=device_hfid + ["foo"])


async def test_get_many(db: InfrahubDatabase, default_branch: Branch, criticality_low, criticality_medium):
    nodes = await NodeManager.get_many(db=db, ids=[criticality_low.id, criticality_medium.id])
    assert len(nodes) == 2


async def test_get_many_with_pagination(
    db: InfrahubDatabase,
    default_branch: Branch,
    criticality_schema: NodeSchema,
    criticality_low: Node,
    criticality_medium: Node,
    criticality_high: Node,
):
    new_node_ids: list[str] = []
    for index in range(10):
        bulk_node = await Node.init(db=db, schema=criticality_schema, branch=default_branch)
        await bulk_node.new(db=db, name=f"bulk-{index}", level=index)
        await bulk_node.save(db=db)
        new_node_ids.append(bulk_node.id)

    original_query_size_limit = config.SETTINGS.database.query_size_limit
    config.SETTINGS.database.query_size_limit = 1
    original_neo4j_runtime = db.default_neo4j_runtime
    db.default_neo4j_runtime = Neo4jRuntime.PARALLEL

    try:
        target_ids = [criticality_low.id, criticality_medium.id, criticality_high.id, *new_node_ids]
        nodes = await NodeManager.get_many(db=db, ids=target_ids)
    finally:
        config.SETTINGS.database.query_size_limit = original_query_size_limit
        db.default_neo4j_runtime = original_neo4j_runtime

    expected_ids = set(target_ids)
    assert set(nodes) == expected_ids
    assert len(nodes) == len(expected_ids)
    assert all(isinstance(nodes[node_id], Node) for node_id in expected_ids)


async def test_get_many_prefetch(
    db: InfrahubDatabase, person_jack_tags_main, tag_blue_main, tag_red_main, branch: Branch
):
    nodes = await NodeManager.get_many(
        db=db, branch=branch, ids=[person_jack_tags_main.id], prefetch_relationships=True
    )

    assert len(nodes) == 1
    assert nodes[person_jack_tags_main.id]
    tag_rels = await nodes[person_jack_tags_main.id].tags.get(db=db)
    assert len(tag_rels) == 2
    assert {t.peer_id for t in tag_rels} == {tag_blue_main.id, tag_red_main.id}
    assert isinstance(tag_rels[0]._peer, Node)
    assert tag_rels[0]._peer.get_kind() == "BuiltinTag"
    assert isinstance(tag_rels[1]._peer, Node)
    assert tag_rels[1]._peer.get_kind() == "BuiltinTag"

    # remove a tag
    person_branch = await NodeManager.get_one(db=db, branch=branch, id=person_jack_tags_main.id)
    await person_branch.tags.update(db=db, data=[tag_blue_main])
    await person_branch.save(db=db)

    # check that prefetch respects removed relationships
    updated_nodes = await NodeManager.get_many(
        db=db, branch=branch, ids=[person_jack_tags_main.id], prefetch_relationships=True
    )
    assert len(updated_nodes) == 1
    assert updated_nodes[person_jack_tags_main.id]
    tag_rels = await updated_nodes[person_jack_tags_main.id].tags.get(db=db)
    assert len(tag_rels) == 1
    assert {t.peer_id for t in tag_rels} == {tag_blue_main.id}
    assert isinstance(tag_rels[0]._peer, Node)
    assert tag_rels[0]._peer.get_kind() == "BuiltinTag"


async def test_get_many_prefetch_hierarchical(
    db: InfrahubDatabase, default_branch: Branch, hierarchical_location_data: dict[str, Node]
):
    nodes_to_query = ["europe", "asia", "paris", "chicago", "london-r1"]
    node_ids = [hierarchical_location_data[value].id for value in nodes_to_query]
    nodes = await NodeManager.get_many(db=db, ids=node_ids, prefetch_relationships=True)
    assert len(nodes) == 5

    paris_id = hierarchical_location_data["paris"].id
    europe_id = hierarchical_location_data["europe"].id

    assert nodes[paris_id]
    children_paris = await nodes[paris_id].children.get(db=db)
    assert len(children_paris) == 2
    parent_paris = await nodes[paris_id].parent.get(db=db)
    assert isinstance(parent_paris, Relationship)
    assert parent_paris.peer_id == europe_id

    europe_id = hierarchical_location_data["europe"].id
    assert nodes[europe_id]
    children_europe = await nodes[europe_id].children.get(db=db)
    assert len(children_europe) == 2
    parent_europe = await nodes[europe_id].parent.get(db=db)
    assert parent_europe is None


async def test_get_many_branch_agnostic(
    db: InfrahubDatabase, default_branch: Branch, criticality_low, criticality_medium
):
    branch = await create_branch(db=db, branch_name="branch")
    crit_schema = registry.schema.get(name="TestCriticality", branch=branch, duplicate=False)
    new_crit = await Node.init(schema=crit_schema, db=db, branch=branch)
    await new_crit.new(db=db, name="new crit", level=42)
    await new_crit.save(db=db)

    node_map = await NodeManager.get_many(
        db=db, branch=default_branch, ids=[criticality_low.id, criticality_medium.id, new_crit.id], branch_agnostic=True
    )
    assert len(node_map) == 3
    assert node_map[criticality_low.id].get_branch_based_on_support_type().name == default_branch.name
    assert node_map[criticality_medium.id].get_branch_based_on_support_type().name == default_branch.name
    assert node_map[new_crit.id].get_branch_based_on_support_type().name == branch.name

    node_map = await NodeManager.get_many(
        db=db, branch=default_branch, ids=[criticality_low.id, criticality_medium.id, new_crit.id]
    )
    assert len(node_map) == 2
    assert node_map[criticality_low.id].get_branch_based_on_support_type().name == default_branch.name
    assert node_map[criticality_medium.id].get_branch_based_on_support_type().name == default_branch.name

    node_map = await NodeManager.get_many(
        db=db, branch=branch, ids=[criticality_low.id, criticality_medium.id, new_crit.id]
    )
    assert len(node_map) == 3
    assert node_map[criticality_low.id].get_branch_based_on_support_type().name == branch.name
    assert node_map[criticality_medium.id].get_branch_based_on_support_type().name == branch.name
    assert node_map[new_crit.id].get_branch_based_on_support_type().name == branch.name


async def test_get_many_relationship_fields(
    db: InfrahubDatabase, default_branch: Branch, hierarchical_location_data: dict[str, Node]
):
    nodes_to_query = ["europe", "asia", "paris", "chicago", "london-r1"]
    node_ids = [hierarchical_location_data[value].id for value in nodes_to_query]
    fields = {"parent": None}
    nodes = await NodeManager.get_many(db=db, ids=node_ids, fields=fields)
    assert len(nodes) == 5

    paris_id = hierarchical_location_data["paris"].id
    europe_id = hierarchical_location_data["europe"].id

    assert nodes[paris_id]
    parent_europe_rel = nodes[paris_id].parent.get_one()
    assert parent_europe_rel.peer_id == europe_id
    # make sure we did not get the whole peer node, just the ID
    assert parent_europe_rel._peer is None
    europe_parent_node = await nodes[paris_id].parent.get_peer(db=db)
    assert europe_parent_node.get_kind() == "LocationRegion"
    assert europe_parent_node.get_id() == europe_id
    # make sure we didn't get the children relationships even though they have the same identifier
    with pytest.raises(LookupError):
        list(nodes[paris_id].children)
    # make sure we didn't get other relationships
    with pytest.raises(LookupError):
        list(nodes[paris_id].things)

    assert nodes[europe_id]
    # europe has no parent
    with pytest.raises(LookupError):
        nodes[europe_id].parent.get_one()
    # make sure we didn't get the children relationships even though they have the same identifier
    with pytest.raises(LookupError):
        list(nodes[europe_id].children)
    # make sure we didn't get other relationships
    with pytest.raises(LookupError):
        list(nodes[europe_id].things)


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


async def test_query_protocol(
    db: InfrahubDatabase,
    default_branch: Branch,
    criticality_protocol,
    criticality_low: Node,
    criticality_medium: Node,
    criticality_high: Node,
):
    nodes = await NodeManager.query(db=db, schema=criticality_protocol)
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
    assert obj2.name.value == "accord"
    assert obj2.nbr_seats.value == 4
    assert obj2.color.value == "#444444"
    assert obj2.is_electric.value is True
