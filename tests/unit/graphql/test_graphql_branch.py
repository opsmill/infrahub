import pytest
from graphql import graphql

from infrahub.core.branch import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.graphql import generate_graphql_schema
from infrahub.message_bus.events import (
    CheckMessageAction,
    GitMessageAction,
    InfrahubRPCResponse,
    MessageType,
    RPCStatusCode,
)


@pytest.fixture
async def repos_and_checks_in_main(session, register_core_models_schema):
    repo01 = await Node.init(session=session, schema="Repository")
    await repo01.new(session=session, name="repo01", location="git@github.com:user/repo01.git")
    await repo01.save(session=session)

    repo02 = await Node.init(session=session, schema="Repository")
    await repo02.new(session=session, name="repo02", location="git@github.com:user/repo02.git")
    await repo02.save(session=session)

    query01 = await Node.init(session=session, schema="GraphQLQuery")
    await query01.new(session=session, name="my_query", query="query { check { id } }")
    await query01.save(session=session)

    check01 = await Node.init(session=session, schema="Check")
    await check01.new(
        session=session,
        name="check01",
        query=query01,
        repository=repo01,
        file_path="check01.py",
        class_name="Check01",
        rebase=True,
    )
    await check01.save(session=session)

    check02 = await Node.init(session=session, schema="Check")
    await check02.new(
        session=session,
        name="check02",
        query=query01,
        repository=repo02,
        file_path="check02.py",
        class_name="Check02",
        rebase=True,
    )
    await check02.save(session=session)


async def test_branch_create(db, session, default_branch, car_person_schema, register_core_models_schema):
    schema = await generate_graphql_schema(session=session, include_subscription=False)

    query = """
    mutation {
        branch_create(data: { name: "branch2", is_data_only: true }) {
            ok
            object {
                id
                name
                description
                is_data_only
                is_default
                branched_from
            }
        }
    }
    """
    result = await graphql(
        schema,
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["branch_create"]["ok"] is True
    assert len(result.data["branch_create"]["object"]["id"]) == 36  # lenght of an UUID
    assert result.data["branch_create"]["object"]["name"] == "branch2"
    assert result.data["branch_create"]["object"]["description"] == ""
    assert result.data["branch_create"]["object"]["is_data_only"] == True
    assert result.data["branch_create"]["object"]["is_default"] == False
    assert result.data["branch_create"]["object"]["branched_from"] is not None

    assert await Branch.get_by_name(session=session, name="branch2")

    # Validate that we can't create a branch with a name that already exist
    result = await graphql(
        schema,
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db},
        root_value=None,
        variable_values={},
    )
    assert len(result.errors) == 1
    assert "The branch branch2, already exist" in result.errors[0].message

    # Create another branch with different inputs
    query = """
    mutation {
        branch_create(data: { name: "branch3", description: "my description" }) {
            ok
            object {
                id
                name
                description
                is_data_only
            }
        }
    }
    """
    result = await graphql(
        schema,
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["branch_create"]["ok"] is True
    assert len(result.data["branch_create"]["object"]["id"]) == 36  # lenght of an UUID
    assert result.data["branch_create"]["object"]["name"] == "branch3"
    assert result.data["branch_create"]["object"]["description"] == "my description"
    assert result.data["branch_create"]["object"]["is_data_only"] == False


async def test_branch_create_with_repositories(
    db, session, default_branch, rpc_client, repos_and_checks_in_main, register_core_models_schema, data_schema
):
    mock_response = InfrahubRPCResponse(status=RPCStatusCode.OK.value)
    await rpc_client.add_response(
        response=mock_response, message_type=MessageType.GIT, action=GitMessageAction.BRANCH_ADD
    )
    await rpc_client.add_response(
        response=mock_response, message_type=MessageType.GIT, action=GitMessageAction.BRANCH_ADD
    )

    query = """
    mutation {
        branch_create(data: { name: "branch2", is_data_only: false }) {
            ok
            object {
                id
                name
            }
        }
    }
    """
    result = await graphql(
        await generate_graphql_schema(session=session, include_subscription=False),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_rpc_client": rpc_client},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["branch_create"]["ok"] is True
    assert len(result.data["branch_create"]["object"]["id"]) == 36  # lenght of an UUID

    assert await Branch.get_by_name(session=session, name="branch2")


async def test_branch_rebase(db, session, default_branch, car_person_schema):
    branch2 = await create_branch(session=session, branch_name="branch2")

    query = """
    mutation {
        branch_rebase(data: { name: "branch2" }) {
            ok
            object {
                id
            }
        }
    }
    """
    result = await graphql(
        await generate_graphql_schema(session=session, include_subscription=False),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["branch_rebase"]["ok"] is True
    assert result.data["branch_rebase"]["object"]["id"] == str(branch2.uuid)

    new_branch2 = await Branch.get_by_name(session=session, name="branch2")
    assert new_branch2.branched_from != branch2.branched_from


async def test_branch_validate(db, session, base_dataset_02, register_core_models_schema):
    branch1 = await Branch.get_by_name(session=session, name="branch1")

    query = """
    mutation {
        branch_validate(data: { name: "branch1" }) {
            ok
            object {
                id
            }
        }
    }
    """
    result = await graphql(
        await generate_graphql_schema(session=session, include_subscription=False),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["branch_validate"]["ok"] is True
    assert result.data["branch_validate"]["object"]["id"] == str(branch1.uuid)


async def test_branch_validate_with_repositories_success(
    db, session, rpc_client, base_dataset_02, repos_and_checks_in_main, register_core_models_schema
):
    mock_response = InfrahubRPCResponse(status=RPCStatusCode.OK.value, response={"passed": True, "errors": []})
    await rpc_client.add_response(
        response=mock_response, message_type=MessageType.CHECK, action=CheckMessageAction.PYTHON
    )
    await rpc_client.add_response(
        response=mock_response, message_type=MessageType.CHECK, action=CheckMessageAction.PYTHON
    )

    branch2 = await create_branch(branch_name="branch2", session=session)

    query = """
    mutation {
        branch_validate(data: { name: "branch2" }) {
            ok
            object {
                id
            }
        }
    }
    """
    result = await graphql(
        await generate_graphql_schema(session=session, include_subscription=False),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_rpc_client": rpc_client},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["branch_validate"]["ok"] is True
    assert result.data["branch_validate"]["object"]["id"] == str(branch2.uuid)

    assert await rpc_client.ensure_all_responses_have_been_delivered()


async def test_branch_validate_with_repositories_failed(
    db, session, rpc_client, base_dataset_02, repos_and_checks_in_main, register_core_models_schema
):
    mock_response = InfrahubRPCResponse(
        status=RPCStatusCode.OK.value,
        response={"passed": False, "errors": [{"branch": "main", "level": "ERROR", "message": "Not Valid"}]},
    )
    await rpc_client.add_response(
        response=mock_response, message_type=MessageType.CHECK, action=CheckMessageAction.PYTHON
    )
    await rpc_client.add_response(
        response=mock_response, message_type=MessageType.CHECK, action=CheckMessageAction.PYTHON
    )

    branch2 = await create_branch(branch_name="branch2", session=session)

    query = """
    mutation {
        branch_validate(data: { name: "branch2" }) {
            ok
            object {
                id
            }
        }
    }
    """
    result = await graphql(
        await generate_graphql_schema(session=session, include_subscription=False),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_rpc_client": rpc_client},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["branch_validate"]["ok"] is False
    assert result.data["branch_validate"]["object"]["id"] == str(branch2.uuid)

    assert await rpc_client.ensure_all_responses_have_been_delivered()


async def test_branch_merge(db, session, base_dataset_02, register_core_models_schema):
    branch1 = await Branch.get_by_name(session=session, name="branch1")

    query = """
    mutation {
        branch_merge(data: { name: "branch1" }) {
            ok
            object {
                id
            }
        }
    }
    """
    result = await graphql(
        await generate_graphql_schema(session=session, include_subscription=False),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["branch_merge"]["ok"] is True
    assert result.data["branch_merge"]["object"]["id"] == str(branch1.uuid)


async def test_branch_merge_with_repositories(db, session, rpc_client, base_dataset_02, repos_and_checks_in_main):
    branch2 = await create_branch(branch_name="branch2", session=session)

    p1 = await Node.init(session=session, schema="Person", branch=branch2)
    await p1.new(session=session, name="bob", height=155)
    await p1.save(session=session)

    mock_response = InfrahubRPCResponse(status=RPCStatusCode.OK.value)
    await rpc_client.add_response(response=mock_response, message_type=MessageType.GIT, action=GitMessageAction.MERGE)
    await rpc_client.add_response(response=mock_response, message_type=MessageType.GIT, action=GitMessageAction.MERGE)

    mock_response = InfrahubRPCResponse(status=RPCStatusCode.OK.value, response={"passed": True, "errors": []})
    await rpc_client.add_response(
        response=mock_response, message_type=MessageType.CHECK, action=CheckMessageAction.PYTHON
    )
    await rpc_client.add_response(
        response=mock_response, message_type=MessageType.CHECK, action=CheckMessageAction.PYTHON
    )

    query = """
    mutation {
        branch_merge(data: { name: "branch2" }) {
            ok
            object {
                id
            }
        }
    }
    """
    result = await graphql(
        await generate_graphql_schema(session=session, include_subscription=False),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_rpc_client": rpc_client},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["branch_merge"]["ok"] is True
    assert result.data["branch_merge"]["object"]["id"] == str(branch2.uuid)

    assert await rpc_client.ensure_all_responses_have_been_delivered()


async def test_branch_diff_with_repositories(db, session, rpc_client, base_dataset_02, repos_and_checks_in_main):
    branch2 = await create_branch(branch_name="branch2", session=session)

    mock_response = InfrahubRPCResponse(
        status=RPCStatusCode.OK.value, response={"files_changed": ["readme.md", "mydir/myfile.py"]}
    )
    await rpc_client.add_response(response=mock_response, message_type=MessageType.GIT, action=GitMessageAction.DIFF)
    mock_response = InfrahubRPCResponse(status=RPCStatusCode.OK.value, response={"files_changed": ["anotherfile.rb"]})
    await rpc_client.add_response(response=mock_response, message_type=MessageType.GIT, action=GitMessageAction.DIFF)

    repos_list = await NodeManager.query(session=session, schema="Repository", branch=branch2)
    repos = {repo.name.value: repo for repo in repos_list}

    repo01 = repos["repo01"]
    repo01.commit.value = "dddddddddd"
    await repo01.save(session=session)

    repo02 = repos["repo02"]
    repo02.commit.value = "eeeeeeeeee"
    await repo02.save(session=session)

    p1 = await Node.init(session=session, schema="Person", branch=branch2)
    await p1.new(session=session, name="bob", height=155)
    await p1.save(session=session)

    mock_response = InfrahubRPCResponse(status=RPCStatusCode.OK.value)
    await rpc_client.add_response(response=mock_response, message_type=MessageType.GIT, action=GitMessageAction.MERGE)
    await rpc_client.add_response(response=mock_response, message_type=MessageType.GIT, action=GitMessageAction.MERGE)

    mock_response = InfrahubRPCResponse(status=RPCStatusCode.OK.value, response={"passed": True, "errors": []})
    await rpc_client.add_response(
        response=mock_response, message_type=MessageType.CHECK, action=CheckMessageAction.PYTHON
    )
    await rpc_client.add_response(
        response=mock_response, message_type=MessageType.CHECK, action=CheckMessageAction.PYTHON
    )

    query = """
    query {
        diff(branch: "branch2") {
            nodes {
                branch
                labels
                id
                changed_at
                action
                attributes {
                    name
                    id
                    changed_at
                    action
                    properties {
                        action
                    }
                }
            }
            relationships {
                branch
                id
                name
                properties {
                    branch
                    type
                    changed_at
                    action
                }
                changed_at
                action
            }
            files {
                action
                repository
                branch
                location
            }
        }
    }
    """
    result = await graphql(
        await generate_graphql_schema(session=session, include_subscription=False),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_rpc_client": rpc_client},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["diff"] == {}
