import pytest

from infrahub.core import registry
from infrahub.core.timestamp import Timestamp
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.relationship import Relationship
from infrahub.core.query.relationship import RelationshipGetPeerQuery


@pytest.mark.asyncio
async def test_relationship_init(session, default_branch, person_tag_schema):

    person_schema = await registry.get_schema(session=session, name="Person")
    rel_schema = person_schema.get_relationship("tags")

    t1 = await Node.init(session=session, schema="Tag")
    await t1.new(session=session, name="blue")
    await t1.save(session=session)
    p1 = await Node.init(session=session, schema=person_schema)
    await p1.new(session=session, firstname="John", lastname="Doe")
    await p1.save(session=session)

    rel = Relationship(schema=rel_schema, branch=default_branch, node=p1)

    assert rel.schema == rel_schema
    assert rel.name == rel_schema.name
    assert rel.branch == default_branch
    assert rel.node_id == p1.id
    assert await rel.get_node(session=session) == p1

    rel = Relationship(schema=rel_schema, branch=default_branch, node_id=p1.id)

    assert rel.schema == rel_schema
    assert rel.name == rel_schema.name
    assert rel.branch == default_branch
    assert rel.node_id == p1.id

    rel_node = await rel.get_node(session=session)
    assert type(rel_node) == Node
    assert rel_node.id == p1.id


@pytest.mark.asyncio
async def test_relationship_init_w_node_property(
    session, default_branch, person_tag_schema, first_account, second_account
):

    person_schema = await registry.get_schema(session=session, name="Person")
    rel_schema = person_schema.get_relationship("tags")

    t1 = await Node.init(session=session, schema="Tag")
    await t1.new(session=session, name="blue")
    await t1.save(session=session)

    p1 = await Node.init(session=session, schema=person_schema)
    await p1.new(session=session, firstname="John", lastname="Doe")
    await p1.save(session=session)

    rel = Relationship(schema=rel_schema, branch=default_branch, node=p1, source=first_account, owner=second_account)

    assert rel.schema == rel_schema
    assert rel.name == rel_schema.name
    assert rel.branch == default_branch
    assert rel.node_id == p1.id
    assert await rel.get_node(session=session) == p1
    assert rel.source_id == first_account.id
    assert rel.owner_id == second_account.id


@pytest.mark.asyncio
async def test_relationship_load_existing(session, default_branch, car_person_schema):

    car_schema = await registry.get_schema(session=session, name="Car")
    rel_schema = car_schema.get_relationship("owner")

    p1 = await Node.init(session=session, schema="Person")
    await p1.new(session=session, name="John", height=180)
    await p1.save(session=session)

    c3 = await Node.init(session=session, schema="Car")
    await c3.new(
        session=session,
        name="smart",
        nbr_seats=2,
        is_electric=True,
        owner={"id": p1.id, "_relation__is_protected": True, "_relation__is_visible": False},
    )
    await c3.save(session=session)

    rel = Relationship(schema=rel_schema, branch=default_branch, node=c3)

    query = await RelationshipGetPeerQuery.init(
        session=session,
        source=c3,
        at=Timestamp(),
        rel=rel,
    )
    await query.execute(session=session)

    peers = list(query.get_peers())

    assert peers[0].properties["is_protected"].value is True

    await rel.load(session=session, data=peers[0])

    assert rel.id == peers[0].rel_node_id
    assert rel.db_id == peers[0].rel_node_db_id

    assert rel.is_protected is True
    assert rel.is_visible is False


@pytest.mark.asyncio
async def test_relationship_peer(session, default_branch, person_tag_schema, first_account, second_account):

    person_schema = await registry.get_schema(session=session, name="Person")
    rel_schema = person_schema.get_relationship("tags")

    t1 = await Node.init(session=session, schema="Tag")
    await t1.new(session=session, name="blue")
    await t1.save(session=session)

    p1 = await Node.init(session=session, schema=person_schema)
    await p1.new(session=session, firstname="John", lastname="Doe")
    await p1.save(session=session)

    rel = Relationship(schema=rel_schema, branch=default_branch, node=p1)
    await rel.set_peer(value=t1)

    assert rel.schema == rel_schema
    assert rel.name == rel_schema.name
    assert rel.branch == default_branch
    assert rel.node_id == p1.id
    assert await rel.get_node(session=session) == p1
    assert rel.peer_id == t1.id
    assert await rel.get_peer(session=session) == t1


@pytest.mark.asyncio
async def test_relationship_save(session, default_branch, person_tag_schema):

    person_schema = await registry.get_schema(session=session, name="Person")
    rel_schema = person_schema.get_relationship("tags")

    t1 = await Node.init(session=session, schema="Tag")
    await t1.new(session=session, name="blue")
    await t1.save(session=session)
    p1 = await Node.init(session=session, schema=person_schema)
    await p1.new(session=session, firstname="John", lastname="Doe")
    await p1.save(session=session)

    rel = Relationship(schema=rel_schema, branch=default_branch, node=p1)
    await rel.set_peer(value=t1)
    await rel.save(session=session)

    p11 = await NodeManager.get_one(id=p1.id, session=session)
    tags = list(p11.tags)
    assert len(tags) == 1
    assert tags[0].id == rel.id
