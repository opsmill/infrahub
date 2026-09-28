from fast_depends import Provider

from infrahub.core.constants import InfrahubKind
from infrahub.git import InfrahubRepository
from infrahub.message_bus import messages
from infrahub.message_bus.messages import ROUTING_KEY_MAP
from infrahub.workers.dependencies import build_message_bus
from tests.conftest import TestHelper
from tests.helpers.dependency_override import override_dependency


async def test_branch_deleted(
    git_fixture_repo: InfrahubRepository, helper: TestHelper, dependency_provider: Provider
) -> None:
    branch_name = "test-branch-to-delete"
    branch_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

    await git_fixture_repo.create_branch_in_git(branch_name=branch_name, branch_id=branch_id)

    local_branches = git_fixture_repo.get_branches_from_local(include_worktree=False)
    assert branch_name in local_branches

    message = messages.RefreshGitRepositoryBranchDeleted(
        repository_id=str(git_fixture_repo.id),
        repository_name=git_fixture_repo.name,
        repository_kind=InfrahubKind.REPOSITORY,
        branch_name=branch_name,
    )

    routing_key = ROUTING_KEY_MAP[type(message)]
    bus_simulator = await helper.get_message_bus_simulator()
    with override_dependency(build_message_bus, lambda: bus_simulator, dependency_provider=dependency_provider):
        await bus_simulator.publish(message=message, routing_key=routing_key)

    local_branches = git_fixture_repo.get_branches_from_local(include_worktree=False)
    assert branch_name not in local_branches
