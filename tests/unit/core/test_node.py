import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import NodeSchema
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import get_paths_between_nodes
from infrahub.exceptions import ValidationError


def test_node_init(default_branch, criticality_schema):

    obj = Node(criticality_schema).new(name="low", level=4)

    assert obj.name.value == "low"
    assert obj.level.value == 4
    assert obj.description.value is None
    assert obj.color.value == "#444444"

    obj = Node(criticality_schema).new(name="medium", level=3, description="My desc", color="#333333")

    assert obj.name.value == "medium"
    assert obj.level.value == 3
    assert obj.description.value == "My desc"
    assert obj.color.value == "#333333"


def test_node_init_schema_name(default_branch, criticality_schema):

    registry.set_schema("Criticality", criticality_schema)
    obj = Node("Criticality").new(name="low", level=4)

    assert obj.name.value == "low"
    assert obj.level.value == 4
    assert obj.description.value is None
    assert obj.color.value == "#444444"


def test_node_init_mandatory_missing(default_branch, criticality_schema):

    with pytest.raises(ValidationError) as exc:
        Node(criticality_schema).new(level=4)

    assert "mandatory" in str(exc.value)


def test_node_init_invalid_attribute(default_branch, criticality_schema):

    with pytest.raises(ValidationError) as exc:
        Node(criticality_schema).new(name="low", level=4, notvalid=False)

    assert "not a valid input" in str(exc.value)


def test_node_init_invalid_value(default_branch, criticality_schema):

    with pytest.raises(ValidationError) as exc:
        Node(criticality_schema).new(name="low", level="notanint")

    assert "not of type Integer" in str(exc.value)

    with pytest.raises(ValidationError) as exc:
        Node(criticality_schema).new(name=False, level=3)

    assert "not of type String" in str(exc.value)


def test_node_default_value(default_branch):

    SCHEMA = {
        "name": "one_of_each_kind",
        "kind": "OneOfEachKind",
        "default_filter": "name__value",
        "branch": True,
        "attributes": [
            {"name": "name", "kind": "String", "unique": True},
            {"name": "myint", "kind": "Integer"},
            {"name": "myint_default", "kind": "Integer", "default_value": 10},
            {"name": "mystr", "kind": "String"},
            {"name": "mystr_default", "kind": "String", "default_value": "test"},
            {"name": "mybool", "kind": "Boolean"},
            {"name": "mybool_default", "kind": "Boolean", "default_value": True},
        ],
    }

    node_schema = NodeSchema(**SCHEMA)
    registry.set_schema(node_schema.kind, node_schema)

    obj = Node(node_schema).new(name="test01", myint=100, mybool=False, mystr="test02")

    assert obj.name.value == "test01"
    assert obj.myint.value == 100
    assert obj.myint_default.value == 10
    assert obj.mystr.value == "test02"
    assert obj.mystr_default.value == "test"
    assert obj.mybool.value is False
    assert obj.mybool_default.value is True


def test_node_init_with_single_relationship(default_branch, car_person_schema):

    car = registry.get_schema("Car")
    person = registry.get_schema("Person")

    p1 = Node(person).new(name="John", height=180)

    assert p1.name.value == "John"
    assert p1.height.value == 180
    assert list(p1.cars) == []

    p1.save()

    c1 = Node(car).new(name="volt", nbr_seats=4, is_electric=True, owner=p1)
    assert c1.name.value == "volt"
    assert c1.nbr_seats.value == 4
    assert c1.is_electric.value is True
    assert c1.owner.peer == p1

    c2 = Node(car).new(name="volt", nbr_seats=4, is_electric=True, owner=p1.id)
    assert c2.name.value == "volt"
    assert c2.nbr_seats.value == 4
    assert c2.is_electric.value is True
    assert c2.owner.peer.id == p1.id


# --------------------------------------------------------------------------
# Create
# --------------------------------------------------------------------------
def test_node_create_local_attrs(default_branch, criticality_schema):

    obj = Node(criticality_schema).new(name="low", level=4).save()

    assert obj.id
    assert obj.db_id
    assert obj.name.value == "low"
    assert obj.name.id
    assert obj.level.value == 4
    assert obj.level.id
    assert obj.description.value is None
    assert obj.description.id
    assert obj.color.value == "#444444"
    assert obj.color.id
    assert obj.id
    assert obj.db_id

    obj = Node(criticality_schema).new(name="medium", level=3, description="My desc", color="#333333").save()

    assert obj.id
    assert obj.db_id
    assert obj.name.value == "medium"
    assert obj.name.id
    assert obj.level.value == 3
    assert obj.level.id
    assert obj.description.value == "My desc"
    assert obj.description.id
    assert obj.color.value == "#333333"
    assert obj.color.id


def test_node_create_with_single_relationship(default_branch, car_person_schema):

    car = registry.get_schema("Car")
    person = registry.get_schema("Person")

    p1 = Node(person).new(name="John", height=180)

    assert p1.name.value == "John"
    assert p1.height.value == 180
    assert list(p1.cars) == []

    p1.save()

    c1 = Node(car).new(name="volt", nbr_seats=4, is_electric=True, owner=p1).save()
    assert c1.name.value == "volt"
    assert c1.nbr_seats.value == 4
    assert c1.is_electric.value is True
    assert c1.owner.peer == p1

    # We should have 2 paths between c1 and p1
    # First for the relationship
    # Second via the branch
    paths = get_paths_between_nodes(c1.db_id, p1.db_id, 2)
    assert len(paths) == 2

    c2 = Node(car).new(name="accord", nbr_seats=5, is_electric=False, owner=p1.id).save()
    assert c2.name.value == "accord"
    assert c2.nbr_seats.value == 5
    assert c2.is_electric.value is False
    assert c2.owner.peer.id == p1.id

    paths = get_paths_between_nodes(c2.db_id, p1.db_id, 2)
    assert len(paths) == 2


def test_node_create_with_multiple_relationship(default_branch, fruit_tag_schema):

    fruit = registry.get_schema("Fruit")
    tag = registry.get_schema("Tag")

    t1 = Node(tag).new(name="tag1").save()
    t2 = Node(tag).new(name="tag2").save()
    t3 = Node(tag).new(name="tag3").save()

    f1 = Node(fruit).new(name="apple", tags=[t1, t2, t3]).save()
    assert f1.name.value == "apple"
    assert len(list(f1.tags)) == 3

    # We should have 2 paths between f1 and t1, t2 & t3
    # First for the relationship, second via the branch
    paths = get_paths_between_nodes(f1.db_id, t1.db_id, 2)
    assert len(paths) == 2
    paths = get_paths_between_nodes(f1.db_id, t2.db_id, 2)
    assert len(paths) == 2
    paths = get_paths_between_nodes(f1.db_id, t3.db_id, 2)
    assert len(paths) == 2


# --------------------------------------------------------------------------
# Update
# --------------------------------------------------------------------------


def test_node_update_local_attrs(default_branch, criticality_schema):

    obj1 = Node(criticality_schema).new(name="low", level=4).save()

    obj2 = NodeManager.get_one(obj1.id)
    obj2.name.value = "high"
    obj2.level.value = 1
    obj2.save()

    obj3 = NodeManager.get_one(obj1.id)
    assert obj3.name.value == "high"
    assert obj3.level.value == 1


# --------------------------------------------------------------------------
# Delete
# --------------------------------------------------------------------------
def test_node_delete_local_attrs(default_branch, criticality_schema):

    obj2 = Node(criticality_schema).new(name="medium", level=3, description="My desc", color="#333333").save()
    obj1 = Node(criticality_schema).new(name="low", level=4).save()

    time1 = Timestamp()

    obj22 = NodeManager.get_one(obj2.id, at=time1)
    assert obj22

    obj22.delete()

    assert NodeManager.get_one(obj1.id)
    assert not NodeManager.get_one(obj2.id)


def test_node_delete_query_past(default_branch, criticality_schema):

    obj1 = Node(criticality_schema).new(name="low", level=4).save()
    obj2 = Node(criticality_schema).new(name="medium", level=3, description="My desc", color="#333333").save()

    time1 = Timestamp()

    obj22 = NodeManager.get_one(obj2.id)
    assert obj22

    obj22.delete()

    assert NodeManager.get_one(obj1.id)
    assert not NodeManager.get_one(obj2.id)
    assert NodeManager.get_one(obj2.id, at=time1)


def test_node_delete_local_attrs_in_branch(default_branch, criticality_schema):

    obj1 = Node(criticality_schema).new(name="low", level=4).save()
    obj2 = Node(criticality_schema).new(name="medium", level=3, description="My desc", color="#333333").save()

    branch1 = Branch(name="branch1", status="OPEN")
    branch1.save()

    obj21 = NodeManager.get_one(obj2.id, branch=branch1)
    assert obj21

    obj21.delete()

    assert NodeManager.get_one(obj1.id)
    assert NodeManager.get_one(obj2.id)
    assert not NodeManager.get_one(obj2.id, branch=branch1)

    assert len(NodeManager.query(criticality_schema)) == 2
    assert len(NodeManager.query(criticality_schema, branch=branch1)) == 1


def test_node_delete_with_relationship_bidir(default_branch, car_person_schema):

    p1 = Node("Person").new(name="John", height=180).save()
    c1 = Node("Car").new(name="volt", nbr_seats=4, is_electric=True, owner=p1).save()
    Node("Car").new(name="accord", nbr_seats=5, is_electric=False, owner=p1.id).save()

    time1 = Timestamp()

    c1.delete()

    assert len(NodeManager.query("Car")) == 1
    assert len(NodeManager.query("Car", at=time1)) == 2

    p11 = NodeManager.get_one(p1.id)
    assert len(list(p11.cars)) == 1

    p12 = NodeManager.get_one(p1.id, at=time1)
    assert len(list(p12.cars)) == 2


# ---------------------------------------   -----------------------------------
# With Branch
# --------------------------------------------------------------------------
def test_node_create_in_branch(default_branch, criticality_schema):

    branch1 = Branch(name="branch1", status="OPEN")
    branch1.save()

    obj = Node(criticality_schema, branch=branch1).new(name="low", level=4).save()
    assert NodeManager.get_one(obj.id) is None
    assert NodeManager.get_one(obj.id, branch=branch1).id == obj.id


def test_node_update_in_branch(default_branch, criticality_schema):

    obj1 = Node(criticality_schema).new(name="low", level=4).save()

    branch1 = create_branch("branch1")

    obj2 = NodeManager.get_one(obj1.id, branch=branch1)
    obj2.name.value = "High"
    obj2.level.value = 5
    obj2.save()

    obj11 = NodeManager.get_one(obj1.id)
    assert obj11.name.value == "low"
    assert obj11.level.value == 4

    obj21 = NodeManager.get_one(obj1.id, branch=branch1)
    assert obj21.name.value == "High"
    assert obj21.level.value == 5
