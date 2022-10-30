from re import A
import pytest

from infrahub.core import branch, registry
from infrahub.core.node import Node
from infrahub.core.relationship import Relationship
from infrahub.core.query.relationship import (
    RelationshipQuery,
    RelationshipGetPeerQuery,
    RelationshipCreateQuery,
    RelationshipDeleteQuery,
)
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import get_paths_between_nodes


class DummyRelationshipQuery(RelationshipQuery):
    def query_init(self):
        pass


def test_RelationshipQuery_init(default_branch, person_tag_schema):

    person_schema = registry.get_schema("Person")
    rel_schema = person_schema.get_relationship("tags")

    t1 = Node("Tag").new(name="blue").save()
    p1 = Node(person_schema).new(firstname="John", lastname="Doe").save()

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


def test_query_RelationshipCreateQuery(default_branch, person_tag_schema):

    person_schema = registry.get_schema("Person")
    rel_schema = person_schema.get_relationship("tags")

    t1 = Node("Tag").new(name="blue").save()
    t2 = Node("Tag").new(name="red").save()
    p1 = Node(person_schema).new(firstname="John", lastname="Doe").save()

    query = RelationshipCreateQuery(
        source=p1, destination=t1, schema=rel_schema, rel=Relationship, branch=default_branch, at=Timestamp()
    )
    query.execute()

    # We should have 2 paths between t1 and p1
    # First for the relationship, Second via the branch
    paths = get_paths_between_nodes(source_id=t1.db_id, destination_id=p1.db_id, max_length=2)
    assert len(paths) == 2


def test_query_RelationshipCreateQuery_w_node_property(default_branch, person_tag_schema, first_account):

    person_schema = registry.get_schema("Person")
    rel_schema = person_schema.get_relationship("tags")

    t1 = Node("Tag").new(name="blue").save()
    t2 = Node("Tag").new(name="red").save()
    p1 = Node(person_schema).new(firstname="John", lastname="Doe").save()

    paths = get_paths_between_nodes(
        source_id=t1.db_id, destination_id=p1.db_id, relationships=["IS_RELATED"], max_length=2
    )
    assert len(paths) == 0

    rel = Relationship(schema=rel_schema, branch=default_branch, node=p1, source=first_account, owner=first_account)
    query = RelationshipCreateQuery(source=p1, destination=t1, rel=rel).execute()

    paths = get_paths_between_nodes(
        source_id=t1.db_id, destination_id=p1.db_id, relationships=["IS_RELATED"], max_length=2
    )
    assert len(paths) == 1


def test_query_RelationshipDeleteQuery(default_branch, person_tag_schema):

    person_schema = registry.get_schema("Person")
    rel_schema = person_schema.get_relationship("tags")

    t1 = Node("Tag").new(name="blue").save()
    t2 = Node("Tag").new(name="red").save()
    p1 = Node(person_schema).new(firstname="John", lastname="Doe", tags=[t1, t2]).save()

    # We should have 2 paths between t1 and p1
    # First for the relationship, Second via the branch
    paths = get_paths_between_nodes(source_id=t1.db_id, destination_id=p1.db_id, max_length=2)
    assert len(paths) == 2

    query = RelationshipDeleteQuery(
        source=p1, destination=t1, schema=rel_schema, rel=Relationship, branch=default_branch, at=Timestamp()
    )
    query.execute()

    # We should have 5 paths between t1 and p1
    # Because we have 3 "real" paths between the nodes
    # but if we calculate all the permutations it will equal to 5 paths.
    paths = get_paths_between_nodes(source_id=t1.db_id, destination_id=p1.db_id, max_length=2)
    assert len(paths) == 5


def test_query_RelationshipGetPeerQuery(default_branch, person_tag_schema):

    person_schema = registry.get_schema("Person")
    rel_schema = person_schema.get_relationship("tags")
    t1 = Node("Tag").new(name="blue").save()
    t2 = Node("Tag").new(name="red").save()
    p1 = Node(person_schema).new(firstname="John", lastname="Doe", tags=[t1, t2]).save()

    query = RelationshipGetPeerQuery(
        source_id=p1.id, schema=rel_schema, rel=Relationship, branch=default_branch, at=Timestamp()
    )
    query.execute()

    peers = list(query.get_peers())
    assert len(peers) == 2
    assert len(peers[0].rel_db_ids) == 2
    assert isinstance(peers[0].rel_node_db_id, int)
    assert isinstance(peers[0].rel_node_id, str)
    assert list(peers[0].properties.keys()) == ["is_visible", "is_protected"]
    assert peers[0].properties["is_visible"].value == True
    assert peers[0].properties["is_protected"].value == False
    assert peers[0].properties["is_protected"].prop_db_id == peers[1].properties["is_protected"].prop_db_id
    assert isinstance(peers[0].properties["is_protected"].prop_db_id, int)
    assert isinstance(peers[0].properties["is_protected"].rel_db_id, int)
    assert isinstance(peers[0].properties["is_protected"].prop_db_id, int)


def test_query_RelationshipGetPeerQuery_with_filter(default_branch, person_tag_schema):

    person_schema = registry.get_schema("Person")
    rel_schema = person_schema.get_relationship("tags")
    t1 = Node("Tag").new(name="blue").save()
    t2 = Node("Tag").new(name="red").save()
    p1 = Node(person_schema).new(firstname="John", lastname="Doe", tags=[t1, t2]).save()

    query = RelationshipGetPeerQuery(
        source_id=p1.id,
        schema=rel_schema,
        filters={"tags__name__value": "blue"},
        rel=Relationship,
        branch=default_branch,
        at=Timestamp(),
    )
    query.execute()

    assert len(query.get_peer_ids()) == 1
