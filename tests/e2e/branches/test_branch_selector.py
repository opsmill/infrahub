"""Port of frontend/app/tests/e2e/branches/branch-selector.spec.ts.

The branch selector dropdown: create-disabled when anonymous, branch search and
switching, quick-create form, and the redirect-to-main fallback for an unknown
branch. Searching/switching to `atl1-delete-upstream` needs data_scenario_branches
(searching "atl1" must yield exactly that one scenario branch).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from playwright.async_api import expect

pytestmark = pytest.mark.shard_branches_repo

if TYPE_CHECKING:
    from data.handles import ScenarioBranchesHandle
    from playwright.async_api import Page


class TestBranchSelectorNotLoggedIn:
    async def test_cannot_create_a_branch_if_not_logged_in(self, page: Page) -> None:
        await page.goto("/")
<<<<<<< HEAD
        await page.get_by_test_id("branch-selector-trigger").click()
=======
        await page.get_by_role("button", name="main", exact=True).click()
>>>>>>> origin/release-1.10
        await expect(page.get_by_role("button", name="Create branch")).to_be_disabled()

        # to go branch list view
        await page.get_by_role("link", name="View all branches").click()
        await expect(page.get_by_test_id("branches-table")).to_be_visible()

    async def test_no_quick_create_for_non_existent_branch(self, page: Page) -> None:
        await page.goto("/")
<<<<<<< HEAD
        await page.get_by_test_id("branch-selector-trigger").click()
=======
        await page.get_by_role("button", name="main", exact=True).click()
>>>>>>> origin/release-1.10

        non_existent_branch_name = "non-existent-branch-123"
        await page.get_by_placeholder("Search...").fill(non_existent_branch_name)

        await expect(page.get_by_role("option", name=f"Create branch {non_existent_branch_name}")).not_to_be_visible()

    async def test_search_and_switch_branch(self, page: Page, data_scenario_branches: ScenarioBranchesHandle) -> None:
        await page.goto("/")
<<<<<<< HEAD
        await page.get_by_test_id("branch-selector-trigger").click()
=======
        await page.get_by_role("button", name="main", exact=True).click()
>>>>>>> origin/release-1.10

        branch_list = page.get_by_label("branch list")
        await expect(branch_list.get_by_role("option", name="main default")).to_be_visible()
        await expect(branch_list.get_by_role("option", name="atl1-delete-upstream")).to_be_visible()

        await page.get_by_placeholder("Search...").fill("atl1")
        await expect(branch_list.get_by_role("option", name="atl1-delete-upstream")).to_be_visible()
        await expect(branch_list.get_by_role("option", name="main default")).to_be_hidden()
        await branch_list.get_by_role("option", name="atl1-delete-upstream").click()
        await expect(page.get_by_role("button", name="atl1-delete-upstream", exact=True)).to_be_visible()


class TestBranchSelectorLoggedInAsAdmin:
    async def test_create_a_branch_with_a_name_that_does_not_exist(self, admin_page: Page) -> None:
        await admin_page.goto("/")
<<<<<<< HEAD
        await admin_page.get_by_test_id("branch-selector-trigger").click()
=======
        await admin_page.get_by_role("button", name="main", exact=True).click()
>>>>>>> origin/release-1.10
        await admin_page.get_by_placeholder("Search...").fill("quick-branch-form")
        await admin_page.get_by_role("option", name="Create branch quick-branch-form").click()
        await expect(admin_page.get_by_label("New branch name *")).to_have_value("quick-branch-form")

    async def test_unknown_branch_redirects_to_main(self, admin_page: Page) -> None:
        await admin_page.goto("/?branch=unknown-branch-for-testing")
        await expect(admin_page.get_by_text("you have been redirected to the main branch")).to_be_visible()
        await expect(admin_page.get_by_role("button", name="Other")).to_be_visible()
        assert "/?branch=unknown-branch-for-testing" not in admin_page.url
