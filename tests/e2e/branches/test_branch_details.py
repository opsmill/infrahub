"""Port of frontend/app/tests/e2e/branches/branch-details.spec.ts.

Branch details view for the default branch (main) and a non-default branch
(`atl1-delete-upstream`, created by the demo-data branch scenarios — hence the
data_scenario_branches dependency on the non-default tests).
"""

from __future__ import annotations

import contextlib
import re
from typing import TYPE_CHECKING
from urllib.parse import quote

import pytest
from helpers import generate_random_branch_name
from playwright.async_api import expect

pytestmark = pytest.mark.shard_branches_repo

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from data.handles import ScenarioBranchesHandle
    from helpers import BranchAPI
    from playwright.async_api import Page

NON_DEFAULT_BRANCH = "atl1-delete-upstream"


class TestBranchDetailsDefaultBranch:
    async def test_display_branch_name_and_default_badge(self, admin_page: Page) -> None:
        await admin_page.goto("/branches/main")

        # Header
        await expect(admin_page.get_by_role("heading", name="main")).to_be_visible()
        await expect(admin_page.get_by_text("default", exact=True)).to_be_visible()
        await expect(admin_page.get_by_role("button", name="View node metadata")).to_be_visible()
        await expect(admin_page.get_by_role("button", name="Copy branch name")).to_be_visible()
        await expect(admin_page.get_by_role("button", name="Refresh data")).to_be_visible()

        # Already working on main, so there is nothing to switch to
        await expect(admin_page.get_by_test_id("branch-working-notice")).to_be_visible()
        await expect(admin_page.get_by_test_id("switch-to-viewed-branch")).not_to_be_visible()

        # Tabs
        await expect(admin_page.get_by_role("navigation", name="Tabs")).not_to_be_visible()

        # Branch attributes
        await expect(admin_page.get_by_text("Name")).to_be_visible()
        await expect(admin_page.get_by_text("Sync with Git")).to_be_visible()

        # Non-default specific attributes should NOT be visible
        await expect(admin_page.get_by_text("Schema differs from default branch")).not_to_be_visible()
        await expect(admin_page.get_by_text("Last rebase")).not_to_be_visible()

        # All action buttons should be not visible
        await expect(admin_page.get_by_role("button", name="Merge")).not_to_be_visible()
        await expect(admin_page.get_by_role("button", name="Rebase")).not_to_be_visible()
        await expect(admin_page.get_by_role("button", name="Validate")).not_to_be_visible()
        await expect(admin_page.get_by_role("button", name="Delete")).not_to_be_visible()
        await expect(admin_page.get_by_role("link", name="Propose change")).not_to_be_visible()
        await expect(admin_page.get_by_test_id("branch-tasks-card")).not_to_be_visible()

        await expect(admin_page.get_by_test_id("branch-repositories-card")).not_to_be_visible()


class TestBranchDetailsNonDefaultBranch:
    async def test_display_branch_name_and_no_default_badge(
        self, admin_page: Page, data_scenario_branches: ScenarioBranchesHandle
    ) -> None:
        await admin_page.goto(f"/branches/{NON_DEFAULT_BRANCH}")

        # Header
        await expect(admin_page.get_by_role("heading", name=NON_DEFAULT_BRANCH)).to_be_visible()
        await expect(admin_page.get_by_text("default", exact=True)).not_to_be_visible()
        await expect(admin_page.get_by_role("button", name="View node metadata")).to_be_visible()
        await expect(admin_page.get_by_role("button", name="Copy branch name")).to_be_visible()
        await expect(admin_page.get_by_role("button", name="Refresh data")).to_be_visible()

        # Branch attributes
        await expect(admin_page.get_by_text("Name")).to_be_visible()
        await expect(admin_page.get_by_text("Sync with Git")).to_be_visible()
        await expect(admin_page.get_by_text("Schema differs from default branch")).to_be_visible()
        await expect(admin_page.get_by_text("Last rebase")).to_be_visible()

        # Tabs navigation should be visible with all tabs
        tabs_nav = admin_page.get_by_role("navigation", name="Tabs")
        await expect(tabs_nav).to_be_visible()
        await expect(tabs_nav.get_by_text("Details")).to_be_visible()
        await expect(tabs_nav.get_by_text("Data")).to_be_visible()
        await expect(tabs_nav.get_by_text("Files")).to_be_visible()
        await expect(tabs_nav.get_by_text("Artifacts")).to_be_visible()
        await expect(tabs_nav.get_by_text("Schema")).to_be_visible()

        # All action buttons should be visible
        await expect(admin_page.get_by_role("button", name="Merge")).to_be_visible()
        await expect(admin_page.get_by_role("link", name="Propose change")).to_be_visible()
        await expect(admin_page.get_by_role("button", name="Rebase")).to_be_visible()
        await expect(admin_page.get_by_role("button", name="Validate")).to_be_visible()
        await expect(admin_page.get_by_role("button", name="Delete", exact=True)).to_be_visible()
        await expect(admin_page.get_by_test_id("branch-tasks-card")).to_be_visible()

    async def test_git_repositories_card_renders_above_the_merge_button(
        self, admin_page: Page, data_scenario_branches: ScenarioBranchesHandle
    ) -> None:
        await admin_page.goto(f"/branches/{NON_DEFAULT_BRANCH}")

        repositories_card = admin_page.get_by_test_id("branch-repositories-card")
        merge_button = admin_page.get_by_role("button", name="Merge")
        await expect(repositories_card).to_be_visible()
        await expect(merge_button).to_be_visible()

        card_box = await repositories_card.bounding_box()
        merge_box = await merge_button.bounding_box()
        assert card_box is not None
        assert merge_box is not None
        assert card_box["y"] + card_box["height"] <= merge_box["y"]

    async def test_navigate_between_tabs(
        self, admin_page: Page, data_scenario_branches: ScenarioBranchesHandle
    ) -> None:
        await admin_page.goto(f"/branches/{NON_DEFAULT_BRANCH}")

        tabs_nav = admin_page.get_by_role("navigation", name="Tabs")
        await tabs_nav.get_by_text("Data").click()
        await expect(admin_page).to_have_url(re.compile(rf"/branches/{NON_DEFAULT_BRANCH}/data"))

        await tabs_nav.get_by_text("Files").click()
        await expect(admin_page).to_have_url(re.compile(rf"/branches/{NON_DEFAULT_BRANCH}/files"))

        await tabs_nav.get_by_text("Artifacts").click()
        await expect(admin_page).to_have_url(re.compile(rf"/branches/{NON_DEFAULT_BRANCH}/artifacts"))

        await tabs_nav.get_by_text("Schema").click()
        await expect(admin_page).to_have_url(re.compile(rf"/branches/{NON_DEFAULT_BRANCH}/schema"))

        # Going back to the Details tab (first tab) returns to the bare branch URL.
        await tabs_nav.get_by_text("Details").click()
        await expect(admin_page).to_have_url(re.compile(rf"/branches/{NON_DEFAULT_BRANCH}$"))

    async def test_switch_to_viewed_branch_from_mismatch_notice(
        self, admin_page: Page, data_scenario_branches: ScenarioBranchesHandle
    ) -> None:
        await admin_page.goto(f"/branches/{NON_DEFAULT_BRANCH}")

        await expect(admin_page.get_by_test_id("branch-mismatch-notice")).to_contain_text(
            f"You're viewing {NON_DEFAULT_BRANCH} but working on main"
        )

        await admin_page.get_by_test_id("switch-to-viewed-branch").click()

        await expect(admin_page.get_by_test_id("branch-working-notice")).to_be_visible()
        await expect(admin_page.get_by_test_id("branch-mismatch-notice")).not_to_be_visible()
        await expect(admin_page.get_by_test_id("branch-selector-trigger")).to_contain_text(NON_DEFAULT_BRANCH)

    async def test_display_node_metadata(
        self, admin_page: Page, data_scenario_branches: ScenarioBranchesHandle
    ) -> None:
        await admin_page.goto(f"/branches/{NON_DEFAULT_BRANCH}")

        await admin_page.get_by_role("button", name="View node metadata").click()

        await expect(admin_page.get_by_text("Created at")).to_be_visible()
        await expect(admin_page.get_by_text("Created by")).to_be_visible()
        await expect(admin_page.get_by_text("Updated at")).to_be_visible()
        await expect(admin_page.get_by_text("Updated by")).to_be_visible()


class TestBranchDetailsTasks:
    @pytest.fixture
    async def fresh_branch(self, branch_api: BranchAPI) -> AsyncGenerator[str, None]:
        """A branch created for this test, so validating it leaves the shared demo branches untouched."""
        name = generate_random_branch_name("tasks-")
        await branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            await branch_api.delete(name)

    async def test_validate_task_row_opens_task_details(self, admin_page: Page, fresh_branch: str) -> None:
        await admin_page.goto(f"/branches/{quote(fresh_branch, safe='')}")

        await admin_page.get_by_role("button", name="Validate").click()
        await expect(admin_page.locator("#alert-success")).to_contain_text("Branch validation requested!")

        tasks_card = admin_page.get_by_test_id("branch-tasks-card")
        validate_row = tasks_card.get_by_role("row").filter(has_text="Validate")
        await expect(validate_row.first).to_be_visible(timeout=30_000)

        await validate_row.first.get_by_role("link").click()
        await expect(admin_page).to_have_url(re.compile(r"/tasks/[0-9a-f-]+"))


class TestBranchDetailsSlashName:
    @pytest.fixture
    async def slash_branch(self, branch_api: BranchAPI) -> AsyncGenerator[str, None]:
        """A branch whose name contains a slash, created via the API and removed afterwards."""
        name = generate_random_branch_name("feat/slash-")
        await branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            await branch_api.delete(name)

    async def test_opens_detail_page_from_branches_list(self, admin_page: Page, slash_branch: str) -> None:
        await admin_page.goto("/branches")
        await admin_page.get_by_role("link", name=slash_branch, exact=True).click()

        await expect(admin_page.get_by_role("heading", name=slash_branch)).to_be_visible()
        await expect(admin_page.get_by_role("navigation", name="Tabs")).to_be_visible()
        await expect(admin_page).to_have_url(re.compile(rf"/branches/{re.escape(quote(slash_branch, safe=''))}$"))

    async def test_navigates_to_path_based_tab(self, admin_page: Page, slash_branch: str) -> None:
        await admin_page.goto(f"/branches/{quote(slash_branch, safe='')}")

        await admin_page.get_by_role("navigation", name="Tabs").get_by_text("Data").click()

        await expect(admin_page.get_by_role("heading", name=slash_branch)).to_be_visible()
        await expect(admin_page).to_have_url(re.compile(rf"/branches/{re.escape(quote(slash_branch, safe=''))}/data"))
