import pytest
from neo4j import AsyncSession

from infrahub.core import registry
from infrahub.core.branch import Branch
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


async def test_RelationshipQuery_init(
    session: AsyncSession, tag_blue_main: Node, person_jack_main: Node, branch: Branch
):
    person_schema = registry.get_schema(name="Person")
    rel_schema = person_schema.get_relationship("tags")

    with pytest.raises(ValueError) as exc:
        rq = DummyRelationshipQuery()
    assert "Either source or source_id must be provided." in str(exc.value)

    with pytest.raises(ValueError) as exc:
        rq = DummyRelationshipQuery(source=person_jack_main)
    assert "Either rel or rel_type must be provided." in str(exc.value)

    with pytest.raises(ValueError) as exc:
        rq = DummyRelationshipQuery(source=person_jack_main, rel=Relationship)
    assert "Either an instance of Relationship or a valid schema must be provided." in str(exc.value)

    with pytest.raises(ValueError) as exc:
        rq = DummyRelationshipQuery(source=person_jack_main, rel=Relationship, schema=rel_schema)
    assert "Either an instance of Relationship or a valid branch must be provided." in str(exc.value)

    # Initialization with the Relationship class
    rq = DummyRelationshipQuery(source=person_jack_main, rel=Relationship, schema=rel_schema, branch=branch)
    assert rq.schema == rel_schema
    assert rq.branch == branch
    assert rq.source_id == person_jack_main.id
    assert rq.source == person_jack_main

    rq = DummyRelationshipQuery(source_id=person_jack_main.id, rel=Relationship, schema=rel_schema, branch=branch)
    assert rq.schema == rel_schema
    assert rq.branch == branch
    assert rq.source_id == person_jack_main.id
    assert rq.source is None

    # Initialization with an instance of Relationship
    rel = Relationship(schema=rel_schema, branch=branch, node=person_jack_main)
    rq = DummyRelationshipQuery(source=person_jack_main, rel=rel)
    assert rq.schema == rel_schema
    assert rq.branch == branch


async def test_query_RelationshipCreateQuery(
    session: AsyncSession, tag_blue_main: Node, person_jack_main: Node, branch: Branch
):
    person_schema = registry.get_schema(name="Person")
    rel_schema = person_schema.get_relationship("tags")

    query = await RelationshipCreateQuery.init(
        session=session,
        source=person_jack_main,
        destination=tag_blue_main,
        schema=rel_schema,
        rel=Relationship,
        branch=branch,
        at=Timestamp(),
    )
    await query.execute(session=session)

    # We should have 2 paths between t1 and p1
    # First for the relationship, Second via the branch
    paths = await get_paths_between_nodes(
        session=session, source_id=tag_blue_main.db_id, destination_id=person_jack_main.db_id, max_length=2
    )
    assert len(paths) == 2


async def test_query_RelationshipCreateQuery_w_node_property(
    session: AsyncSession, tag_blue_main: Node, person_jack_main: Node, first_account: Node, branch: Branch
):
    person_schema = registry.get_schema(name="Person")
    rel_schema = person_schema.get_relationship("tags")

    paths = await get_paths_between_nodes(
        session=session,
        source_id=tag_blue_main.db_id,
        destination_id=person_jack_main.db_id,
        relationships=["IS_RELATED"],
        max_length=2,
    )
    assert len(paths) == 0

    rel = Relationship(
        schema=rel_schema, branch=branch, node=person_jack_main, source=first_account, owner=first_account
    )
    query = await RelationshipCreateQuery.init(
        session=session, branch=branch, source=person_jack_main, destination=tag_blue_main, rel=rel
    )
    await query.execute(session=session)

    paths = await get_paths_between_nodes(
        session=session,
        source_id=tag_blue_main.db_id,
        destination_id=person_jack_main.db_id,
        relationships=["IS_RELATED"],
        max_length=2,
    )
    assert len(paths) == 1


async def test_query_RelationshipDeleteQuery(
    session: AsyncSession, tag_blue_main: Node, person_jack_tags_main: Node, branch: Branch
):
    person_schema = registry.get_schema(name="Person")
    rel_schema = person_schema.get_relationship("tags")

    # We should have 2 paths between t1 and p1
    # First for the relationship, Second via the branch
    paths = await get_paths_between_nodes(
        session=session, source_id=tag_blue_main.db_id, destination_id=person_jack_tags_main.db_id, max_length=2
    )
    assert len(paths) == 2

    query = await RelationshipDeleteQuery.init(
        session=session,
        source=person_jack_tags_main,
        destination=tag_blue_main,
        schema=rel_schema,
        rel=Relationship,
        branch=branch,
        at=Timestamp(),
    )
    await query.execute(session=session)

    # We should have 5 paths between t1 and p1
    # Because we have 3 "real" paths between the nodes
    # but if we calculate all the permutations it will equal to 5 paths.
    paths = await get_paths_between_nodes(
        session=session, source_id=tag_blue_main.db_id, destination_id=person_jack_tags_main.db_id, max_length=2
    )
    assert len(paths) == 5


async def test_query_RelationshipGetPeerQuery(
    session: AsyncSession, tag_blue_main: Node, person_jack_tags_main: Node, branch: Branch
):
    person_schema = registry.get_schema(name="Person")
    rel_schema = person_schema.get_relationship("tags")

    query = await RelationshipGetPeerQuery.init(
        session=session,
        source_id=person_jack_tags_main.id,
        schema=rel_schema,
        rel=Relationship,
        branch=branch,
        at=Timestamp(),
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


async def test_query_RelationshipGetPeerQuery_with_filter(
    session: AsyncSession, person_jack_tags_main: Node, branch: Branch
):
    person_schema = registry.get_schema(name="Person")
    rel_schema = person_schema.get_relationship("tags")

    query = await RelationshipGetPeerQuery.init(
        session=session,
        source_id=person_jack_tags_main.id,
        schema=rel_schema,
        filters={"tags__name__value": "Blue"},
        rel=Relationship,
        branch=branch,
        at=Timestamp(),
    )

    await query.execute(session=session)

    assert len(query.get_peer_ids()) == 1
