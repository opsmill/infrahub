from typing import Dict

import pytest
from deepdiff import DeepDiff
from pydantic import Field
from pydantic.error_wrappers import ValidationError

from infrahub.core import get_branch
from infrahub.core.branch import BaseDiffElement, Branch, Diff
from infrahub.core.constants import DiffAction
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp
from infrahub.database import execute_read_query_async
from infrahub.exceptions import BranchNotFound
from infrahub.message_bus.events import (
    GitMessageAction,
    InfrahubRPCResponse,
    MessageType,
    RPCStatusCode,
)
from infrahub.message_bus.rpc import InfrahubRpcClientTesting


async def test_branch_name_validator(session):
    assert Branch(name="new-branch")
    assert Branch(name="cr1234")
    assert Branch(name="cr1234")

    # No space
    with pytest.raises(ValidationError):
        Branch(name="new branch")

    # No comma
    with pytest.raises(ValidationError):
        Branch(name="new,branch")

    # No dot
    with pytest.raises(ValidationError):
        Branch(name="new.branch")

    # No exclamation point
    with pytest.raises(ValidationError):
        Branch(name="new!branch")

    # No uppercase
    with pytest.raises(ValidationError):
        Branch(name="New-Branch")

    # Must start with a letter
    with pytest.raises(ValidationError):
        Branch(name="1branch")

    # Need at least 3 characters
    assert Branch(name="cr1")
    with pytest.raises(ValidationError):
        Branch(name="cr")

    # No more than 32 characters
    with pytest.raises(ValidationError):
        Branch(name="qwertyuiopqwertyuiopqwertyuiopqwe")

    assert Branch(name="new-branch")
    assert Branch(name="cr1234-qwerty-qwerty")


async def test_branch_branched_form_format_validator(session):
    assert Branch(name="new-branch").branched_from is not None

    time1 = Timestamp().to_string()
    assert Branch(name="cr1234", branched_from=time1).branched_from == time1

    with pytest.raises(ValidationError):
        Branch(name="cr1234", branched_from="not a date")


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

    results = main_branch.get_branches_and_times_to_query(at=Timestamp())
    assert Timestamp(results["main"]) > now

    t1 = Timestamp("2s")
    results = main_branch.get_branches_and_times_to_query(at=t1.to_string())
    assert results["main"] == t1.to_string()


async def test_get_branches_and_times_to_query_branch1(session, base_dataset_02):
    now = Timestamp("1s")

    branch1 = await get_branch(branch="branch1", session=session)

    results = branch1.get_branches_and_times_to_query(at=Timestamp())
    assert Timestamp(results["branch1"]) > now
    assert results["main"] == base_dataset_02["time_m45"]

    t1 = Timestamp("2s")
    results = branch1.get_branches_and_times_to_query(at=t1.to_string())
    assert results["branch1"] == t1.to_string()
    assert results["main"] == base_dataset_02["time_m45"]

    branch1.ephemeral_rebase = True
    results = branch1.get_branches_and_times_to_query(at=Timestamp())
    assert Timestamp(results["branch1"]) > now
    assert results["main"] == results["branch1"]


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


async def test_diff_has_changes_graph(session, base_dataset_02):
    branch1 = await Branch.get_by_name(name="branch1", session=session)

    diff = await Diff.init(branch=branch1, session=session)
    assert await diff.has_changes_graph(session=session)

    diff = await Diff.init(branch=branch1, diff_from=base_dataset_02["time0"], session=session)

    assert not await diff.has_changes_graph(session=session)

    # Create a change in main to validate that a new change will be detected but not if main is excluded (branch_only)
    c1 = await NodeManager.get_one(id="c1", session=session)
    c1.name.value = "new name"
    await c1.save(session=session)

    diff = await Diff.init(branch=branch1, diff_from=base_dataset_02["time0"], session=session)
    assert await diff.has_changes_graph(session=session)

    diff = await Diff.init(branch=branch1, branch_only=True, diff_from=base_dataset_02["time0"])
    assert not await diff.has_changes_graph(session=session)


async def test_diff_has_conflict_graph(session, base_dataset_02):
    branch1 = await Branch.get_by_name(name="branch1", session=session)

    diff = await Diff.init(branch=branch1, session=session)
    assert not await diff.has_conflict_graph(session=session)

    # Change the name of C1 in Branch1 to create a conflict
    c1 = await NodeManager.get_one(id="c1", branch=branch1, session=session)
    c1.name.value = "new name"
    await c1.save(session=session)

    diff = await Diff.init(branch=branch1, session=session)
    assert await diff.has_conflict_graph(session=session)

    # The conflict shouldn't be reported if we are only considering the branch
    diff = await Diff.init(branch=branch1, branch_only=True, session=session)
    assert not await diff.has_conflict_graph(session=session)


async def test_diff_get_modified_paths_graph(session, base_dataset_02):
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
        ("relationships", "car__person", "r1", "IS_PROTECTED"),
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
        ("relationships", "car__person", "r1", "IS_VISIBLE"),
        ("relationships", "car__person", "r2", "IS_VISIBLE"),
        ("relationships", "car__person", "r2", "IS_PROTECTED"),
    }

    diff = await Diff.init(branch=branch1, session=session)
    paths = await diff.get_modified_paths_graph(session=session)

    assert paths["main"] == expected_paths_main
    assert paths["branch1"] == expected_paths_branch1

    # Change the name of C1 in Branch1 to create a conflict
    c1 = await NodeManager.get_one(id="c1", branch=branch1, session=session)
    c1.name.value = "new name"
    await c1.save(session=session)

    diff = await Diff.init(branch=branch1, session=session)
    paths = await diff.get_modified_paths_graph(session=session)
    expected_paths_branch1.add(("node", "c1", "name", "HAS_VALUE"))

    assert paths["branch1"] == expected_paths_branch1


async def test_diff_get_files_repository(session, rpc_client, repos_in_main, base_dataset_02):
    mock_response = InfrahubRPCResponse(
        status=RPCStatusCode.OK.value,
        response={
            "files_changed": ["readme.md", "mydir/myfile.py"],
            "files_removed": ["notthere.md"],
            "files_added": ["newandshiny.md"],
        },
    )
    await rpc_client.add_response(response=mock_response, message_type=MessageType.GIT, action=GitMessageAction.DIFF)

    branch2 = await create_branch(branch_name="branch2", session=session)

    diff = await Diff.init(branch=branch2, session=session)

    resp = await diff.get_files_repository(
        rpc_client=rpc_client,
        branch_name=branch2.name,
        repository=repos_in_main["repo01"],
        commit_from="aaaaaa",
        commit_to="ccccccc",
    )

    assert len(resp) == 4
    assert isinstance(resp, list)
    assert sorted([fde.location for fde in resp]) == [
        "mydir/myfile.py",
        "newandshiny.md",
        "notthere.md",
        "readme.md",
    ]


async def test_diff_get_files_repositories_for_branch_case01(
    session, rpc_client: InfrahubRpcClientTesting, default_branch: Branch, repos_in_main
):
    """Testing the get_modified_paths_repositories_for_branch_case01 method with 2 repositories in the database
    but only one has a different commit value between 2 and from so we expect only 2 files"""

    mock_response = InfrahubRPCResponse(
        status=RPCStatusCode.OK.value, response={"files_changed": ["readme.md", "mydir/myfile.py"]}
    )
    await rpc_client.add_response(response=mock_response, message_type=MessageType.GIT, action=GitMessageAction.DIFF)

    branch2 = await create_branch(branch_name="branch2", session=session)

    repos_list = await NodeManager.query(session=session, schema="Repository", branch=branch2)
    repos = {repo.name.value: repo for repo in repos_list}

    repo01 = repos["repo01"]
    repo01.commit.value = "dddddddddd"
    await repo01.save(session=session)

    diff = await Diff.init(branch=branch2, session=session)

    resp = await diff.get_files_repositories_for_branch(session=session, rpc_client=rpc_client, branch=branch2)

    assert len(resp) == 2
    assert isinstance(resp, list)
    assert sorted([fde.location for fde in resp]) == ["mydir/myfile.py", "readme.md"]

    assert await rpc_client.ensure_all_responses_have_been_delivered()


async def test_diff_get_files_repositories_for_branch_case02(
    session, rpc_client: InfrahubRpcClientTesting, default_branch: Branch, repos_in_main
):
    """Testing the get_modified_paths_repositories_for_branch_case01 method with 2 repositories in the database
    both repositories have a new commit value so we expect both to return something"""

    mock_response = InfrahubRPCResponse(
        status=RPCStatusCode.OK.value, response={"files_changed": ["readme.md", "mydir/myfile.py"]}
    )
    await rpc_client.add_response(response=mock_response, message_type=MessageType.GIT, action=GitMessageAction.DIFF)
    mock_response = InfrahubRPCResponse(status=RPCStatusCode.OK.value, response={"files_changed": ["anotherfile.rb"]})
    await rpc_client.add_response(response=mock_response, message_type=MessageType.GIT, action=GitMessageAction.DIFF)

    branch2 = await create_branch(branch_name="branch2", session=session)

    repos_list = await NodeManager.query(session=session, schema="Repository", branch=branch2)
    repos = {repo.name.value: repo for repo in repos_list}

    repo01 = repos["repo01"]
    repo01.commit.value = "dddddddddd"
    await repo01.save(session=session)

    repo02 = repos["repo02"]
    repo02.commit.value = "eeeeeeeeee"
    await repo02.save(session=session)

    diff = await Diff.init(branch=branch2, session=session)

    resp = await diff.get_files_repositories_for_branch(session=session, rpc_client=rpc_client, branch=branch2)

    assert len(resp) == 3
    assert isinstance(resp, list)
    assert sorted([fde.location for fde in resp]) == ["anotherfile.rb", "mydir/myfile.py", "readme.md"]


async def test_diff_get_files(session, rpc_client: InfrahubRpcClientTesting, default_branch: Branch, repos_in_main):
    """Testing the get_modified_paths_repositories_for_branch_case01 method with 2 repositories in the database
    both repositories have a new commit value so we expect both to return something"""

    mock_response = InfrahubRPCResponse(
        status=RPCStatusCode.OK.value, response={"files_changed": ["readme.md", "mydir/myfile.py"]}
    )
    await rpc_client.add_response(response=mock_response, message_type=MessageType.GIT, action=GitMessageAction.DIFF)
    mock_response = InfrahubRPCResponse(status=RPCStatusCode.OK.value, response={"files_changed": ["anotherfile.rb"]})
    await rpc_client.add_response(response=mock_response, message_type=MessageType.GIT, action=GitMessageAction.DIFF)

    branch2 = await create_branch(branch_name="branch2", session=session)

    repos_list = await NodeManager.query(session=session, schema="Repository", branch=branch2)
    repos = {repo.name.value: repo for repo in repos_list}

    repo01 = repos["repo01"]
    repo01.commit.value = "dddddddddd"
    await repo01.save(session=session)

    repo02 = repos["repo02"]
    repo02.commit.value = "eeeeeeeeee"
    await repo02.save(session=session)

    diff = await Diff.init(branch=branch2, session=session)

    resp = await diff.get_files(session=session, rpc_client=rpc_client)

    assert len(resp) == 2
    assert "branch2" in resp
    assert isinstance(resp["branch2"], list)
    assert sorted([fde.location for fde in resp["branch2"]]) == ["anotherfile.rb", "mydir/myfile.py", "readme.md"]


@pytest.mark.xfail(reason="FIXME: Currently the previous value is incorrect")
async def test_diff_get_nodes_entire_branch(session, default_branch, repos_in_main):
    branch2 = await create_branch(branch_name="branch2", session=session)

    repo01b2 = await NodeManager.get_one(id=repos_in_main["repo01"].id, branch=branch2, session=session)
    repo01b2.commit.value = "1234567890"

    time01 = Timestamp()
    await repo01b2.save(session=session, at=time01)
    Timestamp()

    repo01b2 = await NodeManager.get_one(id=repos_in_main["repo01"].id, branch=branch2, session=session)
    repo01b2.commit.value = "0987654321"

    time02 = Timestamp()
    await repo01b2.save(session=session, at=time02)
    Timestamp()

    # Calculate the diff since the creation of the branch
    diff1 = await Diff.init(branch=branch2, session=session)
    nodes = await diff1.get_nodes(session=session)

    expected_response_branch2_repo01_time01 = {
        "branch": "branch2",
        "labels": ["Node", "Repository"],
        "kind": "Repository",
        "id": repo01b2.id,
        "action": "updated",
        "changed_at": None,
        "attributes": [
            {
                "id": repo01b2.commit.id,
                "name": "commit",
                "action": "updated",
                "changed_at": None,
                "properties": [
                    {
                        "branch": "branch2",
                        "type": "HAS_VALUE",
                        "action": "updated",
                        "value": {
                            "new": "0987654321",
                            "previous": "aaaaaaaaaaa",
                        },
                        "changed_at": time01.to_string(),
                    }
                ],
            }
        ],
    }

    assert nodes["branch2"][repo01b2.id].to_graphql() == expected_response_branch2_repo01_time01


@pytest.mark.xfail(reason="FIXME: Currently the previous value is incorrect")
async def test_diff_get_nodes_multiple_changes(session, default_branch, repos_in_main):
    branch2 = await create_branch(branch_name="branch2", session=session)

    repo01b2 = await NodeManager.get_one(id=repos_in_main["repo01"].id, branch=branch2, session=session)
    repo01b2.commit.value = "1234567890"

    time01 = Timestamp()
    await repo01b2.save(session=session, at=time01)
    time01_after = Timestamp()

    repo01b2 = await NodeManager.get_one(id=repos_in_main["repo01"].id, branch=branch2, session=session)
    repo01b2.commit.value = "0987654321"

    time02 = Timestamp()
    await repo01b2.save(session=session, at=time02)
    Timestamp()

    # Calculate the diff, just after the first modication in the branch (time01_after)
    # It should change the previous value returned by the query

    diff2 = await Diff.init(branch=branch2, session=session, diff_from=time01_after)
    nodes = await diff2.get_nodes(session=session)

    expected_response_branch2_repo01_time02 = {
        "branch": "branch2",
        "labels": ["Node", "Repository"],
        "kind": "Repository",
        "id": repo01b2.id,
        "action": "updated",
        "changed_at": None,
        "attributes": [
            {
                "id": repo01b2.commit.id,
                "name": "commit",
                "action": "updated",
                "changed_at": None,
                "properties": [
                    {
                        "branch": "branch2",
                        "type": "HAS_VALUE",
                        "action": "updated",
                        "value": {
                            "new": "0987654321",
                            "previous": "1234567890",
                        },
                        "changed_at": time02.to_string(),
                    }
                ],
            }
        ],
    }

    assert nodes["branch2"][repo01b2.id].to_graphql() == expected_response_branch2_repo01_time02


async def test_diff_get_nodes_dataset_02(session, base_dataset_02):
    branch1 = await Branch.get_by_name(name="branch1", session=session)

    diff = await Diff.init(branch=branch1, session=session)
    nodes = await diff.get_nodes(session=session)

    expected_response_main_c1 = {
        "branch": "main",
        "labels": ["Car", "Node"],
        "kind": "Car",
        "id": "c1",
        "action": "updated",
        "changed_at": None,
        "attributes": [
            {
                "id": "c1at1",
                "name": "name",
                "action": "updated",
                "changed_at": None,
                "properties": [
                    {
                        "branch": "main",
                        "type": "HAS_VALUE",
                        "action": "updated",
                        "value": {"new": "volt", "previous": "accord"},
                        "changed_at": base_dataset_02["time_m20"],
                    }
                ],
            }
        ],
    }
    assert nodes["main"]["c1"].to_graphql() == expected_response_main_c1

    expected_response_branch1_c1 = {
        "branch": "branch1",
        "labels": ["Car", "Node"],
        "kind": "Car",
        "id": "c1",
        "action": "updated",
        "changed_at": None,
        "attributes": [
            {
                "id": "c1at2",
                "name": "nbr_seats",
                "action": "updated",
                "changed_at": None,
                "properties": [
                    {
                        "branch": "branch1",
                        "type": "IS_PROTECTED",
                        "action": "updated",
                        "value": {"new": True, "previous": False},
                        "changed_at": base_dataset_02["time_m20"],
                    },
                    {
                        "branch": "branch1",
                        "type": "HAS_VALUE",
                        "action": "updated",
                        "value": {"new": 4, "previous": 5},
                        "changed_at": base_dataset_02["time_m20"],
                    },
                ],
            }
        ],
    }

    assert (
        DeepDiff(nodes["branch1"]["c1"].to_graphql(), expected_response_branch1_c1, ignore_order=True).to_dict() == {}
    )

    assert nodes["branch1"]["c3"].action == DiffAction.ADDED
    assert nodes["branch1"]["c3"].attributes["nbr_seats"].action == DiffAction.ADDED
    assert nodes["branch1"]["c3"].attributes["nbr_seats"].properties["HAS_VALUE"].action == DiffAction.ADDED

    # ADD a new node in Branch1 and validate that the diff is reporting it properly
    p1 = await Node.init(schema="Person", branch=branch1, session=session)
    await p1.new(name="Bill", height=175, session=session)
    await p1.save(session=session)

    diff = await Diff.init(branch=branch1, session=session)
    nodes = await diff.get_nodes(session=session)

    assert nodes["branch1"][p1.id].action == DiffAction.ADDED
    assert nodes["branch1"][p1.id].attributes["name"].action == DiffAction.ADDED
    assert nodes["branch1"][p1.id].attributes["name"].properties["HAS_VALUE"].action == DiffAction.ADDED

    # TODO DELETE node
    p3 = await NodeManager.get_one(id="p3", branch=branch1, session=session)
    await p3.delete(session=session)

    diff = await Diff.init(branch=branch1, session=session)
    nodes = await diff.get_nodes(session=session)
    assert nodes["branch1"]["p3"].action == DiffAction.REMOVED
    assert nodes["branch1"]["p3"].attributes["name"].action == DiffAction.REMOVED
    assert nodes["branch1"]["p3"].attributes["name"].properties["HAS_VALUE"].action == DiffAction.REMOVED


async def test_diff_get_nodes_rebased_branch(session, base_dataset_03):
    branch2 = await Branch.get_by_name(name="branch2", session=session)

    # Calculate the diff with the default value
    diff = await Diff.init(branch=branch2, session=session)
    nodes = await diff.get_nodes(session=session)

    assert list(nodes.keys()) == ["branch2"]
    assert list(nodes["branch2"].keys()) == ["p2"]
    assert sorted(nodes["branch2"]["p2"].attributes.keys()) == ["firstname", "lastname"]


async def test_diff_get_relationships(session, base_dataset_02):
    branch1 = await Branch.get_by_name(name="branch1", session=session)

    diff = await Diff.init(branch=branch1, session=session)
    rels = await diff.get_relationships(session=session)

    assert sorted(rels.keys()) == ["branch1", "main"]

    assert sorted(rels["branch1"]["car__person"].keys()) == ["r1", "r2"]
    assert rels["branch1"]["car__person"]["r1"].action == DiffAction.UPDATED
    assert rels["branch1"]["car__person"]["r1"].properties["IS_VISIBLE"].action == DiffAction.UPDATED

    assert rels["branch1"]["car__person"]["r2"].action == DiffAction.ADDED

    assert rels["main"]["car__person"]["r1"].action == DiffAction.UPDATED
    assert rels["main"]["car__person"]["r1"].properties["IS_PROTECTED"].action == DiffAction.UPDATED
    assert rels["main"]["car__person"]["r1"].properties["IS_PROTECTED"].value.previous is False
    assert rels["main"]["car__person"]["r1"].properties["IS_PROTECTED"].value.new is True


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
    assert messages == ["Conflict detected at node/c1/name/HAS_VALUE"]


async def test_validate_empty_branch(session, base_dataset_02, register_core_models_schema):
    branch2 = await create_branch(branch_name="branch2", session=session)

    passed, messages = await branch2.validate_graph(session=session)

    assert passed is True
    assert messages == []


async def test_merge_graph(session, base_dataset_02, register_core_models_schema):
    branch1 = await Branch.get_by_name(name="branch1", session=session)
    await branch1.merge_graph(session=session)

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


async def test_merge_graph_delete(session, base_dataset_02, register_core_models_schema):
    branch1 = await Branch.get_by_name(name="branch1", session=session)

    persons = sorted(await NodeManager.query(schema="Person", session=session), key=lambda p: p.id)
    assert len(persons) == 3

    p3 = await NodeManager.get_one(id="p3", branch=branch1, session=session)
    await p3.delete(session=session)

    await branch1.merge_graph(session=session)

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


async def test_base_diff_element():
    class CL3(BaseDiffElement):
        name: str

    class CL2(BaseDiffElement):
        name: str

    class CL1(BaseDiffElement):
        name: str
        attrs: Dict[str, CL2]
        attr: CL3
        hideme: str = Field(exclude=True)
        action: DiffAction

    data = {
        "name": "firstclass",
        "attrs": {"attr1": {"name": "first attr"}, "attr2": {"name": "second attr"}},
        "attr": {"name": "third attr"},
        "hideme": "should not export",
        "action": "added",
    }

    expected_response = {
        "name": "firstclass",
        "attrs": [{"name": "first attr"}, {"name": "second attr"}],
        "attr": {"name": "third attr"},
        "action": "added",
    }

    obj = CL1(**data)

    assert obj.to_graphql() == expected_response


async def test_delete_branch(
    session, rpc_client: InfrahubRpcClientTesting, default_branch: Branch, repos_in_main, car_person_schema
):
    branch_name = "delete-me"
    branch = await create_branch(branch_name=branch_name, session=session)
    found = await Branch.get_by_name(name=branch_name, session=session)

    p1 = await Node.init(schema="Person", branch=branch_name, session=session)
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
