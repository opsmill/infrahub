from pathlib import Path

from infrahub_sdk import InfrahubClient
from infrahub_sdk.protocols import CoreReadOnlyRepository, CoreRepository
from infrahub_sdk.testing.docker import TestInfrahubDockerClient
from infrahub_sdk.testing.repository import GitRepo, GitRepoType

from infrahub.core.constants import RepositoryOperationalStatus
from tests.helpers.fixtures import get_fixtures_dir


class TestRepositoryOperationalStatus(TestInfrahubDockerClient):
    async def test_read_only_repo_operational_status(self, client: InfrahubClient, remote_repos_dir: Path) -> None:
        fixture_dir = get_fixtures_dir()
        repo_name = "read-only-repo"
        repo_dir = fixture_dir / "repos" / repo_name / "initial__main"
        repo = GitRepo(
            type=GitRepoType.READ_ONLY, name=repo_name, src_directory=repo_dir, dst_directory=remote_repos_dir
        )
        await repo.add_to_infrahub(client=client)
        in_sync = await repo.wait_for_sync_to_complete(client=client)
        assert in_sync

        repos = await client.all(kind=CoreReadOnlyRepository)
        assert len(repos) == 1
        assert repos[0].operational_status.value == RepositoryOperationalStatus.ONLINE.value

    async def test_core_repo_operational_status(self, client: InfrahubClient, remote_repos_dir: Path) -> None:
        fixture_dir = get_fixtures_dir()
        repo_name = "core-repo"
        repo_dir = fixture_dir / "repos" / repo_name / "initial__main"
        repo = GitRepo(name=repo_name, src_directory=repo_dir, dst_directory=remote_repos_dir)
        await repo.add_to_infrahub(client=client)
        in_sync = await repo.wait_for_sync_to_complete(client=client)
        assert in_sync

        repos = await client.all(kind=CoreRepository)
        assert len(repos) == 1
        assert repos[0].operational_status.value == RepositoryOperationalStatus.ONLINE.value
