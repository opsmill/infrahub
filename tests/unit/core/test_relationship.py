import pytest

from infrahub.core import registry
from infrahub.core.node import Node
from infrahub.core.relationship import RelationshipManager
from infrahub.core.relationship.query import RelationshipGetPeerQuery
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import get_paths_between_nodes


def test_rel_manager_one_init_no_input_no_rel(default_branch, person_tag_schema):

    person_schema = registry.get_schema("Person")
    rel_schema = person_schema.get_relationship("primary_tag")
    p1 = Node(person_schema).new(firstname="John", lastname="Doe").save()

    relm = RelationshipManager(schema=rel_schema, branch=default_branch, at=Timestamp(), node=p1, name="primary_tag")

    # shouldn't be able to iterate over it since it's a "one" relationship
    with pytest.raises(TypeError) as excinfo:
        iter(relm)

    assert not relm.peer
    assert not relm.get()


def test_rel_manager_one_init_no_input_existing_rel(default_branch, person_tag_schema):

    person_schema = registry.get_schema("Person")
    rel_schema = person_schema.get_relationship("primary_tag")
    t1 = Node("Tag").new(name="blue").save()
    p1 = Node(person_schema).new(firstname="John", lastname="Doe", primary_tag=t1).save()

    relm = RelationshipManager(schema=rel_schema, branch=default_branch, at=Timestamp(), node=p1, name="primary_tag")

    assert relm.peer.id == t1.id
    assert relm.get().id == t1.id


def test_rel_manager_many_init_no_input_no_rel(default_branch, person_tag_schema):

    person_schema = registry.get_schema("Person")
    rel_schema = person_schema.get_relationship("tags")
    p1 = Node(person_schema).new(firstname="John", lastname="Doe").save()

    relm = RelationshipManager(schema=rel_schema, branch=default_branch, at=Timestamp(), node=p1, name="tags")

    # shouldn't be able to query the peer since it's many type relationship
    with pytest.raises(TypeError) as excinfo:
        relm.peer

    assert not len(list(relm))
    assert not len(relm.get())


def test_rel_manager_many_init_no_input_existing_rel(default_branch, person_tag_schema):

    person_schema = registry.get_schema("Person")
    rel_schema = person_schema.get_relationship("tags")
    t1 = Node("Tag").new(name="blue").save()
    t2 = Node("Tag").new(name="red").save()
    p1 = Node(person_schema).new(firstname="John", lastname="Doe", tags=[t1, t2]).save()

    relm = RelationshipManager(schema=rel_schema, branch=default_branch, at=Timestamp(), node=p1, name="tags")

    assert len(list(relm)) == 2
    assert len(relm.get()) == 2


def test_rel_manager_one_init_input_obj(default_branch, person_tag_schema):

    person_schema = registry.get_schema("Person")
    rel_schema = person_schema.get_relationship("primary_tag")
    t1 = Node("Tag").new(name="blue").save()
    p1 = Node(person_schema).new(firstname="John", lastname="Doe").save()

    relm = RelationshipManager(
        schema=rel_schema, branch=default_branch, at=Timestamp(), node=p1, name="primary_tag", data=t1
    )

    assert relm.peer.id == t1.id


def test_rel_manager_one_save_input_obj(default_branch, person_tag_schema):

    person_schema = registry.get_schema("Person")
    rel_schema = person_schema.get_relationship("primary_tag")
    t1 = Node("Tag").new(name="blue").save()
    p1 = Node(person_schema).new(firstname="John", lastname="Doe").save()

    # We should have only 1 paths between t1 and p1 via the branch
    paths = get_paths_between_nodes(t1.db_id, p1.db_id, 2)
    assert len(paths) == 1

    relm = RelationshipManager(
        schema=rel_schema, branch=default_branch, at=Timestamp(), node=p1, name="primary_tag", data=t1
    )
    relm.save()

    # We should have 2 paths between t1 and p1
    # First for the relationship, Second via the branch
    paths = get_paths_between_nodes(t1.db_id, p1.db_id, 2)
    assert len(paths) == 2


def test_rel_manager_many_init_input_obj(default_branch, person_tag_schema):

    person_schema = registry.get_schema("Person")
    rel_schema = person_schema.get_relationship("tags")
    t1 = Node("Tag").new(name="blue").save()
    t2 = Node("Tag").new(name="red").save()
    p1 = Node(person_schema).new(firstname="John", lastname="Doe").save()

    relm = RelationshipManager(
        schema=rel_schema, branch=default_branch, at=Timestamp(), node=p1, name="tags", data=[t1, t2]
    )

    assert len(list(relm)) == 2


def test_rel_manager_many_save_input_obj(default_branch, person_tag_schema):

    person_schema = registry.get_schema("Person")
    rel_schema = person_schema.get_relationship("tags")
    t1 = Node("Tag").new(name="blue").save()
    t2 = Node("Tag").new(name="red").save()
    p1 = Node(person_schema).new(firstname="John", lastname="Doe").save()

    # We should have only 1 paths between t1 and p1 via the branch
    paths = get_paths_between_nodes(t1.db_id, p1.db_id, 2)
    assert len(paths) == 1

    paths = get_paths_between_nodes(t2.db_id, p1.db_id, 2)
    assert len(paths) == 1

    relm = RelationshipManager(
        schema=rel_schema, branch=default_branch, at=Timestamp(), node=p1, name="tags", data=[t1, t2]
    )
    relm.save()

    paths = get_paths_between_nodes(t1.db_id, p1.db_id, 2)
    assert len(paths) == 2

    paths = get_paths_between_nodes(t2.db_id, p1.db_id, 2)
    assert len(paths) == 2


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


def test_rel_manager_many_update(default_branch, person_tag_schema):

    person_schema = registry.get_schema("Person")
    rel_schema = person_schema.get_relationship("tags")
    t1 = Node("Tag").new(name="blue").save()
    t2 = Node("Tag").new(name="red").save()
    p1 = Node(person_schema).new(firstname="John", lastname="Doe").save()

    relm = RelationshipManager(schema=rel_schema, branch=default_branch, at=Timestamp(), node=p1, name="tags")
    relm.save()

    # We should have only 1 paths between t1 and p1 via the branch
    paths = get_paths_between_nodes(t1.db_id, p1.db_id, 2)
    assert len(paths) == 1

    paths = get_paths_between_nodes(t2.db_id, p1.db_id, 2)
    assert len(paths) == 1

    relm.update(t1)
    relm.save()

    paths = get_paths_between_nodes(t1.db_id, p1.db_id, 2)
    assert len(paths) == 2

    paths = get_paths_between_nodes(t2.db_id, p1.db_id, 2)
    assert len(paths) == 1

    relm.update([t1, t2])
    relm.save()

    paths = get_paths_between_nodes(t1.db_id, p1.db_id, 2)
    assert len(paths) == 2

    paths = get_paths_between_nodes(t2.db_id, p1.db_id, 2)
    assert len(paths) == 2
