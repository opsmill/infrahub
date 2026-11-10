from dataclasses import dataclass

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.query.relationship import RelationshipGetPeerQuery
from infrahub.core.relationship import RelationshipManager
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import get_paths_between_nodes
from infrahub.database import InfrahubDatabase
from tests.helpers.db_query_counter import CountingInfrahubDatabase


async def test_one_init_no_input_no_rel(db: InfrahubDatabase, person_jack_main: Node, branch: Branch) -> None:
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
) -> None:
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


async def test_many_init_no_input_no_rel(db: InfrahubDatabase, person_jack_main: Node, branch: Branch) -> None:
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    relm = await RelationshipManager.init(
        db=db, schema=rel_schema, branch=branch, at=Timestamp(), node=person_jack_main
    )

    # shouldn't be able to query the peer since it's many type relationship
    with pytest.raises(TypeError):
        await relm.get_peer(db=db)

    assert not len(await relm.get(db=db))


async def test_many_init_no_input_existing_rel(
    db: InfrahubDatabase, person_jack_tags_main: Node, branch: Branch
) -> None:
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    relm = await RelationshipManager.init(
        db=db, schema=rel_schema, branch=branch, at=Timestamp(), node=person_jack_tags_main
    )

    assert len(await relm.get(db=db)) == 2


async def test_one_init_input_obj(
    db: InfrahubDatabase, tag_blue_main: Node, person_jack_main: Node, branch: Branch
) -> None:
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


async def test_one_save_input_obj(
    db: InfrahubDatabase, tag_blue_main: Node, person_jack_main: Node, branch: Branch
) -> None:
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
) -> None:
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
) -> None:
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
) -> None:
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
) -> None:
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


async def test_many_update_with_tuple(
    db: InfrahubDatabase, tag_blue_main: Node, tag_red_main: Node, person_jack_main: Node, branch: Branch
) -> None:
    """A tuple of peers is treated as a collection of peers, like the equivalent list."""
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    relm = await RelationshipManager.init(
        db=db, schema=rel_schema, branch=branch, at=Timestamp(), node=person_jack_main
    )
    await relm.save(db=db)

    await relm.update(db=db, data=(tag_blue_main, tag_red_main))
    await relm.save(db=db)

    peer_ids = {rel.peer_id for rel in await relm.get_relationships(db=db)}
    assert peer_ids == {tag_blue_main.id, tag_red_main.id}


async def test_many_update_with_peer_id_string(
    db: InfrahubDatabase, tag_blue_main: Node, person_jack_main: Node, branch: Branch
) -> None:
    """A peer id is a single peer, never a sequence of one-character peer ids."""
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    relm = await RelationshipManager.init(
        db=db, schema=rel_schema, branch=branch, at=Timestamp(), node=person_jack_main
    )
    await relm.save(db=db)

    await relm.update(db=db, data=tag_blue_main.id)
    await relm.save(db=db)

    peer_ids = {rel.peer_id for rel in await relm.get_relationships(db=db)}
    assert peer_ids == {tag_blue_main.id}


async def test_many_add(
    db: InfrahubDatabase, tag_blue_main: Node, tag_red_main: Node, person_jack_main: Node, branch: Branch
) -> None:
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


async def test_get_parent(db: InfrahubDatabase, car_accord_main: Node, person_john_main: Node, branch: Branch) -> None:
    car_schema = registry.schema.get(name="TestCar")
    rel_schema = car_schema.get_relationship("owner")

    relm = await RelationshipManager.init(db=db, schema=rel_schema, branch=branch, at=Timestamp(), node=car_accord_main)
    parent = await relm.get_parent(db=db)
    assert parent
    assert parent.get_peer_id() == person_john_main.id
    assert parent.get_peer_kind() == person_john_main.get_kind()


@dataclass
class RelationshipManagerOptionalAndCountTestCaseData:
    name: str
    optional: bool
    schema_min_count: int
    schema_max_count: int
    expected_min_count: int
    expected_max_count: int


RELATIONSHIP_MANAGER_OPTIONAL_AND_COUNT_CONSTRAINTS_TEST_CASES = [
    RelationshipManagerOptionalAndCountTestCaseData(
        name="not-optional-with-min-count-only",
        optional=False,
        schema_min_count=2,
        schema_max_count=0,
        expected_min_count=2,
        expected_max_count=0,
    ),
    RelationshipManagerOptionalAndCountTestCaseData(
        name="optional-with-min-count-only",
        optional=True,
        schema_min_count=2,
        schema_max_count=0,
        expected_min_count=0,
        expected_max_count=0,
    ),
    RelationshipManagerOptionalAndCountTestCaseData(
        name="not-optional-with-min-and-max-count",
        optional=False,
        schema_min_count=2,
        schema_max_count=5,
        expected_min_count=2,
        expected_max_count=5,
    ),
    RelationshipManagerOptionalAndCountTestCaseData(
        name="optional-with-min-and-max-count",
        optional=True,
        schema_min_count=2,
        schema_max_count=5,
        expected_min_count=0,
        expected_max_count=5,
    ),
]


@pytest.mark.parametrize(
    "test_case",
    [pytest.param(tc, id=tc.name) for tc in RELATIONSHIP_MANAGER_OPTIONAL_AND_COUNT_CONSTRAINTS_TEST_CASES],
)
async def test_can_create_relationship_manager_with_optional_and_count_constraints(
    db: InfrahubDatabase,
    tag_blue_main: Node,
    person_jack_primary_tag_main: Node,
    branch: Branch,
    test_case: RelationshipManagerOptionalAndCountTestCaseData,
) -> None:
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("primary_tag")
    rel_schema.optional = test_case.optional
    rel_schema.min_count = test_case.schema_min_count
    rel_schema.max_count = test_case.schema_max_count

    relm = await RelationshipManager.init(
        db=db,
        schema=rel_schema,
        branch=branch,
        at=Timestamp(),
        node=person_jack_primary_tag_main,
    )
    await relm.save(db=db)

    assert relm._relationships.min_count == test_case.expected_min_count
    assert relm._relationships.max_count == test_case.expected_max_count


async def test_no_peer_read_for_a_node_absent_from_the_database(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch
) -> None:
    person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person.new(db=db, name="John", height=180)
    await person.save(db=db)

    car = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car.new(db=db, name="accord", nbr_seats=5, owner=person.id)

    counting_db = CountingInfrahubDatabase.from_db(db=db)
    relm: RelationshipManager = car.owner
    details = await relm.fetch_relationship_ids(db=counting_db, force_refresh=True)

    assert counting_db.count_for(RelationshipGetPeerQuery.name) == 0
    assert details.peers_database == {}
    assert details.peer_ids_present_both == []
    assert details.peer_ids_present_local_only == [person.id]
    assert details.peer_ids_present_database_only == []

    await car.save(db=db)
    saved_car = await NodeManager.get_one(db=db, id=car.id, branch=default_branch, raise_on_error=True)
    counting_db.reset_counts()
    saved_relm: RelationshipManager = saved_car.owner
    details = await saved_relm.fetch_relationship_ids(db=counting_db, force_refresh=True)

    assert counting_db.count_for(RelationshipGetPeerQuery.name) == 1
    assert set(details.peers_database) == {person.id}
    assert details.peer_ids_present_both == []
    assert details.peer_ids_present_local_only == []
    assert details.peer_ids_present_database_only == [person.id]


async def test_update_details_are_recomputed_without_reading_the_peers_again(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch
) -> None:
    john = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await john.new(db=db, name="John", height=180)
    await john.save(db=db)

    jane = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await jane.new(db=db, name="Jane", height=170)
    await jane.save(db=db)

    car = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car.new(db=db, name="accord", nbr_seats=5, owner=john.id)
    await car.save(db=db)

    loaded_car = await NodeManager.get_one(db=db, id=car.id, branch=default_branch, raise_on_error=True)
    counting_db = CountingInfrahubDatabase.from_db(db=db)
    relm: RelationshipManager = loaded_car.owner

    await relm.fetch_relationship_ids(db=counting_db, force_refresh=True)
    assert counting_db.count_for(RelationshipGetPeerQuery.name) == 1

    await relm.update(db=counting_db, data=jane.id)
    details = await relm.refresh_update_details(db=counting_db)

    assert counting_db.count_for(RelationshipGetPeerQuery.name) == 1
    assert details.peer_ids_present_both == []
    assert details.peer_ids_present_local_only == [jane.id]
    assert details.peer_ids_present_database_only == [john.id]

    # Writing to the relationship discards the recorded read, so the next comparison reads again.
    await relm.save(db=counting_db)
    counting_db.reset_counts()
    await relm.refresh_update_details(db=counting_db)

    assert counting_db.count_for(RelationshipGetPeerQuery.name) == 1
    reloaded_car = await NodeManager.get_one(db=db, id=car.id, branch=default_branch, raise_on_error=True)
    reloaded_owner = await reloaded_car.owner.get_peer(db=db)
    assert reloaded_owner is not None
    assert reloaded_owner.id == jane.id


async def test_peers_read_before_the_node_exists_are_not_reused(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch
) -> None:
    """Creating the node writes its edges outside the manager, so that answer cannot be reused."""
    person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person.new(db=db, name="John", height=180)
    await person.save(db=db)

    car = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car.new(db=db, name="accord", nbr_seats=5, owner=person.id)

    relm: RelationshipManager = car.owner
    await relm.fetch_relationship_ids(db=db, force_refresh=True)
    await car.save(db=db)

    counting_db = CountingInfrahubDatabase.from_db(db=db)
    await relm.refresh_update_details(db=counting_db)

    assert counting_db.count_for(RelationshipGetPeerQuery.name) == 1


async def test_details_computed_before_the_node_exists_are_not_reused(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch
) -> None:
    """Once the node is written its edges exist, so the comparison made before that must not be returned again.

    The manager's own `at` predates the write, so the second read is made at a later time to see the edges.
    """
    person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person.new(db=db, name="John", height=180)
    await person.save(db=db)

    car = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car.new(db=db, name="accord", nbr_seats=5, owner=person.id)

    relm: RelationshipManager = car.owner
    details = await relm.fetch_relationship_ids(db=db, force_refresh=True)
    assert details.peer_ids_present_local_only == [person.id]

    await car.save(db=db)

    counting_db = CountingInfrahubDatabase.from_db(db=db)
    details = await relm.fetch_relationship_ids(db=counting_db, at=Timestamp(), force_refresh=False)

    assert counting_db.count_for(RelationshipGetPeerQuery.name) == 1
    assert details.peer_ids_present_both == [person.id]
    assert details.peer_ids_present_local_only == []
    assert details.peer_ids_present_database_only == []
