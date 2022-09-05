from infrahub.core import get_branch
from infrahub.core.branch import Branch, Diff
from infrahub.core.manager import NodeManager
from infrahub.core.timestamp import Timestamp


def test_get_query_filter_relationships_main(base_dataset_02, car_person_schema):

    default_branch = get_branch("main")

    filters, params = default_branch.get_query_filter_relationships(
        rel_labels=["r1", "r2"], at=Timestamp().to_string(), include_outside_parentheses=False
    )

    expected_filters = [
        "(r1.branch = $branch0 AND r1.from <= $time0 AND r1.to IS NULL)\n OR (r1.branch = $branch0 AND r1.from <= $time0 AND r1.to >= $time0)",
        "((r1.branch = $branch0 AND r1.from <= $time0 AND r1.to IS NULL)\n OR (r1.branch = $branch0 AND r1.from <= $time0 AND r1.to >= $time0))",
        "(r2.branch = $branch0 AND r2.from <= $time0 AND r2.to IS NULL)\n OR (r2.branch = $branch0 AND r2.from <= $time0 AND r2.to >= $time0)",
        "((r2.branch = $branch0 AND r2.from <= $time0 AND r2.to IS NULL)\n OR (r2.branch = $branch0 AND r2.from <= $time0 AND r2.to >= $time0))",
    ]
    assert isinstance(filters, list)
    assert filters == expected_filters
    assert isinstance(params, dict)
    assert sorted(params.keys()) == ["branch0", "time0"]


def test_get_query_filter_relationships_branch1(base_dataset_02, car_person_schema):

    branch1 = get_branch("branch1")

    filters, params = branch1.get_query_filter_relationships(
        rel_labels=["r1", "r2"], at=Timestamp().to_string(), include_outside_parentheses=False
    )

    assert isinstance(filters, list)
    assert len(filters) == 4
    assert isinstance(params, dict)
    assert sorted(params.keys()) == ["branch0", "branch1", "time0", "time1"]


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
