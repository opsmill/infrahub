
from infrahub.core import registry
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node

# ("low", 2),
# ("medium", 3),
# ("high", 4),


def test_get_one_local_attribute(default_branch, criticality_schema):

    obj1 = Node(criticality_schema).new(name="low", level=4).save()
    obj2 = Node(criticality_schema).new(name="medium", level=3, description="My desc", color="#333333").save()

    obj = NodeManager.get_one(obj2.id)

    assert obj.id == obj2.id
    assert obj.db_id == obj2.db_id
    assert obj.name.value == "medium"
    assert obj.name.id
    assert obj.level.value == 3
    assert obj.level.id
    assert obj.description.value == "My desc"
    assert obj.description.id
    assert obj.color.value == "#333333"
    assert obj.color.id

    obj = NodeManager.get_one(obj1.id)

    assert obj.id == obj1.id
    assert obj.db_id == obj1.db_id
    assert obj.name.value == "low"
    assert obj.name.id
    assert obj.level.value == 4
    assert obj.level.id
    assert obj.description.value is None
    assert obj.description.id
    assert obj.color.value == "#444444"
    assert obj.color.id


def test_get_one_relationship(default_branch, car_person_schema):

    car = registry.get_schema("Car")
    person = registry.get_schema("Person")

    p1 = Node(person).new(name="John", height=180).save()

    c1 = Node(car).new(name="volt", nbr_seats=4, is_electric=True, owner=p1).save()
    c2 = Node(car).new(name="accord", nbr_seats=5, is_electric=False, owner=p1.id).save()

    c11 = NodeManager.get_one(c1.id)

    assert c11.name.value == "volt"
    assert c11.nbr_seats.value == 4
    assert c11.is_electric.value is True
    assert c11.owner.peer.id == p1.id

    p11 = NodeManager.get_one(p1.id)
    assert p11.name.value == "John"
    assert p11.height.value == 180
    assert len(list(p11.cars)) == 2


def test_get_many(default_branch, criticality_schema):

    obj1 = Node(criticality_schema).new(name="low", level=4).save()
    obj2 = Node(criticality_schema).new(name="medium", level=3, description="My desc", color="#333333").save()

    nodes = NodeManager.get_many(ids=[obj1.id, obj2.id])
    assert len(nodes) == 2


def test_query_no_filter(default_branch, criticality_schema):

    obj1 = Node(criticality_schema).new(name="low", level=4).save()
    obj2 = Node(criticality_schema).new(name="medium", level=3, description="My desc", color="#333333").save()
    obj3 = Node(criticality_schema).new(name="high", level=3, description="My desc", color="#333333").save()

    nodes = NodeManager.query(criticality_schema)
    assert len(nodes) == 3


def test_query_with_filter_string_int(default_branch, criticality_schema):

    obj1 = Node(criticality_schema).new(name="low", level=3).save()

    obj2 = Node(criticality_schema).new(name="medium", level=3, description="My desc", color="#333333").save()

    obj3 = Node(criticality_schema).new(name="high", level=4, description="My other desc", color="#333333").save()

    nodes = NodeManager.query(criticality_schema, filters={"color__value": "#333333"})
    assert len(nodes) == 2

    nodes = NodeManager.query(criticality_schema, filters={"description__value": "My other desc"})
    assert len(nodes) == 1

    nodes = NodeManager.query(criticality_schema, filters={"level__value": 3, "color__value": "#333333"})
    assert len(nodes) == 1


def test_query_with_filter_bool_rel(default_branch, car_person_schema):

    car = registry.get_schema("Car")
    person = registry.get_schema("Person")

    p1 = Node(person).new(name="John", height=180).save()
    p2 = Node(person).new(name="Jane", height=160).save()

    c1 = Node(car).new(name="volt", nbr_seats=4, is_electric=True, owner=p1).save()
    c2 = Node(car).new(name="accord", nbr_seats=5, is_electric=False, owner=p1.id).save()
    c3 = Node(car).new(name="camry", nbr_seats=5, is_electric=False, owner=p2).save()
    c4 = Node(car).new(name="yaris", nbr_seats=4, is_electric=False, owner=p2).save()

    # Check filter with a boolean
    nodes = NodeManager.query(car, filters={"is_electric__value": False})
    assert len(nodes) == 3

    # Check filter with a relationship
    nodes = NodeManager.query(car, filters={"owner__name__value": "John"})
    assert len(nodes) == 2


def test_query_non_default_class(default_branch, criticality_schema):
    class Criticality(Node):
        def always_true(self):
            return True

    registry.node["Criticality"] = Criticality

    obj1 = Node(criticality_schema).new(name="low", level=4).save()

    obj2 = Node(criticality_schema).new(name="medium", level=3, description="My desc", color="#333333").save()

    nodes = NodeManager.query(criticality_schema)
    assert len(nodes) == 2
    assert isinstance(nodes[0], Criticality)
    assert nodes[0].always_true()


def test_query_class_name(default_branch, criticality_schema):

    obj1 = Node(criticality_schema).new(name="low", level=4).save()
    obj2 = Node(criticality_schema).new(name="medium", level=3, description="My desc", color="#333333").save()

    nodes = NodeManager.query("Criticality")
    assert len(nodes) == 2


# ------------------------------------------------------------------------
# WITH BRANCH
# ------------------------------------------------------------------------
def test_get_one_local_attribute_with_branch(default_branch, criticality_schema):

    obj1 = Node(criticality_schema).new(name="low", level=4).save()

    second_branch = create_branch("branch2")
    obj2 = (
        Node(criticality_schema, branch=second_branch)
        .new(name="medium", level=3, description="My desc", color="#333333")
        .save()
    )

    obj = NodeManager.get_one(obj2.id, branch=second_branch)

    assert obj.id == obj2.id
    assert obj.db_id == obj2.db_id
    assert obj.name.value == "medium"
    assert obj.name.id
    assert obj.level.value == 3
    assert obj.level.id
    assert obj.description.value == "My desc"
    assert obj.description.id
    assert obj.color.value == "#333333"
    assert obj.color.id

    obj = NodeManager.get_one(obj1.id, branch=second_branch)

    assert obj.id == obj1.id
    assert obj.db_id == obj1.db_id
    assert obj.name.value == "low"
    assert obj.name.id
    assert obj.level.value == 4
    assert obj.level.id
    assert obj.description.value is None
    assert obj.description.id
    assert obj.color.value == "#444444"
    assert obj.color.id
