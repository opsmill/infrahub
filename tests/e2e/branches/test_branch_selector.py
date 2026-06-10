"""Port of frontend/app/tests/e2e/branches/branch-selector.spec.ts.

The branch selector dropdown: create-disabled when anonymous, branch search and
switching, quick-create form, and the redirect-to-main fallback for an unknown
branch. Searching/switching to `atl1-delete-upstream` needs data_scenario_branches
(searching "atl1" must yield exactly that one scenario branch).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from playwright.sync_api import expect

if TYPE_CHECKING:
    from data.handles import ScenarioBranchesHandle
    from playwright.sync_api import Page


class TestBranchSelectorNotLoggedIn:
    def test_cannot_create_a_branch_if_not_logged_in(self, page: Page) -> None:
        page.goto("/")
        page.get_by_test_id("branch-selector-trigger").click()
        expect(page.get_by_test_id("create-branch-button")).to_be_disabled()

        # to go branch list view
        page.get_by_role("link", name="View all branches").click()
        expect(page.get_by_test_id("branches-table")).to_contain_text("main")

    def test_no_quick_create_for_non_existent_branch(self, page: Page) -> None:
        page.goto("/")
        page.get_by_test_id("branch-selector-trigger").click()

        non_existent_branch_name = "non-existent-branch-123"
        page.get_by_test_id("branch-search-input").fill(non_existent_branch_name)

        expect(page.get_by_text("No branch found")).to_be_visible()
        expect(page.get_by_role("option", name=f"Create branch {non_existent_branch_name}")).not_to_be_visible()

    def test_search_and_switch_branch(self, page: Page, data_scenario_branches: ScenarioBranchesHandle) -> None:
        page.goto("/")
        expect(page.get_by_test_id("branch-selector-trigger")).to_contain_text("main")
        page.get_by_test_id("branch-selector-trigger").click()
        expect(page.get_by_test_id("branch-list").get_by_role("option", name="main default")).to_be_visible()

        page.get_by_test_id("branch-search-input").fill("atl1")
        branch_list = page.get_by_test_id("branch-list")
        expect(branch_list.get_by_role("option", name="atl1-delete-upstream")).to_be_visible()
        expect(branch_list.get_by_role("option")).to_have_count(1)
        branch_list.get_by_role("option", name="atl1-delete-upstream").click()
        expect(page.get_by_test_id("branch-selector-trigger")).to_contain_text("atl1-delete-upstream")


class TestBranchSelectorLoggedInAsAdmin:
    def test_create_a_branch_with_a_name_that_does_not_exist(self, admin_page: Page) -> None:
        admin_page.goto("/")
        admin_page.get_by_test_id("branch-selector-trigger").click()
        admin_page.get_by_test_id("branch-search-input").fill("quick-branch-form")
        admin_page.get_by_role("option", name="Create branch quick-branch-form").click()
        expect(admin_page.get_by_label("New branch name *")).to_have_value("quick-branch-form")

    def test_unknown_branch_redirects_to_main(self, admin_page: Page) -> None:
        admin_page.goto("/?branch=unknown-branch-for-testing")
        expect(admin_page.get_by_text("you have been redirected to the main branch")).to_be_visible()
        expect(admin_page.get_by_role("button", name="Other")).to_be_visible()
        assert "/?branch=unknown-branch-for-testing" not in admin_page.url
