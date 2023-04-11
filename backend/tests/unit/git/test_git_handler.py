import uuid

from infrahub.git import InfrahubRepository, handle_message
from infrahub.message_bus.events import (
    CheckMessageAction,
    InfrahubCheckRPC,
    InfrahubRPCResponse,
    RPCStatusCode,
)


async def test_handle_unknown_message(client, git_repo_checks: InfrahubRepository):
    commit = git_repo_checks.get_commit_value(branch_name="main")

    message = InfrahubCheckRPC(
        action=CheckMessageAction.PYTHON.value,
        repository_id=uuid.uuid4(),
        repository_name=git_repo_checks.name,
        commit=commit,
        branch_name="main",
        check_name="Check01",
        check_location="check01.py",
    )
    message.type = "unknown"

    response = await handle_message(message=message, client=client)

    assert isinstance(response, InfrahubRPCResponse)
    assert response.status == RPCStatusCode.NOT_FOUND.value


async def test_git_check_python_success(client, git_repo_checks: InfrahubRepository, mock_gql_query_my_query):
    commit = git_repo_checks.get_commit_value(branch_name="main")

    message = InfrahubCheckRPC(
        action=CheckMessageAction.PYTHON.value,
        repository_id=uuid.uuid4(),
        repository_name=git_repo_checks.name,
        commit=commit,
        branch_name="main",
        check_name="Check01",
        check_location="check01.py",
    )

    response = await handle_message(message=message, client=client)

    assert isinstance(response, InfrahubRPCResponse)
    assert response.status == RPCStatusCode.OK.value
    assert response.response["passed"] is False
    assert response.response["errors"] == [{"branch": "main", "level": "ERROR", "message": "Not Valid"}]
