"""The repository sync status indicator in the application header.

Both states are exercised on one throwaway branch whose repository statuses this test sets
itself, so the result does not depend on what other specs in the shard left on the default
branch. `sync_status` is branch-local, which is asserted here too.
"""

from __future__ import annotations

import contextlib
import re
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name
from playwright.async_api import expect

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from infrahub_sdk import InfrahubClient
    from playwright.async_api import Page

pytestmark = pytest.mark.shard_branches_repo

ERROR_IMPORT = "error-import"
IN_SYNC = "in-sync"
REPOSITORY_KINDS = ("CoreRepository", "CoreReadOnlyRepository")
INDICATOR = "repository-sync-status"
INDICATOR_ERROR_LABEL = "Repositories failed to import on this branch"
INDICATOR_HEALTHY_LABEL = "All Git repositories are in sync on this branch"


async def _set_sync_status(client: InfrahubClient, branch: str, value: str, name: str | None = None) -> None:
    for kind in REPOSITORY_KINDS:
        for repository in await client.all(kind=kind, branch=branch):
            if name is not None and repository.name.value != name:
                continue
            repository.sync_status.value = value
            await repository.save()


class TestRepositorySyncStatus:
    @pytest.fixture(scope="class")
    async def branch(
        self, infrahub_client: InfrahubClient, demo_edge_repo: None
    ) -> AsyncGenerator[str, None]:
        """A branch whose repositories all start in sync, whatever the default branch holds."""
        name = generate_random_branch_name("repo-sync-status")
        await infrahub_client.branch.create(branch_name=name, sync_with_git=False)
        await _set_sync_status(infrahub_client, branch=name, value=IN_SYNC)

        yield name

        with contextlib.suppress(Exception):
            await infrahub_client.branch.delete(branch_name=name)

    async def test_reports_in_sync_and_links_to_the_full_list(
        self, admin_page: Page, branch: str
    ) -> None:
        await admin_page.goto(f"/?branch={branch}")

        indicator = admin_page.get_by_test_id(INDICATOR)
        await expect(indicator).to_be_visible()
        await expect(indicator).to_have_attribute("aria-label", INDICATOR_HEALTHY_LABEL)

        await indicator.click()

        # Unfiltered: narrowing to an error that is not there would land on an empty table.
        await expect(admin_page).not_to_have_url(re.compile(re.escape(ERROR_IMPORT)))
        await expect(admin_page.get_by_role("link", name="demo-edge")).to_be_visible()

    async def test_reports_the_failure_and_links_to_it(
        self, admin_page: Page, branch: str, infrahub_client: InfrahubClient
    ) -> None:
        await _set_sync_status(infrahub_client, branch=branch, value=ERROR_IMPORT, name="demo-edge")

        await admin_page.goto(f"/?branch={branch}")

        indicator = admin_page.get_by_test_id(INDICATOR)
        await expect(indicator).to_be_visible()
        await expect(indicator).to_have_attribute("aria-label", INDICATOR_ERROR_LABEL)

        await indicator.click()

        await expect(admin_page).to_have_url(re.compile(re.escape(ERROR_IMPORT)))
        await expect(admin_page.get_by_role("link", name="demo-edge")).to_be_visible()

    async def test_the_failure_stays_on_its_branch(
        self, branch: str, infrahub_client: InfrahubClient
    ) -> None:
        on_branch = await infrahub_client.get(kind="CoreRepository", name__value="demo-edge", branch=branch)
        on_default = await infrahub_client.get(kind="CoreRepository", name__value="demo-edge")

        assert on_branch.sync_status.value == ERROR_IMPORT
        assert on_default.sync_status.value != ERROR_IMPORT
