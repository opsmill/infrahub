from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest
from broken_repository import BrokenRepository
from helpers import Deadline, generate_random_branch_name
from infrahub_sdk.graphql import Mutation
from infrahub_sdk.testing.repository import GitRepo
from infrahub_testcontainers.container import PROJECT_ENV_VARIABLES

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from pathlib import Path

    from helpers import BranchAPI
    from infrahub_sdk import InfrahubClient

logger = logging.getLogger(__name__)

POLL_TIMEOUT_SECONDS = 150.0
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
    deadline = Deadline(f"repository {repository_name} to reach error-import on {branch}", timeout=POLL_TIMEOUT_SECONDS)
    while True:
        repository = await client.get(kind="CoreRepository", name__value=repository_name, branch=branch)
        if repository.sync_status.value == "error-import":
            return repository.id
        await deadline.tick(pause=POLL_INTERVAL_SECONDS)


async def _wait_for_failed_import_task(client: InfrahubClient, branch: str, repository_id: str) -> None:
    # The repository reaches Import Error before its import task is recorded as failed.
    deadline = Deadline(
        f"a failed import task for repository {repository_id} on {branch}", timeout=POLL_TIMEOUT_SECONDS
    )
    while True:
        response = await client.execute_graphql(
            query=FAILED_IMPORT_TASK_QUERY,
            variables={"branch": branch, "repositoryId": repository_id},
            tracker="query-failed-import-task",
        )
        if response["InfrahubTask"]["edges"]:
            return
        await deadline.tick(pause=POLL_INTERVAL_SECONDS)


async def _delete_repository(client: InfrahubClient, repository_name: str) -> None:
    repository = await client.get(kind="CoreRepository", name__value=repository_name)
    await repository.delete()


@pytest.fixture
async def broken_repository(
    branch_api: BranchAPI,
    infrahub_client: InfrahubClient,
    infrahub_compose_dir: Path,
    infrahub_provisioned_externally: bool,
    tmp_path: Path,
) -> AsyncGenerator[BrokenRepository, None]:
    """Create a Git-synced branch holding one repository in Import Error, and remove both on teardown."""
    if infrahub_provisioned_externally:
        pytest.skip("Needs the compose /remote directory to host the fixture repository")

    branch = generate_random_branch_name("repo-error-")
    repository_name = generate_random_branch_name("broken-repo-")

    source = tmp_path / repository_name
    source.mkdir()
    # Without an .infrahub.yml the first import of the repository always fails.
    (source / "README.md").write_text("Fixture repository without an .infrahub.yml\n", encoding="utf-8")
    remote_dir = infrahub_compose_dir / PROJECT_ENV_VARIABLES["INFRAHUB_TESTING_LOCAL_REMOTE_GIT_DIRECTORY"]
    GitRepo(name=repository_name, src_directory=source, dst_directory=remote_dir)

    # A branch without Git sync lists only read-only repositories, so it would hide this one.
    await branch_api.create(branch, sync_with_git=True)
    repository_created = False
    try:
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
        await infrahub_client.execute_graphql(
            query=mutation.render(), branch_name=branch, tracker="mutation-repository-create"
        )
        repository_created = True

        repository_id = await _wait_for_import_error(infrahub_client, branch, repository_name)
        await _wait_for_failed_import_task(infrahub_client, branch, repository_id)
        yield BrokenRepository(branch=branch, repository_name=repository_name, repository_id=repository_id)
    finally:
        try:
            await branch_api.delete(branch)
        except Exception:
            logger.warning("Teardown could not delete branch %s", branch, exc_info=True)
        if repository_created:
            # Repositories are branch-agnostic, so the node outlives its branch.
            try:
                await _delete_repository(infrahub_client, repository_name)
            except Exception:
                logger.warning("Teardown could not delete repository %s", repository_name, exc_info=True)
