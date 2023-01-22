import pytest
from neo4j import AsyncSession

from infrahub.core import registry
from infrahub.core.node import Node
from infrahub.core.query.relationship import (
    RelationshipCreateQuery,
    RelationshipDeleteQuery,
    RelationshipGetPeerQuery,
    RelationshipQuery,
)
from infrahub.core.relationship import Relationship
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import get_paths_between_nodes


class DummyRelationshipQuery(RelationshipQuery):
    async def query_init(self, session: AsyncSession, *args, **kwargs):
        pass


async def test_RelationshipQuery_init(session, default_branch, person_tag_schema):

    person_schema = registry.get_schema(name="Person")
    rel_schema = person_schema.get_relationship("tags")

    t1 = await Node.init(session=session, schema="Tag")
    await t1.new(session=session, name="blue")
    await t1.save(session=session)
    p1 = await Node.init(session=session, schema=person_schema)
    await p1.new(session=session, firstname="John", lastname="Doe")
    await p1.save(session=session)

    with pytest.raises(ValueError) as exc:
        rq = DummyRelationshipQuery()
    assert "Either source or source_id must be provided." in str(exc.value)

    with pytest.raises(ValueError) as exc:
        rq = DummyRelationshipQuery(source=p1)
    assert "Either rel or rel_type must be provided." in str(exc.value)

    with pytest.raises(ValueError) as exc:
        rq = DummyRelationshipQuery(source=p1, rel=Relationship)
    assert "Either an instance of Relationship or a valid schema must be provided." in str(exc.value)

    with pytest.raises(ValueError) as exc:
        rq = DummyRelationshipQuery(source=p1, rel=Relationship, schema=rel_schema)
    assert "Either an instance of Relationship or a valid branch must be provided." in str(exc.value)

    # Initialization with the Relationship class
    rq = DummyRelationshipQuery(source=p1, rel=Relationship, schema=rel_schema, branch=default_branch)
    assert rq.schema == rel_schema
    assert rq.branch == default_branch
    assert rq.source_id == p1.id
    assert rq.source == p1

    rq = DummyRelationshipQuery(source_id=p1.id, rel=Relationship, schema=rel_schema, branch=default_branch)
    assert rq.schema == rel_schema
    assert rq.branch == default_branch
    assert rq.source_id == p1.id
    assert rq.source is None

    # Initialization with an instance of Relationship
    rel = Relationship(schema=rel_schema, branch=default_branch, node=p1)
    rq = DummyRelationshipQuery(source=p1, rel=rel)
    assert rq.schema == rel_schema
    assert rq.branch == default_branch


async def test_query_RelationshipCreateQuery(session, default_branch, person_tag_schema):

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

    query = await RelationshipCreateQuery.init(
        session=session,
        source=p1,
        destination=t1,
        schema=rel_schema,
        rel=Relationship,
        branch=default_branch,
        at=Timestamp(),
    )
    await query.execute(session=session)

    # We should have 2 paths between t1 and p1
    # First for the relationship, Second via the branch
    paths = await get_paths_between_nodes(session=session, source_id=t1.db_id, destination_id=p1.db_id, max_length=2)
    assert len(paths) == 2


async def test_query_RelationshipCreateQuery_w_node_property(session, default_branch, person_tag_schema, first_account):

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

    paths = await get_paths_between_nodes(
        session=session, source_id=t1.db_id, destination_id=p1.db_id, relationships=["IS_RELATED"], max_length=2
    )
    assert len(paths) == 0

    rel = Relationship(schema=rel_schema, branch=default_branch, node=p1, source=first_account, owner=first_account)
    query = await RelationshipCreateQuery.init(session=session, source=p1, destination=t1, rel=rel)
    await query.execute(session=session)

    paths = await get_paths_between_nodes(
        session=session, source_id=t1.db_id, destination_id=p1.db_id, relationships=["IS_RELATED"], max_length=2
    )
    assert len(paths) == 1


async def test_query_RelationshipDeleteQuery(session, default_branch, person_tag_schema):

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

    # We should have 2 paths between t1 and p1
    # First for the relationship, Second via the branch
    paths = await get_paths_between_nodes(session=session, source_id=t1.db_id, destination_id=p1.db_id, max_length=2)
    assert len(paths) == 2

    query = await RelationshipDeleteQuery.init(
        session=session,
        source=p1,
        destination=t1,
        schema=rel_schema,
        rel=Relationship,
        branch=default_branch,
        at=Timestamp(),
    )
    await query.execute(session=session)

    # We should have 5 paths between t1 and p1
    # Because we have 3 "real" paths between the nodes
    # but if we calculate all the permutations it will equal to 5 paths.
    paths = await get_paths_between_nodes(session=session, source_id=t1.db_id, destination_id=p1.db_id, max_length=2)
    assert len(paths) == 5


async def test_query_RelationshipGetPeerQuery(session, default_branch, person_tag_schema):

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

    query = await RelationshipGetPeerQuery.init(
        session=session, source_id=p1.id, schema=rel_schema, rel=Relationship, branch=default_branch, at=Timestamp()
    )
    await query.execute(session=session)

    peers = list(query.get_peers())
    assert len(peers) == 2
    assert len(peers[0].rels) == 2
    assert isinstance(peers[0].rel_node_db_id, str)
    assert isinstance(peers[0].rel_node_id, str)
    assert list(peers[0].properties.keys()) == ["is_visible", "is_protected"]
    assert peers[0].properties["is_visible"].value is True
    assert peers[0].properties["is_protected"].value is False
    assert peers[0].properties["is_protected"].prop_db_id == peers[1].properties["is_protected"].prop_db_id
    assert isinstance(peers[0].properties["is_protected"].prop_db_id, str)
    assert isinstance(peers[0].properties["is_protected"].rel.db_id, str)
    assert isinstance(peers[0].properties["is_protected"].prop_db_id, str)


async def test_query_RelationshipGetPeerQuery_with_filter(session, default_branch, person_tag_schema):

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

    query = await RelationshipGetPeerQuery.init(
        session=session,
        source_id=p1.id,
        schema=rel_schema,
        filters={"tags__name__value": "blue"},
        rel=Relationship,
        branch=default_branch,
        at=Timestamp(),
    )
    await query.execute(session=session)

    assert len(query.get_peer_ids()) == 1
