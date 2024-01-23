from infrahub_sdk import UUIDT, InfrahubClient

from infrahub.core.constants import InfrahubKind
from infrahub.git import InfrahubRepository
from infrahub.message_bus import Meta, messages
from infrahub.message_bus.responses import ContentResponse
from infrahub.services import InfrahubServices


async def test_file_get(git_fixture_repo: InfrahubRepository, helper):
    repo = git_fixture_repo.get_git_repo_main()
    correlation_id = str(UUIDT())

    message = messages.GitFileGet(
        repository_id=str(git_fixture_repo.id),
        repository_name=git_fixture_repo.name,
        repository_kind=InfrahubKind.REPOSITORY,
        commit=repo.head.commit.hexsha,
        file="sample.txt",
        meta=Meta(reply_to="ci-testing", correlation_id=correlation_id),
    )

    bus_simulator = helper.get_message_bus_simulator()
    service = InfrahubServices(client=InfrahubClient(), message_bus=bus_simulator)
    bus_simulator.service = service

    await service.send(message=message)
    assert len(bus_simulator.replies) == 1
    reply = bus_simulator.replies[0]
    assert reply.passed
    assert reply.meta.correlation_id == correlation_id
    content_response = reply.parse(ContentResponse)
    assert content_response.content == "Someone will read this from Git."
