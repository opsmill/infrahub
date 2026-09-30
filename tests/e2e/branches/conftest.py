"""Shared fixtures for the branch E2E tests.

`broken_repository` adds a repository on a throwaway branch from a fixture repo without an
`.infrahub.yml`, so its initial import (`git-repository-add-read-write`) fails deterministically
and leaves it in Import Error on that branch.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name
from infrahub_testcontainers.container import PROJECT_ENV_VARIABLES

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Awaitable, Callable
    from pathlib import Path

    from helpers import BranchAPI
    from infrahub_sdk import InfrahubClient

POLL_ATTEMPTS = 30
POLL_INTERVAL_SECONDS = 5

FAILED_IMPORT_TASK_QUERY = """
query FailedImportTask($branch: String!, $repositoryId: String!) {
  InfrahubTask(
    branch: $branch
    related_node__ids: [$repositoryId]
    workflow: ["git-repository-add-read-write"]
    state: [FAILED]
    limit: 1
  ) {
    edges { node { id } }
  }
}
"""


async def _wait_for_import_error(client: InfrahubClient, branch: str, repository_name: str) -> str:
    for _ in range(POLL_ATTEMPTS):
        repository = await client.get(kind="CoreRepository", name__value=repository_name, branch=branch)
        if repository.sync_status.value == "error-import":
            return repository.id
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
    raise RuntimeError(f"Repository {repository_name} never reached error-import on {branch}")


async def _wait_for_failed_import_task(client: InfrahubClient, branch: str, repository_id: str) -> str:
    # sync_status flips before the flow run ends Failed; the band reads the run's error lines.
    for _ in range(POLL_ATTEMPTS):
        response = await client.execute_graphql(
            query=FAILED_IMPORT_TASK_QUERY,
            variables={"branch": branch, "repositoryId": repository_id},
            tracker="query-failed-import-task",
        )
        edges = response["InfrahubTask"]["edges"]
        if edges:
            return edges[0]["node"]["id"]
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
    raise RuntimeError(f"No failed import task found for repository {repository_id} on {branch}")


@pytest.fixture
async def broken_repository(
    branch_api: BranchAPI,
    infrahub_client: InfrahubClient,
    infrahub_compose_dir: Path,
    infrahub_provisioned_externally: bool,
    tmp_path: Path,
) -> AsyncGenerator[Callable[..., Awaitable[tuple[str, str, str]]], None]:
    """Factory for branches holding one CoreRepository in Import Error.

    Awaiting the factory with `sync_with_git=...` creates a branch and returns (branch, repository
    name, failed import task id). Every branch and repository created is removed on teardown.
    """
    if infrahub_provisioned_externally:
        pytest.skip("Needs the compose /remote directory to host the fixture repository")

    from infrahub_sdk.graphql import Mutation
    from infrahub_sdk.testing.repository import GitRepo

    remote_dir = infrahub_compose_dir / PROJECT_ENV_VARIABLES["INFRAHUB_TESTING_LOCAL_REMOTE_GIT_DIRECTORY"]
    created_branches: list[str] = []
    created_repositories: list[str] = []

    async def make(*, sync_with_git: bool) -> tuple[str, str, str]:
        branch = generate_random_branch_name("repo-error-")
        repository_name = generate_random_branch_name("broken-repo-")

        source = tmp_path / repository_name
        source.mkdir()
        (source / "README.md").write_text("Fixture repository without an .infrahub.yml\n", encoding="utf-8")
        GitRepo(name=repository_name, src_directory=source, dst_directory=remote_dir)

        await branch_api.create(branch, sync_with_git=sync_with_git)
        created_branches.append(branch)

        mutation = Mutation(
            mutation="CoreRepositoryCreate",
            input_data={
                "data": {
                    "name": {"value": repository_name},
                    "location": {"value": f"/remote/{repository_name}"},
                }
            },
            query={"ok": None},
        )
        created_repositories.append(repository_name)
        await infrahub_client.execute_graphql(
            query=mutation.render(), branch_name=branch, tracker="mutation-repository-create"
        )

        repository_id = await _wait_for_import_error(infrahub_client, branch, repository_name)
        task_id = await _wait_for_failed_import_task(infrahub_client, branch, repository_id)
        return branch, repository_name, task_id

    try:
        yield make
    finally:
        for branch in created_branches:
            with contextlib.suppress(Exception):
                await branch_api.delete(branch)
        # Repositories are branch-agnostic, so the node outlives its branch.
        for repository_name in created_repositories:
            with contextlib.suppress(Exception):
                repository = await infrahub_client.get(kind="CoreRepository", name__value=repository_name)
                await repository.delete()
