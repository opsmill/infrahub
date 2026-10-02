"""Git repositories card on the branch details page: the import error band.

The repository is added on a throwaway Sync-with-Git branch from a fixture repo without an
`.infrahub.yml`, so its initial import (`git-repository-add-read-write`) fails deterministically and
leaves it in Import Error on that branch.
"""

from __future__ import annotations

import asyncio
import contextlib
import re
from typing import TYPE_CHECKING
from urllib.parse import quote

import pytest
from helpers import generate_random_branch_name
from infrahub_testcontainers.container import PROJECT_ENV_VARIABLES
from playwright.async_api import expect

pytestmark = pytest.mark.shard_branches_repo

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from pathlib import Path

    from helpers import BranchAPI
    from infrahub_sdk import InfrahubClient
    from playwright.async_api import Page

POLL_ATTEMPTS = 30
POLL_INTERVAL_SECONDS = 5
BAND_TIMEOUT_MS = 30_000

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


class TestBranchDetailsRepositoryImportError:
    @pytest.fixture
    async def broken_repository(
        self,
        branch_api: BranchAPI,
        infrahub_client: InfrahubClient,
        infrahub_compose_dir: Path,
        infrahub_provisioned_externally: bool,
        tmp_path: Path,
    ) -> AsyncGenerator[tuple[str, str, str], None]:
        """A branch holding one CoreRepository in Import Error, plus its failed import task id."""
        if infrahub_provisioned_externally:
            pytest.skip("Needs the compose /remote directory to host the fixture repository")

        from infrahub_sdk.graphql import Mutation
        from infrahub_sdk.testing.repository import GitRepo

        branch = generate_random_branch_name("repo-error-")
        repository_name = generate_random_branch_name("broken-repo-")

        source = tmp_path / "broken-repo"
        source.mkdir()
        (source / "README.md").write_text("Fixture repository without an .infrahub.yml\n", encoding="utf-8")
        remote_dir = infrahub_compose_dir / PROJECT_ENV_VARIABLES["INFRAHUB_TESTING_LOCAL_REMOTE_GIT_DIRECTORY"]
        GitRepo(name=repository_name, src_directory=source, dst_directory=remote_dir)

        # With Sync with Git off the card lists read-only repositories only, which would hide this one.
        await branch_api.create(branch, sync_with_git=True)
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

            repository_id = await _wait_for_import_error(infrahub_client, branch, repository_name)
            task_id = await _wait_for_failed_import_task(infrahub_client, branch, repository_id)

            yield branch, repository_name, task_id
        finally:
            with contextlib.suppress(Exception):
                await branch_api.delete(branch)
            # Repositories are branch-agnostic, so the node outlives its branch.
            with contextlib.suppress(Exception):
                repository = await infrahub_client.get(kind="CoreRepository", name__value=repository_name)
                await repository.delete()

    async def test_import_error_band_links_to_the_task_page(
        self, admin_page: Page, broken_repository: tuple[str, str, str]
    ) -> None:
        branch, repository_name, task_id = broken_repository

        await admin_page.goto(f"/branches/{quote(branch, safe='')}")

        # The table is paged and ordered by name on the server, so the repository's row may sit on
        # another page; its band comes from a separate failing-repositories query and is always shown.
        repositories_card = admin_page.get_by_test_id("branch-repositories-card")
        bands = repositories_card.get_by_test_id("repository-error-band")
        await expect(bands.first).to_be_visible(timeout=BAND_TIMEOUT_MS)
        # Only the first three bands show until "Show all"; other tests may leave failing repositories.
        show_all = repositories_card.get_by_role("button", name="Show all")
        if await show_all.is_visible():
            await show_all.click()

        band = bands.filter(has_text=repository_name)
        await expect(band).to_be_visible(timeout=BAND_TIMEOUT_MS)
        await expect(band).to_contain_text("import failed")
        await expect(band).to_contain_text("is missing a configuration file")

        await band.get_by_role("link", name="View task log").click()
        await expect(admin_page).to_have_url(re.compile(rf"/tasks/{re.escape(task_id)}"))
