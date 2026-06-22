"""Port of frontend/app/tests/e2e/objects/list/object-list-bulk-edit-some-rows.spec.ts.

/objects/:objectKind - Bulk edit some rows: select three InfraDevice rows and
apply a single set of changes (site, description, type, status, role, loopback
pool) to all of them at once. Runs as Admin on a throwaway branch cut from main,
hence the data_sites dependency (the first 3 device rows atl1-core1/core2/edge1,
the den1 site option, and — transitively — the "Loopbacks pool").
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name
from playwright.async_api import expect

pytestmark = pytest.mark.shard_sites_b

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from data.handles import SitesHandle
    from helpers import BranchAPI
    from playwright.async_api import Page


class TestBulkEditSomeRows:
    @pytest.fixture
    async def branch(
        self,
        branch_api: BranchAPI,
        data_sites: SitesHandle,
    ) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("bulk-edit-some-rows")
        await branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            await branch_api.delete(name)

    async def test_should_be_able_to_update_multiple_objects_at_once(self, admin_page: Page, branch: str) -> None:
        # navigate to objects page and select items
        await admin_page.goto(f"/objects/InfraDevice?branch={branch}")
        await admin_page.get_by_test_id("identifier-cell").nth(0).locator("label").click()
        await admin_page.get_by_test_id("identifier-cell").nth(1).locator("label").click()
        await admin_page.get_by_test_id("identifier-cell").nth(2).locator("label").click()
        await admin_page.get_by_test_id("object-table-toolbar").get_by_role("button", name="Edit").click()

        # verify bulk edit panel is displayed correctly
        await expect(admin_page.get_by_role("heading", name="objects selected for editing")).to_be_visible()
        await expect(admin_page.get_by_text("atl1-core1Waiting for changes")).to_be_visible()
        await expect(admin_page.get_by_text("atl1-core2Waiting for changes")).to_be_visible()
        await expect(admin_page.get_by_text("atl1-edge1Waiting for changes")).to_be_visible()
        await expect(admin_page.get_by_role("heading", name="Set bulk changes")).to_be_visible()
        await expect(admin_page.get_by_label("Description")).to_be_visible()
        await expect(admin_page.get_by_label("Name")).to_be_hidden()
        await expect(admin_page.get_by_label("Member of groups")).to_be_hidden()
        await expect(admin_page.get_by_label("Edit").get_by_text("Description")).to_be_visible()

        # make bulk changes
        await admin_page.get_by_label("Site").click()
        await admin_page.get_by_role("option", name="den1").click()
        await admin_page.get_by_label("Description").fill("test desc")
        await admin_page.get_by_label("Type").fill("test type")
        await admin_page.get_by_label("Status").click()
        await admin_page.get_by_role("option", name="Drained Temporarily taken out").click()
        await admin_page.get_by_label("Role").click()
        await admin_page.get_by_role("option", name="Leaf Switch Top of Rack part").click()
        await admin_page.get_by_test_id("select-open-pool-option-button").click()
        await admin_page.get_by_role("option", name="Loopbacks pool").click()
        await admin_page.get_by_role("button", name="Save").click()

        # verify changes were applied successfully
        await expect(admin_page.get_by_text("atl1-core1success")).to_be_visible()
        await expect(admin_page.get_by_text("atl1-core2success")).to_be_visible()
        await expect(admin_page.get_by_text("atl1-edge1success")).to_be_visible()
        await expect(admin_page.get_by_text("Drained").nth(0)).to_be_visible()
        await expect(admin_page.get_by_text("Drained").nth(1)).to_be_visible()
        await expect(admin_page.get_by_text("Drained").nth(2)).to_be_visible()
