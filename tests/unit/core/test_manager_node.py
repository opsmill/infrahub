import pytest

from infrahub.core import registry
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node


@pytest.mark.asyncio
async def test_get_one_attribute(session, default_branch, criticality_schema):

    obj1 = await Node.init(session=session, schema=criticality_schema)
    await obj1.new(session=session, name="low", level=4)
    await obj1.save(session=session)
    obj2 = await Node.init(session=session, schema=criticality_schema)
    await obj2.new(session=session, name="medium", level=3, description="My desc", color="#333333")
    await obj2.save(session=session)

    obj = await NodeManager.get_one(session=session, id=obj2.id)

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

    obj = await NodeManager.get_one(session=session, id=obj1.id)

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


@pytest.mark.asyncio
async def test_get_one_attribute_with_node_property(
    session, default_branch, criticality_schema, first_account, second_account
):

    obj1 = await Node.init(session=session, schema=criticality_schema)
    await obj1.new(session=session, name="low", level=4, _source=first_account)
    await obj1.save(session=session)
    obj2 = await Node.init(session=session, schema=criticality_schema)
    await obj2.new(
        session=session,
        name="medium",
        level={"value": 3, "source": second_account.id},
        description="My desc",
        color="#333333",
        _source=first_account,
    )
    await obj2.save(session=session)

    obj = await NodeManager.get_one(session=session, id=obj2.id, include_source=True)

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


@pytest.mark.asyncio
async def test_get_one_attribute_with_flag_property(
    session, default_branch, criticality_schema, first_account, second_account
):

    obj1 = await Node.init(session=session, schema=criticality_schema)
    await obj1.new(
        session=session, name={"value": "low", "is_protected": True}, level={"value": 4, "is_visible": False}
    )
    await obj1.save(session=session)

    obj = await NodeManager.get_one(session=session, id=obj1.id, fields={"name": True, "level": True, "color": True})

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


@pytest.mark.asyncio
async def test_get_one_relationship(session, default_branch, car_person_schema):

    car = await registry.get_schema(session=session, name="Car")
    person = await registry.get_schema(session=session, name="Person")

    p1 = await Node.init(session=session, schema=person)
    await p1.new(session=session, name="John", height=180)
    await p1.save(session=session)

    c1 = await Node.init(session=session, schema=car)
    await c1.new(session=session, name="volt", nbr_seats=4, is_electric=True, owner=p1)
    await c1.save(session=session)
    c2 = await Node.init(session=session, schema=car)
    await c2.new(session=session, name="accord", nbr_seats=5, is_electric=False, owner=p1.id)
    await c2.save(session=session)

    c11 = await NodeManager.get_one(session=session, id=c1.id)

    assert c11.name.value == "volt"
    assert c11.nbr_seats.value == 4
    assert c11.is_electric.value is True
    c11_peer = await c11.owner.get_peer(session=session)
    assert c11_peer.id == p1.id

    p11 = await NodeManager.get_one(session=session, id=p1.id)
    assert p11.name.value == "John"
    assert p11.height.value == 180
    assert len(list(p11.cars)) == 2


@pytest.mark.asyncio
async def test_get_one_relationship_with_flag_property(session, default_branch, car_person_schema):

    p1 = await Node.init(session=session, schema="Person")
    await p1.new(session=session, name="John", height=180)
    await p1.save(session=session)

    c1 = await Node.init(session=session, schema="Car")
    await c1.new(
        session=session,
        name="volt",
        nbr_seats=4,
        is_electric=True,
        owner={"id": p1.id, "_relation__is_protected": True, "_relation__is_visible": False},
    )
    await c1.save(session=session)

    c2 = await Node.init(session=session, schema="Car")
    await c2.new(
        session=session,
        name="accord",
        nbr_seats=5,
        is_electric=False,
        owner={"id": p1.id, "_relation__is_visible": False},
    )
    await c2.save(session=session)

    c11 = await NodeManager.get_one(session=session, id=c1.id)

    assert c11.name.value == "volt"
    assert c11.nbr_seats.value == 4
    assert c11.is_electric.value is True
    c11_peer = await c11.owner.get_peer(session=session)
    assert c11_peer.id == p1.id
    rel = c11.owner.get()
    assert rel.is_visible is False
    assert rel.is_protected is True

    p11 = await NodeManager.get_one(session=session, id=p1.id)
    assert p11.name.value == "John"
    assert p11.height.value == 180

    rels = p11.cars.get()
    assert len(rels) == 2
    assert rels[0].is_visible is False
    assert rels[1].is_visible is False


@pytest.mark.asyncio
async def test_get_many(session, default_branch, criticality_schema):

    obj1 = await Node.init(session=session, schema=criticality_schema)
    await obj1.new(session=session, name="low", level=4)
    await obj1.save(session=session)

    obj2 = await Node.init(session=session, schema=criticality_schema)
    await obj2.new(session=session, name="medium", level=3, description="My desc", color="#333333")
    await obj2.save(session=session)

    nodes = await NodeManager.get_many(session=session, ids=[obj1.id, obj2.id])
    assert len(nodes) == 2


@pytest.mark.asyncio
async def test_query_no_filter(session, default_branch, criticality_schema):

    obj1 = await Node.init(session=session, schema=criticality_schema)
    await obj1.new(session=session, name="low", level=4)
    await obj1.save(session=session)

    obj2 = await Node.init(session=session, schema=criticality_schema)
    await obj2.new(session=session, name="medium", level=3, description="My desc", color="#333333")
    await obj2.save(session=session)

    obj3 = await Node.init(session=session, schema=criticality_schema)
    await obj3.new(session=session, name="high", level=3, description="My desc", color="#333333")
    await obj3.save(session=session)

    nodes = await NodeManager.query(session=session, schema=criticality_schema)
    assert len(nodes) == 3


@pytest.mark.asyncio
async def test_query_with_filter_string_int(session, default_branch, criticality_schema):

    obj1 = await Node.init(session=session, schema=criticality_schema)
    await obj1.new(session=session, name="low", level=3)
    await obj1.save(session=session)

    obj2 = await Node.init(session=session, schema=criticality_schema)
    await obj2.new(session=session, name="medium", level=3, description="My desc", color="#333333")
    await obj2.save(session=session)

    obj3 = await Node.init(session=session, schema=criticality_schema)
    await obj3.new(session=session, name="high", level=4, description="My other desc", color="#333333")
    await obj3.save(session=session)

    nodes = await NodeManager.query(session=session, schema=criticality_schema, filters={"color__value": "#333333"})
    assert len(nodes) == 2

    nodes = await NodeManager.query(
        session=session, schema=criticality_schema, filters={"description__value": "My other desc"}
    )
    assert len(nodes) == 1

    nodes = await NodeManager.query(
        session=session, schema=criticality_schema, filters={"level__value": 3, "color__value": "#333333"}
    )
    assert len(nodes) == 1


@pytest.mark.asyncio
async def test_query_with_filter_bool_rel(session, default_branch, car_person_schema):

    car = await registry.get_schema(session=session, name="Car")
    person = await registry.get_schema(session=session, name="Person")

    p1 = await Node.init(session=session, schema=person)
    await p1.new(session=session, name="John", height=180)
    await p1.save(session=session)

    p2 = await Node.init(session=session, schema=person)
    await p2.new(session=session, name="Jane", height=160)
    await p2.save(session=session)

    c1 = await Node.init(session=session, schema=car)
    await c1.new(session=session, name="volt", nbr_seats=4, is_electric=True, owner=p1)
    await c1.save(session=session)
    c2 = await Node.init(session=session, schema=car)
    await c2.new(session=session, name="accord", nbr_seats=5, is_electric=False, owner=p1.id)
    await c2.save(session=session)
    c3 = await Node.init(session=session, schema=car)
    await c3.new(session=session, name="camry", nbr_seats=5, is_electric=False, owner=p2)
    await c3.save(session=session)
    c4 = await Node.init(session=session, schema=car)
    await c4.new(session=session, name="yaris", nbr_seats=4, is_electric=False, owner=p2)
    await c4.save(session=session)

    # Check filter with a boolean
    nodes = await NodeManager.query(session=session, schema=car, filters={"is_electric__value": False})
    assert len(nodes) == 3

    # Check filter with a relationship
    nodes = await NodeManager.query(session=session, schema=car, filters={"owner__name__value": "John"})
    assert len(nodes) == 2


@pytest.mark.asyncio
async def test_query_non_default_class(session, default_branch, criticality_schema):
    class Criticality(Node):
        def always_true(self):
            return True

    registry.node["Criticality"] = Criticality

    obj1 = await Node.init(session=session, schema=criticality_schema)
    await obj1.new(session=session, name="low", level=4)
    await obj1.save(session=session)

    obj2 = await Node.init(session=session, schema=criticality_schema)
    await obj2.new(session=session, name="medium", level=3, description="My desc", color="#333333")
    await obj2.save(session=session)

    nodes = await NodeManager.query(session=session, schema=criticality_schema)
    assert len(nodes) == 2
    assert isinstance(nodes[0], Criticality)
    assert nodes[0].always_true()


@pytest.mark.asyncio
async def test_query_class_name(session, default_branch, criticality_schema):

    obj1 = await Node.init(session=session, schema=criticality_schema)
    await obj1.new(session=session, name="low", level=3)
    await obj1.save(session=session)

    obj2 = await Node.init(session=session, schema=criticality_schema)
    await obj2.new(session=session, name="medium", level=3, description="My desc", color="#333333")
    await obj2.save(session=session)

    nodes = await NodeManager.query(session=session, schema="Criticality")
    assert len(nodes) == 2


# ------------------------------------------------------------------------
# WITH BRANCH
# ------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_one_local_attribute_with_branch(session, default_branch, criticality_schema):

    obj1 = await Node.init(session=session, schema=criticality_schema)
    await obj1.new(session=session, name="low", level=4)
    await obj1.save(session=session)

    second_branch = await create_branch(branch_name="branch2", session=session)

    obj2 = await Node.init(session=session, schema=criticality_schema, branch=second_branch)
    await obj2.new(session=session, name="medium", level=3, description="My desc", color="#333333")
    await obj2.save(session=session)

    obj = await NodeManager.get_one(session=session, id=obj2.id, branch=second_branch)

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

    obj = await NodeManager.get_one(session=session, id=obj1.id, branch=second_branch)

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
