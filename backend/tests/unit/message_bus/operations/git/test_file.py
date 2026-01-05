from infrahub.core.constants import InfrahubKind
from infrahub.git import InfrahubRepository
from infrahub.message_bus import messages
from infrahub.workers.dependencies import build_message_bus


async def test_file_get(git_fixture_repo: InfrahubRepository, helper, dependency_provider) -> None:
    repo = git_fixture_repo.get_git_repo_main()

    message = messages.GitFileGet(
        repository_id=str(git_fixture_repo.id),
        repository_name=git_fixture_repo.name,
        repository_kind=InfrahubKind.REPOSITORY,
        commit=repo.head.commit.hexsha,
        file="sample.txt",
    )

    bus_simulator = await helper.get_message_bus_simulator()
    with dependency_provider.scope(build_message_bus, lambda: bus_simulator):
        reply = await bus_simulator.rpc(message=message, response_class=messages.GitFileGetResponse)

        assert reply.passed
        assert reply.data.content == "Someone will read this from Git."
