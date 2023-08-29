from infrahub.git import InfrahubRepository, handle_git_check_message
from infrahub.message_bus.events import (
    CheckMessageAction,
    InfrahubCheckRPC,
    InfrahubRPCResponse,
    RPCStatusCode,
)
from infrahub_client import UUIDT


async def test_git_check_python_success(client, git_repo_checks: InfrahubRepository, mock_gql_query_my_query):
    commit = git_repo_checks.get_commit_value(branch_name="main")

    message = InfrahubCheckRPC(
        action=CheckMessageAction.PYTHON.value,
        repository_id=str(UUIDT()),
        repository_name=git_repo_checks.name,
        commit=commit,
        branch_name="main",
        check_name="Check01",
        check_location="check01.py",
    )

    response = await handle_git_check_message(message=message, client=client)

    assert isinstance(response, InfrahubRPCResponse)
    assert response.status == RPCStatusCode.OK
    assert response.response["passed"] is False
    assert response.response["errors"] == [{"branch": "main", "level": "ERROR", "message": "Not Valid"}]


async def test_git_check_python_missing(client, git_repo_checks: InfrahubRepository):
    commit = git_repo_checks.get_commit_value(branch_name="main")

    message = InfrahubCheckRPC(
        action=CheckMessageAction.PYTHON.value,
        repository_id=str(UUIDT()),
        repository_name=git_repo_checks.name,
        commit=commit,
        branch_name="main",
        check_name="Check01",
        check_location="notthere.py",
    )

    response = await handle_git_check_message(message=message, client=client)

    assert isinstance(response, InfrahubRPCResponse)
    assert response.status == RPCStatusCode.INTERNAL_ERROR
