"""Port of frontend/app/tests/e2e/branches/merged-branch-permissions.spec.ts.

A merged branch is read-only: create + create/edit/delete and add-relationship
actions are disabled with an explanatory tooltip. The branch is created and
merged once for the whole class (beforeAll/afterAll -> class-scoped fixture).
Operates on demo objects (BuiltinTag blue and InfraPlatform Cisco IOS come
transitively via org_registry; the platform's 10 devices are the site leaves),
so it depends on data_sites.

The TS spec marked this `test.slow()`; Playwright's own action/expect timeouts
cover the extra latency here.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name
from playwright.async_api import expect

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from data.handles import SitesHandle
    from infrahub_sdk import InfrahubClient
    from playwright.async_api import Page

TOOLTIP_MESSAGE = "Cannot edit objects on a merged branch"


class TestMergedBranchDisabledActions:
    @pytest.fixture(scope="class")
    async def merged_branch(
        self,
        infrahub_client: InfrahubClient,
        data_sites: SitesHandle,
    ) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("merged-branch")
        await infrahub_client.branch.create(branch_name=name, sync_with_git=False)
        await infrahub_client.branch.merge(branch_name=name)
        yield name
        with contextlib.suppress(Exception):
            await infrahub_client.branch.delete(branch_name=name)

    async def test_show_merged_status_badge(self, admin_page: Page, merged_branch: str) -> None:
        await admin_page.goto(f"/branches/{merged_branch}")

        await expect(admin_page.get_by_role("heading", name=merged_branch)).to_be_visible()
        await expect(admin_page.get_by_role("banner").get_by_text("Merged", exact=True)).to_be_visible()

    async def test_disable_create_and_row_actions_on_list(self, admin_page: Page, merged_branch: str) -> None:
        await admin_page.goto(f"/objects/BuiltinTag?branch={merged_branch}")
        await expect(admin_page.get_by_role("link", name="blue")).to_be_visible()

        # create button is disabled with tooltip
        await expect(admin_page.get_by_test_id("create-object-button")).to_be_disabled()
        await admin_page.get_by_test_id("create-object-button").hover(force=True)
        await expect(admin_page.get_by_text(TOOLTIP_MESSAGE)).to_be_visible()

        # row action menu items are disabled
        await admin_page.get_by_test_id("actions-cell-blue").click()
        await expect(admin_page.get_by_role("menuitem", name="Edit")).to_be_disabled()
        await expect(admin_page.get_by_role("menuitem", name="Delete")).to_be_disabled()

    async def test_disable_edit_button_on_details(self, admin_page: Page, merged_branch: str) -> None:
        await admin_page.goto(f"/objects/BuiltinTag?branch={merged_branch}")
        await expect(admin_page.get_by_role("link", name="blue")).to_be_visible()
        await admin_page.get_by_role("link", name="blue").click()

        # edit button is disabled with tooltip
        await expect(admin_page.get_by_test_id("edit-button")).to_be_visible()
        await expect(admin_page.get_by_test_id("edit-button")).to_be_disabled()
        await admin_page.get_by_test_id("edit-button").hover(force=True)
        await expect(admin_page.get_by_text(TOOLTIP_MESSAGE)).to_be_visible()

        # menu actions are disabled
        await admin_page.get_by_test_id("object-details-menu").click()
        await expect(admin_page.get_by_role("menuitem", name="Groups")).to_have_attribute("aria-disabled", "true")
        await expect(admin_page.get_by_role("menuitem", name="Delete")).to_have_attribute("aria-disabled", "true")

    async def test_disable_add_relationship_button(self, admin_page: Page, merged_branch: str) -> None:
        await admin_page.goto(f"/objects/InfraPlatform?branch={merged_branch}")
        await expect(admin_page.get_by_role("link", name="Cisco IOS", exact=True)).to_be_visible()
        await admin_page.get_by_role("link", name="Cisco IOS", exact=True).click()
        await expect(admin_page.get_by_role("link", name="Devices 10")).to_be_visible()
        await admin_page.get_by_role("link", name="Devices 10").click()

        # add relationship button is disabled with tooltip
        await expect(admin_page.get_by_test_id("open-relationship-form-button")).to_be_visible()
        await expect(admin_page.get_by_test_id("open-relationship-form-button")).to_be_disabled()
        await admin_page.get_by_test_id("open-relationship-form-button").hover(force=True)
        await expect(admin_page.get_by_text(TOOLTIP_MESSAGE)).to_be_visible()
