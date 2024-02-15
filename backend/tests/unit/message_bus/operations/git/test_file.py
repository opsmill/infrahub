from infrahub_sdk import InfrahubClient

from infrahub.core.constants import InfrahubKind
from infrahub.git import InfrahubRepository
from infrahub.message_bus import messages
from infrahub.services import InfrahubServices


async def test_file_get(git_fixture_repo: InfrahubRepository, helper):
    repo = git_fixture_repo.get_git_repo_main()

    message = messages.GitFileGet(
        repository_id=str(git_fixture_repo.id),
        repository_name=git_fixture_repo.name,
        repository_kind=InfrahubKind.REPOSITORY,
        commit=repo.head.commit.hexsha,
        file="sample.txt",
    )

    bus_simulator = helper.get_message_bus_simulator()
    service = InfrahubServices(client=InfrahubClient(), message_bus=bus_simulator)
    bus_simulator.service = service

    reply = await service.message_bus.rpc(message=message, response_class=messages.GitFileGetResponse)
    assert reply.passed
    assert reply.data.content == "Someone will read this from Git."
