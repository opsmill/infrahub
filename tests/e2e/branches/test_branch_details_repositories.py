"""Git repositories card on the branch details page: the import error band."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from urllib.parse import quote

import pytest
from playwright.async_api import expect

pytestmark = pytest.mark.shard_branches_repo

if TYPE_CHECKING:
    from broken_repository import BrokenRepository
    from infrahub_sdk import InfrahubClient
    from playwright.async_api import Page

BAND_TIMEOUT_MS = 30_000

# The workflows the band reads a failed import from; a failed task of another workflow must not pass.
IMPORT_WORKFLOWS = (
    "git-repository-add-read-write",
    "git-repository-add-read-only",
    "git-repository-import-object",
    "git-read-only-repository-import-last-commit",
    "git-repository-pull-read-only",
    "sync-git-repo-with-origin",
)

FAILED_REPOSITORY_TASK_QUERY = """
query FailedRepositoryTask($taskId: String!, $branch: String!, $repositoryId: String!, $workflows: [String]!) {
  InfrahubTask(
    ids: [$taskId]
    branch: $branch
    related_node__ids: [$repositoryId]
    workflow: $workflows
    state: [FAILED, CRASHED]
  ) {
    edges { node { id } }
  }
}
"""


class TestBranchDetailsRepositoryImportError:
    async def test_import_error_band_links_to_the_task_page(
        self, admin_page: Page, infrahub_client: InfrahubClient, broken_repository: BrokenRepository
    ) -> None:
        await admin_page.goto(f"/branches/{quote(broken_repository.branch, safe='')}")

        # The table is paged and ordered by name on the server, so the repository's row may sit on
        # another page; its band comes from a separate failing-repositories query and is always shown.
        repositories_card = admin_page.get_by_test_id("branch-repositories-card")
        bands = repositories_card.get_by_test_id("repository-error-band")
        await expect(bands.first).to_be_visible(timeout=BAND_TIMEOUT_MS)
        # Only the first three bands show until "Show all"; other tests may leave failing repositories.
        show_all = repositories_card.get_by_role("button", name="Show all")
        if await show_all.is_visible():
            await show_all.click()

        band = bands.filter(has_text=broken_repository.repository_name)
        await expect(band).to_be_visible(timeout=BAND_TIMEOUT_MS)
        await expect(band).to_contain_text("import failed")
        await expect(band).to_contain_text("is missing a configuration file")

        await band.get_by_role("link", name="View task log").click()
        # The band links the newest failed import, which the periodic Git sync can replace after the first one.
        task_url = re.compile(r"/tasks/([0-9a-f-]{36})(?=$|[?#])")
        await expect(admin_page).to_have_url(task_url)
        match = task_url.search(admin_page.url)
        assert match
        response = await infrahub_client.execute_graphql(
            query=FAILED_REPOSITORY_TASK_QUERY,
            variables={
                "taskId": match[1],
                "branch": broken_repository.branch,
                "repositoryId": broken_repository.repository_id,
                "workflows": list(IMPORT_WORKFLOWS),
            },
            tracker="query-failed-repository-task",
        )
        assert response["InfrahubTask"]["edges"]
