import pytest
from neo4j import AsyncSession

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.query.relationship import RelationshipGetPeerQuery
from infrahub.core.relationship import Relationship
from infrahub.core.timestamp import Timestamp


async def test_relationship_init(
    session: AsyncSession, default_branch: Branch, tag_blue_main: Node, person_jack_main: Node, branch: Branch
):
    person_schema = registry.get_schema(name="Person")
    rel_schema = person_schema.get_relationship("tags")

    rel = Relationship(schema=rel_schema, branch=branch, node=person_jack_main)

    assert rel.schema == rel_schema
    assert rel.name == rel_schema.name
    assert rel.branch == branch
    assert rel.node_id == person_jack_main.id
    assert await rel.get_node(session=session) == person_jack_main

    rel = Relationship(schema=rel_schema, branch=branch, node_id=person_jack_main.id)

    assert rel.schema == rel_schema
    assert rel.name == rel_schema.name
    assert rel.branch == branch
    assert rel.node_id == person_jack_main.id

    rel_node = await rel.get_node(session=session)
    assert type(rel_node) == Node
    assert rel_node.id == person_jack_main.id


async def test_relationship_init_w_node_property(
    session,
    default_branch: Branch,
    first_account: Node,
    second_account: Node,
    tag_blue_main: Node,
    person_jack_main: Node,
    branch: Branch,
):
    person_schema = registry.get_schema(name="Person")
    rel_schema = person_schema.get_relationship("tags")

    rel = Relationship(
        schema=rel_schema, branch=branch, node=person_jack_main, source=first_account, owner=second_account
    )

    assert rel.schema == rel_schema
    assert rel.name == rel_schema.name
    assert rel.branch == branch
    assert rel.node_id == person_jack_main.id
    assert await rel.get_node(session=session) == person_jack_main
    assert rel.source_id == first_account.id
    assert rel.owner_id == second_account.id


@pytest.fixture
async def car_smart_properties_main(session: AsyncSession, default_branch: Branch, person_john_main: Node) -> Node:
    car: Node = await Node.init(session=session, schema="Car", branch=default_branch)
    await car.new(
        session=session,
        name="smart",
        nbr_seats=2,
        is_electric=True,
        owner={"id": person_john_main.id, "_relation__is_protected": True, "_relation__is_visible": False},
    )
    await car.save(session=session)

    return car


async def test_relationship_load_existing(
    session: AsyncSession, person_john_main: Node, car_smart_properties_main: Node, branch: Branch
):
    car_schema = registry.get_schema(name="Car")
    rel_schema = car_schema.get_relationship("owner")

    rel = Relationship(schema=rel_schema, branch=branch, node=car_smart_properties_main)

    query = await RelationshipGetPeerQuery.init(
        session=session,
        source=car_smart_properties_main,
        branch=branch,
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


async def test_relationship_peer(session: AsyncSession, tag_blue_main: Node, person_jack_main: Node, branch: Branch):
    person_schema = registry.get_schema(name="Person")
    rel_schema = person_schema.get_relationship("tags")

    rel = Relationship(schema=rel_schema, branch=branch, node=person_jack_main)
    await rel.set_peer(value=tag_blue_main)

    assert rel.schema == rel_schema
    assert rel.name == rel_schema.name
    assert rel.branch == branch
    assert rel.node_id == person_jack_main.id
    assert await rel.get_node(session=session) == person_jack_main
    assert rel.peer_id == tag_blue_main.id
    assert await rel.get_peer(session=session) == tag_blue_main


async def test_relationship_save(session: AsyncSession, tag_blue_main: Node, person_jack_main: Node, branch: Branch):
    person_schema = registry.get_schema(name="Person")
    rel_schema = person_schema.get_relationship("tags")

    rel = Relationship(schema=rel_schema, branch=branch, node=person_jack_main)
    await rel.set_peer(value=tag_blue_main)
    await rel.save(session=session)

    p11 = await NodeManager.get_one(id=person_jack_main.id, session=session, branch=branch)
    tags = await p11.tags.get(session=session)
    assert len(tags) == 1
    assert tags[0].id == rel.id
