"""On-demand remote check from a repository's Commits tab.

The action exists only for read-only repositories, so this module registers one of its own: a git
repository copied into the compose `repos` directory (mounted at /remote) with an empty
`.infrahub.yml`, so its import adds no queries, transforms or definitions to the shared dataset.
Its Infrahub node is deleted when the module ends. `demo-edge` stands in for the read-write kind.
Nothing here needs network egress.
"""

from __future__ import annotations

import re
import shutil
from datetime import datetime
from typing import TYPE_CHECKING

import pytest
from helpers import Deadline
from infrahub_sdk.testing.repository import GitRepo, GitRepoType
from infrahub_testcontainers.container import PROJECT_ENV_VARIABLES
from playwright.async_api import expect

pytestmark = pytest.mark.shard_branches_repo

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from pathlib import Path

    from infrahub_sdk import InfrahubClient
    from playwright.async_api import Page

READ_ONLY_REPO_NAME = "check-remote-read-only"
CHECK_BUTTON = "Check remote now"
CHECK_TIMEOUT_MS = 60_000
# The scheduled check runs every minute; waiting past two ticks covers a slow first one.
SCHEDULED_CHECK_WAIT_SECONDS = 150.0

COMMITS_FRESHNESS_QUERY = """
query RepositoryFreshness($id: String!) {
  InfrahubRepositoryCommits(repository_id: $id, limit: 1) {
    fetched_at
    checked_at
  }
}
"""


TASK_STATE_QUERY = """
query TaskState($id: String!) {
  InfrahubTask(ids: [$id]) {
    edges {
      node {
        state
      }
    }
  }
}
"""


def commits_tab_url(kind: str, repository_id: str) -> str:
    return f"/objects/{kind}/{repository_id}/repository_commits"


async def read_freshness(client: InfrahubClient, repository_id: str) -> dict[str, str | None]:
    response = await client.execute_graphql(
        query=COMMITS_FRESHNESS_QUERY, variables={"id": repository_id}, tracker="query-repository-freshness"
    )
    return response["InfrahubRepositoryCommits"]


async def read_task_state(client: InfrahubClient, task_id: str) -> str:
    response = await client.execute_graphql(
        query=TASK_STATE_QUERY, variables={"id": task_id}, tracker="query-task-state"
    )
    return response["InfrahubTask"]["edges"][0]["node"]["state"]


@pytest.fixture(scope="module")
async def read_only_repo_id(
    infrahub_client: InfrahubClient,
    infrahub_compose_dir: Path,
    infrahub_provisioned_externally: bool,
    tmp_path_factory: pytest.TempPathFactory,
) -> AsyncGenerator[str, None]:
    if infrahub_provisioned_externally:
        pytest.skip("Needs a fixture remote in the compose repos directory")

    source = tmp_path_factory.mktemp(READ_ONLY_REPO_NAME)
    (source / ".infrahub.yml").write_text("---\nqueries: []\n", encoding="utf-8")
    remote_dir = infrahub_compose_dir / PROJECT_ENV_VARIABLES["INFRAHUB_TESTING_LOCAL_REMOTE_GIT_DIRECTORY"]
    repo = GitRepo(type=GitRepoType.READ_ONLY, name=READ_ONLY_REPO_NAME, src_directory=source, dst_directory=remote_dir)
    await repo.add_to_infrahub(client=infrahub_client)
    if not await repo.wait_for_sync_to_complete(client=infrahub_client, retries=30):
        raise RuntimeError(f"The {READ_ONLY_REPO_NAME} repository did not reach the in-sync state")

    node = await infrahub_client.get(kind="CoreReadOnlyRepository", name__value=READ_ONLY_REPO_NAME)
    # Wait for the scheduled check to stamp a check time first, so the test has an earlier time to
    # compare against, and the next scheduled check is a full interval away when it presses the button.
    deadline = Deadline(f"the scheduled check of {READ_ONLY_REPO_NAME}", timeout=SCHEDULED_CHECK_WAIT_SECONDS)
    while (await read_freshness(infrahub_client, node.id))["checked_at"] is None:
        await deadline.tick(pause=5)

    yield node.id

    await node.delete()
    shutil.rmtree(remote_dir / READ_ONLY_REPO_NAME, ignore_errors=True)


class TestRepositoryCheckRemote:
    @pytest.mark.usefixtures("demo_edge_repo")
    async def test_check_is_offered_on_read_only_repositories_only(
        self, admin_page: Page, infrahub_client: InfrahubClient, read_only_repo_id: str
    ) -> None:
        # Read-only repository: the action is offered.
        await admin_page.goto(commits_tab_url("CoreReadOnlyRepository", read_only_repo_id))
        await expect(admin_page.get_by_role("button", name=CHECK_BUTTON)).to_be_enabled()

        # Read-write repository: once the commit view has loaded, the action is absent.
        demo_edge = await infrahub_client.get(kind="CoreRepository", name__value="demo-edge")
        await admin_page.goto(commits_tab_url("CoreRepository", demo_edge.id))
        await expect(admin_page.get_by_text(re.compile(r"^Tracking "))).to_be_visible()
        await expect(admin_page.get_by_role("button", name=CHECK_BUTTON)).to_have_count(0)

    async def test_check_is_disabled_without_update_permission(
        self, read_only_page: Page, read_only_repo_id: str
    ) -> None:
        await read_only_page.goto(commits_tab_url("CoreReadOnlyRepository", read_only_repo_id))
        check_button = read_only_page.get_by_role("button", name=CHECK_BUTTON)
        await check_button.hover()
        # The tooltip names the permission, so the button is not disabled by a running check instead.
        await expect(read_only_page.get_by_role("tooltip")).to_have_text(
            "You don't have permission to update this object."
        )
        await expect(check_button).to_be_disabled()

    async def test_check_links_its_task_and_advances_the_check_time(
        self, admin_page: Page, infrahub_client: InfrahubClient, read_only_repo_id: str
    ) -> None:
        before = await read_freshness(infrahub_client, read_only_repo_id)

        await admin_page.goto(commits_tab_url("CoreReadOnlyRepository", read_only_repo_id))
        check_button = admin_page.get_by_role("button", name=CHECK_BUTTON)
        await expect(check_button).to_be_enabled()
        await check_button.click()

        await expect(check_button).to_be_disabled()
        task_link = admin_page.get_by_role("link", name="View task")
        await expect(task_link).to_have_attribute("href", re.compile(r"/tasks/[\w-]+$"))
        href = await task_link.get_attribute("href")
        assert href is not None
        task_id = href.rsplit("/", 1)[-1]

        await expect(task_link).to_have_count(0, timeout=CHECK_TIMEOUT_MS)
        await expect(check_button).to_be_enabled()

        assert await read_task_state(infrahub_client, task_id) == "COMPLETED"
        after = await read_freshness(infrahub_client, read_only_repo_id)
        assert before["checked_at"] is not None
        assert after["checked_at"] is not None
        assert datetime.fromisoformat(after["checked_at"]) > datetime.fromisoformat(before["checked_at"])
