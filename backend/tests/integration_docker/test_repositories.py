from pathlib import Path

import pytest
from infrahub_sdk import InfrahubClient
from infrahub_sdk.protocols import CoreGenericRepository, CoreReadOnlyRepository, CoreRepository
from infrahub_sdk.testing.docker import TestInfrahubDockerClient
from infrahub_sdk.testing.repository import GitRepo, GitRepoType

from infrahub.core.constants import RepositoryOperationalStatus
from tests.helpers.fixtures import get_fixtures_dir


class TestRepositoryOperationalStatus(TestInfrahubDockerClient):
    @pytest.mark.parametrize(
        "git_repo_type,repo_kind",
        [
            pytest.param(
                GitRepoType.READ_ONLY,
                CoreReadOnlyRepository,
                id="read-only-repo",
            ),
            pytest.param(
                GitRepoType.INTEGRATED,
                CoreRepository,
                id="core-repo",
            ),
        ],
    )
    async def test_repo_operational_status(
        self,
        client: InfrahubClient,
        remote_repos_dir: Path,
        git_repo_type: GitRepoType,
        repo_kind: CoreGenericRepository,
    ) -> None:
        fixture_dir = get_fixtures_dir()
        repo_name = "test_base"
        repo_dir = fixture_dir / "repos" / repo_name / "initial__main"
        repo = GitRepo(type=git_repo_type, name=repo_name, src_directory=repo_dir, dst_directory=remote_repos_dir)
        await repo.add_to_infrahub(client=client)
        in_sync = await repo.wait_for_sync_to_complete(client=client)
        assert in_sync

        repos = await client.all(kind=repo_kind)
        assert len(repos) == 1
        assert repos[0].operational_status.value == RepositoryOperationalStatus.ONLINE.value
