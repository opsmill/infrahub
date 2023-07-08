from typing import Dict

import pytest
from neo4j import AsyncSession

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.query.relationship import (
    RelationshipCreateQuery,
    RelationshipDataDeleteQuery,
    RelationshipDeleteQuery,
    RelationshipGetPeerQuery,
    RelationshipPeerData,
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
    person_schema = registry.get_schema(name="TestPerson")
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
    person_schema = registry.get_schema(name="TestPerson")
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
    person_schema = registry.get_schema(name="TestPerson")
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
    person_schema = registry.get_schema(name="TestPerson")
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
    person_schema = registry.get_schema(name="TestPerson")
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
    session: AsyncSession,
    person_john_main,
    car_accord_main,
    car_camry_main,
    car_volt_main,
    car_prius_main,
    car_yaris_main,
    branch: Branch,
):
    person_schema = registry.get_schema(name="TestPerson")
    rel_schema = person_schema.get_relationship("cars")

    query = await RelationshipGetPeerQuery.init(
        session=session,
        source_id=person_john_main.id,
        schema=rel_schema,
        filters={"cars__is_electric__value": True},
        rel=Relationship,
        branch=branch,
        at=Timestamp(),
    )

    await query.execute(session=session)

    assert query.get_peer_ids() == sorted([car_volt_main.id, car_prius_main.id])


async def test_query_RelationshipGetPeerQuery_with_id(
    session: AsyncSession,
    person_john_main,
    car_accord_main,
    car_camry_main,
    car_volt_main,
    car_prius_main,
    car_yaris_main,
    branch: Branch,
):
    person_schema = registry.get_schema(name="TestPerson")
    rel_schema = person_schema.get_relationship("cars")

    query = await RelationshipGetPeerQuery.init(
        session=session,
        source_id=person_john_main.id,
        schema=rel_schema,
        filters={"cars__id": car_accord_main.id},
        rel=Relationship,
        branch=branch,
        at=Timestamp(),
    )

    await query.execute(session=session)
    assert query.get_peer_ids() == sorted([car_accord_main.id])


async def test_query_RelationshipGetPeerQuery_with_ids(
    session: AsyncSession,
    person_john_main,
    car_accord_main,
    car_camry_main,
    car_volt_main,
    car_prius_main,
    car_yaris_main,
    branch: Branch,
):
    person_schema = registry.get_schema(name="TestPerson")
    rel_schema = person_schema.get_relationship("cars")

    query = await RelationshipGetPeerQuery.init(
        session=session,
        source_id=person_john_main.id,
        schema=rel_schema,
        filters={"cars__ids": [car_accord_main.id, car_prius_main.id]},
        rel=Relationship,
        branch=branch,
        at=Timestamp(),
    )

    await query.execute(session=session)
    assert query.get_peer_ids() == sorted([car_prius_main.id, car_accord_main.id])


async def test_query_RelationshipGetPeerQuery_with_sort(
    session: AsyncSession,
    person_john_main,
    car_accord_main,
    car_camry_main,
    car_volt_main,
    car_prius_main,
    car_yaris_main,
    branch: Branch,
):
    car_schema = registry.schema.get(name="TestCar", branch=branch)
    car_schema.order_by = ["name__value"]
    registry.schema.set(name="TestCar", branch=branch.name, schema=car_schema)

    person_schema = registry.schema.get(name="TestPerson", branch=branch)
    rel_schema = person_schema.get_relationship("cars")

    query = await RelationshipGetPeerQuery.init(
        session=session,
        source_id=person_john_main.id,
        schema=rel_schema,
        rel=Relationship,
        branch=branch,
        at=Timestamp(),
    )

    await query.execute(session=session)

    assert query.get_peer_ids() == [car_accord_main.id, car_prius_main.id, car_volt_main.id]


async def test_query_RelationshipGetPeerQuery_deleted_node(
    session: AsyncSession,
    person_john_main,
    car_accord_main,
    car_camry_main,
    car_volt_main,
    car_prius_main,
    car_yaris_main,
    branch: Branch,
):
    node = await NodeManager.get_one(id=car_volt_main.id, session=session, branch=branch)
    await node.delete(session=session)

    person_schema = registry.get_schema(name="TestPerson")
    rel_schema = person_schema.get_relationship("cars")

    query = await RelationshipGetPeerQuery.init(
        session=session,
        source_id=person_john_main.id,
        schema=rel_schema,
        rel=Relationship,
        branch=branch,
        at=Timestamp(),
    )

    await query.execute(session=session)
    assert query.get_peer_ids() == sorted([car_accord_main.id, car_prius_main.id])


async def test_query_RelationshipGetPeerQuery_with_multiple_filter(
    session: AsyncSession,
    person_john_main,
    car_accord_main,
    car_camry_main,
    car_volt_main,
    car_prius_main,
    car_yaris_main,
    branch: Branch,
):
    person_schema = registry.get_schema(name="TestPerson")
    rel_schema = person_schema.get_relationship("cars")

    query = await RelationshipGetPeerQuery.init(
        session=session,
        source_id=person_john_main.id,
        schema=rel_schema,
        filters={"cars__is_electric__value": True, "cars__nbr_seats__value": 4},
        rel=Relationship,
        branch=branch,
        at=Timestamp(),
    )

    await query.execute(session=session)

    assert query.get_peer_ids() == [car_volt_main.id]


async def test_query_RelationshipDataDeleteQuery(
    session: AsyncSession, tag_blue_main: Node, person_jack_tags_main: Node, branch: Branch
):
    person_schema = registry.get_schema(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    # We should have 2 paths between t1 and p1
    # First for the relationship, Second via the branch
    paths = await get_paths_between_nodes(
        session=session,
        source_id=tag_blue_main.db_id,
        destination_id=person_jack_tags_main.db_id,
        max_length=2,
        relationships=["IS_RELATED"],
    )
    assert len(paths) == 1

    # Query the existing relationship in RelationshipPeerData format
    query1 = await RelationshipGetPeerQuery.init(
        session=session,
        source=person_jack_tags_main,
        schema=rel_schema,
        rel=Relationship(schema=rel_schema, branch=branch, node=person_jack_tags_main),
    )
    await query1.execute(session=session)
    peers_database: Dict[str, RelationshipPeerData] = {peer.peer_id: peer for peer in query1.get_peers()}

    # Delete the relationship
    query2 = await RelationshipDataDeleteQuery.init(
        session=session,
        branch=branch,
        source=person_jack_tags_main,
        data=peers_database[tag_blue_main.id],
        schema=rel_schema,
        rel=Relationship,
    )
    await query2.execute(session=session)

    # We should have 4 paths between t1 and p1
    # Because we have 2 "real" paths between the nodes
    # but if we calculate all the permutations it will equal to 4 paths.
    paths = await get_paths_between_nodes(
        session=session,
        source_id=tag_blue_main.db_id,
        destination_id=person_jack_tags_main.db_id,
        max_length=2,
        relationships=["IS_RELATED"],
    )

    assert len(paths) == 4
