from infrahub.git import InfrahubRepository
from infrahub.message_bus import messages
from infrahub.services import InfrahubServices
from infrahub_client import InfrahubClient


async def test_branch_create(git_fixture_repo: InfrahubRepository, helper):
    repo = git_fixture_repo.get_git_repo_main()
    original_branches = [ref.name for ref in repo.refs if not ref.name.startswith("origin/")]
    message = messages.GitBranchCreate(
        repository_id=str(git_fixture_repo.id), repository_name=git_fixture_repo.name, branch="new-branch"
    )

    bus_simulator = helper.get_message_bus_simulator()
    service = InfrahubServices(client=InfrahubClient(), message_bus=bus_simulator)
    bus_simulator.service = service

    await service.send(message=message)

    branches = [ref.name for ref in repo.refs if not ref.name.startswith("origin/")]
    assert original_branches == ["main"]
    assert branches == sorted(["main", "new-branch"])
