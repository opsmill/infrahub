import pytest

from infrahub.core import registry
from infrahub.core.node import Node
from infrahub.core.relationship import RelationshipManager
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import get_paths_between_nodes


async def test_one_init_no_input_no_rel(session, default_branch, person_tag_schema):

    person_schema = registry.get_schema(name="Person")
    rel_schema = person_schema.get_relationship("primary_tag")

    p1 = await Node.init(session=session, schema=person_schema)
    await p1.new(session=session, firstname="John", lastname="Doe")
    await p1.save(session=session)

    relm = await RelationshipManager.init(
        session=session, schema=rel_schema, branch=default_branch, at=Timestamp(), node=p1, name="primary_tag"
    )

    # shouldn't be able to iterate over it since it's a "one" relationship
    with pytest.raises(TypeError):
        iter(relm)

    assert not await relm.get_peer(session=session)


async def test_one_init_no_input_existing_rel(session, default_branch, person_tag_schema):

    person_schema = registry.get_schema(name="Person")
    rel_schema = person_schema.get_relationship("primary_tag")
    t1 = await Node.init(session=session, schema="Tag")
    await t1.new(session=session, name="blue")
    await t1.save(session=session)
    p1 = await Node.init(session=session, schema=person_schema)
    await p1.new(session=session, firstname="John", lastname="Doe", primary_tag=t1)
    await p1.save(session=session)

    relm = await RelationshipManager.init(
        session=session, schema=rel_schema, branch=default_branch, at=Timestamp(), node=p1, name="primary_tag"
    )

    peer = await relm.get_peer(session=session)
    assert peer.id == t1.id


async def test_many_init_no_input_no_rel(session, default_branch, person_tag_schema):

    person_schema = registry.get_schema(name="Person")
    rel_schema = person_schema.get_relationship("tags")
    p1 = await Node.init(session=session, schema=person_schema)
    await p1.new(session=session, firstname="John", lastname="Doe")
    await p1.save(session=session)

    relm = await RelationshipManager.init(
        session=session, schema=rel_schema, branch=default_branch, at=Timestamp(), node=p1, name="tags"
    )

    # shouldn't be able to query the peer since it's many type relationship
    with pytest.raises(TypeError):
        await relm.get_peer(session=session)

    assert not len(await relm.get(session=session))


async def test_many_init_no_input_existing_rel(session, default_branch, person_tag_schema):

    person_schema = registry.get_schema(name="Person")
    rel_schema = person_schema.get_relationship("tags")
    t1 = await Node.init(session=session, schema="Tag")
    await t1.new(session=session, name="blue")
    await t1.save(session=session)
    t2 = await Node.init(session=session, schema="Tag")
    await t2.new(session=session, name="red")
    await t2.save(session=session)
    p1 = await Node.init(session=session, schema=person_schema)
    await p1.new(session=session, firstname="John", lastname="Doe", tags=[t1, t2])
    await p1.save(session=session)

    relm = await RelationshipManager.init(
        session=session, schema=rel_schema, branch=default_branch, at=Timestamp(), node=p1, name="tags"
    )

    assert len(await relm.get(session=session)) == 2


async def test_one_init_input_obj(session, default_branch, person_tag_schema):

    person_schema = registry.get_schema(name="Person")
    rel_schema = person_schema.get_relationship("primary_tag")
    t1 = await Node.init(session=session, schema="Tag")
    await t1.new(session=session, name="blue")
    await t1.save(session=session)
    p1 = await Node.init(session=session, schema=person_schema)
    await p1.new(session=session, firstname="John", lastname="Doe")
    await p1.save(session=session)

    relm = await RelationshipManager.init(
        session=session, schema=rel_schema, branch=default_branch, at=Timestamp(), node=p1, name="primary_tag", data=t1
    )

    peer = await relm.get_peer(session=session)
    assert peer.id == t1.id


async def test_one_save_input_obj(session, default_branch, person_tag_schema):

    person_schema = registry.get_schema(name="Person")
    rel_schema = person_schema.get_relationship("primary_tag")

    t1 = await Node.init(session=session, schema="Tag")
    await t1.new(session=session, name="blue")
    await t1.save(session=session)
    p1 = await Node.init(session=session, schema=person_schema)
    await p1.new(session=session, firstname="John", lastname="Doe")
    await p1.save(session=session)

    # We should have only 1 paths between t1 and p1 via the branch
    paths = await get_paths_between_nodes(session=session, source_id=t1.db_id, destination_id=p1.db_id, max_length=2)
    assert len(paths) == 1

    relm = await RelationshipManager.init(
        session=session, schema=rel_schema, branch=default_branch, at=Timestamp(), node=p1, name="primary_tag", data=t1
    )
    await relm.save(session=session)

    # We should have 2 paths between t1 and p1
    # First for the relationship, Second via the branch
    paths = await get_paths_between_nodes(session=session, source_id=t1.db_id, destination_id=p1.db_id, max_length=2)
    assert len(paths) == 2


async def test_many_init_input_obj(session, default_branch, person_tag_schema):

    person_schema = registry.get_schema(name="Person")
    rel_schema = person_schema.get_relationship("tags")

    t1 = await Node.init(session=session, schema="Tag")
    await t1.new(session=session, name="blue")
    await t1.save(session=session)
    t2 = await Node.init(session=session, schema="Tag")
    await t2.new(session=session, name="red")
    await t2.save(session=session)
    p1 = await Node.init(session=session, schema=person_schema)
    await p1.new(session=session, firstname="John", lastname="Doe")
    await p1.save(session=session)

    relm = await RelationshipManager.init(
        session=session, schema=rel_schema, branch=default_branch, at=Timestamp(), node=p1, name="tags", data=[t1, t2]
    )

    assert len(list(relm)) == 2


async def test_many_save_input_obj(session, default_branch, person_tag_schema):

    person_schema = registry.get_schema(name="Person")
    rel_schema = person_schema.get_relationship("tags")
    t1 = await Node.init(session=session, schema="Tag")
    await t1.new(session=session, name="blue")
    await t1.save(session=session)
    t2 = await Node.init(session=session, schema="Tag")
    await t2.new(session=session, name="red")
    await t2.save(session=session)
    p1 = await Node.init(session=session, schema=person_schema)
    await p1.new(session=session, firstname="John", lastname="Doe")
    await p1.save(session=session)

    # We should have only 1 paths between t1 and p1 via the branch
    paths = await get_paths_between_nodes(session=session, source_id=t1.db_id, destination_id=p1.db_id, max_length=2)
    assert len(paths) == 1

    paths = await get_paths_between_nodes(session=session, source_id=t2.db_id, destination_id=p1.db_id, max_length=2)
    assert len(paths) == 1

    relm = await RelationshipManager.init(
        session=session, schema=rel_schema, branch=default_branch, at=Timestamp(), node=p1, name="tags", data=[t1, t2]
    )
    await relm.save(session=session)

    paths = await get_paths_between_nodes(session=session, source_id=t1.db_id, destination_id=p1.db_id, max_length=2)
    assert len(paths) == 2

    paths = await get_paths_between_nodes(session=session, source_id=t2.db_id, destination_id=p1.db_id, max_length=2)
    assert len(paths) == 2


async def test_many_update(session, default_branch, person_tag_schema):

    person_schema = registry.get_schema(name="Person")
    rel_schema = person_schema.get_relationship("tags")

    t1 = await Node.init(session=session, schema="Tag")
    await t1.new(session=session, name="blue")
    await t1.save(session=session)
    t2 = await Node.init(session=session, schema="Tag")
    await t2.new(session=session, name="red")
    await t2.save(session=session)
    p1 = await Node.init(session=session, schema=person_schema)
    await p1.new(session=session, firstname="John", lastname="Doe")
    await p1.save(session=session)

    relm = await RelationshipManager.init(
        session=session, schema=rel_schema, branch=default_branch, at=Timestamp(), node=p1, name="tags"
    )
    await relm.save(session=session)

    # We should have only 1 paths between t1 and p1 via the branch
    paths = await get_paths_between_nodes(session=session, source_id=t1.db_id, destination_id=p1.db_id, max_length=2)
    assert len(paths) == 1

    paths = await get_paths_between_nodes(session=session, source_id=t2.db_id, destination_id=p1.db_id, max_length=2)
    assert len(paths) == 1

    await relm.update(session=session, data=t1)
    await relm.save(session=session)

    paths = await get_paths_between_nodes(session=session, source_id=t1.db_id, destination_id=p1.db_id, max_length=2)
    assert len(paths) == 2

    paths = await get_paths_between_nodes(session=session, source_id=t2.db_id, destination_id=p1.db_id, max_length=2)
    assert len(paths) == 1

    await relm.update(session=session, data=[t1, t2])
    await relm.save(session=session)

    paths = await get_paths_between_nodes(session=session, source_id=t1.db_id, destination_id=p1.db_id, max_length=2)
    assert len(paths) == 2

    paths = await get_paths_between_nodes(session=session, source_id=t2.db_id, destination_id=p1.db_id, max_length=2)
    assert len(paths) == 2
