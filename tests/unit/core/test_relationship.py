import pytest

from infrahub.core import registry
from infrahub.core.node import Node
from infrahub.core.relationship import RelationshipManager
from infrahub.core.relationship.query import RelationshipGetPeerQuery
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import get_paths_between_nodes


def test_query_RelationshipGetPeerQuery(default_branch, person_tag_schema):

    person_schema = registry.get_schema("Person")
    rel_schema = person_schema.get_relationship("tags")
    t1 = Node("Tag").new(name="blue").save()
    t2 = Node("Tag").new(name="red").save()
    p1 = Node(person_schema).new(firstname="John", lastname="Doe", tags=[t1, t2]).save()

    query = RelationshipGetPeerQuery(source_id=p1.id, schema=rel_schema, branch=default_branch, at=Timestamp())
    query.execute()

    assert len(query.get_peer_ids()) == 2


def test_query_RelationshipGetPeerQuery_with_filter(default_branch, person_tag_schema):

    person_schema = registry.get_schema("Person")
    rel_schema = person_schema.get_relationship("tags")
    t1 = Node("Tag").new(name="blue").save()
    t2 = Node("Tag").new(name="red").save()
    p1 = Node(person_schema).new(firstname="John", lastname="Doe", tags=[t1, t2]).save()

    query = RelationshipGetPeerQuery(
        source_id=p1.id, schema=rel_schema, filters={"tags__name__value": "blue"}, branch=default_branch, at=Timestamp()
    )
    query.execute()

    assert len(query.get_peer_ids()) == 1

