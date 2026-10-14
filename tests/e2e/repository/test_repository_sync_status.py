"""The repository sync status indicator in the application header.

Scoped to the failing state on a throwaway branch. The shard's default branch carries
whatever repositories other specs have registered, in whatever state their imports reached,
so an assertion about everything being in sync is not this spec's to make. The remaining
states are covered by the component tests, which control the counts directly.
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
INDICATOR = "repository-sync-status"
INDICATOR_ERROR_LABEL = "Repositories failed to import on this branch"


class TestRepositorySyncStatus:
    @pytest.fixture(scope="class")
    async def branch_with_failed_import(
        self, infrahub_client: InfrahubClient, demo_edge_repo: None
    ) -> AsyncGenerator[str, None]:
        """A branch where the demo-edge repository is marked as failed to import."""
        name = generate_random_branch_name("repo-sync-status")
        await infrahub_client.branch.create(branch_name=name, sync_with_git=False)

        repository = await infrahub_client.get(kind="CoreRepository", name__value="demo-edge", branch=name)
        repository.sync_status.value = ERROR_IMPORT
        await repository.save()

        yield name

        with contextlib.suppress(Exception):
            await infrahub_client.branch.delete(branch_name=name)

    async def test_reports_the_failure_and_links_to_it(self, admin_page: Page, branch_with_failed_import: str) -> None:
        await admin_page.goto(f"/?branch={branch_with_failed_import}")

        indicator = admin_page.get_by_test_id(INDICATOR)
        await expect(indicator).to_be_visible()
        await expect(indicator).to_have_attribute("aria-label", INDICATOR_ERROR_LABEL)

        await indicator.click()

        await expect(admin_page).to_have_url(re.compile(re.escape(ERROR_IMPORT)))
        await expect(admin_page.get_by_role("link", name="demo-edge")).to_be_visible()
