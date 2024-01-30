import pytest

from infrahub.core import registry
from infrahub.core.branch.branch import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.query.relationship import RelationshipGetPeerQuery
from infrahub.core.relationship import Relationship
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase


async def test_relationship_init(
    db: InfrahubDatabase, default_branch: Branch, tag_blue_main: Node, person_jack_main: Node, branch: Branch
):
    person_schema = registry.get_schema(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    rel = Relationship(schema=rel_schema, branch=branch, node=person_jack_main)

    assert rel.schema == rel_schema
    assert rel.name == rel_schema.name
    assert rel.branch == branch
    assert rel.node_id == person_jack_main.id
    assert await rel.get_node(db=db) == person_jack_main

    rel = Relationship(schema=rel_schema, branch=branch, node_id=person_jack_main.id)

    assert rel.schema == rel_schema
    assert rel.name == rel_schema.name
    assert rel.branch == branch
    assert rel.node_id == person_jack_main.id

    rel_node = await rel.get_node(db=db)
    assert type(rel_node) == Node
    assert rel_node.id == person_jack_main.id


async def test_relationship_init_w_node_property(
    db: InfrahubDatabase,
    default_branch: Branch,
    first_account: Node,
    second_account: Node,
    tag_blue_main: Node,
    person_jack_main: Node,
    branch: Branch,
):
    person_schema = registry.get_schema(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    rel = Relationship(
        schema=rel_schema, branch=branch, node=person_jack_main, source=first_account, owner=second_account
    )

    assert rel.schema == rel_schema
    assert rel.name == rel_schema.name
    assert rel.branch == branch
    assert rel.node_id == person_jack_main.id
    assert await rel.get_node(db=db) == person_jack_main
    assert rel.source_id == first_account.id
    assert rel.owner_id == second_account.id


@pytest.fixture
async def car_smart_properties_main(db: InfrahubDatabase, default_branch: Branch, person_john_main: Node) -> Node:
    car: Node = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car.new(
        db=db,
        name="smart",
        nbr_seats=2,
        is_electric=True,
        owner={"id": person_john_main.id, "_relation__is_protected": True, "_relation__is_visible": False},
    )
    await car.save(db=db)

    return car


async def test_relationship_load_existing(
    db: InfrahubDatabase, person_john_main: Node, car_smart_properties_main: Node, branch: Branch
):
    car_schema = registry.get_schema(name="TestCar")
    rel_schema = car_schema.get_relationship("owner")

    rel = Relationship(schema=rel_schema, branch=branch, node=car_smart_properties_main)

    query = await RelationshipGetPeerQuery.init(
        db=db,
        source=car_smart_properties_main,
        branch=branch,
        at=Timestamp(),
        rel=rel,
    )
    await query.execute(db=db)

    peers = list(query.get_peers())

    assert peers[0].properties["is_protected"].value is True

    await rel.load(db=db, data=peers[0])

    assert rel.id == peers[0].rel_node_id
    assert rel.db_id == peers[0].rel_node_db_id

    assert rel.is_protected is True
    assert rel.is_visible is False


async def test_relationship_peer(db: InfrahubDatabase, tag_blue_main: Node, person_jack_main: Node, branch: Branch):
    person_schema = registry.get_schema(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    rel = Relationship(schema=rel_schema, branch=branch, node=person_jack_main)
    await rel.set_peer(value=tag_blue_main)

    assert rel.schema == rel_schema
    assert rel.name == rel_schema.name
    assert rel.branch == branch
    assert rel.node_id == person_jack_main.id
    assert await rel.get_node(db=db) == person_jack_main
    assert rel.peer_id == tag_blue_main.id
    assert await rel.get_peer(db=db) == tag_blue_main


async def test_relationship_save(db: InfrahubDatabase, tag_blue_main: Node, person_jack_main: Node, branch: Branch):
    person_schema = registry.get_schema(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    rel = Relationship(schema=rel_schema, branch=branch, node=person_jack_main)
    await rel.set_peer(value=tag_blue_main)
    await rel.save(db=db)

    p11 = await NodeManager.get_one(id=person_jack_main.id, db=db, branch=branch)
    tags = await p11.tags.get(db=db)
    assert len(tags) == 1
    assert tags[0].id == rel.id


async def test_relationship_hash(
    db: InfrahubDatabase, tag_blue_main: Node, person_jack_main: Node, branch: Branch, first_account
):
    person_schema = registry.get_schema(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    rel = Relationship(schema=rel_schema, branch=branch, node=person_jack_main)
    await rel.set_peer(value=tag_blue_main)
    await rel.save(db=db)
    hash1 = hash(rel)

    # Update flag property back and forth and check that hash is the same
    await rel.load(db=db, data={"_relation__is_protected": True})
    hash2 = hash(rel)

    await rel.load(db=db, data={"_relation__is_protected": False})
    hash3 = hash(rel)

    assert hash1 == hash3
    assert hash1 != hash2

    # Update node property back and forth and check that hash is the same as well
    await rel.load(db=db, data={"_relation__owner": first_account})
    hash4 = hash(rel)

    await rel.load(db=db, data={"_relation__owner": None})
    hash5 = hash(rel)

    await rel.load(db=db, data={"_relation__owner": first_account})
    hash6 = hash(rel)

    assert hash4 == hash6
    assert hash4 != hash5
