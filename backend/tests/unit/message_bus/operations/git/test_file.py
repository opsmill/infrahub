from infrahub_sdk import InfrahubClient

from infrahub.core.constants import InfrahubKind
from infrahub.git import InfrahubRepository
from infrahub.git.models import GitFileGet, GitFileGetResponseData
from infrahub.services import InfrahubServices, WorkflowLocalExecution
from infrahub.workflows.catalogue import GIT_GET_FILE


async def test_file_get(git_fixture_repo: InfrahubRepository, helper):
    repo = git_fixture_repo.get_git_repo_main()

    model = GitFileGet(
        repository_id=str(git_fixture_repo.id),
        repository_name=git_fixture_repo.name,
        repository_kind=InfrahubKind.REPOSITORY,
        commit=repo.head.commit.hexsha,
        file="sample.txt",
    )

    bus_simulator = await helper.get_message_bus_simulator()
    service = await InfrahubServices.new(
        client=InfrahubClient(), message_bus=bus_simulator, workflow=WorkflowLocalExecution()
    )

    reply = await service.workflow.execute_workflow(
        workflow=GIT_GET_FILE, parameters={"model": model}, expected_return=GitFileGetResponseData
    )
    assert reply.content == "Someone will read this from Git."
