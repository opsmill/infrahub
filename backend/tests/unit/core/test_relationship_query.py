from typing import Dict

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import RelationshipDirection
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.query.relationship import (
    RelationshipCountPerNodeQuery,
    RelationshipCreateQuery,
    RelationshipDataDeleteQuery,
    RelationshipDeleteQuery,
    RelationshipGetPeerQuery,
    RelationshipPeerData,
    RelationshipQuery,
    RelData,
)
from infrahub.core.relationship import Relationship
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import get_paths_between_nodes
from infrahub.database import InfrahubDatabase


class DummyRelationshipQuery(RelationshipQuery):
    async def query_init(self, db: InfrahubDatabase, *args, **kwargs):
        pass


async def test_RelationshipQuery_init(
    db: InfrahubDatabase, tag_blue_main: Node, person_jack_main: Node, branch: Branch
):
    person_schema = registry.schema.get(name="TestPerson")
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
    db: InfrahubDatabase, tag_blue_main: Node, person_jack_main: Node, branch: Branch
):
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    query = await RelationshipCreateQuery.init(
        db=db,
        source=person_jack_main,
        destination=tag_blue_main,
        schema=rel_schema,
        rel=Relationship,
        branch=branch,
        at=Timestamp(),
    )
    await query.execute(db=db)

    # We should have 2 paths between t1 and p1
    # First for the relationship, Second via the branch
    paths = await get_paths_between_nodes(
        db=db, source_id=tag_blue_main.db_id, destination_id=person_jack_main.db_id, max_length=2
    )
    assert len(paths) == 2


async def test_query_RelationshipCreateQuery_w_node_property(
    db: InfrahubDatabase, tag_blue_main: Node, person_jack_main: Node, first_account: Node, branch: Branch
):
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    paths = await get_paths_between_nodes(
        db=db,
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
        db=db, branch=branch, source=person_jack_main, destination=tag_blue_main, rel=rel
    )
    await query.execute(db=db)

    paths = await get_paths_between_nodes(
        db=db,
        source_id=tag_blue_main.db_id,
        destination_id=person_jack_main.db_id,
        relationships=["IS_RELATED"],
        max_length=2,
    )
    assert len(paths) == 1


async def test_query_RelationshipDeleteQuery(
    db: InfrahubDatabase, tag_blue_main: Node, person_jack_tags_main: Node, branch: Branch
):
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    # We should have 2 paths between t1 and p1
    # First for the relationship, Second via the branch
    paths = await get_paths_between_nodes(
        db=db,
        source_id=tag_blue_main.db_id,
        destination_id=person_jack_tags_main.db_id,
        max_length=2,
        relationships=["IS_RELATED"],
    )
    assert len(paths) == 1

    rel_node = [node for node in paths[0][0]._nodes if "Relationship" in node.labels][0]

    rel_data = RelationshipPeerData(
        source_id=person_jack_tags_main.id,
        branch=branch.name,
        peer_id=tag_blue_main.id,
        peer_kind=tag_blue_main.get_kind(),
        peer_db_id=tag_blue_main.db_id,
        rel_node_id=rel_node.get("uuid"),
        rel_node_db_id=rel_node.element_id,
        rels=[RelData.from_db(rel) for rel in paths[0][0]._relationships],
        properties={},
    )

    rel = Relationship(schema=rel_schema, branch=branch, node=person_jack_tags_main)
    await rel.load(db=db, data=rel_data)

    query = await RelationshipDeleteQuery.init(
        db=db,
        source=person_jack_tags_main,
        destination=tag_blue_main,
        schema=rel_schema,
        rel=rel,
        branch=branch,
        at=Timestamp(),
    )
    await query.execute(db=db)

    # We should have 4 paths between t1 and p1
    # Because we have 2 "real" paths between the nodes
    # but if we calculate all the permutations it will equal to 4 paths.
    paths = await get_paths_between_nodes(
        db=db,
        source_id=tag_blue_main.db_id,
        destination_id=person_jack_tags_main.db_id,
        max_length=2,
        relationships=["IS_RELATED"],
    )
    assert len(paths) == 4

    # ------------------------------------------------------------
    # Recreate the relationship to delete it again
    # ------------------------------------------------------------
    rel = Relationship(schema=rel_schema, branch=branch, node=tag_blue_main)
    query = await RelationshipCreateQuery.init(
        db=db, branch=branch, source=tag_blue_main, destination=person_jack_tags_main, rel=rel
    )
    await query.execute(db=db)

    # We should have 5 paths between t1 and p1
    # Because we have 3 "real" paths between the nodes
    # but if we calculate all the permutations it will equal to 5 paths.
    paths = await get_paths_between_nodes(
        db=db,
        source_id=tag_blue_main.db_id,
        destination_id=person_jack_tags_main.db_id,
        max_length=2,
        relationships=["IS_RELATED"],
    )
    assert len(paths) == 5

    def get_active_path_and_rel(all_paths, previous_rel: str):
        for path in all_paths:
            for node in path[0]._nodes:
                if "Relationship" in node.labels and node.get("uuid") != previous_rel:
                    return path, node

    active_path, latest_rel_node = get_active_path_and_rel(all_paths=paths, previous_rel=rel_node.get("uuid"))

    rel_data = RelationshipPeerData(
        source_id=person_jack_tags_main.id,
        branch=branch.name,
        peer_id=tag_blue_main.id,
        peer_kind=tag_blue_main.get_kind(),
        peer_db_id=tag_blue_main.db_id,
        rel_node_id=latest_rel_node.get("uuid"),
        rel_node_db_id=latest_rel_node.element_id,
        rels=[RelData.from_db(rel) for rel in active_path[0]._relationships],
        properties={},
    )

    rel = Relationship(schema=rel_schema, branch=branch, node=person_jack_tags_main)
    await rel.load(db=db, data=rel_data)

    query = await RelationshipDeleteQuery.init(
        db=db,
        source=person_jack_tags_main,
        destination=tag_blue_main,
        schema=rel_schema,
        rel=rel,
        branch=branch,
        at=Timestamp(),
    )
    await query.execute(db=db)

    # We should have 8 paths between t1 and p1
    # Because we have 4 "real" paths between the nodes divided in 2 relationships
    # but if we calculate all the permutations it will equal to 8 paths.
    paths = await get_paths_between_nodes(
        db=db,
        source_id=tag_blue_main.db_id,
        destination_id=person_jack_tags_main.db_id,
        max_length=2,
        relationships=["IS_RELATED"],
    )
    assert len(paths) == 8


async def test_query_RelationshipGetPeerQuery(
    db: InfrahubDatabase, tag_blue_main: Node, person_jack_tags_main: Node, branch: Branch
):
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    query = await RelationshipGetPeerQuery.init(
        db=db,
        source_ids=[person_jack_tags_main.id],
        schema=rel_schema,
        rel=Relationship,
        branch=branch,
        at=Timestamp(),
    )
    await query.execute(db=db)

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
    db: InfrahubDatabase,
    person_john_main,
    car_accord_main,
    car_camry_main,
    car_volt_main,
    car_prius_main,
    car_yaris_main,
    branch: Branch,
):
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("cars")

    query = await RelationshipGetPeerQuery.init(
        db=db,
        source_ids=[person_john_main.id],
        schema=rel_schema,
        filters={"cars__is_electric__value": True},
        rel=Relationship,
        branch=branch,
        at=Timestamp(),
    )

    await query.execute(db=db)

    assert query.get_peer_ids() == sorted([car_volt_main.id, car_prius_main.id])


async def test_query_RelationshipGetPeerQuery_with_id(
    db: InfrahubDatabase,
    person_john_main,
    car_accord_main,
    car_camry_main,
    car_volt_main,
    car_prius_main,
    car_yaris_main,
    branch: Branch,
):
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("cars")

    query = await RelationshipGetPeerQuery.init(
        db=db,
        source_ids=[person_john_main.id],
        schema=rel_schema,
        filters={"cars__ids": [car_accord_main.id]},
        rel=Relationship,
        branch=branch,
        at=Timestamp(),
    )

    await query.execute(db=db)
    assert query.get_peer_ids() == sorted([car_accord_main.id])


async def test_query_RelationshipGetPeerQuery_with_ids(
    db: InfrahubDatabase,
    person_john_main,
    car_accord_main,
    car_camry_main,
    car_volt_main,
    car_prius_main,
    car_yaris_main,
    branch: Branch,
):
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("cars")

    query = await RelationshipGetPeerQuery.init(
        db=db,
        source_ids=[person_john_main.id],
        schema=rel_schema,
        filters={"cars__ids": [car_accord_main.id, car_prius_main.id]},
        rel=Relationship,
        branch=branch,
        at=Timestamp(),
    )

    await query.execute(db=db)
    assert query.get_peer_ids() == sorted([car_prius_main.id, car_accord_main.id])


async def test_query_RelationshipGetPeerQuery_with_sort(
    db: InfrahubDatabase,
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
        db=db,
        source_ids=[person_john_main.id],
        schema=rel_schema,
        rel=Relationship,
        branch=branch,
        at=Timestamp(),
    )

    await query.execute(db=db)

    assert query.get_peer_ids() == [car_accord_main.id, car_prius_main.id, car_volt_main.id]


async def test_query_RelationshipGetPeerQuery_deleted_node(
    db: InfrahubDatabase,
    person_john_main,
    car_accord_main,
    car_camry_main,
    car_volt_main,
    car_prius_main,
    car_yaris_main,
    branch: Branch,
):
    node = await NodeManager.get_one(id=car_volt_main.id, db=db, branch=branch)
    await node.delete(db=db)

    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("cars")

    query = await RelationshipGetPeerQuery.init(
        db=db,
        source_ids=[person_john_main.id],
        schema=rel_schema,
        rel=Relationship,
        branch=branch,
        at=Timestamp(),
    )

    await query.execute(db=db)
    assert query.get_peer_ids() == sorted([car_accord_main.id, car_prius_main.id])


async def test_query_RelationshipGetPeerQuery_with_multiple_filter(
    db: InfrahubDatabase,
    person_john_main,
    car_accord_main,
    car_camry_main,
    car_volt_main,
    car_prius_main,
    car_yaris_main,
    branch: Branch,
):
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("cars")

    query = await RelationshipGetPeerQuery.init(
        db=db,
        source_ids=[person_john_main.id],
        schema=rel_schema,
        filters={"cars__is_electric__value": True, "cars__nbr_seats__value": 4},
        rel=Relationship,
        branch=branch,
        at=Timestamp(),
    )

    await query.execute(db=db)

    assert query.get_peer_ids() == [car_volt_main.id]


async def test_query_RelationshipDataDeleteQuery(
    db: InfrahubDatabase, tag_blue_main: Node, person_jack_tags_main: Node, branch: Branch
):
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    # We should have 2 paths between t1 and p1
    # First for the relationship, Second via the branch
    paths = await get_paths_between_nodes(
        db=db,
        source_id=tag_blue_main.db_id,
        destination_id=person_jack_tags_main.db_id,
        max_length=2,
        relationships=["IS_RELATED"],
    )
    assert len(paths) == 1

    # Query the existing relationship in RelationshipPeerData format
    query1 = await RelationshipGetPeerQuery.init(
        db=db,
        source=person_jack_tags_main,
        schema=rel_schema,
        rel=Relationship(schema=rel_schema, branch=branch, node=person_jack_tags_main),
    )
    await query1.execute(db=db)
    peers_database: Dict[str, RelationshipPeerData] = {peer.peer_id: peer for peer in query1.get_peers()}

    # Delete the relationship
    query2 = await RelationshipDataDeleteQuery.init(
        db=db,
        branch=branch,
        source=person_jack_tags_main,
        data=peers_database[tag_blue_main.id],
        schema=rel_schema,
        rel=Relationship,
    )
    await query2.execute(db=db)

    # We should have 4 paths between t1 and p1
    # Because we have 2 "real" paths between the nodes
    # but if we calculate all the permutations it will equal to 4 paths.
    paths = await get_paths_between_nodes(
        db=db,
        source_id=tag_blue_main.db_id,
        destination_id=person_jack_tags_main.db_id,
        max_length=2,
        relationships=["IS_RELATED"],
    )

    assert len(paths) == 4


async def test_query_RelationshipCountPerNodeQuery(
    db: InfrahubDatabase,
    person_john_main,
    person_jane_main,
    car_accord_main,
    car_camry_main,
    car_volt_main,
    car_prius_main,
    car_yaris_main,
    branch: Branch,
):
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("cars")

    albert = await Node.init(db=db, schema="TestPerson", branch=branch)
    await albert.new(db=db, name="Albert", height=120)
    await albert.save(db=db)

    peer_ids = [person_john_main.id, person_jane_main.id, albert.id]

    query = await RelationshipCountPerNodeQuery.init(
        db=db,
        node_ids=peer_ids,
        identifier=rel_schema.identifier,
        direction=RelationshipDirection.INBOUND,
        branch=branch,
        at=Timestamp(),
    )
    await query.execute(db=db)
    count_per_peer = await query.get_count_per_peer()
    assert count_per_peer == {
        person_john_main.id: 3,
        person_jane_main.id: 2,
        albert.id: 0,
    }

    # Revert the direction to ensure this is working as expected
    query = await RelationshipCountPerNodeQuery.init(
        db=db,
        node_ids=peer_ids,
        identifier=rel_schema.identifier,
        direction=RelationshipDirection.OUTBOUND,
        branch=branch,
        at=Timestamp(),
    )
    await query.execute(db=db)
    count_per_peer = await query.get_count_per_peer()
    assert count_per_peer == {
        person_john_main.id: 0,
        person_jane_main.id: 0,
        albert.id: 0,
    }
