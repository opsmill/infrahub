
from infrahub.core.branch import Branch, Diff
from infrahub.core.manager import NodeManager


def test_diff_attribute(base_dataset_02, car_person_schema):

    branch1 = Branch.get_by_name("branch1")

    diff = Diff(branch=branch1)
    attrs = diff.get_attributes()

    ordered_attributes = sorted(attrs, key=lambda a: a.attr_name)

    assert len(attrs) == 1
    assert ordered_attributes[0].attr_name == "nbr_seats"
    assert ordered_attributes[0].attr_uuid == "c1at2"


def test_diff_nodes(base_dataset_02, car_person_schema):

    branch1 = Branch.get_by_name("branch1")

    diff = Diff(branch=branch1)
    nodes = diff.get_nodes()

    ordered_attributes = sorted(nodes[0].attributes, key=lambda a: a.attr_name)
    assert len(nodes) == 1
    assert ordered_attributes[1].attr_name == "name"
    assert ordered_attributes[1].attr_uuid == "c3at1"


def test_diff_relationships(base_dataset_02, car_person_schema):

    branch1 = Branch.get_by_name("branch1")

    diff = Diff(branch=branch1)
    rels = diff.get_relationships()

    assert len(rels) == 1


def test_merge(base_dataset_02, register_core_models_schema, car_person_schema):

    branch1 = Branch.get_by_name("branch1")
    branch1.merge()

    # Query all cars in main before and after the merge
    cars = sorted(NodeManager.query("Car"), key=lambda c: c.id)
    assert len(cars) == 3
    assert cars[0].id == "c1"
    assert cars[0].nbr_seats.value == 4

    cars = sorted(NodeManager.query("Car", at=base_dataset_02["time0"]), key=lambda c: c.id)
    assert len(cars) == 2
    assert cars[0].id == "c1"
    assert cars[0].nbr_seats.value == 5

    # Query all cars in branch1 before and after the merge
    cars = sorted(NodeManager.query("Car", branch=branch1), key=lambda c: c.id)
    assert len(cars) == 3

    cars = sorted(NodeManager.query("Car", branch=branch1, at=base_dataset_02["time0"]), key=lambda c: c.id)
    assert len(cars) == 3


def test_rebase_flag(base_dataset_02, car_person_schema):

    branch1 = Branch.get_by_name("branch1")

    cars = sorted(NodeManager.query("Car", branch=branch1), key=lambda c: c.id)
    assert len(cars) == 2
    assert cars[0].id == "c1"
    assert cars[0].name.value == "accord"

    branch1.ephemeral_rebase = True

    cars = sorted(NodeManager.query("Car", branch=branch1), key=lambda c: c.id)
    assert len(cars) == 3
    assert cars[0].id == "c1"
    assert cars[0].name.value == "volt"
