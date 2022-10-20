import pytest

from infrahub.core import registry
from infrahub.core.node import Node
from infrahub.core.relationship import Relationship
from infrahub.core.query.relationship import RelationshipGetPeerQuery, RelationshipCreateQuery, RelationshipDeleteQuery
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import get_paths_between_nodes


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
    paths = get_paths_between_nodes(t1.db_id, p1.db_id, 2)
    assert len(paths) == 2


def test_query_RelationshipDeleteQuery(default_branch, person_tag_schema):

    person_schema = registry.get_schema("Person")
    rel_schema = person_schema.get_relationship("tags")

    t1 = Node("Tag").new(name="blue").save()
    t2 = Node("Tag").new(name="red").save()
    p1 = Node(person_schema).new(firstname="John", lastname="Doe", tags=[t1, t2]).save()

    # We should have 2 paths between t1 and p1
    # First for the relationship, Second via the branch
    paths = get_paths_between_nodes(t1.db_id, p1.db_id, 2)
    assert len(paths) == 2

    query = RelationshipDeleteQuery(
        source=p1, destination=t1, schema=rel_schema, rel=Relationship, branch=default_branch, at=Timestamp()
    )
    query.execute()

    # We should have 5 paths between t1 and p1
    # Because we have 3 "real" paths between the nodes
    # but if we calculate all the permutations it will equal to 5 paths.
    paths = get_paths_between_nodes(t1.db_id, p1.db_id, 2)
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

    assert len(query.get_peer_ids()) == 2


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
