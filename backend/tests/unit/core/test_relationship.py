import pytest

from infrahub import exceptions as infra_execs
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.query.relationship import RelationshipGetPeerQuery
from infrahub.core.relationship import Relationship, RelationshipValidatorList
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


async def test_relationship_validate_one_init_empty_success():
    result = RelationshipValidatorList(min_count=1, max_count=1)

    # Assert that the list is empty
    assert not result
    assert result.min_count == 1
    assert result.max_count == 1
    assert isinstance(result, RelationshipValidatorList)


async def test_relationship_validate_many_init_empty_success():
    result = RelationshipValidatorList(min_count=100, max_count=100)

    # Assert that the list is empty
    assert not result
    assert result.min_count == 100
    assert result.max_count == 100


async def test_relationship_validate_empty_init_success():
    result = RelationshipValidatorList()

    # Assert that the list is empty
    assert not result
    assert result.min_count == 0
    assert result.max_count == 0
    assert isinstance(result, RelationshipValidatorList)


async def test_relationship_validate_many_init_empty_raise_min_ge_max():
    with pytest.raises(infra_execs.ValidationError):
        RelationshipValidatorList(min_count=200, max_count=100)


async def test_relationship_validate_init_below_min_raise(db: InfrahubDatabase, person_jack_main: Node, branch: Branch):
    person_schema = registry.get_schema(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    rel_jack = Relationship(schema=rel_schema, branch=branch, node=person_jack_main)

    with pytest.raises(infra_execs.ValidationError, match="max_count must be greater than min_count"):
        RelationshipValidatorList(rel_jack, min_count=3, max_count=0)


async def test_relationship_validate_init_above_max_raise(db: InfrahubDatabase, person_jack_main: None, branch: Branch):
    person_schema = registry.get_schema(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    rel_1 = Relationship(schema=rel_schema, branch=branch, node=person_jack_main)
    rel_2 = Relationship(schema=rel_schema, branch=branch, node=Node(person_schema, branch, at="now"))
    rel_3 = Relationship(schema=rel_schema, branch=branch, node=Node(person_schema, branch, at="now"))

    with pytest.raises(infra_execs.ValidationError, match="Too many relationships, max 2"):
        RelationshipValidatorList(rel_1, rel_2, rel_3, min_count=0, max_count=2)


async def test_relationship_validate_one_success(db: InfrahubDatabase, person_jack_main: Node, branch: Branch):
    person_schema = registry.get_schema(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    rel_jack = Relationship(schema=rel_schema, branch=branch, node=person_jack_main)

    result = RelationshipValidatorList(rel_jack, min_count=1, max_count=1)

    result.append(rel_jack)
    assert len(result) == 1
    assert result._relationships_count == 1
    result.clear()
    assert len(result) == 0
    assert result.min_count == 1
    assert result.max_count == 1


async def test_relationship_validate_one_append_raise(db: InfrahubDatabase, person_jack_main: Node, branch: Branch):
    """Validate that it raises when appending a second relationship onto cardinality of one."""
    person_schema = registry.get_schema(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    rel_jack = Relationship(schema=rel_schema, branch=branch, node=person_jack_main)
    rel_doe = Relationship(schema=rel_schema, branch=branch, node=Node(person_schema, branch, at="now"))
    result = RelationshipValidatorList(min_count=1, max_count=1)

    assert len(result) == 0
    assert result._relationships_count == 0

    result.append(rel_jack)
    assert len(result) == 1
    assert result._relationships_count == 1

    with pytest.raises(infra_execs.ValidationError, match="Too many relationships, max 1"):
        result.append(rel_doe)


async def test_relationship_validate_one_append_extend_duplicate(
    db: InfrahubDatabase, person_jack_main: Node, branch: Branch
):
    """Attempting to use the methods that would insert over the max_count but are duplicates."""
    person_schema = registry.get_schema(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    rel_jack = Relationship(schema=rel_schema, branch=branch, node=person_jack_main)
    result = RelationshipValidatorList(rel_jack, min_count=1, max_count=1)

    # RelationshipValidatorList should not append/extend a duplicate relationship
    result.append(rel_jack)
    assert len(result) == 1
    assert result._relationships_count == 1
    result.extend([rel_jack])
    assert result._relationships_count == 1
    result.insert(1, rel_jack)
    assert rel_jack in result
    assert result._relationships_count == 1
    assert result.get(0) == rel_jack


async def test_relationship_validate_one_extend_raise(db: InfrahubDatabase, person_jack_main: Node, branch: Branch):
    person_schema = registry.get_schema(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    rel_jack = Relationship(schema=rel_schema, branch=branch, node=person_jack_main)

    result = RelationshipValidatorList(rel_jack, min_count=1, max_count=1)

    with pytest.raises(infra_execs.ValidationError, match="Too many relationships, max 1"):
        rel_albert = Relationship(schema=rel_schema, branch=branch, node=Node(person_schema, branch, at="now"))
        result.extend([rel_albert])


async def test_relationship_validate_one_remove_raise(db: InfrahubDatabase, person_jack_main: Node, branch: Branch):
    person_schema = registry.get_schema(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    rel_jack = Relationship(schema=rel_schema, branch=branch, node=person_jack_main)

    result = RelationshipValidatorList(rel_jack, min_count=1, max_count=1)

    expected_msg = "Too few relationships, min 1"
    with pytest.raises(infra_execs.ValidationError, match=expected_msg):
        result.pop()
    with pytest.raises(infra_execs.ValidationError, match=expected_msg):
        result.pop(0)
    with pytest.raises(infra_execs.ValidationError, match=expected_msg):
        result.remove(rel_jack)
    with pytest.raises(infra_execs.ValidationError, match=expected_msg):
        del result[0]


async def test_relationship_validate_many_no_limit_success(
    db: InfrahubDatabase, person_jack_main: Node, branch: Branch
):
    person_schema = registry.get_schema(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    rel_jack = Relationship(schema=rel_schema, branch=branch, node=person_jack_main)
    rel_doe_one = Relationship(schema=rel_schema, branch=branch, node=Node(person_schema, branch, at="now"))
    rel_doe_two = Relationship(schema=rel_schema, branch=branch, node=Node(person_schema, branch, at="now"))

    result = RelationshipValidatorList(rel_jack, rel_doe_one, rel_doe_two, min_count=0, max_count=0)

    assert result[0] == rel_jack
    assert result[1] == rel_doe_one
    assert result[2] == rel_doe_two


async def test_relationship_validate_many_no_limit_duplicate_success(
    db: InfrahubDatabase, person_jack_main: Node, branch: Branch
):
    person_schema = registry.get_schema(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    rel = Relationship(schema=rel_schema, branch=branch, node=person_jack_main)

    result = RelationshipValidatorList(rel, min_count=rel_schema.min_count, max_count=rel_schema.max_count)

    for _ in range(5):
        result.append(rel)
    assert len(result) == 1
    assert result[0] == rel


async def test_relationship_validate_many_above_max_count_raise(
    db: InfrahubDatabase, person_jack_main: Node, branch: Branch
):
    person_schema = registry.get_schema(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    rel_jack = Relationship(schema=rel_schema, branch=branch, node=person_jack_main)
    rel_doe_one = Relationship(schema=rel_schema, branch=branch, node=Node(person_schema, branch, at="now"))
    rel_doe_two = Relationship(schema=rel_schema, branch=branch, node=Node(person_schema, branch, at="now"))

    result = RelationshipValidatorList(rel_jack, rel_doe_one, min_count=2, max_count=2)

    assert result[0] == rel_jack
    assert result[1] == rel_doe_one

    expected_msg = "Too many relationships, max 2"
    with pytest.raises(infra_execs.ValidationError, match=expected_msg):
        result.append(rel_doe_two)
    with pytest.raises(infra_execs.ValidationError, match=expected_msg):
        result.insert(2, rel_doe_two)
    with pytest.raises(infra_execs.ValidationError, match=expected_msg):
        result.extend([rel_doe_two])


async def test_relationship_validate_many_less_than_min_raise(
    db: InfrahubDatabase, person_jack_main: Node, branch: Branch
):
    person_schema = registry.get_schema(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    rel_jack = Relationship(schema=rel_schema, branch=branch, node=person_jack_main)
    rel_doe_one = Relationship(schema=rel_schema, branch=branch, node=Node(person_schema, branch, at="now"))

    result = RelationshipValidatorList(rel_jack, rel_doe_one, min_count=2, max_count=2)

    assert result[0] == rel_jack
    assert result[1] == rel_doe_one

    expected_msg = "Too few relationships, min 2"
    with pytest.raises(infra_execs.ValidationError, match=expected_msg):
        result.pop()
    with pytest.raises(infra_execs.ValidationError, match=expected_msg):
        result.pop(0)
    with pytest.raises(infra_execs.ValidationError, match=expected_msg):
        result.remove(rel_doe_one)
    with pytest.raises(infra_execs.ValidationError, match=expected_msg):
        del result[0]
