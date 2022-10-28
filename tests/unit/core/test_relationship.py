import pytest

from infrahub.core import registry
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.relationship import Relationship


def test_relationship_init(default_branch, person_tag_schema):

    person_schema = registry.get_schema("Person")
    rel_schema = person_schema.get_relationship("tags")

    t1 = Node("Tag").new(name="blue").save()
    p1 = Node(person_schema).new(firstname="John", lastname="Doe").save()

    rel = Relationship(schema=rel_schema, branch=default_branch, node=p1)

    assert rel.schema == rel_schema
    assert rel.name == rel_schema.name
    assert rel.branch == default_branch
    assert rel.node_id == p1.id
    assert rel.node == p1

    rel = Relationship(schema=rel_schema, branch=default_branch, node_id=p1.id)

    assert rel.schema == rel_schema
    assert rel.name == rel_schema.name
    assert rel.branch == default_branch
    assert rel.node_id == p1.id
    assert type(rel.node) == Node
    assert rel.node.id == p1.id


def test_relationship_init_w_node_property(default_branch, person_tag_schema, first_account, second_account):

    person_schema = registry.get_schema("Person")
    rel_schema = person_schema.get_relationship("tags")

    t1 = Node("Tag").new(name="blue").save()
    p1 = Node(person_schema).new(firstname="John", lastname="Doe").save()

    rel = Relationship(schema=rel_schema, branch=default_branch, node=p1, source=first_account, owner=second_account)

    assert rel.schema == rel_schema
    assert rel.name == rel_schema.name
    assert rel.branch == default_branch
    assert rel.node_id == p1.id
    assert rel.node == p1
    assert rel.source_id == first_account.id
    assert rel.owner_id == second_account.id


def test_relationship_peer(default_branch, person_tag_schema, first_account, second_account):

    person_schema = registry.get_schema("Person")
    rel_schema = person_schema.get_relationship("tags")

    t1 = Node("Tag").new(name="blue").save()
    p1 = Node(person_schema).new(firstname="John", lastname="Doe").save()

    rel = Relationship(schema=rel_schema, branch=default_branch, node=p1)
    rel.peer = t1

    assert rel.schema == rel_schema
    assert rel.name == rel_schema.name
    assert rel.branch == default_branch
    assert rel.node_id == p1.id
    assert rel.node == p1
    assert rel.peer_id == t1.id
    assert rel.peer == t1


def test_relationship_save(default_branch, person_tag_schema):

    person_schema = registry.get_schema("Person")
    rel_schema = person_schema.get_relationship("tags")

    t1 = Node("Tag").new(name="blue").save()
    p1 = Node(person_schema).new(firstname="John", lastname="Doe").save()

    rel = Relationship(schema=rel_schema, branch=default_branch, node=p1)
    rel.peer = t1
    rel.save()

    p11 = NodeManager.get_one(p1.id)
    tags = list(p11.tags)
    assert len(tags) == 1
    assert tags[0].id == rel.id
