from typing import Dict

import pendulum
import pytest
from deepdiff import DeepDiff
from neo4j import AsyncSession
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


async def test_diff_has_changes_graph(session: AsyncSession, base_dataset_02):
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


async def test_diff_has_conflict_graph(session: AsyncSession, base_dataset_02):
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


async def test_diff_get_modified_paths_graph(session: AsyncSession, base_dataset_02):
    branch1 = await Branch.get_by_name(name="branch1", session=session)

    expected_paths_main = [
        "data/c1",
        "data/c1/name/value",
        "data/c1/owner/p1/property/IS_PROTECTED",
        "data/c2",
        "data/c2/color/value",
        "data/c2/color/property/IS_PROTECTED",
        "data/c2/color/property/IS_VISIBLE",
        "data/c2/is_electric/value",
        "data/c2/is_electric/property/IS_PROTECTED",
        "data/c2/is_electric/property/IS_VISIBLE",
        "data/c2/name/value",
        "data/c2/name/property/IS_PROTECTED",
        "data/c2/name/property/IS_VISIBLE",
        "data/c2/nbr_seats/value",
        "data/c2/nbr_seats/property/IS_PROTECTED",
        "data/c2/nbr_seats/property/IS_VISIBLE",
        "data/p1/cars/c1/property/IS_PROTECTED",
    ]

    expected_paths_branch1 = [
        "data/c1",
        "data/c1/nbr_seats/value",
        "data/c1/nbr_seats/property/IS_PROTECTED",
        "data/c1/owner/p1/property/IS_VISIBLE",
        "data/c2/owner/p1/property/IS_PROTECTED",
        "data/c2/owner/p1/property/IS_VISIBLE",
        "data/c3",
        "data/c3/color/value",
        "data/c3/color/property/IS_PROTECTED",
        "data/c3/color/property/IS_VISIBLE",
        "data/c3/is_electric/value",
        "data/c3/is_electric/property/IS_PROTECTED",
        "data/c3/is_electric/property/IS_VISIBLE",
        "data/c3/name/value",
        "data/c3/name/property/IS_PROTECTED",
        "data/c3/name/property/IS_VISIBLE",
        "data/c3/nbr_seats/value",
        "data/c3/nbr_seats/property/IS_PROTECTED",
        "data/c3/nbr_seats/property/IS_VISIBLE",
        "data/p1/cars/c1/property/IS_VISIBLE",
        "data/p1/cars/c2/property/IS_PROTECTED",
        "data/p1/cars/c2/property/IS_VISIBLE",
    ]

    diff = await Diff.init(branch=branch1, session=session)
    paths = await diff.get_modified_paths_graph(session=session)

    # Due to how the conflict check works on ModifiedPath with def __eq__ we can't compare
    # the paths directly against each other, instead the string version of the paths are compared
    modified_main = sorted([str(path) for path in paths["main"]])
    modified_branch1 = sorted([str(path) for path in paths["branch1"]])
    assert modified_main == sorted(expected_paths_main)
    assert modified_branch1 == sorted(expected_paths_branch1)

    # Change the name of C1 in Branch1 to create a conflict
    c1 = await NodeManager.get_one(id="c1", branch=branch1, session=session)
    c1.name.value = "new name"
    await c1.save(session=session)

    diff = await Diff.init(branch=branch1, session=session)
    paths = await diff.get_modified_paths_graph(session=session)
    expected_paths_branch1.append("data/c1/name/value")
    modified_branch1 = sorted([str(path) for path in paths["branch1"]])

    assert modified_branch1 == sorted(expected_paths_branch1)


async def test_diff_get_files_repository(session: AsyncSession, rpc_client, repos_in_main, base_dataset_02):
    mock_response = InfrahubRPCResponse(
        status=RPCStatusCode.OK,
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
        status=RPCStatusCode.OK, response={"files_changed": ["readme.md", "mydir/myfile.py"]}
    )
    await rpc_client.add_response(response=mock_response, message_type=MessageType.GIT, action=GitMessageAction.DIFF)

    branch2 = await create_branch(branch_name="branch2", session=session)

    repos_list = await NodeManager.query(session=session, schema="CoreRepository", branch=branch2)
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
        status=RPCStatusCode.OK, response={"files_changed": ["readme.md", "mydir/myfile.py"]}
    )
    await rpc_client.add_response(response=mock_response, message_type=MessageType.GIT, action=GitMessageAction.DIFF)
    mock_response = InfrahubRPCResponse(status=RPCStatusCode.OK, response={"files_changed": ["anotherfile.rb"]})
    await rpc_client.add_response(response=mock_response, message_type=MessageType.GIT, action=GitMessageAction.DIFF)

    branch2 = await create_branch(branch_name="branch2", session=session)

    repos_list = await NodeManager.query(session=session, schema="CoreRepository", branch=branch2)
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


async def test_diff_get_files(
    session: AsyncSession, rpc_client: InfrahubRpcClientTesting, default_branch: Branch, repos_in_main
):
    """Testing the get_modified_paths_repositories_for_branch_case01 method with 2 repositories in the database
    both repositories have a new commit value so we expect both to return something"""

    mock_response = InfrahubRPCResponse(
        status=RPCStatusCode.OK, response={"files_changed": ["readme.md", "mydir/myfile.py"]}
    )
    await rpc_client.add_response(response=mock_response, message_type=MessageType.GIT, action=GitMessageAction.DIFF)
    mock_response = InfrahubRPCResponse(status=RPCStatusCode.OK, response={"files_changed": ["anotherfile.rb"]})
    await rpc_client.add_response(response=mock_response, message_type=MessageType.GIT, action=GitMessageAction.DIFF)

    branch2 = await create_branch(branch_name="branch2", session=session)

    repos_list = await NodeManager.query(session=session, schema="CoreRepository", branch=branch2)
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


async def test_diff_get_nodes_entire_branch(session: AsyncSession, default_branch, repos_in_main):
    branch2 = await create_branch(branch_name="branch2", session=session)

    repo01b2 = await NodeManager.get_one(id=repos_in_main["repo01"].id, branch=branch2, session=session)
    repo01b2.commit.value = "1234567890"
    repo01b2.description.value = "Repo 01 first change in branch"

    time01 = Timestamp()
    await repo01b2.save(session=session, at=time01)

    time02 = Timestamp()

    repo01b2 = await NodeManager.get_one(id=repos_in_main["repo01"].id, branch=branch2, session=session)
    repo01b2.commit.value = "0987654321"
    repo01b2.description.value = "Repo 01 second change in branch"
    time03 = Timestamp()
    await repo01b2.save(session=session, at=time03)

    # Calculate the diff since the creation of the branch
    diff1 = await Diff.init(branch=branch2, session=session)
    nodes = await diff1.get_nodes(session=session)

    expected_response_branch2_repo01_time01 = {
        "branch": "branch2",
        "labels": ["CoreRepository", "LineageOwner", "LineageSource", "Node"],
        "kind": "CoreRepository",
        "id": repo01b2.id,
        "action": "updated",
        "changed_at": None,
        "attributes": [
            {
                "id": repo01b2.description.id,
                "name": "description",
                "action": "updated",
                "changed_at": None,
                "properties": [
                    {
                        "branch": "branch2",
                        "type": "HAS_VALUE",
                        "action": "updated",
                        "value": {
                            "new": "Repo 01 second change in branch",
                            "previous": "Repo 01 initial value",
                        },
                        "changed_at": time03.to_string(),
                    }
                ],
            }
        ],
    }

    assert nodes["branch2"][repo01b2.id].to_graphql() == expected_response_branch2_repo01_time01

    # Calculate the diff since the creation of the branch
    diff1 = await Diff.init(branch=branch2, session=session, diff_to=time02)
    nodes = await diff1.get_nodes(session=session)

    expected_response_branch2_repo01_time02 = {
        "branch": "branch2",
        "labels": ["CoreRepository", "LineageOwner", "LineageSource", "Node"],
        "kind": "CoreRepository",
        "id": repo01b2.id,
        "action": "updated",
        "changed_at": None,
        "attributes": [
            {
                "id": repo01b2.description.id,
                "name": "description",
                "action": "updated",
                "changed_at": None,
                "properties": [
                    {
                        "branch": "branch2",
                        "type": "HAS_VALUE",
                        "action": "updated",
                        "value": {
                            "new": "Repo 01 first change in branch",
                            "previous": "Repo 01 initial value",
                        },
                        "changed_at": time01.to_string(),
                    }
                ],
            }
        ],
    }

    assert nodes["branch2"][repo01b2.id].to_graphql() == expected_response_branch2_repo01_time02


@pytest.mark.xfail(reason="Need to investigate, fails on every other run")
async def test_diff_get_nodes_multiple_changes(session: AsyncSession, default_branch, repos_in_main):
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

    # Calculate the diff, just after the first modification in the branch (time01_after)
    # It should change the previous value returned by the query

    diff2 = await Diff.init(branch=branch2, session=session, diff_from=time01_after)
    nodes = await diff2.get_nodes(session=session)

    expected_response_branch2_repo01_time02 = {
        "branch": "branch2",
        "labels": ["DataOwner", "DataSource", "Node", "Repository"],
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


async def test_diff_get_nodes_dataset_02(session: AsyncSession, base_dataset_02):
    branch1 = await Branch.get_by_name(name="branch1", session=session)

    diff = await Diff.init(branch=branch1, session=session)
    nodes = await diff.get_nodes(session=session)

    expected_response_main_c1 = {
        "branch": "main",
        "labels": ["Node", "TestCar"],
        "kind": "TestCar",
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
        "labels": ["Node", "TestCar"],
        "kind": "TestCar",
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
    p1 = await Node.init(schema="TestPerson", branch=branch1, session=session)
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


async def test_diff_get_nodes_rebased_branch(session: AsyncSession, base_dataset_03):
    branch2 = await Branch.get_by_name(name="branch2", session=session)

    # Calculate the diff with the default value
    diff = await Diff.init(branch=branch2, session=session)
    nodes = await diff.get_nodes(session=session)

    assert list(nodes.keys()) == ["branch2"]
    assert list(nodes["branch2"].keys()) == ["p2"]
    assert sorted(nodes["branch2"]["p2"].attributes.keys()) == ["firstname", "lastname"]


async def test_diff_get_relationships(session: AsyncSession, base_dataset_02):
    branch1 = await Branch.get_by_name(name="branch1", session=session)

    diff = await Diff.init(branch=branch1, session=session)
    rels = await diff.get_relationships(session=session)

    assert sorted(rels.keys()) == ["branch1", "main"]
    assert sorted(rels["branch1"]["testcar__testperson"].keys()) == ["r1", "r2"]

    # ---------------------------------------------------
    # Branch1 / R1
    # ---------------------------------------------------
    expected_result_branch1_r1 = {
        "branch": "branch1",
        "id": "r1",
        "name": "testcar__testperson",
        "action": DiffAction.UPDATED,
        "nodes": {
            "c1": {"id": "c1", "labels": ["TestCar", "Node"], "kind": "TestCar"},
            "p1": {"id": "p1", "labels": ["Node", "TestPerson"], "kind": "TestPerson"},
        },
        "properties": {
            "IS_VISIBLE": {
                "branch": "branch1",
                "type": "IS_VISIBLE",
                "action": DiffAction.UPDATED,
                "value": {"previous": True, "new": False},
                "changed_at": Timestamp(base_dataset_02["time_m20"]),
            }
        },
        "changed_at": None,
    }

    assert (
        DeepDiff(
            expected_result_branch1_r1,
            rels["branch1"]["testcar__testperson"]["r1"].dict(),
            ignore_order=True,
        ).to_dict()
        == {}
    )
    # ---------------------------------------------------
    # Branch1 / R2
    # ---------------------------------------------------
    expected_result_branch1_r2 = {
        "branch": "branch1",
        "id": "r2",
        "name": "testcar__testperson",
        "action": DiffAction.ADDED,
        "nodes": {
            "c2": {"id": "c2", "labels": ["TestCar", "Node"], "kind": "TestCar"},
            "p1": {"id": "p1", "labels": ["Node", "TestPerson"], "kind": "TestPerson"},
        },
        "properties": {
            "IS_VISIBLE": {
                "branch": "branch1",
                "type": "IS_VISIBLE",
                "action": DiffAction.ADDED,
                "value": {"previous": None, "new": True},
                "changed_at": Timestamp(base_dataset_02["time_m20"]),
            },
            "IS_PROTECTED": {
                "branch": "branch1",
                "type": "IS_PROTECTED",
                "action": DiffAction.ADDED,
                "value": {"previous": None, "new": False},
                "changed_at": Timestamp(base_dataset_02["time_m20"]),
            },
        },
        "changed_at": Timestamp(base_dataset_02["time_m20"]),
    }

    assert (
        DeepDiff(
            expected_result_branch1_r2,
            rels["branch1"]["testcar__testperson"]["r2"].dict(),
            ignore_order=True,
        ).to_dict()
        == {}
    )

    # ---------------------------------------------------
    # main / R1
    # ---------------------------------------------------

    expected_result_main_r1 = {
        "branch": "main",
        "id": "r1",
        "name": "testcar__testperson",
        "action": DiffAction.UPDATED,
        "nodes": {
            "c1": {"id": "c1", "labels": ["TestCar", "Node"], "kind": "TestCar"},
            "p1": {"id": "p1", "labels": ["Node", "TestPerson"], "kind": "TestPerson"},
        },
        "properties": {
            "IS_PROTECTED": {
                "branch": "main",
                "action": DiffAction.UPDATED,
                "type": "IS_PROTECTED",
                "value": {"previous": False, "new": True},
                "changed_at": Timestamp(base_dataset_02["time_m30"]),
            }
        },
        "changed_at": None,
    }
    assert (
        DeepDiff(
            expected_result_main_r1,
            rels["main"]["testcar__testperson"]["r1"].dict(),
            ignore_order=True,
        ).to_dict()
        == {}
    )


async def test_diff_relationship_one_conflict(session: AsyncSession, default_branch: Branch, car_person_data_generic):
    c1_main = car_person_data_generic["c1"]
    p1_main = car_person_data_generic["p1"]
    p2_main = car_person_data_generic["p2"]

    time_minus1 = pendulum.now(tz="UTC")

    await c1_main.previous_owner.update(data=p2_main, session=session)
    await c1_main.save(session=session, at=time_minus1)

    branch2 = await create_branch(branch_name="branch2", session=session)

    c1_branch = await NodeManager.get_one(session=session, id=c1_main.id, branch=branch2)
    p1_branch = await NodeManager.get_one(session=session, id=p1_main.id, branch=branch2)

    # Change previous owner of C1 from P2 to P1 in branch
    time11 = pendulum.now(tz="UTC")
    await c1_branch.previous_owner.update(data=p1_branch, session=session)
    await c1_branch.save(session=session, at=time11)

    # Change previous owner of C1 from P2 to Null in main
    time12 = pendulum.now(tz="UTC")
    c1_main = await NodeManager.get_one(session=session, id=c1_main.id)
    await c1_main.previous_owner.update(data=[], session=session)
    await c1_main.save(session=session, at=time12)

    diff = await Diff.init(branch=branch2, session=session, branch_only=False)
    rels = await diff.get_relationships(session=session)

    assert sorted(rels.keys()) == ["branch2", "main"]
    assert len(rels["main"]["person_previous__car"].keys()) == 1
    assert len(rels["branch2"]["person_previous__car"].keys()) == 2

    rel_id_main = list(rels["main"]["person_previous__car"].keys())[0]
    rels_branch = [value.dict() for value in rels["branch2"]["person_previous__car"].values()]

    # ---------------------------------------------------
    # Branch
    # ---------------------------------------------------
    expected_result_branch = [
        {
            "branch": "branch2",
            "id": "XXXXX",
            "name": "person_previous__car",
            "action": DiffAction.ADDED,
            "nodes": {
                c1_main.id: {
                    "id": c1_main.id,
                    "labels": ["CoreArtifactTarget", "Node", "TestCar", "TestElectricCar"],
                    "kind": "TestElectricCar",
                },
                p1_main.id: {"id": p1_main.id, "labels": ["Node", "TestPerson"], "kind": "TestPerson"},
            },
            "properties": {
                "IS_VISIBLE": {
                    "branch": "branch2",
                    "type": "IS_VISIBLE",
                    "action": DiffAction.ADDED,
                    "value": {"previous": None, "new": True},
                    "changed_at": Timestamp(time11),
                },
                "IS_PROTECTED": {
                    "branch": "branch2",
                    "type": "IS_PROTECTED",
                    "action": DiffAction.ADDED,
                    "value": {"previous": None, "new": False},
                    "changed_at": Timestamp(time11),
                },
            },
            "changed_at": Timestamp(time11),
        },
        {
            "branch": "branch2",
            "id": "XXXXXX",
            "name": "person_previous__car",
            "action": DiffAction.REMOVED,
            "nodes": {
                c1_main.id: {
                    "id": c1_main.id,
                    "labels": ["CoreArtifactTarget", "Node", "TestCar", "TestElectricCar"],
                    "kind": "TestElectricCar",
                },
                p2_main.id: {"id": p2_main.id, "labels": ["Node", "TestPerson"], "kind": "TestPerson"},
            },
            "properties": {
                "IS_VISIBLE": {
                    "branch": "branch2",
                    "type": "IS_VISIBLE",
                    "action": DiffAction.REMOVED,
                    "value": {"previous": True, "new": True},
                    "changed_at": Timestamp(time11),
                },
                "IS_PROTECTED": {
                    "branch": "branch2",
                    "type": "IS_PROTECTED",
                    "action": DiffAction.REMOVED,
                    "value": {"previous": False, "new": False},
                    "changed_at": Timestamp(time11),
                },
            },
            "changed_at": Timestamp(time11),
        },
    ]

    paths_to_exclude = [
        r"root\[\d\]\['db_id'\]",
        r"root\[\d\]\['id'\]",
    ]

    assert (
        DeepDiff(
            expected_result_branch,
            rels_branch,
            exclude_regex_paths=paths_to_exclude,
            ignore_order=True,
        ).to_dict()
        == {}
    )

    # ---------------------------------------------------
    # Main
    # ---------------------------------------------------
    expected_result_main = {
        rel_id_main: {
            "branch": "main",
            "id": rel_id_main,
            "db_id": "89106",
            "name": "person_previous__car",
            "action": DiffAction.REMOVED,
            "nodes": {
                c1_main.id: {
                    "id": c1_main.id,
                    "labels": ["CoreArtifactTarget", "Node", "TestCar", "TestElectricCar"],
                    "kind": "TestElectricCar",
                },
                p2_main.id: {"id": p2_main.id, "labels": ["Node", "TestPerson"], "kind": "TestPerson"},
            },
            "properties": {
                "IS_VISIBLE": {
                    "branch": "main",
                    "type": "IS_VISIBLE",
                    "action": DiffAction.REMOVED,
                    "value": {"previous": True, "new": True},
                    "changed_at": Timestamp(time12),
                },
                "IS_PROTECTED": {
                    "branch": "main",
                    "type": "IS_PROTECTED",
                    "action": DiffAction.REMOVED,
                    "value": {"previous": False, "new": False},
                    "changed_at": Timestamp(time12),
                },
            },
            "changed_at": Timestamp(time12),
        }
    }

    paths_to_exclude = [
        r"root\['[\-\w]+'\]\['db_id'\]",
    ]

    assert (
        DeepDiff(
            expected_result_main,
            {key: value.dict() for key, value in rels["main"]["person_previous__car"].items()},
            exclude_regex_paths=paths_to_exclude,
            ignore_order=True,
        ).to_dict()
        == {}
    )


async def test_diff_relationship_many(session: AsyncSession, default_branch: Branch, base_dataset_04):
    branch1 = await get_branch(branch="branch1", session=session)

    diff = await Diff.init(branch=branch1, session=session)
    rels = await diff.get_relationships(session=session)

    assert sorted(rels.keys()) == ["branch1", "main"]
    assert len(rels["main"]["builtintag__coreorganization"].keys()) == 1
    assert len(rels["branch1"]["builtintag__coreorganization"].keys()) == 1

    rel_id_main = list(rels["main"]["builtintag__coreorganization"].keys())[0]
    rel_id_branch = list(rels["branch1"]["builtintag__coreorganization"].keys())[0]

    org1 = base_dataset_04["org1"]
    red = base_dataset_04["red"]
    yellow = base_dataset_04["yellow"]

    # ---------------------------------------------------
    # Branch1
    # ---------------------------------------------------
    expected_result_branch1 = {
        "branch": "branch1",
        "id": rel_id_branch,
        "name": "builtintag__coreorganization",
        "action": DiffAction.ADDED,
        "nodes": {
            org1.id: {"id": org1.id, "labels": ["CoreOrganization", "Node"], "kind": "CoreOrganization"},
            red.id: {"id": red.id, "labels": ["BuiltinTag", "Node"], "kind": "BuiltinTag"},
        },
        "properties": {
            "IS_VISIBLE": {
                "branch": "branch1",
                "type": "IS_VISIBLE",
                "action": DiffAction.ADDED,
                "value": {"previous": None, "new": True},
                "changed_at": Timestamp(base_dataset_04["time_m5"]),
            },
            "IS_PROTECTED": {
                "branch": "branch1",
                "type": "IS_PROTECTED",
                "action": DiffAction.ADDED,
                "value": {"previous": None, "new": False},
                "changed_at": Timestamp(base_dataset_04["time_m5"]),
            },
        },
        "changed_at": Timestamp(base_dataset_04["time_m5"]),
    }

    assert (
        DeepDiff(
            expected_result_branch1,
            rels["branch1"]["builtintag__coreorganization"][rel_id_branch].dict(),
            ignore_order=True,
        ).to_dict()
        == {}
    )

    # ---------------------------------------------------
    # Main
    # ---------------------------------------------------
    expected_result_branch1 = {
        "branch": "main",
        "id": rel_id_main,
        "name": "builtintag__coreorganization",
        "action": DiffAction.ADDED,
        "nodes": {
            org1.id: {"id": org1.id, "labels": ["CoreOrganization", "Node"], "kind": "CoreOrganization"},
            yellow.id: {"id": yellow.id, "labels": ["BuiltinTag", "Node"], "kind": "BuiltinTag"},
        },
        "properties": {
            "IS_VISIBLE": {
                "branch": "main",
                "type": "IS_VISIBLE",
                "action": DiffAction.ADDED,
                "value": {"previous": None, "new": True},
                "changed_at": Timestamp(base_dataset_04["time_m10"]),
            },
            "IS_PROTECTED": {
                "branch": "main",
                "type": "IS_PROTECTED",
                "action": DiffAction.ADDED,
                "value": {"previous": None, "new": False},
                "changed_at": Timestamp(base_dataset_04["time_m10"]),
            },
        },
        "changed_at": Timestamp(base_dataset_04["time_m10"]),
    }

    assert (
        DeepDiff(
            expected_result_branch1,
            rels["main"]["builtintag__coreorganization"][rel_id_main].dict(),
            ignore_order=True,
        ).to_dict()
        == {}
    )


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
