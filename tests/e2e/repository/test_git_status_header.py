"""The Git status indicator in the application header (IFC-3199).

Proves the end the feature exists for: on a branch where a repository carries the
import-error sync status, the header indicator is in its error state from an ordinary
page, and activating it lands on the repository list filtered to the failure.

The failing status is set directly with a mutation rather than by engineering a real
import failure. The indicator reads `sync_status` and nothing else, so setting it
exercises the whole contract this feature depends on; that a genuine failure *produces*
that status is the importer's behaviour, covered by backend tests and untouched here.

`sync_status` is branch-local, so writing it on a throwaway branch leaves `main` and the
session-scoped `demo_edge_repo` fixture untouched — no cleanup race, and no later test
inheriting a repository that looks broken.
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
INDICATOR_ERROR_LABEL = "Repositories failed to import on this branch"
INDICATOR_HEALTHY_LABEL = "All Git repositories are in sync on this branch"


class TestGitStatusHeader:
    @pytest.fixture(scope="class")
    async def branch_with_failed_import(
        self, infrahub_client: InfrahubClient, demo_edge_repo: None
    ) -> AsyncGenerator[str, None]:
        """A branch on which the demo-edge repository's import is marked as failed."""
        name = generate_random_branch_name("git-status-header")
        await infrahub_client.branch.create(branch_name=name, sync_with_git=False)

        repository = await infrahub_client.get(kind="CoreRepository", name__value="demo-edge", branch=name)
        repository.sync_status.value = ERROR_IMPORT
        await repository.save()

        yield name

        with contextlib.suppress(Exception):
            await infrahub_client.branch.delete(branch_name=name)

    async def test_indicator_reports_the_failure_and_links_to_it(
        self, admin_page: Page, branch_with_failed_import: str
    ) -> None:
        # The operator is somewhere unrelated — the point is that the header answers from
        # anywhere, not that they were already looking at repositories.
        await admin_page.goto(f"/?branch={branch_with_failed_import}")

        indicator = admin_page.get_by_role("link", name=INDICATOR_ERROR_LABEL)
        await expect(indicator).to_be_visible()

        await indicator.click()

        await expect(admin_page).to_have_url(re.compile(re.escape(ERROR_IMPORT)))
        await expect(admin_page.get_by_role("link", name="demo-edge")).to_be_visible()

    async def test_indicator_is_not_in_the_error_state_on_the_default_branch(
        self, admin_page: Page, branch_with_failed_import: str
    ) -> None:
        # The failure was written on a branch, and sync_status is branch-local: the default
        # branch must be unaffected. This is the branch-safety guarantee the constitution
        # requires, asserted rather than assumed.
        await admin_page.goto("/")

        # Assert the healthy state positively first. Checking only that the error state is
        # absent would pass just as happily if the indicator failed to render at all, which
        # would prove nothing about branch scoping.
        await expect(admin_page.get_by_role("link", name=INDICATOR_HEALTHY_LABEL)).to_be_visible()
        await expect(admin_page.get_by_role("link", name=INDICATOR_ERROR_LABEL)).not_to_be_visible()
