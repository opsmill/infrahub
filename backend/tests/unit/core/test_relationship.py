import pytest

from infrahub import exceptions as infra_execs
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind, MetadataOptions
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.ip_prefix_pool import CoreIPPrefixPool
from infrahub.core.query.relationship import RelationshipGetPeerQuery
from infrahub.core.relationship.model import Relationship, RelationshipValidatorList
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase


async def test_relationship_init(
    db: InfrahubDatabase, default_branch: Branch, tag_blue_main: Node, person_jack_main: Node, branch: Branch
) -> None:
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    rel = Relationship(schema=rel_schema, branch=branch, source_kind=person_jack_main.get_kind(), node=person_jack_main)

    assert rel.schema == rel_schema
    assert rel.name == rel_schema.name
    assert rel.branch == branch
    assert rel.node_id == person_jack_main.id
    assert await rel.get_node(db=db) == person_jack_main

    rel = Relationship(
        schema=rel_schema, branch=branch, source_kind=person_jack_main.get_kind(), node_id=person_jack_main.id
    )

    assert rel.schema == rel_schema
    assert rel.name == rel_schema.name
    assert rel.branch == branch
    assert rel.node_id == person_jack_main.id

    rel_node = await rel.get_node(db=db)
    assert type(rel_node) is Node
    assert rel_node.id == person_jack_main.id


async def test_relationship_init_w_node_property(
    db: InfrahubDatabase,
    default_branch: Branch,
    first_account: Node,
    second_account: Node,
    tag_blue_main: Node,
    person_jack_main: Node,
    branch: Branch,
) -> None:
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    rel = Relationship(
        schema=rel_schema,
        branch=branch,
        source_kind=person_jack_main.get_kind(),
        node=person_jack_main,
        source=first_account,
        owner=second_account,
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
) -> None:
    car_schema = registry.schema.get(name="TestCar")
    rel_schema = car_schema.get_relationship("owner")

    rel = Relationship(
        schema=rel_schema,
        branch=branch,
        source_kind=car_smart_properties_main.get_kind(),
        node=car_smart_properties_main,
    )

    query = await RelationshipGetPeerQuery.init(
        db=db,
        source=car_smart_properties_main,
        branch=branch,
        at=Timestamp(),
        rel=rel,
        include_metadata=MetadataOptions.IS_PROTECTED | MetadataOptions.IS_VISIBLE,
    )
    await query.execute(db=db)

    peers = list(query.get_peers())

    assert peers[0].properties["is_protected"].value is True

    rel.load(db=db, data=peers[0])

    assert rel.id == peers[0].rel_node_id
    assert rel.db_id == peers[0].rel_node_db_id

    assert rel.is_protected is True
    assert rel.is_visible is False


async def test_relationship_peer(
    db: InfrahubDatabase, tag_blue_main: Node, person_jack_main: Node, branch: Branch
) -> None:
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    rel = Relationship(schema=rel_schema, branch=branch, source_kind=person_jack_main.get_kind(), node=person_jack_main)
    rel.set_peer(value=tag_blue_main)

    assert rel.schema == rel_schema
    assert rel.name == rel_schema.name
    assert rel.branch == branch
    assert rel.node_id == person_jack_main.id
    assert await rel.get_node(db=db) == person_jack_main
    assert rel.peer_id == tag_blue_main.id
    assert await rel.get_peer(db=db) == tag_blue_main


async def test_relationship_save(
    db: InfrahubDatabase, tag_blue_main: Node, person_jack_main: Node, branch: Branch
) -> None:
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    rel = Relationship(schema=rel_schema, branch=branch, source_kind=person_jack_main.get_kind(), node=person_jack_main)
    rel.set_peer(value=tag_blue_main)
    await rel.save(db=db)

    p11 = await NodeManager.get_one(id=person_jack_main.id, db=db, branch=branch)
    tags = await p11.tags.get(db=db)
    assert len(tags) == 1
    assert tags[0].id == rel.id


async def test_relationship_hash(
    db: InfrahubDatabase, tag_blue_main: Node, person_jack_main: Node, branch: Branch, first_account
) -> None:
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    rel = Relationship(schema=rel_schema, branch=branch, source_kind=person_jack_main.get_kind(), node=person_jack_main)
    rel.set_peer(value=tag_blue_main)
    await rel.save(db=db)
    hash1 = hash(rel)

    # Update flag property back and forth and check that hash is the same
    rel.load(db=db, data={"_relation__is_protected": True})
    hash2 = hash(rel)

    rel.load(db=db, data={"_relation__is_protected": False})
    hash3 = hash(rel)

    assert hash1 == hash3
    assert hash1 != hash2

    # Update node property back and forth and check that hash is the same as well
    rel.load(db=db, data={"_relation__owner": first_account})
    hash4 = hash(rel)

    rel.load(db=db, data={"_relation__owner": None})
    hash5 = hash(rel)

    rel.load(db=db, data={"_relation__owner": first_account})
    hash6 = hash(rel)

    assert hash4 == hash6
    assert hash4 != hash5


async def test_relationship_validate_one_init_empty_success() -> None:
    result = RelationshipValidatorList(name="name", min_count=1, max_count=1)

    # Assert that the list is empty
    assert not result
    assert result.min_count == 1
    assert result.max_count == 1
    assert isinstance(result, RelationshipValidatorList)


async def test_relationship_validate_many_init_empty_success() -> None:
    result = RelationshipValidatorList(name="name", min_count=100, max_count=100)

    # Assert that the list is empty
    assert not result
    assert result.min_count == 100
    assert result.max_count == 100


async def test_relationship_validate_empty_init_success() -> None:
    result = RelationshipValidatorList(name="name")

    # Assert that the list is empty
    assert not result
    assert result.min_count == 0
    assert result.max_count == 0
    assert isinstance(result, RelationshipValidatorList)


async def test_relationship_validate_many_init_empty_raise_min_ge_max() -> None:
    with pytest.raises(infra_execs.ValidationError):
        RelationshipValidatorList(name="name", min_count=200, max_count=100)


async def test_relationship_validate_init_below_min_raise(
    db: InfrahubDatabase, person_jack_main: Node, branch: Branch
) -> None:
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    rel_jack = Relationship(
        schema=rel_schema, branch=branch, source_kind=person_jack_main.get_kind(), node=person_jack_main
    )

    with pytest.raises(infra_execs.ValidationError, match="max_count must be greater than min_count"):
        RelationshipValidatorList(rel_jack, name="name", min_count=3, max_count=0)


async def test_relationship_validate_init_above_max_raise(
    db: InfrahubDatabase, person_jack_main: None, branch: Branch
) -> None:
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    rel_1 = Relationship(
        schema=rel_schema, branch=branch, source_kind=person_jack_main.get_kind(), node=person_jack_main
    )
    rel_2 = Relationship(
        schema=rel_schema, branch=branch, source_kind=person_schema.kind, node=Node(person_schema, branch, at="now")
    )
    rel_3 = Relationship(
        schema=rel_schema, branch=branch, source_kind=person_schema.kind, node=Node(person_schema, branch, at="now")
    )

    with pytest.raises(infra_execs.ValidationError, match="Too many relationships, max 2"):
        RelationshipValidatorList(rel_1, rel_2, rel_3, name="name", min_count=0, max_count=2)


async def test_relationship_validate_one_success(db: InfrahubDatabase, person_jack_main: Node, branch: Branch) -> None:
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    rel_jack = Relationship(
        schema=rel_schema, branch=branch, source_kind=person_jack_main.get_kind(), node=person_jack_main
    )

    result = RelationshipValidatorList(rel_jack, name="name", min_count=1, max_count=1)

    result.append(rel_jack)
    assert len(result) == 1
    assert result._relationships_count == 1
    result.clear()
    assert result._relationships_count == 0
    assert len(result) == 0
    assert result.min_count == 1
    assert result.max_count == 1


async def test_relationship_validate_one_append_raise(
    db: InfrahubDatabase, person_jack_main: Node, branch: Branch
) -> None:
    """Validate that it raises when appending a second relationship onto cardinality of one."""
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    rel_jack = Relationship(
        schema=rel_schema, branch=branch, source_kind=person_jack_main.get_kind(), node=person_jack_main
    )
    rel_doe = Relationship(
        schema=rel_schema, branch=branch, source_kind=person_schema.kind, node=Node(person_schema, branch, at="now")
    )
    result = RelationshipValidatorList(name="name", min_count=1, max_count=1)

    assert len(result) == 0
    assert result._relationships_count == 0

    result.append(rel_jack)
    assert len(result) == 1
    assert result._relationships_count == 1

    with pytest.raises(infra_execs.ValidationError, match="Too many relationships, max 1"):
        result.append(rel_doe)


async def test_relationship_validate_one_append_extend_duplicate(
    db: InfrahubDatabase, person_jack_main: Node, branch: Branch
) -> None:
    """Attempting to use the methods that would insert over the max_count but are duplicates."""
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    rel_jack = Relationship(
        schema=rel_schema, branch=branch, source_kind=person_jack_main.get_kind(), node=person_jack_main
    )
    result = RelationshipValidatorList(rel_jack, name="name", min_count=1, max_count=1)

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


async def test_relationship_validate_one_extend_raise(
    db: InfrahubDatabase, person_jack_main: Node, branch: Branch
) -> None:
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    rel_jack = Relationship(
        schema=rel_schema, branch=branch, source_kind=person_jack_main.get_kind(), node=person_jack_main
    )

    result = RelationshipValidatorList(rel_jack, name="name", min_count=1, max_count=1)

    with pytest.raises(infra_execs.ValidationError, match="Too many relationships, max 1"):
        rel_albert = Relationship(
            schema=rel_schema, branch=branch, source_kind=person_schema.kind, node=Node(person_schema, branch, at="now")
        )
        result.extend([rel_albert])


async def test_relationship_validate_one_remove_raise(
    db: InfrahubDatabase, person_jack_main: Node, branch: Branch
) -> None:
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    rel_jack = Relationship(
        schema=rel_schema, branch=branch, source_kind=person_jack_main.get_kind(), node=person_jack_main
    )

    result = RelationshipValidatorList(rel_jack, name="name", min_count=1, max_count=1)

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
) -> None:
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    rel_jack = Relationship(
        schema=rel_schema, branch=branch, source_kind=person_jack_main.get_kind(), node=person_jack_main
    )
    rel_doe_one = Relationship(
        schema=rel_schema, branch=branch, source_kind=person_schema.kind, node=Node(person_schema, branch, at="now")
    )
    rel_doe_two = Relationship(
        schema=rel_schema, branch=branch, source_kind=person_schema.kind, node=Node(person_schema, branch, at="now")
    )

    result = RelationshipValidatorList(rel_jack, rel_doe_one, rel_doe_two, name="name", min_count=0, max_count=0)

    assert result[0] == rel_jack
    assert result[1] == rel_doe_one
    assert result[2] == rel_doe_two


async def test_relationship_validate_many_no_limit_duplicate_success(
    db: InfrahubDatabase, person_jack_main: Node, branch: Branch
) -> None:
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    rel = Relationship(schema=rel_schema, branch=branch, source_kind=person_jack_main.get_kind(), node=person_jack_main)

    result = RelationshipValidatorList(rel, name="name", min_count=rel_schema.min_count, max_count=rel_schema.max_count)

    for _ in range(5):
        result.append(rel)
    assert len(result) == 1
    assert result[0] == rel


async def test_relationship_validate_many_above_max_count_raise(
    db: InfrahubDatabase, person_jack_main: Node, branch: Branch
) -> None:
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    rel_jack = Relationship(
        schema=rel_schema, branch=branch, source_kind=person_jack_main.get_kind(), node=person_jack_main
    )
    rel_doe_one = Relationship(
        schema=rel_schema, branch=branch, source_kind=person_schema.kind, node=Node(person_schema, branch, at="now")
    )
    rel_doe_two = Relationship(
        schema=rel_schema, branch=branch, source_kind=person_schema.kind, node=Node(person_schema, branch, at="now")
    )

    result = RelationshipValidatorList(name="name", min_count=2, max_count=2)
    result.extend([rel_jack, rel_doe_one])

    assert result[0] == rel_jack
    assert result[1] == rel_doe_one
    assert result._relationships_count == 2

    expected_msg = "Too many relationships, max 2"
    with pytest.raises(infra_execs.ValidationError, match=expected_msg):
        result.append(rel_doe_two)
    with pytest.raises(infra_execs.ValidationError, match=expected_msg):
        result.insert(2, rel_doe_two)
    with pytest.raises(infra_execs.ValidationError, match=expected_msg):
        result.extend([rel_doe_two])


async def test_relationship_validate_many_less_than_min_raise(
    db: InfrahubDatabase, person_jack_main: Node, branch: Branch
) -> None:
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    rel_jack = Relationship(
        schema=rel_schema, branch=branch, source_kind=person_jack_main.get_kind(), node=person_jack_main
    )
    rel_doe_one = Relationship(
        schema=rel_schema, branch=branch, source_kind=person_schema.kind, node=Node(person_schema, branch, at="now")
    )

    result = RelationshipValidatorList(rel_jack, rel_doe_one, name="name", min_count=2, max_count=2)

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


async def test_relationship_assign_from_pool(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_extended_schema: SchemaBranch,
    init_nodes_registry,
    ip_dataset_prefix_v4,
) -> None:
    ns1 = ip_dataset_prefix_v4["ns1"]
    net140 = ip_dataset_prefix_v4["net140"]

    prefix_pool_schema = registry.schema.get_node_schema(name=InfrahubKind.IPPREFIXPOOL, branch=default_branch)
    mandatory_prefix_schema = registry.schema.get_node_schema(name="TestMandatoryPrefix", branch=default_branch)

    pool = await CoreIPPrefixPool.init(schema=prefix_pool_schema, db=db, branch=default_branch)
    await pool.new(
        db=db,
        name="pool1",
        default_prefix_length=24,
        default_prefix_type="IpamIPPrefix",
        resources=[net140],
        ip_namespace=ns1,
    )
    await pool.save(db=db)

    obj = await Node.init(schema=mandatory_prefix_schema, db=db, branch=default_branch)
    await obj.new(db=db, name={"value": "site1"}, prefix={"from_pool": {"id": pool.id}})
    await obj.save(db=db)

    assert await obj.prefix.get_peer(db=db)


async def test_relationship_timestamp_changes(
    db: InfrahubDatabase, person_jack_main: Node, tag_blue_main: Node, tag_red_main: Node, branch: Branch
) -> None:
    # test going back in time after adding a relationship
    before_add = Timestamp()
    person_jack = await NodeManager.get_one(db=db, branch=branch, id=person_jack_main.id)
    await person_jack.tags.update(db=db, data=[tag_blue_main.id])
    await person_jack.save(db=db)
    before_add_person_jack = await NodeManager.get_one(
        db=db, branch=branch, id=person_jack_main.id, at=before_add, prefetch_relationships=True
    )
    tag_rels = await before_add_person_jack.tags.get_relationships(db=db)
    assert not tag_rels

    # test going back in time after deleting a relationship
    before_remove = Timestamp()
    person_jack = await NodeManager.get_one(db=db, branch=branch, id=person_jack_main.id)
    await person_jack.tags.update(db=db, data=[None])
    await person_jack.save(db=db)
    before_remove_person_jack = await NodeManager.get_one(
        db=db, branch=branch, id=person_jack_main.id, at=before_remove, prefetch_relationships=True
    )
    tag_rels = await before_remove_person_jack.tags.get_relationships(db=db)
    assert len(tag_rels) == 1
    assert [r.peer_id for r in tag_rels] == [tag_blue_main.id]

    # test with manually set save time
    save_time = Timestamp()
    before_save = save_time.add(microseconds=-1)
    after_save = save_time.add(microseconds=1)
    person_jack = await NodeManager.get_one(db=db, branch=branch, id=person_jack_main.id)
    await person_jack.tags.update(db=db, data=[tag_red_main.id])
    await person_jack.save(db=db, at=save_time)
    before_save_person_jack = await NodeManager.get_one(
        db=db, branch=branch, id=person_jack_main.id, at=before_save, prefetch_relationships=True
    )
    tag_rels = await before_save_person_jack.tags.get_relationships(db=db)
    assert len(tag_rels) == 0
    after_save_person_jack = await NodeManager.get_one(
        db=db, branch=branch, id=person_jack_main.id, at=after_save, prefetch_relationships=True
    )
    tag_rels = await after_save_person_jack.tags.get_relationships(db=db)
    assert len(tag_rels) == 1
    assert [r.peer_id for r in tag_rels] == [tag_red_main.id]


async def test_relationship_second_delete_is_ignored(
    db: InfrahubDatabase, person_jack_main: Node, tag_blue_main: Node, branch: Branch
) -> None:
    person_jack = await NodeManager.get_one(db=db, branch=branch, id=person_jack_main.id)
    await person_jack.tags.update(db=db, data=[tag_blue_main.id])
    await person_jack.save(db=db)
    rels = await person_jack.tags.get_relationships(db=db)

    blue_tag_rel = rels[0]
    await blue_tag_rel.delete(db=db)
    await blue_tag_rel.delete(db=db)

    # verify that only 1 delete path exists
    query = """
MATCH (s:Node {uuid: $source_id})-[r1:IS_RELATED]-(:Relationship {name: $rel_name})-[r2:IS_RELATED]-(d:Node {uuid: $dest_id})
RETURN r1, r2
    """
    results = await db.execute_query(
        query=query,
        params={
            "source_id": person_jack_main.id,
            "branch": branch.name,
            "rel_name": "builtintag__testperson",
            "dest_id": tag_blue_main.id,
        },
    )
    assert len(results) == 1
    r1 = results[0].get("r1")
    r2 = results[0].get("r2")
    assert r1.get("status") == "active" and r1.get("branch") == branch.name and r1.get("to") is not None
    assert r2.get("status") == "active" and r2.get("branch") == branch.name and r2.get("to") is not None


async def test_can_create_relationship_with_min_count_only(
    db: InfrahubDatabase, person_jack_main: Node, branch: Branch
) -> None:
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    rel_jack = Relationship(
        schema=rel_schema, branch=branch, source_kind=person_jack_main.get_kind(), node=person_jack_main
    )
    rel_doe_one = Relationship(
        schema=rel_schema, branch=branch, source_kind=person_schema.kind, node=Node(person_schema, branch, at="now")
    )

    result = RelationshipValidatorList(rel_jack, rel_doe_one, name="name", min_count=1, max_count=None)

    assert result.min_count == 1
    assert result.max_count == 0
    assert len(result) == 2
