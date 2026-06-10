"""Port of frontend/app/tests/e2e/branches/branch-details.spec.ts.

Branch details view for the default branch (main) and a non-default branch
(`atl1-delete-upstream`, created by the demo-data branch scenarios — hence the
data_scenario_branches dependency on the non-default tests).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from playwright.async_api import expect

if TYPE_CHECKING:
    from data.handles import ScenarioBranchesHandle
    from playwright.async_api import Page

NON_DEFAULT_BRANCH = "atl1-delete-upstream"


class TestBranchDetailsDefaultBranch:
    async def test_display_branch_name_and_default_badge(self, admin_page: Page) -> None:
        await admin_page.goto("/branches/main")

        # Header
        await expect(admin_page.get_by_role("heading", name="main")).to_be_visible()
        await expect(admin_page.get_by_text("default", exact=True)).to_be_visible()
        await expect(admin_page.get_by_role("button", name="View node metadata")).to_be_visible()

        # Tabs
        await expect(admin_page.get_by_role("navigation", name="Tabs")).not_to_be_visible()

        # Branch attributes
        await expect(admin_page.get_by_text("Name")).to_be_visible()
        await expect(admin_page.get_by_text("Sync with Git")).to_be_visible()

        # Non-default specific attributes should NOT be visible
        await expect(admin_page.get_by_text("Has schema changes")).not_to_be_visible()
        await expect(admin_page.get_by_text("Last rebase")).not_to_be_visible()

        # All action buttons should be not visible
        await expect(admin_page.get_by_role("button", name="Merge")).not_to_be_visible()
        await expect(admin_page.get_by_role("button", name="Rebase")).not_to_be_visible()
        await expect(admin_page.get_by_role("button", name="Validate")).not_to_be_visible()
        await expect(admin_page.get_by_role("button", name="Delete")).not_to_be_visible()
        await expect(admin_page.get_by_role("link", name="Propose change")).not_to_be_visible()
        await expect(admin_page.get_by_test_id("tasks-accordion")).not_to_be_visible()


class TestBranchDetailsNonDefaultBranch:
    async def test_display_branch_name_and_no_default_badge(
        self, admin_page: Page, data_scenario_branches: ScenarioBranchesHandle
    ) -> None:
        await admin_page.goto(f"/branches/{NON_DEFAULT_BRANCH}")

        # Header
        await expect(admin_page.get_by_role("heading", name=NON_DEFAULT_BRANCH)).to_be_visible()
        await expect(admin_page.get_by_text("default")).not_to_be_visible()
        await expect(admin_page.get_by_role("button", name="View node metadata")).to_be_visible()

        # Branch attributes
        await expect(admin_page.get_by_text("Name")).to_be_visible()
        await expect(admin_page.get_by_text("Sync with Git")).to_be_visible()
        await expect(admin_page.get_by_text("Has schema changes")).to_be_visible()
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
        await expect(admin_page.get_by_test_id("tasks-accordion")).to_be_visible()

    async def test_navigate_between_tabs(
        self, admin_page: Page, data_scenario_branches: ScenarioBranchesHandle
    ) -> None:
        await admin_page.goto(f"/branches/{NON_DEFAULT_BRANCH}")

        tabs_nav = admin_page.get_by_role("navigation", name="Tabs")
        await tabs_nav.get_by_text("Data").click()
        await expect(admin_page).to_have_url(re.compile(r".*branch_tab=data"))

        await tabs_nav.get_by_text("Files").click()
        await expect(admin_page).to_have_url(re.compile(r".*branch_tab=files"))

        await tabs_nav.get_by_text("Artifacts").click()
        await expect(admin_page).to_have_url(re.compile(r".*branch_tab=artifacts"))

        await tabs_nav.get_by_text("Schema").click()
        await expect(admin_page).to_have_url(re.compile(r".*branch_tab=schema"))

        # Going back to the Details tab (first tab) clears the query string param.
        await tabs_nav.get_by_text("Details").click()
        await expect(admin_page).not_to_have_url(re.compile(r".*branch_tab=details"))

    async def test_display_node_metadata(
        self, admin_page: Page, data_scenario_branches: ScenarioBranchesHandle
    ) -> None:
        await admin_page.goto(f"/branches/{NON_DEFAULT_BRANCH}")

        await admin_page.get_by_role("button", name="View node metadata").click()

        await expect(admin_page.get_by_text("Created at")).to_be_visible()
        await expect(admin_page.get_by_text("Created by")).to_be_visible()
        await expect(admin_page.get_by_text("Updated at")).to_be_visible()
        await expect(admin_page.get_by_text("Updated by")).to_be_visible()
