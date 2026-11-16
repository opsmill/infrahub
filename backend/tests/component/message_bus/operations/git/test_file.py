from fast_depends import Provider

from infrahub.core.constants import InfrahubKind
from infrahub.git import InfrahubRepository
from infrahub.message_bus import messages
from infrahub.workers.dependencies import build_client, build_message_bus
from tests.conftest import TestHelper
from tests.helpers.dependency_override import override_dependency
from tests.helpers.git import build_repository_client


async def test_file_get(
    git_fixture_repo: InfrahubRepository,
    helper: TestHelper,
    dependency_provider: Provider,
    register_core_models_schema: None,
) -> None:
    repo = git_fixture_repo.get_git_repo_main()

    message = messages.GitFileGet(
        repository_id=str(git_fixture_repo.id),
        repository_name=git_fixture_repo.name,
        repository_kind=InfrahubKind.REPOSITORY,
        branch_name="main",
        commit=repo.head.commit.hexsha,
        file="sample.txt",
    )

    client = build_repository_client(
        repository_id=str(git_fixture_repo.id),
        name=git_fixture_repo.name,
        location=git_fixture_repo.get_location(),
        default_branch="main",
    )
    bus_simulator = await helper.get_message_bus_simulator()
    with (
        override_dependency(build_message_bus, lambda: bus_simulator, dependency_provider=dependency_provider),
        override_dependency(build_client, lambda: client, dependency_provider=dependency_provider),
    ):
        reply = await bus_simulator.rpc(message=message, response_class=messages.GitFileGetResponse)

        assert reply.passed
        assert reply.data.content == "Someone will read this from Git."
