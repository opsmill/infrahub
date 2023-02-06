from typing import Dict

import pytest
from deepdiff import DeepDiff
from pydantic import Field

from infrahub.core import get_branch
from infrahub.core.branch import BaseDiffElement, Branch, Diff
from infrahub.core.constants import DiffAction
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp
from infrahub.message_bus.events import (
    GitMessageAction,
    InfrahubRPCResponse,
    MessageType,
    RPCStatusCode,
)
from infrahub.message_bus.rpc import InfrahubRpcClientTesting


@pytest.fixture
async def repos_in_main(session, register_core_models_schema):

    repo01 = await Node.init(session=session, schema="Repository")
    await repo01.new(session=session, name="repo01", location="git@github.com:user/repo01.git", commit="aaaaaaaaaaa")
    await repo01.save(session=session)

    repo02 = await Node.init(session=session, schema="Repository")
    await repo02.new(session=session, name="repo02", location="git@github.com:user/repo02.git", commit="bbbbbbbbbbb")
    await repo02.save(session=session)

    return {"repo01": repo01, "repo02": repo02}


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
    assert results["main"] == base_dataset_02["time_m45"]

    t1 = Timestamp("2s")
    results = branch1.get_branches_and_times_to_query(t1.to_string())
    assert results["branch1"] == t1.to_string()
    assert results["main"] == base_dataset_02["time_m45"]

    branch1.ephemeral_rebase = True
    results = branch1.get_branches_and_times_to_query()
    assert Timestamp(results["branch1"]) > now
    assert results["main"] == results["branch1"]


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
        session=session,
        rpc_client=rpc_client,
        branch_name=branch2.name,
        repository=repos_in_main["repo01"],
        commit_from="aaaaaa",
        commit_to="ccccccc",
    )

    # expected_response = {
    #     ("file", repos_in_main["repo01"].id, "mydir/myfile.py"),
    #     ("file", repos_in_main["repo01"].id, "readme.md"),
    # }
    assert len(resp) == 1
    assert "branch2" in resp
    assert isinstance(resp["branch2"], set)
    assert sorted([fde.location for fde in resp["branch2"]]) == [
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

    assert len(resp) == 1
    assert "branch2" in resp
    assert isinstance(resp["branch2"], set)
    assert sorted([fde.location for fde in resp["branch2"]]) == ["mydir/myfile.py", "readme.md"]

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

    assert len(resp) == 1
    assert "branch2" in resp
    assert isinstance(resp["branch2"], set)
    assert sorted([fde.location for fde in resp["branch2"]]) == ["anotherfile.rb", "mydir/myfile.py", "readme.md"]


async def test_diff_get_nodes(session, base_dataset_02):

    branch1 = await Branch.get_by_name(name="branch1", session=session)

    diff = await Diff.init(branch=branch1, session=session)
    nodes = await diff.get_nodes(session=session)

    expected_response_main_c1 = {
        "branch": None,
        "labels": ["Car"],
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
                        "value": None,
                        "changed_at": base_dataset_02["time_m20"],
                    }
                ],
            }
        ],
    }
    assert DeepDiff(nodes["main"]["c1"].to_graphql(), expected_response_main_c1, ignore_order=True).to_dict() == {}

    expected_response_branch1_c1 = {
        "branch": None,
        "labels": ["Car"],
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
                        "value": None,
                        "changed_at": base_dataset_02["time_m20"],
                    },
                    {
                        "branch": "branch1",
                        "type": "HAS_VALUE",
                        "action": "updated",
                        "value": None,
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
