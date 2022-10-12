from infrahub.core import registry
from infrahub.core import get_branch
from infrahub.core.branch import Branch, Diff
from infrahub.core.node import Node
from infrahub.core.manager import NodeManager
from infrahub.core.timestamp import Timestamp
from infrahub.core.constants import RelationshipStatus, DiffAction
from infrahub.core.initialization import create_branch


def test_get_query_filter_relationships_main(base_dataset_02):

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


def test_get_query_filter_relationships_branch1(base_dataset_02):

    branch1 = get_branch("branch1")

    filters, params = branch1.get_query_filter_relationships(
        rel_labels=["r1", "r2"], at=Timestamp().to_string(), include_outside_parentheses=False
    )

    assert isinstance(filters, list)
    assert len(filters) == 4
    assert isinstance(params, dict)
    assert sorted(params.keys()) == ["branch0", "branch1", "time0", "time1"]


def test_get_branches_and_times_to_query_main(base_dataset_02):

    now = Timestamp("1s")

    main_branch = get_branch("main")

    results = main_branch.get_branches_and_times_to_query()
    assert Timestamp(results["main"]) > now

    t1 = Timestamp("2s")
    results = main_branch.get_branches_and_times_to_query(t1.to_string())
    assert results["main"] == t1.to_string()


def test_get_branches_and_times_to_query_branch1(base_dataset_02):

    now = Timestamp("1s")

    branch1 = get_branch("branch1")

    results = branch1.get_branches_and_times_to_query()
    assert Timestamp(results["branch1"]) > now
    assert results["main"] == base_dataset_02["time_m40"]

    t1 = Timestamp("2s")
    results = branch1.get_branches_and_times_to_query(t1.to_string())
    assert results["branch1"] == t1.to_string()
    assert results["main"] == base_dataset_02["time_m40"]

    branch1.ephemeral_rebase = True
    results = branch1.get_branches_and_times_to_query()
    assert Timestamp(results["branch1"]) > now
    assert results["main"] == results["branch1"]


def test_diff_has_changes(base_dataset_02):

    branch1 = Branch.get_by_name("branch1")

    diff = Diff(branch=branch1)
    assert diff.has_changes

    diff = Diff(branch=branch1, diff_from=base_dataset_02["time0"])
    assert not diff.has_changes

    # Create a change in main to validate that a new change will be detected but not if main is excluded (branch_only)
    c1 = NodeManager.get_one("c1")
    c1.name.value = "new name"
    c1.save()

    diff = Diff(branch=branch1, diff_from=base_dataset_02["time0"])
    assert diff.has_changes

    diff = Diff(branch=branch1, branch_only=True, diff_from=base_dataset_02["time0"])
    assert not diff.has_changes


def test_diff_has_conflict(base_dataset_02):

    branch1 = Branch.get_by_name("branch1")

    diff = Diff(branch=branch1)
    assert not diff.has_conflict

    # Change the name of C1 in Branch1 to create a conflict
    c1 = NodeManager.get_one("c1", branch=branch1)
    c1.name.value = "new name"
    c1.save()

    diff = Diff(branch=branch1)
    assert diff.has_conflict

    # The conflict shouldn't be reported if we are only considering the branch
    diff = Diff(branch=branch1, branch_only=True)
    assert not diff.has_conflict


def test_diff_get_modified_paths(base_dataset_02):

    branch1 = Branch.get_by_name("branch1")

    expected_paths_main = {
        ("node", "c1", "name", "HAS_VALUE"),
        ("node", "c2", "is_electric", "HAS_VALUE"),
        ("node", "c2", "is_electric", "IS_PROTECTED"),
        ("node", "c2", "is_electric", "IS_VISIBLE"),
        ("node", "c2", "name", "HAS_VALUE"),
        ("node", "c2", "name", "IS_PROTECTED"),
        ("node", "c2", "name", "IS_VISIBLE"),
        ("node", "c2", "nbr_seats", "HAS_VALUE"),
        ("node", "c2", "nbr_seats", "IS_PROTECTED"),
        ("node", "c2", "nbr_seats", "IS_VISIBLE"),
        ("node", "c2", "color", "HAS_VALUE"),
        ("node", "c2", "color", "IS_PROTECTED"),
        ("node", "c2", "color", "IS_VISIBLE"),
    }
    expected_paths_branch1 = {
        ("node", "c1", "nbr_seats", "HAS_VALUE"),
        ("node", "c1", "nbr_seats", "IS_PROTECTED"),
        ("node", "c3", "color", "HAS_VALUE"),
        ("node", "c3", "color", "IS_PROTECTED"),
        ("node", "c3", "color", "IS_VISIBLE"),
        ("node", "c3", "is_electric", "HAS_VALUE"),
        ("node", "c3", "is_electric", "IS_PROTECTED"),
        ("node", "c3", "is_electric", "IS_VISIBLE"),
        ("node", "c3", "name", "HAS_VALUE"),
        ("node", "c3", "name", "IS_PROTECTED"),
        ("node", "c3", "name", "IS_VISIBLE"),
        ("node", "c3", "nbr_seats", "HAS_VALUE"),
        ("node", "c3", "nbr_seats", "IS_PROTECTED"),
        ("node", "c3", "nbr_seats", "IS_VISIBLE"),
    }

    diff = Diff(branch=branch1)
    paths = diff.get_modified_paths()

    assert paths["main"] == expected_paths_main
    assert paths["branch1"] == expected_paths_branch1

    # Change the name of C1 in Branch1 to create a conflict
    c1 = NodeManager.get_one("c1", branch=branch1)
    c1.name.value = "new name"
    c1.save()

    diff = Diff(branch=branch1)
    paths = diff.get_modified_paths()
    expected_paths_branch1.add(("node", "c1", "name", "HAS_VALUE"))

    assert paths["branch1"] == expected_paths_branch1


def test_diff_get_nodes(base_dataset_02):

    branch1 = Branch.get_by_name("branch1")

    diff = Diff(branch=branch1)
    nodes = diff.get_nodes()

    assert nodes["branch1"]["c1"].action == DiffAction.UPDATED.value
    assert nodes["branch1"]["c1"].attributes["nbr_seats"].action == DiffAction.UPDATED.value
    assert nodes["branch1"]["c1"].attributes["nbr_seats"].properties["HAS_VALUE"].action == DiffAction.UPDATED.value

    assert nodes["branch1"]["c3"].action == DiffAction.ADDED.value
    assert nodes["branch1"]["c3"].attributes["nbr_seats"].action == DiffAction.ADDED.value
    assert nodes["branch1"]["c3"].attributes["nbr_seats"].properties["HAS_VALUE"].action == DiffAction.ADDED.value

    # ADD a new node in Branch1 and validate that the diff is reporting it properly
    p1 = Node("Person", branch=branch1).new(name="Bill", height=175).save()
    diff = Diff(branch=branch1)
    nodes = diff.get_nodes()

    assert nodes["branch1"][p1.id].action == DiffAction.ADDED.value
    assert nodes["branch1"][p1.id].attributes["name"].action == DiffAction.ADDED.value
    assert nodes["branch1"][p1.id].attributes["name"].properties["HAS_VALUE"].action == DiffAction.ADDED.value

    # TODO DELETE node
    p3 = NodeManager.get_one("p3", branch=branch1)
    p3.delete()

    diff = Diff(branch=branch1)
    nodes = diff.get_nodes()
    assert nodes["branch1"]["p3"].action == DiffAction.REMOVED.value
    assert nodes["branch1"]["p3"].attributes["name"].action == DiffAction.REMOVED.value
    assert nodes["branch1"]["p3"].attributes["name"].properties["HAS_VALUE"].action == DiffAction.REMOVED.value


def test_diff_relationships(base_dataset_02):

    branch1 = Branch.get_by_name("branch1")

    diff = Diff(branch=branch1)
    rels = diff.get_relationships()

    assert len(rels) == 1


def test_validate(base_dataset_02, register_core_models_schema):

    branch1 = Branch.get_by_name("branch1")
    passed, messages = branch1.validate()

    assert passed is True
    assert messages == []

    # Change the name of C1 in Branch1 to create a conflict
    c1 = NodeManager.get_one("c1", branch=branch1)
    c1.name.value = "new name"
    c1.save()

    passed, messages = branch1.validate()
    assert passed is False
    assert messages == ["Conflict detected at node/c1/name/HAS_VALUE"]


def test_validate_empty_branch(base_dataset_02, register_core_models_schema):

    branch2 = create_branch("branch2")

    passed, messages = branch2.validate()

    assert passed is True
    assert messages == []


def test_merge(base_dataset_02, register_core_models_schema):

    branch1 = Branch.get_by_name("branch1")
    branch1.merge()

    # Query all cars in MAIN, AFTER the merge
    cars = sorted(NodeManager.query("Car"), key=lambda c: c.id)
    assert len(cars) == 3
    assert cars[0].id == "c1"
    assert cars[0].nbr_seats.value == 4
    assert cars[0].nbr_seats.is_protected == True
    assert cars[2].id == "c3"
    assert cars[2].name.value == "volt"

    # Query All cars in MAIN, BEFORE the merge
    cars = sorted(NodeManager.query("Car", at=base_dataset_02["time0"]), key=lambda c: c.id)
    assert len(cars) == 2
    assert cars[0].id == "c1"
    assert cars[0].nbr_seats.value == 5
    assert cars[0].nbr_seats.is_protected == False

    # Query all cars in BRANCH1, AFTER the merge
    cars = sorted(NodeManager.query("Car", branch=branch1), key=lambda c: c.id)
    assert len(cars) == 3
    assert cars[2].id == "c3"
    assert cars[2].name.value == "volt"

    # Query all cars in BRANCH1, BEFORE the merge
    cars = sorted(NodeManager.query("Car", branch=branch1, at=base_dataset_02["time0"]), key=lambda c: c.id)
    assert len(cars) == 3
    assert cars[0].id == "c1"
    assert cars[0].nbr_seats.value == 4


def test_rebase_flag(base_dataset_02):

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
