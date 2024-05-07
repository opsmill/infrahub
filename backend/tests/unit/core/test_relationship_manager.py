import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.core.relationship import RelationshipManager
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import get_paths_between_nodes
from infrahub.database import InfrahubDatabase


async def test_one_init_no_input_no_rel(db: InfrahubDatabase, person_jack_main: Node, branch: Branch):
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("primary_tag")

    relm = await RelationshipManager.init(
        db=db, schema=rel_schema, branch=branch, at=Timestamp(), node=person_jack_main
    )

    # shouldn't be able to iterate over it since it's a "one" relationship
    with pytest.raises(TypeError):
        iter(relm)

    assert not await relm.get_peer(db=db)


async def test_one_init_no_input_existing_rel(
    db: InfrahubDatabase, tag_blue_main: Node, person_jack_primary_tag_main: Node, branch: Branch
):
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("primary_tag")

    relm = await RelationshipManager.init(
        db=db,
        schema=rel_schema,
        branch=branch,
        at=Timestamp(),
        node=person_jack_primary_tag_main,
    )

    peer = await relm.get_peer(db=db)
    assert peer.id == tag_blue_main.id


async def test_many_init_no_input_no_rel(db: InfrahubDatabase, person_jack_main: Node, branch: Branch):
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    relm = await RelationshipManager.init(
        db=db, schema=rel_schema, branch=branch, at=Timestamp(), node=person_jack_main
    )

    # shouldn't be able to query the peer since it's many type relationship
    with pytest.raises(TypeError):
        await relm.get_peer(db=db)

    assert not len(await relm.get(db=db))


async def test_many_init_no_input_existing_rel(db: InfrahubDatabase, person_jack_tags_main: Node, branch: Branch):
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    relm = await RelationshipManager.init(
        db=db, schema=rel_schema, branch=branch, at=Timestamp(), node=person_jack_tags_main
    )

    assert len(await relm.get(db=db)) == 2


async def test_one_init_input_obj(db: InfrahubDatabase, tag_blue_main: Node, person_jack_main: Node, branch: Branch):
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("primary_tag")

    relm = await RelationshipManager.init(
        db=db,
        schema=rel_schema,
        branch=branch,
        at=Timestamp(),
        node=person_jack_main,
        data=tag_blue_main,
    )

    peer = await relm.get_peer(db=db)
    assert peer.id == tag_blue_main.id


async def test_one_save_input_obj(db: InfrahubDatabase, tag_blue_main: Node, person_jack_main: Node, branch: Branch):
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("primary_tag")

    # We should have only 1 paths between t1 and p1 via the branch
    paths = await get_paths_between_nodes(
        db=db, source_id=tag_blue_main.db_id, destination_id=person_jack_main.db_id, max_length=2
    )
    assert len(paths) == 1

    relm = await RelationshipManager.init(
        db=db,
        schema=rel_schema,
        branch=branch,
        at=Timestamp(),
        node=person_jack_main,
        data=tag_blue_main,
    )
    await relm.save(db=db)

    # We should have 2 paths between t1 and p1
    # First for the relationship, Second via the branch
    paths = await get_paths_between_nodes(
        db=db, source_id=tag_blue_main.db_id, destination_id=person_jack_main.db_id, max_length=2
    )
    assert len(paths) == 2


async def test_one_udpate(
    db: InfrahubDatabase, tag_blue_main: Node, person_jack_primary_tag_main: Node, branch: Branch
):
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("primary_tag")

    # We should have only 1 paths between t1 and p1 via the branch
    paths = await get_paths_between_nodes(
        db=db, source_id=tag_blue_main.db_id, destination_id=person_jack_primary_tag_main.db_id, max_length=2
    )
    assert len(paths) == 2

    relm = await RelationshipManager.init(
        db=db,
        schema=rel_schema,
        branch=branch,
        at=Timestamp(),
        node=person_jack_primary_tag_main,
        data=tag_blue_main,
    )
    await relm.save(db=db)

    # We should have 2 paths between t1 and p1
    # First for the relationship, Second via the branch
    paths = await get_paths_between_nodes(
        db=db, source_id=tag_blue_main.db_id, destination_id=person_jack_primary_tag_main.db_id, max_length=2
    )
    assert len(paths) == 2


async def test_many_init_input_obj(
    db: InfrahubDatabase, tag_blue_main: Node, tag_red_main: Node, person_jack_main: Node, branch: Branch
):
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    relm = await RelationshipManager.init(
        db=db,
        schema=rel_schema,
        branch=branch,
        at=Timestamp(),
        node=person_jack_main,
        data=[tag_blue_main, tag_red_main],
    )

    assert len(list(relm)) == 2


async def test_many_save_input_obj(
    db: InfrahubDatabase, tag_blue_main: Node, tag_red_main: Node, person_jack_main: Node, branch: Branch
):
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    # We should have only 1 paths between t1 and p1 via the branch
    paths = await get_paths_between_nodes(
        db=db, source_id=tag_blue_main.db_id, destination_id=person_jack_main.db_id, max_length=2
    )
    assert len(paths) == 1

    paths = await get_paths_between_nodes(
        db=db, source_id=tag_red_main.db_id, destination_id=person_jack_main.db_id, max_length=2
    )
    assert len(paths) == 1

    relm = await RelationshipManager.init(
        db=db,
        schema=rel_schema,
        branch=branch,
        at=Timestamp(),
        node=person_jack_main,
        data=[tag_blue_main, tag_red_main],
    )
    await relm.save(db=db)

    paths = await get_paths_between_nodes(
        db=db, source_id=tag_blue_main.db_id, destination_id=person_jack_main.db_id, max_length=2
    )
    assert len(paths) == 2

    paths = await get_paths_between_nodes(
        db=db, source_id=tag_red_main.db_id, destination_id=person_jack_main.db_id, max_length=2
    )
    assert len(paths) == 2


async def test_many_update(
    db: InfrahubDatabase, tag_blue_main: Node, tag_red_main: Node, person_jack_main: Node, branch: Branch
):
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    relm = await RelationshipManager.init(
        db=db, schema=rel_schema, branch=branch, at=Timestamp(), node=person_jack_main
    )
    await relm.save(db=db)

    # We should have only 1 paths between t1 and p1 via the branch
    paths = await get_paths_between_nodes(
        db=db, source_id=tag_blue_main.db_id, destination_id=person_jack_main.db_id, max_length=2
    )
    assert len(paths) == 1

    paths = await get_paths_between_nodes(
        db=db, source_id=tag_red_main.db_id, destination_id=person_jack_main.db_id, max_length=2
    )
    assert len(paths) == 1

    await relm.update(db=db, data=tag_blue_main)
    await relm.save(db=db)

    paths = await get_paths_between_nodes(
        db=db, source_id=tag_blue_main.db_id, destination_id=person_jack_main.db_id, max_length=2
    )
    assert len(paths) == 2

    paths = await get_paths_between_nodes(
        db=db, source_id=tag_red_main.db_id, destination_id=person_jack_main.db_id, max_length=2
    )
    assert len(paths) == 1

    await relm.update(db=db, data=[tag_blue_main, tag_red_main])
    await relm.save(db=db)

    paths = await get_paths_between_nodes(
        db=db, source_id=tag_blue_main.db_id, destination_id=person_jack_main.db_id, max_length=2
    )
    assert len(paths) == 2

    paths = await get_paths_between_nodes(
        db=db, source_id=tag_red_main.db_id, destination_id=person_jack_main.db_id, max_length=2
    )
    assert len(paths) == 2


async def test_many_add(
    db: InfrahubDatabase, tag_blue_main: Node, tag_red_main: Node, person_jack_main: Node, branch: Branch
):
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    relm = await RelationshipManager.init(
        db=db, schema=rel_schema, branch=branch, at=Timestamp(), node=person_jack_main
    )
    await relm.save(db=db)

    paths = await get_paths_between_nodes(
        db=db, source_id=tag_blue_main.db_id, destination_id=person_jack_main.db_id, max_length=2
    )
    assert len(paths) == 1

    paths = await get_paths_between_nodes(
        db=db, source_id=tag_red_main.db_id, destination_id=person_jack_main.db_id, max_length=2
    )
    assert len(paths) == 1

    await relm.add(db=db, data=tag_blue_main)
    await relm.save(db=db)

    paths = await get_paths_between_nodes(
        db=db, source_id=tag_blue_main.db_id, destination_id=person_jack_main.db_id, max_length=2
    )
    assert len(paths) == 2

    paths = await get_paths_between_nodes(
        db=db, source_id=tag_red_main.db_id, destination_id=person_jack_main.db_id, max_length=2
    )
    assert len(paths) == 1

    await relm.add(db=db, data=tag_red_main)
    await relm.save(db=db)

    paths = await get_paths_between_nodes(
        db=db, source_id=tag_blue_main.db_id, destination_id=person_jack_main.db_id, max_length=2
    )
    assert len(paths) == 2

    paths = await get_paths_between_nodes(
        db=db, source_id=tag_red_main.db_id, destination_id=person_jack_main.db_id, max_length=2
    )
    assert len(paths) == 2
