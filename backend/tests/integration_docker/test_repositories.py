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
        ("git_repo_type", "repo_kind", "repo_name"),
        [
            pytest.param(
                GitRepoType.READ_ONLY,
                CoreReadOnlyRepository,
                "read-only-repo",
                id="read-only-repo",
            ),
            pytest.param(
                GitRepoType.INTEGRATED,
                CoreRepository,
                "core-repo",
                id="core-repo",
            ),
        ],
    )
    async def test_repo_operational_status(
        self,
        client: InfrahubClient,
        remote_repos_dir: Path,
        git_repo_type: GitRepoType,
        repo_kind: type[CoreGenericRepository],
        repo_name: str,
    ) -> None:
        fixture_dir = get_fixtures_dir()
        repo_dir = fixture_dir / "repos" / repo_name / "initial__main"
        repo = GitRepo(type=git_repo_type, name=repo_name, src_directory=repo_dir, dst_directory=remote_repos_dir)
        await repo.add_to_infrahub(client=client)
        in_sync = await repo.wait_for_sync_to_complete(client=client)
        assert in_sync

        repos = await client.all(kind=repo_kind)
        assert len(repos) == 1
        assert repos[0].operational_status.value == RepositoryOperationalStatus.ONLINE.value


class TestSameRepoReferences(TestInfrahubDockerClient):
    async def test_same_repo_references_resolve_on_import(
        self,
        client: InfrahubClient,
        remote_repos_dir: Path,
    ) -> None:
        fixture_dir = get_fixtures_dir()
        repo_dir = fixture_dir / "repos" / "same-repo-references" / "initial__main"
        repo = GitRepo(
            type=GitRepoType.INTEGRATED,
            name="same-repo-references",
            src_directory=repo_dir,
            dst_directory=remote_repos_dir,
        )
        await repo.add_to_infrahub(client=client)
        in_sync = await repo.wait_for_sync_to_complete(client=client)
        assert in_sync

        # An object that references a Python transform defined in the same repository should be
        # correctly resolved.
        webhook = await client.get(kind="CoreCustomWebhook", name__value="tags-webhook")
        assert webhook.transformation.id is not None
        transform = await client.get(kind="CoreTransformPython", id=webhook.transformation.id)
        assert transform.name.value == "TagsTransform"

        # A generator definition whose target group is defined as an object in the same repository
        # should also be resolved correctly.
        generator = await client.get(kind="CoreGeneratorDefinition", name__value="tags_generator")
        assert generator.targets.id is not None
        group = await client.get(kind="CoreStandardGroup", name__value="repo_defined_group")
        assert generator.targets.id == group.id
