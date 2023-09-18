import pytest
from pydantic.error_wrappers import ValidationError as PydanticValidationError

from infrahub.core import get_branch
from infrahub.core.branch import Branch
from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp
from infrahub.database import execute_read_query_async
from infrahub.exceptions import BranchNotFound, ValidationError
from infrahub.message_bus.rpc import InfrahubRpcClientTesting


async def test_branch_name_validator(session):
    assert Branch(name="new-branch")
    assert Branch(name="cr1234")
    assert Branch(name="new.branch")
    assert Branch(name="new/branch")

    # Test path segment that ends with a period
    with pytest.raises(ValidationError):
        Branch(name="new/.")

    # Test two consecutive periods
    with pytest.raises(ValidationError):
        Branch(name="new..branch")

    # Test string starting with a forward slash
    with pytest.raises(ValidationError):
        Branch(name="/newbranch")

    # Test two consecutive forward slashes
    with pytest.raises(ValidationError):
        Branch(name="new//branch")

    # Test "@{"
    with pytest.raises(ValidationError):
        Branch(name="new@{branch")

    # Test backslash
    with pytest.raises(ValidationError):
        Branch(name="new\\branch")

    # Test ASCII control characters
    with pytest.raises(ValidationError):
        Branch(name="new\x01branch")

    # Test DEL character
    with pytest.raises(ValidationError):
        Branch(name="new\x7Fbranch")

    # Test space character
    with pytest.raises(ValidationError):
        Branch(name="new branch")

    # Test tilde character
    with pytest.raises(ValidationError):
        Branch(name="new~branch")

    # Test caret character
    with pytest.raises(ValidationError):
        Branch(name="new^branch")

    # Test colon character
    with pytest.raises(ValidationError):
        Branch(name="new:branch")

    # Test question mark
    with pytest.raises(ValidationError):
        Branch(name="new?branch")

    # Test asterisk
    with pytest.raises(ValidationError):
        Branch(name="new*branch")

    # Test square bracket
    with pytest.raises(ValidationError):
        Branch(name="new[branch")

    # Test string ending with ".lock"
    with pytest.raises(ValidationError):
        Branch(name="newbranch.lock")

    # Test string ending with a forward slash
    with pytest.raises(ValidationError):
        Branch(name="newbranch/")

    # Test string ending with a period
    with pytest.raises(ValidationError):
        Branch(name="newbranch.")

    # Need at least 3 characters
    assert Branch(name="cr1")
    with pytest.raises(PydanticValidationError):
        Branch(name="cr")

    # No more than 32 characters
    with pytest.raises(PydanticValidationError):
        Branch(name="qwertyuiopqwertyuiopqwertyuiopqwe")

    assert Branch(name="new-branch")
    assert Branch(name="cr1234-qwerty-qwerty")


async def test_branch_branched_form_format_validator(session):
    assert Branch(name="new-branch").branched_from is not None

    time1 = Timestamp().to_string()
    assert Branch(name="cr1234", branched_from=time1).branched_from == time1

    with pytest.raises(PydanticValidationError):
        Branch(name="cr1234", branched_from="not a date")


async def test_get_query_filter_relationships_main(session, base_dataset_02):
    default_branch = await get_branch(branch="main", session=session)

    filters, params = default_branch.get_query_filter_relationships(
        rel_labels=["r1", "r2"], at=Timestamp().to_string(), include_outside_parentheses=False
    )

    expected_filters = [
        "(r1.branch IN $branch0 AND r1.from <= $time0 AND r1.to IS NULL)\n OR (r1.branch IN $branch0 AND r1.from <= $time0 AND r1.to >= $time0)",
        "((r1.branch IN $branch0 AND r1.from <= $time0 AND r1.to IS NULL)\n OR (r1.branch IN $branch0 AND r1.from <= $time0 AND r1.to >= $time0))",
        "(r2.branch IN $branch0 AND r2.from <= $time0 AND r2.to IS NULL)\n OR (r2.branch IN $branch0 AND r2.from <= $time0 AND r2.to >= $time0)",
        "((r2.branch IN $branch0 AND r2.from <= $time0 AND r2.to IS NULL)\n OR (r2.branch IN $branch0 AND r2.from <= $time0 AND r2.to >= $time0))",
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

    results = main_branch.get_branches_and_times_to_query(at=Timestamp())
    assert Timestamp(results[frozenset(["main"])]) > now

    t1 = Timestamp("2s")
    results = main_branch.get_branches_and_times_to_query(at=t1.to_string())
    assert results[frozenset(["main"])] == t1.to_string()


async def test_get_branches_and_times_to_query_branch1(session, base_dataset_02):
    now = Timestamp("1s")

    branch1 = await get_branch(branch="branch1", session=session)

    results = branch1.get_branches_and_times_to_query(at=Timestamp())
    assert Timestamp(results[frozenset(["branch1"])]) > now
    assert results[frozenset(["main"])] == base_dataset_02["time_m45"]

    t1 = Timestamp("2s")
    results = branch1.get_branches_and_times_to_query(at=t1.to_string())
    assert results[frozenset(["branch1"])] == t1.to_string()
    assert results[frozenset(["main"])] == base_dataset_02["time_m45"]

    branch1.ephemeral_rebase = True
    results = branch1.get_branches_and_times_to_query(at=Timestamp())
    assert Timestamp(results[frozenset(["branch1"])]) > now
    assert results[frozenset(("main",))] == results[frozenset(["branch1"])]


async def test_get_branches_and_times_to_query_global_main(session, base_dataset_02):
    now = Timestamp("1s")

    main_branch = await get_branch(branch="main", session=session)

    results = main_branch.get_branches_and_times_to_query_global(at=Timestamp())
    assert Timestamp(results[frozenset((GLOBAL_BRANCH_NAME, "main"))]) > now

    t1 = Timestamp("2s")
    results = main_branch.get_branches_and_times_to_query_global(at=t1.to_string())
    assert results[frozenset((GLOBAL_BRANCH_NAME, "main"))] == t1.to_string()


async def test_get_branches_and_times_to_query_global_branch1(session, base_dataset_02):
    now = Timestamp("1s")

    branch1 = await get_branch(branch="branch1", session=session)

    results = branch1.get_branches_and_times_to_query_global(at=Timestamp())
    assert Timestamp(results[frozenset((GLOBAL_BRANCH_NAME, "branch1"))]) > now
    assert results[frozenset((GLOBAL_BRANCH_NAME, "main"))] == base_dataset_02["time_m45"]

    t1 = Timestamp("2s")
    results = branch1.get_branches_and_times_to_query_global(at=t1.to_string())
    assert results[frozenset((GLOBAL_BRANCH_NAME, "branch1"))] == t1.to_string()
    assert results[frozenset((GLOBAL_BRANCH_NAME, "main"))] == base_dataset_02["time_m45"]

    branch1.ephemeral_rebase = True
    results = branch1.get_branches_and_times_to_query_global(at=Timestamp())
    assert Timestamp(frozenset((GLOBAL_BRANCH_NAME, "branch1"))) > now
    assert results[frozenset((GLOBAL_BRANCH_NAME, "main"))] == results[frozenset((GLOBAL_BRANCH_NAME, "branch1"))]


async def test_get_branches_and_times_for_range_main(session, base_dataset_02):
    now = Timestamp()
    main_branch = await get_branch(branch="main", session=session)

    start_times, end_times = main_branch.get_branches_and_times_for_range(start_time=Timestamp("1h"), end_time=now)
    assert list(start_times.keys()) == ["main"]
    assert list(end_times.keys()) == ["main"]
    assert start_times["main"] == main_branch.created_at
    assert end_times["main"] == now.to_string()

    t1 = Timestamp("2s")
    t5 = Timestamp("5s")
    start_times, end_times = main_branch.get_branches_and_times_for_range(start_time=t5, end_time=t1)
    assert list(start_times.keys()) == ["main"]
    assert list(end_times.keys()) == ["main"]
    assert start_times["main"] == t5.to_string()
    assert end_times["main"] == t1.to_string()


async def test_get_branches_and_times_for_range_branch1(session, base_dataset_02):
    now = Timestamp()
    branch1 = await get_branch(branch="branch1", session=session)

    start_times, end_times = branch1.get_branches_and_times_for_range(start_time=Timestamp("1h"), end_time=now)
    assert sorted(list(start_times.keys())) == ["branch1", "main"]
    assert sorted(list(end_times.keys())) == ["branch1", "main"]
    assert end_times["branch1"] == now.to_string()
    assert end_times["main"] == now.to_string()
    assert start_times["branch1"] == base_dataset_02["time_m45"]
    assert start_times["main"] == base_dataset_02["time_m45"]

    t1 = Timestamp("2s")
    t10 = Timestamp("10s")
    start_times, end_times = branch1.get_branches_and_times_for_range(start_time=t10, end_time=t1)
    assert sorted(list(start_times.keys())) == ["branch1", "main"]
    assert sorted(list(end_times.keys())) == ["branch1", "main"]
    assert end_times["branch1"] == t1.to_string()
    assert end_times["main"] == t1.to_string()
    assert start_times["branch1"] == t10.to_string()
    assert start_times["main"] == t10.to_string()


async def test_get_branches_and_times_for_range_branch2(session, base_dataset_03):
    now = Timestamp()
    branch2 = await get_branch(branch="branch2", session=session)

    start_times, end_times = branch2.get_branches_and_times_for_range(start_time=Timestamp("1h"), end_time=now)
    assert sorted(list(start_times.keys())) == ["branch2", "main"]
    assert sorted(list(end_times.keys())) == ["branch2", "main"]
    assert end_times["branch2"] == now.to_string()
    assert end_times["main"] == now.to_string()
    assert start_times["branch2"] == base_dataset_03["time_m90"]
    assert start_times["main"] == base_dataset_03["time_m30"]

    t1 = Timestamp("2s")
    t10 = Timestamp("10s")
    start_times, end_times = branch2.get_branches_and_times_for_range(start_time=t10, end_time=t1)
    assert sorted(list(start_times.keys())) == ["branch2", "main"]
    assert sorted(list(end_times.keys())) == ["branch2", "main"]
    assert end_times["branch2"] == t1.to_string()
    assert end_times["main"] == t1.to_string()
    assert start_times["branch2"] == t10.to_string()
    assert start_times["main"] == t10.to_string()


async def test_validate_graph(session, base_dataset_02, register_core_models_schema):
    branch1 = await Branch.get_by_name(name="branch1", session=session)
    passed, messages = await branch1.validate_graph(session=session)

    assert passed is True
    assert messages == []

    # Change the name of C1 in Branch1 to create a conflict
    c1 = await NodeManager.get_one(id="c1", branch=branch1, session=session)
    c1.name.value = "new name"
    await c1.save(session=session)

    passed, messages = await branch1.validate_graph(session=session)
    assert passed is False
    assert messages == ["Conflict detected at data/c1/name/value"]


async def test_validate_empty_branch(session, base_dataset_02, register_core_models_schema):
    branch2 = await create_branch(branch_name="branch2", session=session)

    passed, messages = await branch2.validate_graph(session=session)

    assert passed is True
    assert messages == []


async def test_rebase_flag(session, base_dataset_02):
    branch1 = await Branch.get_by_name(name="branch1", session=session)

    cars = sorted(await NodeManager.query(schema="TestCar", branch=branch1, session=session), key=lambda c: c.id)
    assert len(cars) == 2
    assert cars[0].id == "c1"
    assert cars[0].name.value == "accord"

    branch1.ephemeral_rebase = True

    cars = sorted(await NodeManager.query(schema="TestCar", branch=branch1, session=session), key=lambda c: c.id)
    assert len(cars) == 3
    assert cars[0].id == "c1"
    assert cars[0].name.value == "volt"


async def test_delete_branch(
    session, rpc_client: InfrahubRpcClientTesting, default_branch: Branch, repos_in_main, car_person_schema
):
    branch_name = "delete-me"
    branch = await create_branch(branch_name=branch_name, session=session)
    found = await Branch.get_by_name(name=branch_name, session=session)

    p1 = await Node.init(schema="TestPerson", branch=branch_name, session=session)
    await p1.new(name="Bobby", height=175, session=session)
    await p1.save(session=session)

    relationship_query = """
    MATCH ()-[r]-()
    WHERE r.branch = $branch_name
    RETURN r
    """
    params = {"branch_name": branch_name}
    pre_delete = await execute_read_query_async(session=session, query=relationship_query, params=params)

    await branch.delete(session=session)
    post_delete = await execute_read_query_async(session=session, query=relationship_query, params=params)

    assert branch.id == found.id
    with pytest.raises(BranchNotFound):
        await Branch.get_by_name(name=branch_name, session=session)

    assert pre_delete
    assert not post_delete


async def test_create_branch(session, empty_database):
    """Validate that creating a branch with quotes in descriptions work and are properly handled with params"""
    branch_name = "branching-out"
    description = "It's supported with quotes"
    await create_branch(branch_name=branch_name, session=session, description=description)
    branch = await Branch.get_by_name(name=branch_name, session=session)
    assert branch.name == branch_name
    assert branch.description == description
