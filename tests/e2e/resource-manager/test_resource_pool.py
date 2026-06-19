"""Port of frontend/app/tests/e2e/resource-manager/resource-pool.spec.ts.

Serial: create an IP-prefix pool on main, view its details and edit it, then
delete it.

Serial handling: the source mutates main (no branch) and shares the
UI-created "test prefix pool" across the three tests (create -> edit -> delete).
A class-scoped `resource_pool_data` marker fixture pulls in `data_ipam_pools`
(the seeded "External prefixes pool" and the 10.x IP prefixes the pool allocates
from); every test depends on the SAME fixtures (admin_page + resource_pool_data)
and the chain relies on pytest's default definition-order collection (see the
README's serial-specs gotcha). The suite runs single-process.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from playwright.async_api import expect

pytestmark = pytest.mark.shard_foundation

if TYPE_CHECKING:
    from data.handles import IpamPoolsHandle
    from playwright.async_api import Page


class TestResourceManager:
    @pytest.fixture(scope="class")
    def resource_pool_data(self, data_ipam_pools: IpamPoolsHandle) -> None:
        return None

    async def test_create_a_new_pool(self, admin_page: Page, resource_pool_data: None) -> None:
        await admin_page.goto("/resource-manager")
        await expect(admin_page.get_by_role("link", name="External prefixes pool")).to_be_visible()
        await admin_page.get_by_test_id("create-object-button").click()

        await admin_page.get_by_label("Select an object type").click()

        await admin_page.get_by_role("option", name="IP Prefix Pool Core").click()

        await admin_page.get_by_label("Name *").fill("test prefix pool")
        await admin_page.get_by_label("Resources *").click()
        await admin_page.get_by_role("option", name="10.0.0.0/8").click()
        await admin_page.get_by_role("option", name="10.0.0.0/16").click()
        await admin_page.get_by_role("option", name="10.1.0.0/16").click()
        await expect(admin_page.get_by_label("Default Prefix Type")).to_contain_text("IP PrefixIpam")
        await admin_page.get_by_label("Resources *").click()

        await admin_page.get_by_label("IPAM Namespace *").click()
        await admin_page.get_by_role("option", name="default").click()
        await admin_page.get_by_role("button", name="Save").click()

        await expect(admin_page.get_by_text("IP prefix pool created")).to_be_visible()
        await expect(admin_page.get_by_role("link", name="test prefix pool")).to_be_visible()

    async def test_see_details_and_edit_a_pool(self, admin_page: Page, resource_pool_data: None) -> None:
        await admin_page.goto("/resource-manager")
        await admin_page.get_by_role("link", name="test prefix pool").click()

        await expect(admin_page.get_by_text("Core IP Prefix Pool")).to_be_visible()
        await expect(admin_page.get_by_text("Nametest prefix pool")).to_be_visible()
        await expect(admin_page.get_by_text("Description-")).to_be_visible()
        assert "/resource-manager/" in admin_page.url

        await admin_page.get_by_role("button", name="View node metadata").click()
        await expect(admin_page.get_by_text("Created at")).to_be_visible()
        await expect(admin_page.get_by_text("Created by")).to_be_visible()
        await expect(admin_page.get_by_text("Updated at")).to_be_visible()
        await expect(admin_page.get_by_text("Updated by")).to_be_visible()

        await admin_page.get_by_test_id("edit-button").click()
        await expect(admin_page.get_by_label("Default Prefix Type")).to_contain_text("IP PrefixIpam")
        await admin_page.get_by_label("Description").fill("a test pool for e2e")
        await admin_page.get_by_role("button", name="Save").click()

        await expect(admin_page.get_by_text("IPPrefixPool updated")).to_be_visible()
        await expect(admin_page.get_by_text("Descriptiona test pool for e2e")).to_be_visible()

    async def test_delete_a_pool(self, admin_page: Page, resource_pool_data: None) -> None:
        await admin_page.goto("/resource-manager")

        await admin_page.get_by_test_id("actions-cell-test prefix pool").click()
        await admin_page.get_by_role("menuitem", name="Delete").click()
        await expect(admin_page.get_by_text("Are you sure you want to remove test prefix pool?")).to_be_visible()
        await admin_page.get_by_test_id("modal-delete-confirm").click()

        await expect(admin_page.get_by_text("Object test prefix pool")).to_be_visible()
        await expect(admin_page.get_by_role("link", name="test prefix pool")).to_be_hidden()
