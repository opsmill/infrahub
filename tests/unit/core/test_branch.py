from infrahub.core import get_branch
from infrahub.core.branch import Branch, Diff
from infrahub.core.constants import DiffAction
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp


async def test_get_query_filter_relationships_main(session, base_dataset_02):

    default_branch = await get_branch(branch="main", session=session)

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


async def test_get_query_filter_relationships_branch1(session, base_dataset_02):

    branch1 = await get_branch(branch="branch1", session=session)

    filters, params = branch1.get_query_filter_relationships(
        rel_labels=["r1", "r2"], at=Timestamp().to_string(), include_outside_parentheses=False
    )

    assert isinstance(filters, list)
    assert len(filters) == 4
    assert isinstance(params, dict)
    assert sorted(params.keys()) == ["branch0", "branch1", "time0", "time1"]


async def test_get_branches_and_times_to_query_main(session, base_dataset_02):

    now = Timestamp("1s")

    main_branch = await get_branch(branch="main", session=session)

    results = main_branch.get_branches_and_times_to_query()
    assert Timestamp(results["main"]) > now

    t1 = Timestamp("2s")
    results = main_branch.get_branches_and_times_to_query(t1.to_string())
    assert results["main"] == t1.to_string()


async def test_get_branches_and_times_to_query_branch1(session, base_dataset_02):

    now = Timestamp("1s")

    branch1 = await get_branch(branch="branch1", session=session)

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


async def test_diff_has_changes(session, base_dataset_02):

    branch1 = await Branch.get_by_name(name="branch1", session=session)

    diff = await Diff.init(branch=branch1, session=session)
    assert await diff.has_changes(session=session)

    diff = await Diff.init(branch=branch1, diff_from=base_dataset_02["time0"], session=session)

    assert not await diff.has_changes(session=session)

    # Create a change in main to validate that a new change will be detected but not if main is excluded (branch_only)
    c1 = await NodeManager.get_one(id="c1", session=session)
    c1.name.value = "new name"
    await c1.save(session=session)

    diff = await Diff.init(branch=branch1, diff_from=base_dataset_02["time0"], session=session)
    assert await diff.has_changes(session=session)

    diff = await Diff.init(branch=branch1, branch_only=True, diff_from=base_dataset_02["time0"])
    assert not await diff.has_changes(session=session)


async def test_diff_has_conflict(session, base_dataset_02):

    branch1 = await Branch.get_by_name(name="branch1", session=session)

    diff = await Diff.init(branch=branch1, session=session)
    assert not await diff.has_conflict(session=session)

    # Change the name of C1 in Branch1 to create a conflict
    c1 = await NodeManager.get_one(id="c1", branch=branch1, session=session)
    c1.name.value = "new name"
    await c1.save(session=session)

    diff = await Diff.init(branch=branch1, session=session)
    assert await diff.has_conflict(session=session)

    # The conflict shouldn't be reported if we are only considering the branch
    diff = await Diff.init(branch=branch1, branch_only=True, session=session)
    assert not await diff.has_conflict(session=session)


async def test_diff_get_modified_paths(session, base_dataset_02):

    branch1 = await Branch.get_by_name(name="branch1", session=session)

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
        ("relationships", "car_person", "r1", "IS_PROTECTED"),
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
        ("relationships", "car_person", "r1", "IS_VISIBLE"),
        ("relationships", "car_person", "r2", "IS_VISIBLE"),
        ("relationships", "car_person", "r2", "IS_PROTECTED"),
    }

    diff = await Diff.init(branch=branch1, session=session)
    paths = await diff.get_modified_paths(session=session)

    assert paths["main"] == expected_paths_main
    assert paths["branch1"] == expected_paths_branch1

    # Change the name of C1 in Branch1 to create a conflict
    c1 = await NodeManager.get_one(id="c1", branch=branch1, session=session)
    c1.name.value = "new name"
    await c1.save(session=session)

    diff = await Diff.init(branch=branch1, session=session)
    paths = await diff.get_modified_paths(session=session)
    expected_paths_branch1.add(("node", "c1", "name", "HAS_VALUE"))

    assert paths["branch1"] == expected_paths_branch1


async def test_diff_get_nodes(session, base_dataset_02):

    branch1 = await Branch.get_by_name(name="branch1", session=session)

    diff = await Diff.init(branch=branch1, session=session)
    nodes = await diff.get_nodes(session=session)

    assert nodes["branch1"]["c1"].action == DiffAction.UPDATED.value
    assert nodes["branch1"]["c1"].attributes["nbr_seats"].action == DiffAction.UPDATED.value
    assert nodes["branch1"]["c1"].attributes["nbr_seats"].properties["HAS_VALUE"].action == DiffAction.UPDATED.value

    assert nodes["branch1"]["c3"].action == DiffAction.ADDED.value
    assert nodes["branch1"]["c3"].attributes["nbr_seats"].action == DiffAction.ADDED.value
    assert nodes["branch1"]["c3"].attributes["nbr_seats"].properties["HAS_VALUE"].action == DiffAction.ADDED.value

    # ADD a new node in Branch1 and validate that the diff is reporting it properly
    p1 = await Node.init(schema="Person", branch=branch1, session=session)
    await p1.new(name="Bill", height=175, session=session)
    await p1.save(session=session)

    diff = await Diff.init(branch=branch1, session=session)
    nodes = await diff.get_nodes(session=session)

    assert nodes["branch1"][p1.id].action == DiffAction.ADDED.value
    assert nodes["branch1"][p1.id].attributes["name"].action == DiffAction.ADDED.value
    assert nodes["branch1"][p1.id].attributes["name"].properties["HAS_VALUE"].action == DiffAction.ADDED.value

    # TODO DELETE node
    p3 = await NodeManager.get_one(id="p3", branch=branch1, session=session)
    await p3.delete(session=session)

    diff = await Diff.init(branch=branch1, session=session)
    nodes = await diff.get_nodes(session=session)
    assert nodes["branch1"]["p3"].action == DiffAction.REMOVED.value
    assert nodes["branch1"]["p3"].attributes["name"].action == DiffAction.REMOVED.value
    assert nodes["branch1"]["p3"].attributes["name"].properties["HAS_VALUE"].action == DiffAction.REMOVED.value


async def test_diff_get_relationships(session, base_dataset_02):

    branch1 = await Branch.get_by_name(name="branch1", session=session)

    diff = await Diff.init(branch=branch1, session=session)
    rels = await diff.get_relationships(session=session)

    assert sorted(rels.keys()) == ["branch1", "main"]

    assert sorted(rels["branch1"]["car_person"].keys()) == ["r1", "r2"]
    assert rels["branch1"]["car_person"]["r1"].action == DiffAction.UPDATED.value

    assert rels["branch1"]["car_person"]["r2"].action == DiffAction.ADDED.value

    assert rels["main"]["car_person"]["r1"].action == DiffAction.UPDATED.value
    assert rels["main"]["car_person"]["r1"].properties["IS_PROTECTED"].action == DiffAction.UPDATED.value


async def test_validate(session, base_dataset_02, register_core_models_schema):

    branch1 = await Branch.get_by_name(name="branch1", session=session)
    passed, messages = await branch1.validate(session=session)

    assert passed is True
    assert messages == []

    # Change the name of C1 in Branch1 to create a conflict
    c1 = await NodeManager.get_one(id="c1", branch=branch1, session=session)
    c1.name.value = "new name"
    await c1.save(session=session)

    passed, messages = await branch1.validate(session=session)
    assert passed is False
    assert messages == ["Conflict detected at node/c1/name/HAS_VALUE"]


async def test_validate_empty_branch(session, base_dataset_02, register_core_models_schema):

    branch2 = await create_branch(branch_name="branch2", session=session)

    passed, messages = await branch2.validate(session=session)

    assert passed is True
    assert messages == []


async def test_merge(session, base_dataset_02, register_core_models_schema):

    branch1 = await Branch.get_by_name(name="branch1", session=session)
    await branch1.merge(session=session)

    # Query all cars in MAIN, AFTER the merge
    cars = sorted(await NodeManager.query(schema="Car", session=session), key=lambda c: c.id)
    assert len(cars) == 3
    assert cars[0].id == "c1"
    assert cars[0].nbr_seats.value == 4
    assert cars[0].nbr_seats.is_protected is True
    assert cars[2].id == "c3"
    assert cars[2].name.value == "volt"

    # Query All cars in MAIN, BEFORE the merge
    cars = sorted(
        await NodeManager.query(schema="Car", at=base_dataset_02["time0"], session=session), key=lambda c: c.id
    )
    assert len(cars) == 2
    assert cars[0].id == "c1"
    assert cars[0].nbr_seats.value == 5
    assert cars[0].nbr_seats.is_protected is False

    # Query all cars in BRANCH1, AFTER the merge
    cars = sorted(await NodeManager.query(schema="Car", branch=branch1, session=session), key=lambda c: c.id)
    assert len(cars) == 3
    assert cars[2].id == "c3"
    assert cars[2].name.value == "volt"

    # Query all cars in BRANCH1, BEFORE the merge
    cars = sorted(
        await NodeManager.query(schema="Car", branch=branch1, at=base_dataset_02["time0"], session=session),
        key=lambda c: c.id,
    )
    assert len(cars) == 3
    assert cars[0].id == "c1"
    assert cars[0].nbr_seats.value == 4


async def test_merge_delete(session, base_dataset_02, register_core_models_schema):

    branch1 = await Branch.get_by_name(name="branch1", session=session)

    persons = sorted(await NodeManager.query(schema="Person", session=session), key=lambda p: p.id)
    assert len(persons) == 3

    p3 = await NodeManager.get_one(id="p3", branch=branch1, session=session)
    await p3.delete(session=session)

    await branch1.merge(session=session)

    # Query all cars in MAIN, AFTER the merge
    persons = sorted(await NodeManager.query(schema="Person", session=session), key=lambda p: p.id)
    assert len(persons) == 2


async def test_rebase_flag(session, base_dataset_02):

    branch1 = await Branch.get_by_name(name="branch1", session=session)

    cars = sorted(await NodeManager.query(schema="Car", branch=branch1, session=session), key=lambda c: c.id)
    assert len(cars) == 2
    assert cars[0].id == "c1"
    assert cars[0].name.value == "accord"

    branch1.ephemeral_rebase = True

    cars = sorted(await NodeManager.query(schema="Car", branch=branch1, session=session), key=lambda c: c.id)
    assert len(cars) == 3
    assert cars[0].id == "c1"
    assert cars[0].name.value == "volt"
