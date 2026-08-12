from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import pytest
from infrahub_sdk.graphql import Mutation

from infrahub import config
from infrahub.core.constants import InfrahubKind
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp
from tests.integration.git.conftest import GOGS_ADMIN, create_gogs_repo

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase
    from tests.helpers.git import GogsServer


def _branch_exists_on_gogs(base_url: str, token: str, repo_name: str, branch_name: str) -> bool:
    resp = httpx.get(
        f"{base_url}/api/v1/repos/{GOGS_ADMIN}/{repo_name}/branches/{branch_name}",
        headers={"Authorization": f"token {token}"},
        timeout=10.0,
    )
    return resp.status_code == 200


def _delete_branch_on_gogs(base_url: str, token: str, repo_name: str, branch_name: str) -> None:
    httpx.delete(
        f"{base_url}/api/v1/repos/{GOGS_ADMIN}/{repo_name}/branches/{branch_name}",
        headers={"Authorization": f"token {token}"},
        timeout=10.0,
    )


class TestDeleteGitBranchGogs(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        git_repos_source_dir_module_scope: Path,
        git_repos_dir_module_scope: Path,
        client: InfrahubClient,
        gogs_server: GogsServer,
    ) -> None:
        await load_schema(db, schema=CAR_SCHEMA)

        repo1_url = create_gogs_repo(gogs_server.base_url, gogs_server.token, "gogs-repo-1", gogs_server.container)
        repo2_url = create_gogs_repo(gogs_server.base_url, gogs_server.token, "gogs-repo-2", gogs_server.container)

        for repo_url, repo_name in [(repo1_url, "gogs-repo-1"), (repo2_url, "gogs-repo-2")]:
            node = await client.create(
                kind=InfrahubKind.REPOSITORY,
                data={"name": repo_name, "location": repo_url},
            )
            await node.save()

    async def test_branch_deletion_propagates_to_gogs(
        self,
        initial_dataset: None,
        client: InfrahubClient,
        gogs_server: GogsServer,
        delete_branch_after_merge_reset_config: None,
        delete_git_branch_after_merge_reset_config: None,
    ) -> None:
        base_url = gogs_server.base_url
        token = gogs_server.token
        branch_name = "feature-alpha"

        config.SETTINGS.main.delete_branch_after_merge = True
        config.SETTINGS.git.delete_git_branch_after_merge = True

        branch = await client.branch.create(branch_name=branch_name, sync_with_git=True)

        assert _branch_exists_on_gogs(base_url, token, "gogs-repo-1", branch_name), (
            f"Branch {branch_name!r} not found in gogs-repo-1 after creation"
        )
        assert _branch_exists_on_gogs(base_url, token, "gogs-repo-2", branch_name), (
            f"Branch {branch_name!r} not found in gogs-repo-2 after creation"
        )

        delete_query = Mutation(
            mutation="BranchDelete",
            input_data={"data": {"name": branch.name}},
            query={"ok": None},
        )
        await client.execute_graphql(query=delete_query.render())

        assert not _branch_exists_on_gogs(base_url, token, "gogs-repo-1", branch_name), (
            f"Branch {branch_name!r} still exists in gogs-repo-1 after BranchDelete"
        )
        assert not _branch_exists_on_gogs(base_url, token, "gogs-repo-2", branch_name), (
            f"Branch {branch_name!r} still exists in gogs-repo-2 after BranchDelete"
        )

    async def test_branch_deletion_tolerates_missing_remote_branch(
        self,
        initial_dataset: None,
        client: InfrahubClient,
        gogs_server: GogsServer,
        delete_branch_after_merge_reset_config: None,
        delete_git_branch_after_merge_reset_config: None,
    ) -> None:
        base_url = gogs_server.base_url
        token = gogs_server.token
        branch_name = "feature-beta"

        config.SETTINGS.main.delete_branch_after_merge = True
        config.SETTINGS.git.delete_git_branch_after_merge = True

        branch = await client.branch.create(branch_name=branch_name, sync_with_git=True)

        _delete_branch_on_gogs(base_url, token, "gogs-repo-1", branch_name)
        _delete_branch_on_gogs(base_url, token, "gogs-repo-2", branch_name)

        delete_query = Mutation(
            mutation="BranchDelete",
            input_data={"data": {"name": branch.name}},
            query={"ok": None},
        )
        result = await client.execute_graphql(query=delete_query.render())
        assert result["BranchDelete"]["ok"] is True
